#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import json, time, urllib, urllib2, logging, mimetypes

from core import http

class Plugin(object):

    name = 'Sina Weibo'

    description = 'Sign in with Sina Weibo'

    icon = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAMAAADXqc3KAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAADBQTFRF8p0P8+3r6Flc8JKVPD094hof8MW38rpa8t3S3d7eaGtrt76+4yUpAAAA////8fLzOOB6ZAAAABB0Uk5T////////////////////AOAjXRkAAADkSURBVHjalJJhb8YgCIQBFam19v//2/cO22XJsmS7D23lgRO0cv8i+SvQLtJdf4IQqus3oLGfEU7yAjebRUncFWV9g7BJOTPgFDTc6RmfcYdDMOoJfIenFSaUu8sGT7y1tt/xAPpnMN801CBQrqe5rqVRjJ/sJgRGzWKt4zwWWGEpJxKbrSA8rusaREl4JNZMl9aLGgDxDCRZMK5aByBKFDsmMIJaddEMgM1zEynNUFGPs24r9IUZAYIlew+UacY1LwrEQs8xTjT75udFYYljgoyT53zv1Ybn8U2zEv/+Gb70EWAAQS4XB5EqMS0AAAAASUVORK5CYII='

    def __init__(self, **settings):
        self._client_id = settings.get('client_id', '')
        self._client_secret = settings.get('client_secret', '')
        if not self._client_id or not self._client_secret:
            raise StandardError('weibo signin app_key or app_secret is not configued')

    @classmethod
    def validate(cls, **kw):
        pass

    @classmethod
    def get_inputs(cls):
        return (dict(key='client_id', name='App Key', description='App key'),
                dict(key='client_secret', name='App Secret', description='App secret'))

    def get_auth_url(self, callback_url):
        return '%s?%s' % ('https://api.weibo.com/oauth2/authorize', http.encode_params(redirect_uri=callback_url, response_type='code', client_id=self._client_id))

    def auth_callback(self, callback_url, **kw):
        code = kw.get('code', '')
        if not code:
            raise IOError('missing code')
        c, s = http.http_post('https://api.weibo.com/oauth2/access_token', \
                client_id = self._client_id, \
                client_secret = self._client_secret, \
                redirect_uri = callback_url, \
                code = code, \
                grant_type = 'authorization_code')
        if c!=200:
            raise IOError('Failed get oauth2 access token.')
        r = json.loads(s)
        access_token = 'OAuth2 %s' % r['access_token']
        expires = time.time() + float(r['expires_in'])
        uid = r['uid']

        c, s = http.http_get('https://api.weibo.com/2/users/show.json', headers=dict(Authorization=access_token), uid=uid)
        if c!=200:
            raise IOError('Failed get oauth2 access token.')
        r = json.loads(s)
        return dict(id=uid, \
                name=r['screen_name'], \
                image_url=r['profile_image_url'], \
                auth_token=access_token, \
                expires=expires)
