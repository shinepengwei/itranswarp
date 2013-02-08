#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' Auth module '

import os, re, time, base64, hashlib, logging, functools

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from transwarp.web import ctx, view, get, post, route, jsonrpc, Dict, Template, seeother, notfound, badrequest
from transwarp import db

from apiexporter import *

_REG_EMAIL = re.compile(r'^[0-9a-z]([\-\.\w]*[0-9a-z])*\@([0-9a-z][\-\w]*[0-9a-z]\.)+[a-z]{2,9}$')

_SESSION_COOKIE_NAME = '_auth_session_cookie_'
_SESSION_COOKIE_SALT = '_Auth-SalT_'
_SESSION_COOKIE_EXPIRES = 604800.0

@get('/auth/signin')
@view('templates/auth/signin.html')
def signin():
    redirect = ctx.request.get('redirect', '')
    if not redirect:
        redirect = ctx.request.header('REFERER')
    if not redirect or redirect.find('/signin')!=(-1):
        redirect = '/'
    return dict(website=ctx.website, redirect=redirect)

@api(role=ROLE_GUESTS)
@post('/api/authenticate')
def do_signin():
    i = ctx.request.input(email='', passwd='', remember='')
    email = i.email.strip().lower()
    passwd = i.passwd
    remember = i.remember
    if not email:
        raise APIError('auth:failed', '', 'bad email or password.')
    if not passwd:
        raise APIError('auth:failed', '', 'bad email or password.')
    us = db.select('select * from users where email=?', email)
    if not us:
        raise APIError('auth:failed', '', 'bad email or password.')
    u = us[0]
    if u.website_id != ctx.website.id:
        raise APIError('auth:failed', '', 'bad email or password.')
    if passwd != u.passwd:
        raise APIError('auth:failed', '', 'bad email or password.')
    expires = None
    if remember:
        expires = time.time() + _SESSION_COOKIE_EXPIRES
    make_session_cookie(u.id, passwd, expires)
    # clear passwd:
    u.passwd = '******'
    return u

@get('/auth/signout')
def signout():
    delete_session_cookie()
    redirect = ctx.request.get('redirect', '')
    if not redirect:
        redirect = ctx.request.header('REFERER', '')
    if not redirect or redirect.find('/admin/')!=(-1) or redirect.find('/signin')!=(-1):
        redirect = '/'
    logging.debug('signed out and redirect to: %s' % redirect)
    raise seeother(redirect)

def http_basic_auth(auth):
    try:
        s = base64.b64decode(auth)
        logging.warn(s)
        u, p = s.split(':', 1)
        user = db.select_one('select * from users where email=?', u)
        if user.passwd==hashlib.md5(p).hexdigest():
            logging.info('Basic auth ok: %s' % u)
            # clear passwd in memory:
            user.passwd = '******'
            return user
        return None
    except BaseException, e:
        logging.exception('auth failed.')
        return None

def make_session_cookie(uid, passwd, expires=None):
    '''
    Generate a secure client session cookie by constructing: 
    base64(uid, expires, md5(uid, expires, passwd, salt)).
    
    Args:
        uid: user id.
        expires: unix-timestamp as float.
        passwd: user's password.
        salt: a secure string.
    Returns:
        base64 encoded cookie value as str.
    '''
    sid = str(uid)
    exp = str(int(expires)) if expires else str(int(time.time() + 86400))
    secure = ':'.join([sid, exp, str(passwd), _SESSION_COOKIE_SALT])
    cvalue = ':'.join([sid, exp, hashlib.md5(secure).hexdigest()])
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
        if len(ss)!=3:
            raise ValueError('bad cookie: %s' % s)
        uid, exp, md5 = ss
        if float(exp) < time.time():
            raise ValueError('expired cookie: %s' % s)
        user = db.select_one('select * from users where id=?', uid)
        expected_pwd = str(user.passwd)
        expected = ':'.join([uid, exp, expected_pwd, _SESSION_COOKIE_SALT])
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
