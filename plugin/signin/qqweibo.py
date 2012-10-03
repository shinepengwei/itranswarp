#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import json
import time
import logging

from itranswarp.web import ctx, seeother
import weibo

class Provider(object):

    def __init__(self, **settings):
        self._app_key = settings.get('app_key', '')
        self._app_secret = settings.get('app_secret', '')
        self._callback = settings.get('callback', '')
        if not self._app_key or not self._app_secret or not self._callback:
            raise StandardError('weibo signin is not configured')

    @staticmethod
    def get_name():
        return _('QQ Weibo')

    @staticmethod
    def get_description():
        return _('QQ Weibo Signin')

    @staticmethod
    def get_settings():
        return (dict(key='app_key', name='App Key', description='App key'),
                dict(key='app_secret', name='App Secret', description='App secret'),
                dict(key='callback', name='Callback', description=''))

    def get_auth_url(self):
        referer = ctx.request.header('referer', '/')
        logging.warning('referer: %s' % referer)
        client = weibo.APIClient(self._app_key, self._app_secret, redirect_uri=self._callback)
        return client.get_authorize_url()

    def auth_callback(self):
        # sina weibo login:
        code = ctx.request['code']
        client = weibo.APIClient(self._app_key, self._app_secret, self._callback)
        r = client.request_access_token(code)
        logging.warning('access token: %s' % json.dumps(r))
        access_token, expires_in = r.access_token, r.expires_in
        client.set_access_token(access_token, expires_in)
        uid = r.uid
        u = client.get.users__show(uid=uid)
        logging.warning('user: %s' % json.dumps(u))
        current = time.time()
        return dict(id=str(uid), name=u.screen_name, image_url=u.profile_image_url, auth_token=access_token, expired_time=r.expires_in)
