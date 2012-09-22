#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import time
import json
import uuid
import base64
import hashlib
import logging

from itranswarp.web import ctx, view, get, post, route, jsonrpc, jsonresult, Dict, Template, seeother, notfound, badrequest
from itranswarp import db

import const, util

_COOKIE_SIGNIN_REDIRECT = '_after_signin_'
_SECURE_BIND_KEY = 'secure-BIND'

def _make_bind_key(auth_user):
    uid = str(auth_user['id'])
    exp = int(time.time()) + 600
    s = '%s:%s:%s:%s' % (uid, exp, _SECURE_BIND_KEY, str(auth_user['auth_token']))
    h = hashlib.md5(s).hexdigest()
    return '%s:%s:%s' % (uid, exp, h)

def _verify_bind_key(key):
    logging.info('verify key: %s' % key)
    ss = str(key).split(':', 2)
    if len(ss)!=3:
        raise StandardError('invalid key')
    uid, exp, h = ss[0], int(ss[1]), ss[2]
    if exp < time.time():
        raise StandardError('time expired')
    auser = db.select_one('select * from auth_users where id=?', uid)
    if h != hashlib.md5('%s:%s:%s:%s' % (uid, exp, _SECURE_BIND_KEY, auser.auth_token)).hexdigest():
        raise StandardError('bad signed key')
    return auser

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
    mdict = util.scan_submodules('apps')
    L = []
    for name, mod in mdict.iteritems():
        L.append((name, util.load_module('apps.%s.manage' % name)))
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
    # check cookie:
    if ctx.user is None or ctx.user.role==const.ROLE_GUEST:
        raise seeother('/signin?redirect=/admin/%s/%s' % (mod, handler))

    global _admin_menus, _admin_modules
    m = _admin_modules.get(mod, None)
    if m is None:
        raise notfound()
    f = getattr(m, handler, None)
    if f is None:
        raise notfound()
    r = f(ctx.user, ctx.request, ctx.response)
    if isinstance(r, Template):
        include = 'apps/%s/%s' % (mod, r.template_name)
        logging.warn('set include: %s' % include)
        logging.warn('set model: %s' % str(r.model))
        return Template('templates/admin/index.html', __menus__=_admin_menus, \
            __mod__=mod, __handler__=handler, __include__=include, \
            __site_name__=util.get_setting_site_name(), \
            __site_description__=util.get_setting_site_description(), \
            __user__=ctx.user, \
            **r.model)
    return r

@get('/signin')
@view('templates/admin/signin.html')
def signin():
    redirect = ctx.request.get('redirect', '')
    if not redirect:
        redirect = ctx.request.header('REFERER')
    if not redirect or redirect.find('/signin')!=(-1):
        redirect = '/'
    ctx.response.set_cookie(_COOKIE_SIGNIN_REDIRECT, redirect)
    providers = [p for p in util.get_signin_providers() if p['enabled']]
    return dict(providers=providers)

@post('/signin')
def do_signin():
    i = ctx.request.input(remember='')
    email = i.email.strip().lower()
    passwd = i.passwd
    remember = i.remember
    if not email or not passwd:
        return Template('templates/admin/signin.html', email=email, remember=remember, error='Bad email or password.')
    us = db.select('select id, passwd from users where email=?', email)
    if not us:
        return Template('templates/admin/signin.html', email=email, remember=remember, error='Bad email or password.')
    u = us[0]
    if passwd != u.passwd:
        return Template('templates/admin/signin.html', email=email, remember=remember, error='Bad email or password.')
    expires = time.time() + const.SESSION_COOKIE_EXPIRES_TIME if remember else None
    util.make_session_cookie(const.LOCAL_SIGNIN_PROVIDER, u.id, passwd, expires)
    ctx.response.delete_cookie(_COOKIE_SIGNIN_REDIRECT)
    raise seeother(ctx.request.cookie(_COOKIE_SIGNIN_REDIRECT, '/'))

