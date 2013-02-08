#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import functools, logging

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
