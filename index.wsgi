#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# index.wsgi for Sina AppEngine
#

__author__ = 'Michael Liao'

import sae, pylibmc

import os

from transwarp import i18n; i18n.install_i18n(); i18n.load_i18n('i18n/zh_cn.txt')
from transwarp import cache
from transwarp import web, db

from plugin.filters import load_user, load_i18n

class SAECacheClient(object):
    ' Sina AppEngine Cache Client '

    def __init__(self):
        self._client = pylibmc.Client()

    def set(self, key, value, expires=0):
        self._client.set(key, value, expires)

    def get(self, key, default=None):
        r = self._client.get(key)
        return default if r is None else r

    def gets(self, *keys):
        r = self._client.get_multi(keys)
        return map(lambda k: r.get(k), keys)

    def delete(self, key):
        self._client.delete(key)

    def incr(self, key):
        try:
            return self._client.incr(key)
        except pylibmc.NotFound:
            self._client.set(key, 1)
            return 1

    def decr(self, key):
        try:
            return self._client.decr(key)
        except pylibmc.NotFound:
            return 0

def create_app():
    cache.client = SAECacheClient()
    db.init(db_type = 'mysql', \
            db_schema = sae.const.MYSQL_DB, \
            db_host = sae.const.MYSQL_HOST, \
            db_port = int(sae.const.MYSQL_PORT), \
            db_user = sae.const.MYSQL_USER, \
            db_password = sae.const.MYSQL_PASS, \
            use_unicode = True, charset = 'utf8')
    return web.WSGIApplication(('install', 'admin', 'apps.manage', 'apps.article', 'apps.photo'), \
            document_root=os.path.dirname(os.path.abspath(__file__)), \
            filters=(load_user, load_i18n), template_engine='jinja2', \
            DEBUG=True)

application = sae.create_wsgi_app(create_app())
