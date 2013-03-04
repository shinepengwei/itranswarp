#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import os, re, time, json, uuid, base64, hashlib, logging
from datetime import datetime
from collections import namedtuple

from transwarp.web import ctx, view, get, post, route, Dict, UTC, Template, seeother, notfound, badrequest
from transwarp import db, i18n, cache

from apiexporter import *
import loader, async

for the_name, the_mod in loader.scan_submodules('apps').iteritems():
    the_path = os.path.dirname(os.path.abspath(the_mod.__file__))
    the_i18n = os.path.join(the_path, 'i18n')
    if os.path.isdir(the_i18n):
        for the_fname in os.listdir(the_i18n):
            i18n.load_i18n(os.path.join(os.path.join(the_i18n, the_fname)))

@route('/ab')
def ab_test():
    return ('<html><body><h1>Hello, world!</h1></body></html>',)

@route('/')
def website_index():
    navs = loader.load_navigations()
    if not navs:
        return '<html><body><h1>It works!</h1><p>Now please goto <a href="/admin/">management console</a> to initialize your website!</p></body></html>'
    raise seeother(navs[0].url)

@route('/admin/')
def admin_index():
    raise seeother('/admin/website/overview')

@get('/register')
def admin_get_register():
    return Template('templates/admin/register.html')

_RE_DOMAIN = re.compile(r'^[a-z0-9]{1,20}$')

@api(role=ROLE_GUESTS)
@post('/register')
def admin_post_register():
    i = ctx.request.input(name='', domain='', email='')
    name = i.name.strip()
    pdomain = i.domain.strip().lower()
    email = i.email.strip().lower()
    if not email:
        raise APIValueError('email', 'Email cannot be empty')
    check_email(email)
    if len(db.select('select id from registrations where email=?', email)) > 0:
        raise APIValueError('email', 'Email is already registered')
    if len(db.select('select id from users where email=?', email)) > 0:
        raise APIValueError('email', 'Email is already registered')
    if not name:
        raise APIValueError('name', 'Name cannot be empty')
    if not pdomain:
        raise APIValueError('domain', 'Domain cannot be empty')
    if not _RE_DOMAIN.match(pdomain):
        raise APIValueError('domain', 'Invalid domain')
    domain = '%s.web.itranswarp.com' % pdomain
    if len(db.select('select id from registrations where domain=?', domain)) > 0:
        raise APIValueError('domain', 'Domain is already in use')
    if len(db.select('select id from websites where domain=?', domain)) > 0:
        raise APIValueError('domain', 'Domain is already in use')
    current = time.time()
    registration = dict( \
        id=db.next_str(), \
        domain=domain, name=name, email=email, \
        checked=False, verified=False, verification=uuid.uuid4().hex, \
        creation_time=current, modified_time=current, version=0)
    db.insert('registrations', **registration)
    async.send_mail('webmaster@itranswarp.com', subject='New Registration from %s' % email, body='New registration is waiting for processing.')
    return email

_module_dict = loader.scan_submodules('apps')

class MenuGroup(object):
    __slots__ = ('name', 'order', 'items')

    def __init__(self, name, order, items=None):
        self.name = name
        self.order = order
        self.items = items if items else []

    def filter(self, role):
        items = [i for i in self.items if i.role >= role]
        if items:
            return MenuGroup(self.name, self.order, items)
        return None

    def __str__(self):
        return 'MenuGroup(%s, %s)' % (self.name, self.order)

class MenuItem(object):
    __slots__ = ('modname', 'funcname', 'role', 'name', 'order')

    def __init__(self, modname, funcname, role, name, order):
        self.modname = modname
        self.funcname = funcname
        self.role = role
        self.name = name
        self.order = order

def _get_all_menus():
    def _cmp(m1, m2):
        if m1.order < 0:
            if m2.order < 0:
                return cmp(m1.name, m2.name)
            else:
                return 1
        else: # m1.order >= 0
            if m2.order < 0:
                return -1
            else:
                if m1.order==m2.order:
                    return cmp(m1.name, m2.name)
                return cmp(m1.order, m2.order)

    menus = {}
    for modname, mod in _module_dict.iteritems():
        for fname in dir(mod):
            func = getattr(mod, fname)
            if hasattr(func, '__role__'):
                group_name = func.__menu_group__
                group_order = func.__group_order__
                mi = MenuItem(modname, func.__name__, func.__role__, func.__menu_name__, func.__name_order__)
                if not group_name in menus:
                    menus[group_name] = MenuGroup(group_name, group_order)
                if group_order != (-1):
                    menus[group_name].order = group_order
                menus[group_name].items.append(mi)
    groups = sorted(menus.values(), _cmp)
    for g in groups:
        g.items = sorted(g.items, _cmp)
    return groups

_all_menus = _get_all_menus()

def _filter_menus():
    role = ctx.user.role_id
    L = [g.filter(role) for g in _all_menus]
    return [g for g in L if g]

@route('/admin/<mod>/<handler>')
def admin_menu_item(mod, handler):
    # check user:
    if ctx.user is None or ctx.user.role_id==ROLE_GUESTS:
        raise seeother('/auth/signin?redirect=/admin/%s/%s' % (mod, handler))
    module = _module_dict.get(mod, None)
    if module:
        func = getattr(module, handler, None)
        if callable(func):
            r = func()
            if isinstance(r, Template):
                return Template('templates/admin/index.html', __menus__=_filter_menus(), __include__='apps/%s/%s' % (mod, r.template_name), __mod__=mod, __handler__=handler, __website__=ctx.website, __user__=ctx.user, **r.model)
    raise notfound()

@get('/track/u.js')
def track_js():
    ctx.response.content_type = 'application/x-javascript'
    ctx.response.set_header('Cache-Control', 'private, no-cache, no-cache=Set-Cookie, proxy-revalidate')
    key = 'counter_%s_%d' % (ctx.website.id, int(time.time()) // 3600)
    cache.client.incr(key)
    return r'var __track_ok__ = true;'
