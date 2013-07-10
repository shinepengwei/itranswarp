#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import json, time, cgi, base64, urllib, urllib2, logging, mimetypes

from core import http
from core.models import create_random, verify_random

def _b64decode(s):
    if isinstance(s, unicode):
        s = s.encode('utf-8')
    padded = s + '=' * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(padded)

class Plugin(object):

    name = 'LinkedIn'

    description = 'Sign in with LinkedIn'

    icon = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAMAAADXqc3KAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAADBQTFRFoMvkLpHG5vL6Foe+Ana2bq3Sz+bzAGesS6HPh8DfEH65Ya3afLjdDHKy////8fLzNIH9ZwAAABB0Uk5T////////////////////AOAjXRkAAAC0SURBVHjafNJbDgMhCAVQEARFpfvfbdGa1j6mNyFhcnKDHwO3i8AfyLW/p/a8oAHUWuFMW1B6a7W1/Erf0Iq4lCOtLEDM7p7xpA0onvAtG8jQiJhjiO0JRBQHDWtFBIESvsEobjC6S4rFkTcYW/I0ISgGlOkBOkEnoMYDhdmOxgRRNY/yF8CCo8EXoFfA8eU/bgwdkkQxpdlISVhpg44x5sS2Vn009Du8oI/PKPz/GX7nLsAAmBEVpdUfu6IAAAAASUVORK5CYII='

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
        return (dict(key='client_id', name='API Key', description='API Key'),
                dict(key='client_secret', name='Secret Key', description='Secret Key'))

    def get_auth_url(self, callback_url):
        rnd = create_random()
        return '%s?%s' % ('https://www.linkedin.com/uas/oauth2/authorization', http.encode_params(
                redirect_uri=callback_url, \
                client_id=self._client_id, \
                response_type='code', \
                state=rnd, \
                scope='r_basicprofile r_emailaddress'))

    def auth_callback(self, callback_url, **kw):
        code = kw.get('code', '')
        if not code:
            raise IOError('bad code')
        state = kw.get('state', '')
        if not state:
            raise IOError('bad state')
        verify_random(state)
        c, s = http.http_post('https://www.linkedin.com/uas/oauth2/accessToken', \
                client_id = self._client_id, \
                client_secret = self._client_secret, \
                redirect_uri = callback_url, \
                code = code, \
                grant_type = 'authorization_code')
        if c!=200:
            raise IOError('Failed get oauth2 access token.')
        logging.info('LinkedIn >>>>>> %s' % s)
        r = json.loads(s)
        access_token = r['access_token']
        expires = time.time() + float(r['expires_in'])
        # get user info:
        c, s = http.http_get('https://api.linkedin.com/v1/people/~:(id,email-address,first-name,last-name,picture-url)?oauth2_access_token=%s' % access_token, headers={'x-li-format': 'json'})
        if c!=200:
            raise IOError('Failed get user info.')
        logging.info('LinkedIn >>>>>> %s' % s)
        profile = json.loads(s)

        name = '%s %s' % (profile['firstName'], profile['lastName'])

        return dict(id=profile['id'], \
                email=profile['emailAddress'].strip().lower(), \
                name=name.strip(), \
                image_url=profile['pictureUrl'], \
                auth_token=access_token, \
                expires=expires)
        return profile
