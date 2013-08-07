#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import json, time, cgi, urllib, urllib2, urlparse, logging, mimetypes

from transwarp.web import ctx, seeother, Dict

from core import http
from core.models import create_random, verify_random

class Plugin(object):

    name = 'QQ'

    description = 'Sign in with QQ'

    icon = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAMAAADXqc3KAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAADBQTFRFKCMr97YV9fb4kY6Q6CYGs7G0X11ia0kiyXly44sNnBoMtV8pz8vK3uHm+NhG8fLzNimDjAAAABB0Uk5T////////////////////AOAjXRkAAADnSURBVHjaVJCJksQgCEQJCJ5k/v9vt8VjZ7rKCvQzINBni9Ug8ZPT/g6jJeEfcH0i4y/g8G0fki8gyB3UeRK/gKPC7K1yfgngszaeRTxrkl0woqniCP2Ajiz3532fOkMaG3hrlCv893lqJWrlggQCBD9nJAdISwkotEIPMFZ61eLBAHihlH/UNWakGEJLaq1Ptwz2mJE+ukBKzkseoywgExx/kAVwGmajp3KAmJPO5gympw5jyQPW3lU9xOH3l8/k9X2yeGgYkruruYyeBbI+Yz2gVKh3s9wj8g3YFZd1oNAKZo8/AQYA1L0RkSdi+ngAAAAASUVORK5CYII='

    def __init__(self, **settings):
        self._client_id = settings.get('client_id', '')
        self._client_secret = settings.get('client_secret', '')
        if not self._client_id or not self._client_secret:
            raise StandardError('qq signin app_key or app_secret is not configued')

    @classmethod
    def validate(cls, **kw):
        pass

    @classmethod
    def get_inputs(cls):
        return (dict(key='client_id', name='App Key', description='App key'),
                dict(key='client_secret', name='App Secret', description='App secret'))

    def get_auth_url(self, callback_url):
        rnd = create_random()
        return '%s?%s' % ('https://graph.qq.com/oauth2.0/authorize', http.encode_params( \
                redirect_uri=callback_url, \
                response_type='code', \
                client_id=self._client_id, \
                state=rnd, \
                scope='get_user_info'
        ))

    def auth_callback(self, callback_url, **kw):
        code = kw.get('code', '')
        if not code:
            raise IOError('bad code')
        state = kw.get('state', '')
        if not state:
            raise IOError('bad state')
        verify_random(state)
        c, s = http.http_post('https://graph.qq.com/oauth2.0/token', \
                client_id = self._client_id, \
                client_secret = self._client_secret, \
                redirect_uri = callback_url, \
                code = code, \
                grant_type = 'authorization_code')
        if c!=200:
            raise IOError('Failed get oauth2 access token.')
        logging.info('QQ >>>>>> %s' % s)
        qs = urlparse.parse_qs(s)
        access_token = qs['access_token'][0]
        expires = time.time() + float(qs['expires_in'][0])
        # get openid:
        c, s = http.http_get('https://graph.z.qq.com/moc2/me?access_token=%s' % access_token)
        if c!=200:
            raise IOError('Failed get user openid.')
        openid = urlparse.parse_qs(s)['openid'][0]
        # get user info:
        c, s = http.http_get('https://graph.qq.com/user/get_user_info?%s' % http.encode_params( \
                access_token = access_token, \
                openid=openid, \
                oauth_consumer_key=self._client_id, \
                format = 'json' \
        ))
        if c!=200:
            raise IOError('Failed get user info.')
        logging.info('QQ >>>>>> %s' % s)
        profile = json.loads(s)
        if profile['ret'] != 0:
            raise IOError(profile['msg'])

        return dict(id=openid, \
                name=profile['nickname'].strip(), \
                image_url=profile['figureurl_qq_1'], \
                auth_token=access_token, \
                expires=expires)
        return profile
