#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
A WSGI-compatible app with Redis cache.
'''

import logging
logging.basicConfig(level=logging.INFO)

import os

from transwarp import i18n; i18n.install_i18n(); i18n.load_i18n('i18n/zh_cn.txt')
from transwarp import cache; cache.client = cache.RedisClient('localhost')
from transwarp import web, db

from plugin.filters import load_user, load_i18n

def create_app():
    from conf import dbconf
    kwargs = dict([(s, getattr(dbconf, s)) for s in dir(dbconf) if s.startswith('DB_')])
    dbargs = kwargs.pop('DB_ARGS', {})
    db.init(db_type = kwargs['DB_TYPE'],
            db_schema = kwargs['DB_SCHEMA'],
            db_host = kwargs['DB_HOST'],
            db_port = kwargs.get('DB_PORT', 0),
            db_user = kwargs.get('DB_USER'),
            db_password = kwargs.get('DB_PASSWORD'),
            **dbargs)
    return web.WSGIApplication(('install', 'admin', 'apps.manage', 'apps.article'), document_root=os.path.dirname(os.path.abspath(__file__)), filters=(load_user, load_i18n), template_engine='jinja2', DEBUG=True)

application = create_app()
