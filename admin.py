#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import os, re, time, json, uuid, base64, hashlib, logging
from datetime import datetime

from transwarp.web import ctx, view, get, post, route, Dict, UTC, Template, seeother, notfound, badrequest
from transwarp import db, i18n, cache, task

from apiexporter import *
import loader

import util

def _import_appmenus():
    
    def _load_appmenus(mod_name, mod):
        groups = Dict()
        for attr in dir(mod):
            f = getattr(mod, attr, None)
            if not callable(f):
                continue
            groupname = getattr(f, '__groupname__', None)
            itemname = getattr(f, '__itemname__', None)
            if not groupname or not itemname:
                continue
            grouporder = getattr(f, '__grouporder__')
            itemorder = getattr(f, '__itemorder__')
            logging.error('Group: %s, Order: %s' % (groupname, grouporder))
            if not groupname in groups:
                groups[groupname] = Dict(mod=mod_name, name=groupname, order=grouporder, menus=list())
            g = groups[groupname]
            if grouporder!=(-1) and g.order==(-1):
                g.order = grouporder
            g.menus.append(Dict(handler=f.__name__, name=itemname, order=itemorder))
        # sort groups and items:
        L = groups.values()
        for g in L:
            g.menus.sort()
        return L
    # END _load_appmenus

    L = []
    mdict = loader.scan_submodules('apps')
    for mod_name, mod in mdict.iteritems():
        L.extend(_load_appmenus(mod_name, mod))
    L.sort()
    logging.error(str(L))
    return mdict, L

_apps_modules, _apps_admin_menus = _import_appmenus()

for the_name, the_mod in loader.scan_submodules('apps').iteritems():
    the_path = os.path.dirname(os.path.abspath(the_mod.__file__))
    the_i18n = os.path.join(the_path, 'i18n')
    if os.path.isdir(the_i18n):
        for the_fname in os.listdir(the_i18n):
            i18n.load_i18n(os.path.join(os.path.join(the_i18n, the_fname)))

@route('/')
def website_index():
    raise seeother(loader.load_navigations()[0].url)

@route('/admin/')
def admin_index():
    raise seeother('/admin/manage/overview')

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
    domain = '%s.itranswarp.com' % pdomain
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
    task.create_task(queue='mail-high', name='Notification to super admin')
    return email

_module_dict = loader.scan_submodules('apps')

@route('/admin/<mod>/<handler>')
def admin_menu_item(mod, handler):
    # check cookie:
    if ctx.user is None or ctx.user.role_id==ROLE_GUESTS:
        raise seeother('/auth/signin?redirect=/admin/%s/%s' % (mod, handler))
    module = _module_dict.get(mod, None)
    if module:
        func = getattr(module, handler, None)
        if callable(func):
            r = func()
            if isinstance(r, Template):
                return Template('templates/admin/index.html', __include__='apps/%s/%s' % (mod, r.template_name), __mod__=mod, __handler__=handler, __website__=ctx.website, __user__=ctx.user, **r.model)
    if True:
        return Template('templates/admin/index.html', __mod__='manage', __handler__='overview', __website__=ctx.website, __user__=ctx.user)

    global _apps_modules, _apps_admin_menus
    m = _apps_modules.get(mod, None)
    if m is None:
        raise notfound()
    f = getattr(m, handler, None)
    if f is None:
        raise notfound()
    r = f()
    if isinstance(r, Template):
        include = 'apps/%s/%s' % (mod, r.template_name)
        logging.warn('set include: %s' % include)
        logging.warn('set model: %s' % str(r.model))
        return Template('templates/admin/index.html', \
            __menus__=_apps_admin_menus, \
            **r.model)
    return r

@get('/track/u.js')
def track_js():
    ctx.response.content_type = 'application/x-javascript'
    ctx.response.set_header('Cache-Control', 'private, no-cache, no-cache=Set-Cookie, proxy-revalidate')
    key = '_TR_%d' % (int(time.time()) // 3600)
    cache.client.incr(key)
    return r'var __track_ok__ = true;'
