#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
Roles definition.
'''

import re, json, logging, functools

from transwarp.web import ctx, get, post, forbidden, HttpError, Dict
from transwarp import db, cache

from core.apis import APIPermissionError

ROLE_SUPER_ADMINS = 0
ROLE_ADMINISTRATORS = 1
ROLE_EDITORS = 2
ROLE_AUTHORS = 4
ROLE_CONTRIBUTORS = 8
ROLE_SUBSCRIBERS = 64

ROLE_GUESTS = 0x10000000

ROLE_NAMES = {
    ROLE_SUPER_ADMINS: 'Super Admin',
    ROLE_ADMINISTRATORS: 'Administrator',
    ROLE_EDITORS: 'Editor',
    ROLE_AUTHORS: 'Author',
    ROLE_CONTRIBUTORS: 'Contributor',
    ROLE_SUBSCRIBERS: 'Subscriber',
    ROLE_GUESTS: 'Guest',
}

def allow(role=ROLE_ADMINISTRATORS):
    '''
    A decorator that check role for access permission.

    @api
    @allow(role=ROLE_ADMINISTRATORS)
    @post('/articles/create')
    def api_articles_create():
        return dict(id='123')
    '''
    def _decorator(func):
        @functools.wraps(func)
        def _wrapper(*args, **kw):
            if role < ROLE_GUESTS:
                if not ctx.user or ctx.user.role_id > role:
                    raise APIPermissionError()
            return func(*args, **kw)
        _wrapper.__role__ = role
        return _wrapper
    return _decorator
 