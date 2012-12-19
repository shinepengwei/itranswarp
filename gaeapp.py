#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
A Google AppEngine compatible app with memcache.
'''

from conf.google_appengine import SQL_INSTANCE_NAME, SQL_DATABASE_NAME

import os, logging
logging.basicConfig(level=logging.INFO)

from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import memcache, rdbms

from transwarp import i18n; i18n.install_i18n(); i18n.load_i18n('i18n/zh_cn.txt')
from transwarp import web, db, cache

from plugin.filters import load_user, load_i18n

class GAECacheClient(object):
    ' Google AppEngine Cache Client '

    def set(self, key, value, expires=0):
        memcache.set(key, value, expires)

    def get(self, key, default=None):
        r = memcache.get(key)
        return default if r is None else r

    def gets(self, *keys):
        r = memcache.get_multi(keys)
        return map(lambda k: r.get(k), keys)

    def delete(self, key):
        self._client.delete(key)

    def incr(self, key):
        return memcache.incr(key, initial_value=0)

    def decr(self, key):
        return memcache.decr(key, initial_value=1)

def create_app():
    cache.client = GAECacheClient()
    db.init_connector(lambda: rdbms.connect(instance=SQL_INSTANCE_NAME, database=SQL_DATABASE_NAME))
    return web.WSGIApplication( \
            ('install', 'admin', 'apps.manage', 'apps.article', 'apps.photo'), \
            document_root=os.path.dirname(os.path.abspath(__file__)), \
            filters=(load_user, load_i18n), \
            template_engine='jinja2', DEBUG=True)

app = create_app()
