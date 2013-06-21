#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
management console.
'''

import os, re, time, json, uuid, base64, hashlib, logging
from datetime import datetime
from collections import namedtuple

from transwarp.web import ctx, view, get, post, route, Dict, UTC, Template, seeother, notfound, badrequest, redirect
from transwarp import db, i18n, cache

from core.apis import api
from core.roles import allow, ROLE_GUESTS
from core.utils import load_module, scan_submodules

class App(object):

    __slots__ = ('key', 'order', 'module', 'name', 'menu_list', 'menu_dict')

    def __init__(self, key, order, module, name, menus):
        self.key = key
        self.order = order
        self.module = module
        self.name = name
        self.menu_list = menus
        self.menu_dict = dict([(m.key, m) for m in menus if m.key!='-'])

class MenuItem(object):

    __slots__ = ('key', 'name', 'role')

    def __init__(self, key, name, role):
        self.key = key
        self.name = name
        self.role = role

def scan_app(app_key, mod):
    if not hasattr(mod, 'menus'):
        return None
    try:
        L = []
        for key, name in getattr(mod, 'menus'):
            if key=='-':
                L.append(MenuItem(key, name, None))
            else:
                func = getattr(mod, key, None)
                if func is None:
                    raise ValueError('callable object not found: %s' % key)
                if not callable(func):
                    raise ValueError('menu not callable: %s' % key)
                role = getattr(func, '__role__', None)
                if role is None:
                    raise ValueError('callable object %s does not have __role__.' % key)
                logging.info('found menu: %s' % key)
                L.append(MenuItem(key, name, role))
        if L:
            name = getattr(mod, 'name', app_key)
            order = getattr(mod, 'order', 10000)
            logging.info('add app %s with menus: %s' % (name, str(L)))
            return App(app_key, order, mod, name, L)
    except:
        logging.exception('Error when scan menus.')
    return None

def scan_apps():
    apps = {}
    logging.info('scan apps...')
    for the_name, the_mod in scan_submodules('apps').iteritems():
        logging.info('scan app %s...' % the_name)
        app = scan_app(the_name, the_mod)
        if app:
            logging.info('found app %s...' % the_name)
            apps[the_name] = app
        the_path = os.path.dirname(os.path.abspath(the_mod.__file__))
        the_i18n = os.path.join(the_path, 'i18n')
        if os.path.isdir(the_i18n):
            for the_fname in os.listdir(the_i18n):
                i18n.load_i18n(os.path.join(os.path.join(the_i18n, the_fname)))
    return apps

__apps = scan_apps()
__apps_list = sorted(__apps.values(), cmp=lambda x,y: cmp((x.order, x.name), (y.order, y.name)))

@get('/register')
def admin_get_register():
    return Template('templates/admin/register.html')

_RE_DOMAIN = re.compile(r'^[a-z0-9]{1,20}$')

@api
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

def filter_menus(menus):
    role = ctx.user.role_id
    def _f(m):
        return m.key == '-' or m.role >= role
    return filter(_f, menus)

def first_menu(menus):
    for menu in menus:
        if menu.key != '-':
            return menu
    return None

def manage_app_menu(app_name, menu_name):
    # check user:
    if ctx.user is None or ctx.user.role_id==ROLE_GUESTS:
        raise seeother('/auth/signin?redirect=/manage/%s/%s' % (app_name, menu_name))
    app = __apps.get(app_name)
    if app:
        menu_list = filter_menus(app.menu_list)
        menu = app.menu_dict.get(menu_name) if menu_name else first_menu(menu_list)
        if menu:
            func = getattr(app.module, menu.key)
            r = func()
            if isinstance(r, Template):
                return Template('templates/manage.html', __app__=app, __apps__=__apps_list, __menu__=menu, __menus__=menu_list, __include__='apps/%s/templates/%s' % (app_name, r.template_name), __website__=ctx.website, __user__=ctx.user, **r.model)
            return r
    raise notfound()

@route('/manage/<app_name>/<menu_name>')
def route_app_menu(app_name, menu_name):
    return manage_app_menu(app_name, menu_name)

@route('/manage/<app_name>/')
def route_app(app_name):
    return manage_app_menu(app_name, '')

@get('/manage/')
def manage_entry():
    app = __apps_list[0]
    raise seeother('/manage/%s/' % app.key)

@get('/api/resource/url')
def api_resource_url():
    i = ctx.request.input(id='')
    if i.id:
        # should cached?
        r = db.select_one('select url from resource where id=?', i.id)
        if r:
            raise redirect(r.url)
    raise notfound()

@get('/track/u.js')
def track_js():
    ctx.response.content_type = 'application/x-javascript'
    ctx.response.set_header('Cache-Control', 'private, no-cache, no-cache=Set-Cookie, proxy-revalidate')
    key = 'counter_%s_%d' % (ctx.website.id, int(time.time()) // 3600)
    cache.client.incr(key)
    return r'var __track_ok__ = true;'
