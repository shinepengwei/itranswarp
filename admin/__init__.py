#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import logging

from itranswarp.web import ctx, get, post, route, jsonrpc, Dict, Template, seeother, notfound, badrequest
from itranswarp import db

class _AppMenu(object):

    def __init__(self, mod, menu_order, title):
        self.mod = mod
        self.order = menu_order
        self.title = title
        self.items = []

    def append(self, item):
        self.items.append(item)

class _AppMenuItem(object):

    def __init__(self,role, handler, title):
        self.role = role
        self.handler = handler
        self.title = title

def _imports():
    mods = ['article', 'manage']
    L = []
    for mod in mods:
        try:
            logging.info('try import %s...' % mod)
            m = __import__('apps.%s.manage' % mod, globals(), locals(), ['manage'])
            L.append((mod, m))
        except ImportError:
            logging.exception('Import error!')
            continue
    return L

def _get_all_nav_menus():
    menus = []
    modules = {}
    for name, m in _imports():
        f1 = getattr(m, 'register_navigation_menus', None)
        if callable(f1):
            logging.info('got nav menus.')
            menus.extend([Dict(x) for x in f1()])
    return menus

def _get_all_admin_menus():
    menus = []
    modules = {}
    for mod, m in _imports():
        f1 = getattr(m, 'register_admin_menus', None)
        if callable(f1):
            logging.info('got menus.')
            for ms in f1():
                app_menu = _AppMenu(mod, ms['order'], ms['title'])
                for it in ms['items']:
                    item_handler = it['handler']
                    item_title = it['title']
                    item_role = it['role']
                    app_menu.append(_AppMenuItem(item_role, item_handler, item_title))
                menus.append(app_menu)
            modules[mod] = m
        else:
            logging.info('menus not found.')
    menus.sort(lambda x, y: -1 if x.order < y.order else 1)
    logging.info('load admin modules: %s' % str(modules))
    return modules, menus

_admin_modules, _admin_menus = _get_all_admin_menus()
_nav_menus = _get_all_nav_menus()

def get_navigation_menus():
    return _nav_menus[:]

def get_navigation_menu(mtype):
    for m in _nav_menus:
        if mtype==m.type:
            return m
    raise badrequest()

@route('/admin/')
def index():
    raise seeother('/admin/manage/dashboard')

@route('/admin/<mod>/<handler>')
def menu_item(mod, handler):
    global _admin_menus, _admin_modules
    m = _admin_modules.get(mod, None)
    if m is None:
        raise notfound()
    f = getattr(m, handler, None)
    if f is None:
        raise notfound()
    user = None
    r = f(user, ctx.request, ctx.response)
    if isinstance(r, Template):
        include = 'apps/%s/%s' % (mod, r.template_name)
        logging.warn('set include: %s' % include)
        logging.warn('set model: %s' % str(r.model))
        return Template('templates/admin/index.html', __menus__=_admin_menus, __mod__=mod, __handler__=handler, __include__=include, **r.model)
    return r

@get('/signin')
def signin():
    return Template('templates/admin/signin.html')

@post('/signin')
def do_signin():
    i = ctx.request.input(remember='')
    email = i.email.strip().lower()
    passwd = i.passwd
    remember = i.remember
    if not email or not passwd:
        return Template('templates/admin/signin.html', email=email, remember=remember, error='Bad email or password.')
    us = db.select('select passwd from users where email=?', email)
    if not us:
        return Template('templates/admin/signin.html', email=email, remember=remember, error='Bad email or password.')
    if passwd != us[0].passwd:
        return Template('templates/admin/signin.html', email=email, remember=remember, error='Bad email or password.')
    if remember:
        pass
    raise seeother('/admin/')

if __name__=='__main__':
    import doctest
    doctest.testmod()
