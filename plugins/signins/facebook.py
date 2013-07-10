#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import json, time, cgi, urllib, urllib2, logging, urlparse

from core import http
from core.models import create_random, verify_random

class Plugin(object):

    name = 'Facebook'

    description = 'Sign in with Facebook'

    icon = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAMAAADXqc3KAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAADBQTFRFa3m2NUmbOVevWmqtk53JcofGQVShzdLmxMriITaR6ev0VXC9R2O2////PVCfV4PbR1g5VQAAABB0Uk5T////////////////////AOAjXRkAAACYSURBVHjarNLLDsQgCAVQrlAUtfb//7bYyTyqdjd3RTiJYoSOh9AhW6hDAokDtTnYHELT35aZNUV1qN+uwpSZFa3cAZDdQzaCpX0J4N7OmUcw8j4bvJwhGyYw4w4+7g3QUox+VIyx4g77O/oA2YajRPwZWWTDdHl9Xa7Lca9p/w1hBf2jCmYA9WUo4bMDKaWrKH0ZHnIKMAASAhpQDcMIkAAAAABJRU5ErkJggg=='

    def __init__(self, **settings):
        self._client_id = settings.get('client_id', '')
        self._client_secret = settings.get('client_secret', '')
        if not self._client_id or not self._client_secret:
            raise StandardError('invalid client id or client secret.')

    @classmethod
    def validate(cls, **kw):
        pass

    @classmethod
    def get_inputs(cls):
        return (dict(key='client_id', name='App Key', description='App key'),
                dict(key='client_secret', name='App Secret', description='App secret'))

    def get_auth_url(self, callback_url):
        rnd = create_random()
        return '%s?%s' % ('https://www.facebook.com/dialog/oauth', 
            http.encode_params(
                redirect_uri=callback_url, \
                response_type='code', \
                client_id=self._client_id, \
                state=rnd, \
                scope='email,user_about_me'))

    def auth_callback(self, callback_url, **kw):
        # facebook login:
        code = kw.get('code', '')
        if not code:
            raise IOError('bad code')
        state = kw.get('state', '')
        if not state:
            raise IOError('bad state')
        verify_random(state)
        c, s = http.http_get('https://graph.facebook.com/oauth/access_token', \
                client_id = self._client_id, \
                client_secret = self._client_secret, \
                redirect_uri = callback_url, \
                code = code)
        if c!=200:
            raise IOError('Failed get oauth2 access token.')
        qs = urlparse.parse_qs(s)
        access_token = qs['access_token'][0]
        expires = time.time() + float(qs['expires'][0])

        # get user info:
        c, s = http.http_get('https://graph.facebook.com/me?fields=id,email,name,picture&access_token=%s' % access_token)
        if c!=200:
            raise IOError('Failed get user info.')
        profile = json.loads(s)

        email = profile.get('email', '').strip().lower()

        return dict(id=profile['id'], \
                email=email, \
                name=profile['name'].strip(), \
                image_url=profile['picture']['data']['url'], \
                auth_token=access_token, \
                expires=expires)
        return profile
