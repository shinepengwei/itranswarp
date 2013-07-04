#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' Authentication module for password auth, oauth, etc. '

import os, re, time, base64, hashlib, logging, functools

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from transwarp.web import ctx, view, get, post, route, Dict, Template, seeother, notfound, badrequest
from transwarp import db

from core.models import User
from core.apis import api, APIError
from plugins import signins

_LOCAL_SIGNIN = 'local.pwd'

_SESSION_COOKIE_NAME = '_auth_session_cookie_'
_SESSION_COOKIE_SALT = '_Auth-SalT_'
_SESSION_COOKIE_EXPIRES = 604800.0 # 24 hours

@get('/auth/signin')
@view('templates/auth/signin.html')
def signin():
    redirect = ctx.request.get('redirect', '')
    if not redirect:
        redirect = ctx.request.header('REFERER')
    if not redirect or redirect.find('/signin')!=(-1):
        redirect = '/'
    return dict(website=ctx.website, redirect=redirect, signins=signins.get_enabled_signins())

@api
@post('/api/authenticate')
def api_authenticate():
    '''
    Authenticate user by email and password.
    '''
    i = ctx.request.input(email='', passwd='', remember='')
    email = i.email.strip().lower()
    passwd = i.passwd
    remember = i.remember
    if not email or not passwd:
        raise APIError('auth:failed', '', 'bad email or password.')
    user = User.select_one('where email=?', email)
    if not user or user.website_id != ctx.website.id or passwd != user.passwd:
        raise APIError('auth:failed', '', 'bad email or password.')
    expires = None
    if remember:
        expires = time.time() + _SESSION_COOKIE_EXPIRES
    make_session_cookie(_LOCAL_SIGNIN, user.id, passwd, expires)
    # clear passwd:
    user.passwd = '******'
    return user

@route('/auth/signout')
def signout():
    delete_session_cookie()
    redirect = ctx.request.get('redirect', '')
    if not redirect:
        redirect = ctx.request.header('REFERER', '')
    if not redirect or redirect.find('/admin/')!=(-1) or redirect.find('/signin')!=(-1):
        redirect = '/'
    logging.debug('signed out and redirect to: %s' % redirect)
    raise seeother(redirect)


# deprecated
def http_basic_auth(auth):
    try:
        s = base64.b64decode(auth)
        logging.warn(s)
        u, p = s.split(':', 1)
        user = User.select_one('where email=?', u)
        if not user or user.website_id != ctx.website.id or user.passwd != hashlib.md5(p).hexdigest():
            return None
        logging.info('Basic auth ok: %s' % u)
        # clear passwd in memory:
        user.passwd = '******'
        return user
    except BaseException, e:
        logging.exception('auth failed.')
        return None

def make_session_cookie(signin_privider, uid, passwd, expires=None):
    '''
    Generate a secure client session cookie by constructing: 
    base64(signin_privider, uid, expires, md5(uid, expires, passwd, salt)).
    
    Args:
        signin_privider: signin plugin id.
        uid: user id.
        expires: unix-timestamp as float.
        passwd: user's password.
        salt: a secure string.
    Returns:
        base64 encoded cookie value as str.
    '''
    signin_privider = str(signin_privider)
    sid = str(uid)
    exp = str(int(expires)) if expires else str(int(time.time() + 86400))
    secure = ':'.join([signin_privider, sid, exp, str(passwd), _SESSION_COOKIE_SALT])
    cvalue = ':'.join([signin_privider, sid, exp, hashlib.md5(secure).hexdigest()])
    logging.info('make cookie: %s' % cvalue)
    cookie = base64.urlsafe_b64encode(cvalue).replace('=', '_')
    ctx.response.set_cookie(_SESSION_COOKIE_NAME, cookie, expires=expires)

def extract_session_cookie():
    '''
    Decode a secure client session cookie and return user object, or None if invalid cookie.

    Returns:
        user as object, or None if cookie is invalid.
    '''
    try:
        s = str(ctx.request.cookie(_SESSION_COOKIE_NAME, ''))
        logging.debug('read cookie: %s' % s)
        if not s:
            return None
        ss = base64.urlsafe_b64decode(s.replace('_', '=')).split(':')
        if len(ss)!=4:
            raise ValueError('bad cookie: %s' % s)
        signin_privider, uid, exp, md5 = ss
        if float(exp) < time.time():
            raise ValueError('expired cookie: %s' % s)
        user = User.get_by_id(uid)
        if not user:
            raise ValueError('bad cookie: %s' % s)
        expected_pwd = str(user.passwd) if signin_privider==_LOCAL_SIGNIN else 'TODO:get-by-oauth-token'
        expected = ':'.join([signin_privider, uid, exp, expected_pwd, _SESSION_COOKIE_SALT])
        if hashlib.md5(expected).hexdigest()!=md5:
            raise ValueError('bad cookie: unexpected md5.')
        # clear password in memory:
        user.passwd = '******'
        return user
    except BaseException, e:
        logging.debug('something wrong when extract cookie: %s' % e.message)
        delete_session_cookie()
        return None

def delete_session_cookie():
    ' delete the session cookie immediately. '
    logging.debug('delete session cookie.')
    ctx.response.delete_cookie(_SESSION_COOKIE_NAME)