@get('/signout')
def signout():
    util.delete_session_cookie()
    redirect = ctx.request.get('redirect', '')
    if not redirect:
        redirect = ctx.request.header('REFERER', '')
    if not redirect or redirect.find('/admin/')!=(-1) or redirect.find('/signin')!=(-1):
        redirect = '/'
    raise seeother(redirect)

@get('/auth/from/<provider>')
def auth_start(provider):
    raise seeother(util.create_signin_provider(provider).get_auth_url())

@get('/auth/callback/<provider>')
def auth_callback(provider):
    mixin = util.create_signin_provider(provider)
    auth_user = mixin.auth_callback()
    uid = '%s_%s' % (provider, auth_user['id'])
    ausers = db.select('select * from auth_users where id=?', uid)
    if ausers:
        # check if user associated:
        auser = ausers[0]
        if auser.user_id:
            user = db.select_one('select * from users where id=?', auser.user_id)
            util.make_session_cookie(auser.provider, auser.user_id, auser.auth_token, auser.expired_time)
            ctx.response.delete_cookie(_COOKIE_SIGNIN_REDIRECT)
            raise seeother(ctx.request.cookie(_COOKIE_SIGNIN_REDIRECT, '/'))
        raise seeother('/auth/bind?key=%s' % _make_bind_key(auser))
    current = time.time()
    au = dict(id=uid, \
            user_id='', \
            provider=provider, \
            name=auth_user['name'], \
            image_url=auth_user['image_url'], \
            auth_token=auth_user['auth_token'], \
            expired_time=auth_user['expired_time'], \
            creation_time=current, \
            modified_time=current, \
            version=0)
    db.insert('auth_users', **au)
    raise seeother('/auth/bind?key=%s' % _make_bind_key(au))

@get('/auth/bind')
@view('templates/admin/bind.html')
def bind():
    key = ctx.request['key']
    _verify_bind_key(key)
    return dict(key=key)

@post('/auth/bind')
@jsonresult
def do_bind():
    i = ctx.request.input()
    key = i.key
    auser = _verify_bind_key(key)
    email = i.email.strip().lower()
    current = time.time()
    if not util.validate_email(email):
        return dict(error=u'Invalid email')
    if i.type=='email':
        users = db.select('select email from users where email=?', email)
        if users:
            return dict(error=u'Email exists.')
        # create user:
        user = dict(id=db.next_str(), \
                locked=False, \
                name=auser.name, \
                image_url=auser.image_url, \
                role=const.ROLE_GUEST, \
                email=email, \
                verified=False, \
                passwd='', \
                creation_time=current, \
                modified_time=current, \
                version=0)
        with db.transaction():
            db.insert('users', **user)
            db.update('update auth_users set user_id=? where id=?', user['id'], auser.id)
        util.make_session_cookie(auser.provider, user['id'], auser.auth_token, auser.expired_time)
        ctx.response.delete_cookie(_COOKIE_SIGNIN_REDIRECT)
        return dict(redirect=ctx.request.cookie(_COOKIE_SIGNIN_REDIRECT, '/'))
    elif i.type=='user':
        passwd = i.passwd
        if not passwd:
            return dict(error=u'Bad email or password', field='')
        users = db.select('select id, passwd from users where email=?', email)
        if not users:
            return dict(error=u'Bad email or password', field='')
        user = users[0]
        if passwd != user.passwd:
            return dict(error=u'Bad email or password', field='')
        db.update('update auth_users set user_id=? where id=?', user.id, auser.id)
        util.make_session_cookie(auser.provider, user['id'], auser.auth_token, auser.expired_time)
        ctx.response.delete_cookie(_COOKIE_SIGNIN_REDIRECT)
        return dict(redirect=ctx.request.cookie(_COOKIE_SIGNIN_REDIRECT, '/'))
    return dict(error='bad request')

if __name__=='__main__':
    import doctest
    doctest.testmod()
