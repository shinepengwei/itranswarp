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

> grant select,insert,update,delete privileges on itranswarp.* to 'www-data'@'localhost';
'''

from gevent import monkey; monkey.patch_all()
from gevent.wsgi import WSGIServer

import logging
logging.basicConfig(level=logging.INFO)

import os
import sys
sys.path.append(os.path.abspath('.'))

from itranswarp import web
from itranswarp import db

from plugin.filters import load_user

if __name__=='__main__':
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
    application = web.WSGIApplication(('index', 'admin', 'apps.manage', 'apps.article', 'install'), filters=(load_user,), template_engine='jinja2', DEBUG=True)
    server = WSGIServer(('0.0.0.0', 8080), application)
    server.serve_forever()
