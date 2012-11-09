#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
A gevent app

Commands for init mysql db:

> create database itranswarp;
> create user 'www-data'@'localhost' identified by 'www-data';
> grant all privileges on itranswarp.* to 'www-data'@'localhost';

or for production mode:

> grant select,insert,update,delete on itranswarp.* to 'www-data'@'localhost';
'''

from wsgiref.simple_server import make_server

import os, logging
logging.basicConfig(level=logging.INFO)

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
    return web.WSGIApplication(('static_handler', 'admin', 'apps.manage', 'apps.article', 'install'), document_root=os.path.dirname(os.path.abspath(__file__)), filters=(load_user, load_i18n), template_engine='jinja2', DEBUG=True)

if __name__=='__main__':
    logging.info('application will start...')
    server = make_server('127.0.0.1', 8080, create_app())
    server.serve_forever()
