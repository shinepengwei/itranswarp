#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
A WSGI application entry.
'''

import os, logging

import locale; locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

from transwarp import i18n; i18n.install_i18n(); i18n.load_i18n('i18n/zh_cn.txt')
from transwarp import web, db, cache

def create_app(debug):
    if debug:
        import conf_dev as conf
    else:
        import conf_prod as conf
    logging.info('db conf: %s' % str(conf.db))
    logging.info('cache conf: %s' % str(conf.cache))
    # init db:
    db.init(db_type=conf.db['type'], db_schema=conf.db['schema'], \
        db_host=conf.db['host'], db_port=conf.db['port'], \
        db_user=conf.db['user'], db_password=conf.db['password'], \
        use_unicode=True, charset='utf8')
    # init cache:
    if conf.cache['type']=='redis':
        host = conf.cache.get('host', 'localhost')
        cache.client = cache.RedisClient(host)
    if conf.cache['type']=='memcache':
        host = conf.cache.get('host', 'localhost')
        cache.client = cache.MemcacheClient(host)
    scan = ['apps.article', 'apps.wiki', 'apps.website', 'apps.admin', 'core.auth', 'core.manage']
    if debug:
        scan.append('static_handler')
    from core.interceptors import load_site, load_user, load_i18n
    return web.WSGIApplication(scan, \
            document_root=os.path.dirname(os.path.abspath(__file__)), \
            filters=(load_site, load_user, load_i18n), \
            template_engine='jinja2', \
            DEBUG=debug)
