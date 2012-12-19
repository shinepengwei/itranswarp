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
from transwarp import web, db, cache

from plugin.filters import load_user, load_i18n

from conf.mysql import DB_SCHEMA, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD

def create_app():
    cache.client = cache.RedisClient('localhost')
    db.init(db_type = 'mysql', \
            db_schema = DB_SCHEMA, \
            db_host = DB_HOST, \
            db_port = DB_PORT, \
            db_user = DB_USER, \
            db_password = DB_PASSWORD, \
            use_unicode = True, charset = 'utf8')
    return web.WSGIApplication(('install', 'admin', 'apps.manage', 'apps.article', 'apps.photo'), \
            document_root=os.path.dirname(os.path.abspath(__file__)), \
            filters=(load_user, load_i18n), template_engine='jinja2', \
            DEBUG=True)

application = create_app()
