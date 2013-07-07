#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' Authentication module for password auth, oauth, etc. '

import os, re, time, urllib, base64, hashlib, logging, functools

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from transwarp.web import ctx, view, get, post, route, Dict, Template, seeother, notfound, badrequest
from transwarp import db

from core import http, utils
from core.models import User, create_user
from core.apis import api, APIError, APIValueError
from core.roles import ROLE_SUBSCRIBERS

from plugins import signins

_LOCAL_SIGNIN = 'local.pwd'

_SESSION_COOKIE_NAME = '_auth_session_cookie_'
_SESSION_COOKIE_SALT = '_Auth-SalT_'
_SESSION_COOKIE_EXPIRES = 604800.0 # 24 hours

class Auth_User(db.Model):
    '''
    create table auth_user (
        id varchar(50) not null,
        website_id varchar(50) not null,
        user_id varchar(50) not null,

        auth_provider varchar(50) not null,
        auth_id varchar(200) not null,
        auth_token varchar(200) not null,

        email varchar(100) not null,
        name varchar(100) not null,
        image_url varchar(1000) not null,

        expires_time real not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,

        primary key(id),
        unique key uk_auth_id(auth_id),
        index idx_creation_time(creation_time)
    );
    '''
    id = db.StringField(primary_key=True, default=db.next_str)

    website_id = db.StringField(nullable=False, updatable=False)
    user_id = db.StringField(nullable=False, default='')

    auth_provider = db.StringField(nullable=False, updatable=False)
    auth_id = db.StringField(nullable=False, updatable=False)
    auth_token = db.StringField(nullable=False)

    email = db.StringField(nullable=False, default='')
    name = db.StringField(nullable=False)
    image_url = db.StringField(nullable=False)

    expires_time = db.FloatField(nullable=False)
    creation_time = db.FloatField(nullable=False, updatable=False, default=time.time)
    modified_time = db.FloatField(nullable=False, default=time.time)
    version = db.VersionField()

def _make_bind_key(auser):
    auth_id = auser.auth_id
    exp = int(time.time()) + 3600
    token = auser.auth_token
    s = '%s:%s:%s' % (auth_id, exp, token)
    h = hashlib.md5(s).hexdigest()
    return '%s:%s:%s' % (auth_id, exp, h)

def _verify_bind_key(key):
    logging.info('verify key: %s' % key)
    ss = str(key).split(':', 2)
    if len(ss)!=3:
        raise StandardError('invalid key')
    auth_id, exp, h = ss[0], int(ss[1]), ss[2]
    if exp < time.time():
        raise StandardError('time expired')
    auser = Auth_User.select_one('where auth_id=?', auth_id)
    if not auser:
        raise StandardError('not exist')
    if auser.user_id:
        raise StandardError('already binded.')
    if h != hashlib.md5('%s:%s:%s' % (auth_id, exp, auser.auth_token)).hexdigest():
        raise StandardError('bad signed key')
    return auser

@get('/auth/signin')
@view('templates/auth/signin.html')
def signin():
    redirect = http.get_redirect(excludes='/auth/')
    return dict(website=ctx.website, redirect=redirect, signins=signins.get_enabled_signins())

@get('/auth/from/<provider>')
def auth_from(provider):
    redirect = http.get_redirect(excludes='/auth/')
    p = signins.create_signin_instance(provider)
    if p:
        callback = 'http://%s/auth/callback/%s?redirect=%s' % (ctx.request.host, provider, urllib.quote(redirect))
        raise seeother(p.get_auth_url(callback))
    raise notfound()

