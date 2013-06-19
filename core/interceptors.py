#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' interceptors that binds website, user and i18n context. '

import os, logging, functools

from transwarp.web import ctx, forbidden, notfound
from transwarp import db, i18n

from core.auth import extract_session_cookie, http_basic_auth
from core.models import Website, User
from core.utils import cached_func

#@cached_func(key='website', use_ctx=False)
def _get_site(host):
    ws = Website.select_one('where domain=?', host)
    if ws:
        if ws.disabled:
            logging.debug('website is disabled: %s' % host)
            raise forbidden()
        return ws
    raise notfound()

def load_site(func):
    @functools.wraps(func)
    def _wrapper(*args, **kw):
        website = None
        host = ctx.request.host.lower()
        n = host.find(u':')
        if n!=(-1):
            host = host[:n]
        logging.debug('try load website: %s' % host)
        ws = _get_site(host)
        ctx.website = ws
        try:
            return func(*args, **kw)
        finally:
            del ctx.website
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
        logging.info('bind ctx.user: %s' % user)
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
