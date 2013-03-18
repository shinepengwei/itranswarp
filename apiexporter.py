#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

try:
    import json
except ImportError:
    import simplejson as json

import re, logging, functools

from transwarp.web import ctx, get, post, forbidden, HttpError, Dict
from transwarp import db, cache

_TRUES = set([u'1', u't', u'true', u'y', u'yes'])

def boolean(s):
    if isinstance(s, bool):
        return s
    return s.lower() in _TRUES

QUEUE_MAIL_HIGH = 'mail-high'
QUEUE_MAIL_LOW = 'mail-low'

ROLE_SUPER_ADMINS = 0
ROLE_ADMINISTRATORS = 1
ROLE_EDITORS = 2
ROLE_AUTHORS = 3
ROLE_CONTRIBUTORS = 4
ROLE_SUBSCRIBERS = 100

ROLE_GUESTS = 10000

ROLE_NAMES = {
    ROLE_SUPER_ADMINS: 'Super Admin',
    ROLE_ADMINISTRATORS: 'Administrator',
    ROLE_EDITORS: 'Editor',
    ROLE_AUTHORS: 'Author',
    ROLE_CONTRIBUTORS: 'Contributor',
    ROLE_SUBSCRIBERS: 'Subscriber',
}

class APIError(StandardError):

    def __init__(self, code, data, message=''):
        super(APIError, self).__init__(message)
        self.code = code
        self.data = data
        self.message = message

class APIValueError(APIError):
    def __init__(self, field, message=''):
        super(APIValueError, self).__init__('value:invalid', field, message)

class APIPermissionError(APIError):
    def __init__(self, message=''):
        super(APIPermissionError, self).__init__('permission:forbidden', 'permission', message)

def cached(key=None, timeout=3600, use_ctx=True):
    '''
    Make function result cached.

    >>> import time
    >>> @cached(timeout=2)
    ... def get_time():
    ...     return int(time.time() * 1000)
    >>> n1 = get_time()
    >>> time.sleep(1.0)
    >>> n2 = get_time()
    >>> n1==n2
    True
    >>> time.sleep(2.0)
    >>> n3 = get_time()
    >>> n1==n3
    False
    '''
    def _decorator(func):
        @functools.wraps(func)
        def _wrapper(*args):
            sk = key or func.__name__
            s = '%s--%s' % (ctx.website.id, sk) if use_ctx else sk
            if args:
                L = [s]
                L.extend(args)
                s = '--'.join(L)
            r = cache.client.get(s)
            if r is None:
                logging.debug('Cache not found for key: %s' % s)
                r = func(*args)
                cache.client.set(s, r, timeout)
            return r
        return _wrapper
    return _decorator

def api(role=ROLE_ADMINISTRATORS):
    '''
    A decorator that makes a function to api, makes the return value as json.

    @api(role=ROLE_GUESTS)
    @post('/articles/create')
    def api_articles_create():
        return dict(id='123')
    '''
    def _decorator(func):
        @functools.wraps(func)
        def _wrapper(*args, **kw):
            ctx.response.content_type = 'application/json; charset=utf-8'
            is_guest = role==ROLE_GUESTS
            if not is_guest:
                if ctx.user:
                    if ctx.user.role_id > role:
                        return json.dumps(dict(error='permission:forbidden', data='permission', message='No permission for user: %s' % ctx.user.email))
                else:
                    return json.dumps(dict(error='permission:forbidden', data='permission', message='No permission for anonymous user.'))
            try:
                return json.dumps(func(*args, **kw))
            except HttpError, e:
                ctx.response.content_type = None
                raise
            except APIError, e:
                return json.dumps(dict(error=e.code, data=e.data, message=e.message))
            except Exception, e:
                logging.exception('Error when calling api function.')
                return json.dumps(dict(error='server:error', data=e.__class__.__name__, message=e.message))
        return _wrapper
    return _decorator

_RE_MD5 = re.compile(r'^[0-9a-f]{32}$')
#_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

def check_md5_passwd(passwd):
    pw = str(passwd)
    if _RE_MD5.match(pw) is None:
        raise APIValueError('passwd', 'Invalid password.')
    return pw

_REG_EMAIL = re.compile(r'^[0-9a-z]([\-\.\w]*[0-9a-z])*\@([0-9a-z][\-\w]*[0-9a-z]\.)+[a-z]{2,9}$')

def check_email(email):
    '''
    Validate email address and return formated email.

    >>> check_email('michael@example.com')
    'michael@example.com'
    >>> check_email(' Michael@example.com ')
    'michael@example.com'
    >>> check_email(' michael@EXAMPLE.COM\\n\\n')
    'michael@example.com'
    >>> check_email(u'michael.liao@EXAMPLE.com.cn')
    'michael.liao@example.com.cn'
    >>> check_email('michael-liao@staff.example-inc.com.hk')
    'michael-liao@staff.example-inc.com.hk'
    >>> check_email('007michael@staff.007.com.cn')
    '007michael@staff.007.com.cn'
    >>> check_email('localhost')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    >>> check_email('@localhost')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    >>> check_email('michael@')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    >>> check_email('michael@localhost')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    >>> check_email('michael@local.host.')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    >>> check_email('-hello@example.local')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    >>> check_email('michael$name@local.local')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    >>> check_email('user.@example.com')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    >>> check_email('user-@example.com')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    >>> check_email('user-0@example-.com')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    '''
    e = str(email).strip().lower()
    if _REG_EMAIL.match(e) is None:
        raise APIValueError('email', 'Invalid email address.')
    return e

if __name__=='__main__':
    cache.client = cache.RedisClient('localhost')
    ctx.website = Dict(id='123000')
    import doctest
    doctest.testmod()
 