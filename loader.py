#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' Loader module that load modules dynamic. '

import os, logging, functools

from transwarp.web import ctx, forbidden, notfound
from transwarp import db, i18n

from auth import extract_session_cookie, http_basic_auth

def load_site(func):
    @functools.wraps(func)
    def _wrapper(*args, **kw):
        website = None
        host = ctx.request.host.lower()
        n = host.find(u':')
        if n!=(-1):
            host = host[:n]
        logging.debug('try load website: %s' % host)
        # FIXME: improve speed:
        wss = db.select('select * from websites where domain=?', host)
        if wss:
            ws = wss[0]
            if ws.disabled:
                logging.debug('website is disabled: %s' % host)
                raise forbidden()
            logging.info('bind ctx.website')
            ctx.website = ws
            try:
                return func(*args, **kw)
            finally:
                del ctx.website
        logging.debug('website not found: %s' % host)
        raise notfound()
    return _wrapper

def load_user(func):
    @functools.wraps(func)
    def _wrapper(*args, **kw):
        user = extract_session_cookie()
        if user is None:
            auth = ctx.request.header('AUTHORIZATION')
            logging.debug('get authorization header: %s' % auth)
            if auth and auth.startswith('Basic '):
                user = http_basic_auth(auth[6:])
        if user and ctx.website.id!=user.website_id:
            user = None
        logging.info('bind ctx.user')
        ctx.user = user
        try:
            return func(*args, **kw)
        finally:
            del ctx.user
    return _wrapper

def load_i18n(func):
    @functools.wraps(func)
    def _wrapper(*args, **kw):
        lc = 'en'
        al = ctx.request.header('ACCEPT-LANGUAGE')
        if al:
            lcs = al.split(',')
            lc = lcs[0].strip().lower()
        with i18n.locale(lc):
            return func(*args, **kw)
    return _wrapper

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
    web_root = os.path.dirname(os.path.abspath(__file__))
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

def load_navigations():
    navs = db.select('select * from navigations where website_id=? order by display_order', ctx.website.id)
    return navs

if __name__=='__main__':
    import doctest
    doctest.testmod()
 