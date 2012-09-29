#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
A simple cache interface.
'''

import os, time, uuid, datetime, functools, logging

_FUNC_SET = None
_FUNC_GET = None
_FUNC_DELETE = None

def init(provider, servers, debug=False):
    global _FUNC_GET, _FUNC_SET, _FUNC_DELETE
    if provider=='memcache' or provider=='memcached':
        import memcache
        client = memcache.Client(servers, debug)
        _FUNC_SET = client.set
        _FUNC_GET = client.get
        _FUNC_DELETE = client.delete
    if provider=='redis':
        import redis
        client = redis.StrictRedis(host=servers)
        def _redis_set(name, value, expires):
            if isinstance(value, str):
                value = 'str:%s' % value
            if isinstance(value, unicode):
                value = 'uni:%s' % value.encode('utf-8')
            client.set(name, value)
            if expires:
                client.expire(name, expires)
        def _redis_get(name):
            r = client.get(name)
            if isinstance(r, str):
                if r.startswith('str:'):
                    return r[4:]
                if r.startswith('uni:'):
                    return r[4:].decode('utf-8')
            return r
        _FUNC_SET = _redis_set
        _FUNC_GET = _redis_get
        _FUNC_DELETE = client.delete

def get(key, default=None):
    '''
    Get object by key.

    Args:
        key: cache key as str.
        default: default value if key not found. default to None.
    Returns:
        object or None if not found.

    >>> key = uuid.uuid4().hex
    >>> get(key)
    >>> get(key, 'DEFAULT_OBJECT')
    'DEFAULT_OBJECT'
    >>> set(key, 'Hello')
    >>> get(key)
    'Hello'
    >>> set(key, 100)
    >>> int(get(key))
    100
    '''
    r = _FUNC_GET(key)
    return default if r is None else r

def set(key, value, expires=0):
    '''
    Set object with key.

    Args:
        key: cache key as str.
        value: object value.
        expires: cache time, default to 0 (using default expires time)

    >>> key = uuid.uuid4().hex
    >>> set(key, u'Python\u4e2d\u6587')
    >>> get(key)
    u'Python\u4e2d\u6587'
    >>> set(key, 'Hi', 2)
    >>> get(key)
    'Hi'
    >>> time.sleep(3)
    >>> get(key, 'Not Exist')
    'Not Exist'
    '''
    _FUNC_SET(key, value, expires)

def delete(key):
    '''
    Delete the key from cache.

    Args:
        key: cache key as str.

    >>> key = uuid.uuid4().hex
    >>> set(key, 'Python')
    >>> get(key)
    'Python'
    >>> delete(key)
    >>> get(key)
    '''
    _FUNC_DELETE(key)

if __name__=='__main__':
    import sys, doctest
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    init('memcache', ['127.0.0.1:11211'])
    doctest.testmod()
    init('redis', '127.0.0.1')
    doctest.testmod()
