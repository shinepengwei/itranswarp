#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import functools

from itranswarp.web import ctx
from itranswarp import db, i18n

import util

def load_user(func):
    @functools.wraps(func)
    def _wrapper(*args, **kw):
        user = None
        uid = util.extract_session_cookie()
        if uid:
            users = db.select('select * from users where id=?', uid)
            if users:
                user = users[0]
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
