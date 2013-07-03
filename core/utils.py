#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
Utils.
'''

import os, re, json, time, logging, functools

import markdown2

from transwarp import cache

def load_module(module_name):
    '''
    Load a module and return the module reference.
    '''
    pos = module_name.rfind('.')
    if pos==(-1):
        return __import__(module_name, globals(), locals(), [module_name])
    return __import__(module_name, globals(), locals(), [module_name[pos+1:]])

def scan_submodules(module_name):
    '''
    Scan sub modules and import as dict (key=module name, value=module).

    >>> ms = scan_submodules('apps')
    >>> type(ms['article'])
    <type 'module'>
    >>> ms['article'].__name__
    'apps.article'
    >>> type(ms['website'])
    <type 'module'>
    >>> ms['website'].__name__
    'apps.website'
    '''
    web_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mod_path = os.path.join(web_root, *module_name.split('.'))
    if not os.path.isdir(mod_path):
        raise IOError('No such file or directory: %s' % mod_path)
    dirs = os.listdir(mod_path)
    mod_dict = {}
    for name in dirs:
        if name=='__init__.py':
            continue
        p = os.path.join(mod_path, name)
        if os.path.isfile(p) and name.endswith('.py'):
            pyname = name[:-3]
            mod_dict[pyname] = __import__('%s.%s' % (module_name, pyname), globals(), locals(), [pyname])
        if os.path.isdir(p) and os.path.isfile(os.path.join(mod_path, name, '__init__.py')):
            mod_dict[name] = __import__('%s.%s' % (module_name, name), globals(), locals(), [name])
    return mod_dict

def cached_func(key=None, timeout=3600, use_ctx=True):
    '''
    Make function result cached. the cache key is:
      non-arg function: 'WebsiteId--FunctionName'
      args function: 'WebsiteId--FunctionName--Arg1--Arg2--ArgN'

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

def markdown2html(md):
    return markdown2.markdown(md)

if __name__=='__main__':
    cache.client = cache.MemcacheClient('localhost')
    ctx.website = Dict(id='123000')
    import doctest
    doctest.testmod()
 