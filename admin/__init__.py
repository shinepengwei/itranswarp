#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import os, re, time, json, uuid, base64, hashlib, logging
from datetime import datetime

from transwarp.web import ctx, view, get, post, route, jsonrpc, jsonresult, Dict, UTC, Template, seeother, notfound, badrequest
from transwarp import db, i18n, cache

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

def _sort(g1, g2):
    if g1.order>=0 and g2.order>=0:
        r = cmp(g1.order, g2.order)
        return r if r!=0 else cmp(g1.name, g2.name)
    if g1.order<0 and g2.order<0:
        return cmp(g1.name, g2.name)
    return 1 if g1.order<0 else (-1)

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
            g.menus.sort(cmp=_sort)
        return L
    # END _load_appmenus

    L = []
    mdict = util.scan_submodules('apps')
    for mod_name, mod in mdict.iteritems():
        L.extend(_load_appmenus(mod_name, mod))
    L.sort(cmp=_sort)
    logging.error(str(L))
    return mdict, L

_apps_modules, _apps_admin_menus = _import_appmenus()

for the_name, the_mod in util.scan_submodules('apps').iteritems():
    the_path = os.path.dirname(os.path.abspath(the_mod.__file__))
    the_i18n = os.path.join(the_path, 'i18n')
    if os.path.isdir(the_i18n):
        for the_fname in os.listdir(the_i18n):
            i18n.load_i18n(os.path.join(os.path.join(the_i18n, the_fname)))

@route('/')
def website_index():
    raise seeother(util.get_menus()[0].url)

@get('/profile')
@util.theme('profile.html')
def get_profile():
    if ctx.user is None:
        raise seeother('/signin?redirect=/profile')
    return dict()

@route('/admin/')
def admin_index():
    raise seeother('/admin/manage/overview')

@route('/admin/<mod>/<handler>')
def admin_menu_item(mod, handler):
    # check cookie:
    if ctx.user is None or ctx.user.role==const.ROLE_GUEST:
        raise seeother('/signin?redirect=/admin/%s/%s' % (mod, handler))

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
            __mod__=mod, __handler__=handler, \
            __include__=include, \
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
    providers = [p for p in util.get_plugin_providers('signin') if p['enabled']]
    return dict(providers=providers, __site_name__=util.get_setting_site_name())

@post('/signin')
def do_signin():
    i = ctx.request.input(remember='')
    email = i.email.strip().lower()
    passwd = i.passwd
    remember = i.remember
    if not email or not passwd:
        return Template('templates/admin/signin.html', email=email, remember=remember, error=_('Bad email or password'))
    us = db.select('select id, passwd from users where email=?', email)
    if not us:
        return Template('templates/admin/signin.html', email=email, remember=remember, error=_('Bad email or password'))
    u = us[0]
    if passwd != u.passwd:
        return Template('templates/admin/signin.html', email=email, remember=remember, error=_('Bad email or password'))
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
        return dict(error=_('Invalid email'))
    if i.type=='email':
        users = db.select('select email from users where email=?', email)
        if users:
            return dict(error=_('Email exists'))
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
            return dict(error=_('Bad email or password'), field='')
        users = db.select('select id, passwd from users where email=?', email)
        if not users:
            return dict(error=_('Bad email or password'), field='')
        user = users[0]
        if passwd != user.passwd:
            return dict(error=_('Bad email or password'), field='')
        db.update('update auth_users set user_id=? where id=?', user.id, auser.id)
        util.make_session_cookie(auser.provider, user['id'], auser.auth_token, auser.expired_time)
        ctx.response.delete_cookie(_COOKIE_SIGNIN_REDIRECT)
        return dict(redirect=ctx.request.cookie(_COOKIE_SIGNIN_REDIRECT, '/'))
    return dict(error='bad request')

@get('/track.js')
def track_js():
    ctx.response.content_type = 'application/x-javascript'
    ctx.response.set_header('Cache-Control', 'private, no-cache, no-cache=Set-Cookie, proxy-revalidate')
    key = '_TR_%d' % (int(time.time()) // 3600)
    cache.client.incr(key)
    return r'var __track_ok__ = true;'