@get('/auth/callback/<provider>')
def auth_callback(provider):
    p = signins.create_signin_instance(provider)
    if not p:
        raise notfound()

    redirect = http.get_redirect(excludes='/auth/')
    callback = 'http://%s/auth/callback/%s' % (ctx.request.host, provider)
    u = p.auth_callback(callback, **ctx.request.input())

    auth_id = '%s-%s-%s' % (provider, ctx.website.id, u['id'])
    auth_token = u['auth_token']
    name = u['name']
    image_url = u['image_url']
    expires = u['expires']
    email = u.get('email', '')

    auser = Auth_User.select_one('where auth_id=?', auth_id)
    if auser:
        auser.auth_token = auth_token
        auser.name = name
        auser.image_url = image_url
        auser.expires = expires
        auser.update()
        # check if user associated:
        if auser.user_id:
            user = User.select_one('where id=?', auser.user_id)
            make_session_cookie(provider, auser.auth_id, auth_token, expires)
            raise seeother(redirect)
        raise seeother('/auth/bind?key=%s&redirect=%s' % (_make_bind_key(auser), urllib.quote(redirect)))
    # first time to signin with 3rd-part:
    au = Auth_User( \
            website_id=ctx.website.id, \
            user_id='', \
            auth_provider=provider, \
            auth_id=auth_id, \
            auth_token=auth_token, \
            email = email, \
            name=name, \
            image_url=image_url, \
            expires_time=expires)
    au.insert()
    raise seeother('/auth/bind?key=%s&redirect=%s' % (_make_bind_key(au), urllib.quote(redirect)))

@get('/auth/bind')
@view('templates/auth/bind.html')
def auth_bind():
    i = ctx.request.input(key='')
    auser = _verify_bind_key(i.key)
    return dict(website=ctx.website, key=i.key, auth_user=auser, redirect=http.get_redirect(excludes='/auth/'))

@api
@post('/api/auth/bind')
def api_auth_bind():
    i = ctx.request.input(key='', email='', name='', passwd='')
    name = i.name.strip()
    if not name:
        raise APIValueError('name', 'Name is empty.')
    email = utils.check_email(i.email)
    au = _verify_bind_key(i.key)
    if not au or au.user_id:
        raise APIValueError('key', 'Bind failed.')
    u = User.select_one('where email=?', email)
    if u:
        # user exist, must check passwd:
        logging.info('user exist: %s' % email)
        if i.passwd:
            if i.passwd==u.passwd:
                au.user_id = u.id
                au.update()
                make_session_cookie(au.auth_provider, au.auth_id, au.auth_token, au.expires_time)
                return dict(result=True)
            raise APIValueError('passwd', 'Bad password.')
        raise APIError('password-required', '', 'Need password.')
    else:
        # user not exist:
        logging.info('user not exist, creating...')
        u = create_user(ctx.website.id, email, '', name, ROLE_SUBSCRIBERS, image_url=au.image_url)
        au.user_id = u.id
        au.update()
        make_session_cookie(au.auth_provider, au.auth_id, au.auth_token, au.expires_time)
        return dict(result=True)

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
        signin_privider, the_id, expires, md5 = ss

        # check if expires:
        if float(expires) < time.time():
            raise ValueError('expired cookie: %s' % s)

        # get user id and passwd:
        uid = the_id
        auth_token = None
        if signin_privider != _LOCAL_SIGNIN:
            au = Auth_User.select_one('where auth_id=?', the_id)
            if not au:
                raise ValueError('bad cookie: auth_user not found: %s' % the_id)
            uid = au.user_id
            auth_token = au.auth_token

        # get user:
        user = User.get_by_id(uid)
        if not user:
            raise ValueError('bad cookie: user not found %s' % uid)

        expected_pwd = str(user.passwd) if signin_privider==_LOCAL_SIGNIN else auth_token
        expected = ':'.join([signin_privider, the_id, expires, expected_pwd, _SESSION_COOKIE_SALT])
        if hashlib.md5(expected).hexdigest()!=md5:
            raise ValueError('bad cookie: unexpected md5.')
        # clear password in memory:
        user.passwd = '******'
        return user
    except BaseException, e:
        logging.exception('something wrong when extract cookie. now deleting cookie...')
        delete_session_cookie()
        return None

def delete_session_cookie():
    ' delete the session cookie immediately. '
    logging.debug('delete session cookie.')
    ctx.response.delete_cookie(_SESSION_COOKIE_NAME)
