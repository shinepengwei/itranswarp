#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import json, time, cgi, base64, urllib, urllib2, logging

from core import http
from core.models import create_random, verify_random

def _b64decode(s):
    if isinstance(s, unicode):
        s = s.encode('utf-8')
    padded = s + '=' * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(padded)

class Plugin(object):

    name = 'Google'

    description = 'Sign in with Google'

    icon = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAMAAADXqc3KAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAAGBQTFRF7vDvM2nBKmG9XobKQnXIGlW2WXeqATGgcYapq7jNIVu7lKO7BUi2L2bEPHDHk6nMzM7Rt8nk0d3v59i+EVXEL1WU//LTFFG0AD6xeJfISHnKLGPCN2rGEE2x////V4Pbq/YVuQAAACB0Uk5T/////////////////////////////////////////wBcXBvtAAABC0lEQVR42nSSi46DIBAABUQeItqqdRVY//8vbxfbXnLtTYjZcbKJJjTnPzTnGfMnHGJ7fBIp5KN9Egci8qBqoIFos+521SnFcm1c74fV7SOiE/kVRKys830JOzaCPLeZQ/0Mb1H5XCZ+5hw5DCILITaLe4mhx8OTXWGgSSwW72UxE/pElmtIQ0pJ+gnvwjZZswnBQSYpZfJ6vz3Qg5BsAwcvKx5MjyPoKs/gvU/BWNvTfwTPXIEJ6+xUGx3tvIOmYVkfN4ACxjWFPdVAgMUEWnvomrKRv0PocDQQwMwO9CtsDPQ42c7Ot1BYf0OBw03OKQjbK6RyAQboPKVulC9wOLNMf5Cp3pLv/AgwAAZfKyFODpR/AAAAAElFTkSuQmCC'

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
        return (dict(key='client_id', name='Client ID', description='Client ID'),
                dict(key='client_secret', name='Client Secret', description='Client Secret'))

    def get_auth_url(self, callback_url):
        rnd = create_random()
        return '%s?%s' % ('https://accounts.google.com/o/oauth2/auth', http.encode_params(
                redirect_uri=callback_url, \
                client_id=self._client_id, \
                response_type='code', \
                state=rnd, \
                scope='https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile'))

    def auth_callback(self, callback_url, **kw):
        # google login:
        code = kw.get('code', '')
        if not code:
            raise IOError('bad code')
        state = kw.get('state', '')
        if not state:
            raise IOError('bad state')
        verify_random(state)
        verify_random(state)
        c, s = http.http_post('https://accounts.google.com/o/oauth2/token', \
                client_id = self._client_id, \
                client_secret = self._client_secret, \
                redirect_uri = callback_url, \
                code = code, \
                grant_type = 'authorization_code')
        if c!=200:
            raise IOError('Failed get oauth2 access token.')
        r = json.loads(s)
        access_token = '%s %s' % (r['token_type'], r['access_token'])
        expires = time.time() + float(r['expires_in'])
        segments = r['id_token'].split('.')
        if len(segments) != 3:
            raise IOError('bad id_token.')
        it = json.loads(_b64decode(segments[1]))
        google_id = it['sub']
        email_verified = it.get('email_verified', '')=='true'
        email = it.get('email', '')
        # get user info:
        c, s = http.http_get('https://www.googleapis.com/oauth2/v3/userinfo', headers=dict(Authorization=access_token))
        if c!=200:
            raise IOError('Failed get user info.')
        ui = json.loads(s)

        profile = dict(id=google_id, \
                name=ui.get('name', ''), \
                image_url=ui.get('picture', ''), \
                auth_token=access_token, \
                expires=expires)
        if email and email_verified:
            profile['email'] = email.strip().lower()
        return profile
