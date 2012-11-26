#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import json, time, cgi, urllib, urllib2, logging, mimetypes

from transwarp.web import ctx, seeother

class Provider(object):

    def __init__(self, **settings):
        self._app_key = settings.get('app_key', '')
        self._app_secret = settings.get('app_secret', '')
        domain = settings.get('domain', '')
        if not domain:
            domain = ctx.server_name
        if not domain:
            raise StandardError('domain is not configued')
        self._callback = 'http://%s/auth/callback/qqweibo' % domain
        if not self._app_key or not self._app_secret:
            raise StandardError('qqweibo signin app_key or app_secret is not configued')

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
                dict(key='domain', name='Domain', description='Website domain'))

    def get_auth_url(self):
        referer = ctx.request.header('referer', '/')
        logging.warning('referer: %s' % referer)
        client = APIClient(self._app_key, self._app_secret, redirect_uri=self._callback)
        return client.get_authorize_url()

    def auth_callback(self):
        # sina weibo login:
        code = ctx.request['code']
        client = APIClient(self._app_key, self._app_secret, self._callback)
        r = client.request_access_token(code)
        logging.warning('access token: %s' % json.dumps(r))
        access_token, expires_in, openid = r.access_token, r.expires_in, r.openid
        client.set_access_token(access_token, expires_in, openid)
        u = client.user.info.get()
        logging.warning('user: %s' % json.dumps(u))
        current = time.time()
        return dict(id=str(openid), name=u.nick, image_url=u.head, auth_token=access_token, expired_time=r.expires_in)

# qq weibo api: copied from qqweibo.py

class APIError(StandardError):
    '''
    raise APIError if got failed json message.
    '''
    def __init__(self, error_code, error, request):
        self.error_code = error_code
        self.error = error
        self.request = request
        StandardError.__init__(self, error)

    def __str__(self):
        return 'APIError: %s: %s, request: %s' % (self.error_code, self.error, self.request)

def _parse_json(s):
    ' parse str to JsonDict '

    def _obj_hook(pairs):
        ' convert json object to python object '
        o = JsonDict()
        for k, v in pairs.iteritems():
            o[str(k)] = v
        return o
    return json.loads(s, object_hook=_obj_hook)

class JsonDict(dict):
    ' general json object that can bind any fields but also act as a dict '
    def __getattr__(self, attr):
        return self[attr]

    def __setattr__(self, attr, value):
        self[attr] = value

    def __getstate__(self):
        return self.copy()

    def __setstate__(self, state):
        self.update(state)

def _encode_params(**kw):
    ' do url-encode parameters '
    args = []
    for k, v in kw.iteritems():
        qv = v.encode('utf-8') if isinstance(v, unicode) else str(v)
        args.append('%s=%s' % (k, urllib.quote(qv)))
    return '&'.join(args)

def _encode_multipart(**kw):
    ' build a multipart/form-data body with generated random boundary '
    boundary = '----------%s' % hex(int(time.time() * 1000))
    data = []
    for k, v in kw.iteritems():
        data.append('--%s' % boundary)
        if hasattr(v, 'read'):
            # file-like object:
            filename = getattr(v, 'name', '')
            content = v.read()
            data.append('Content-Disposition: form-data; name="%s"; filename="hidden"' % k)
            data.append('Content-Length: %d' % len(content))
            data.append('Content-Type: %s\r\n' % _guess_content_type(filename))
            data.append(content)
        else:
            data.append('Content-Disposition: form-data; name="%s"\r\n' % k)
            data.append(v.encode('utf-8') if isinstance(v, unicode) else v)
    data.append('--%s--\r\n' % boundary)
    return '\r\n'.join(data), boundary

def _guess_content_type(url):
    n = url.rfind('.')
    if n==(-1):
        return 'application/octet-stream'
    ext = url[n:]
    mimetypes.types_map.get(ext, 'application/octet-stream')

_HTTP_GET = 0
_HTTP_POST = 1
_HTTP_UPLOAD = 2

def _http_get(url, authorization=None, return_json=True, **kw):
    logging.info('GET %s' % url)
    return _http_call(url, _HTTP_GET, authorization, return_json, **kw)

def _http_post(url, authorization=None, return_json=True, **kw):
    logging.info('POST %s' % url)
    return _http_call(url, _HTTP_POST, authorization, return_json, **kw)

def _http_upload(url, authorization=None, return_json=True, **kw):
    logging.info('MULTIPART POST %s' % url)
    return _http_call(url, _HTTP_UPLOAD, authorization, return_json, **kw)

def _http_call(the_url, method, authorization, return_json=True, **kw):
    '''
    send an http request and expect to return a json object if no error.
    '''
    params = None
    boundary = None
    params = _encode_params(**kw) if 'format' in kw else _encode_params(format='json', **kw)
    http_url = '%s?%s' % (the_url, params) if method==_HTTP_GET else the_url
    http_body = None if method==_HTTP_GET else params
    req = urllib2.Request(http_url, data=http_body)
    if authorization:
        req.add_header('Authorization', 'OAuth2 %s' % authorization)
    if boundary:
        req.add_header('Content-Type', 'multipart/form-data; boundary=%s' % boundary)
    try:
        resp = urllib2.urlopen(req)
        body = resp.read()
        if return_json:
            r = _parse_json(body)
            if r.errcode==0:
                return r.data
            raise APIError(r.errcode, r.msg, r.ret)
        return body
    except urllib2.HTTPError, e:
        if return_json:
            try:
                r = _parse_json(e.read())
                raise APIError(r.errcode, r.msg, r.ret)
            except ValueError:
                pass
        raise e

class APIClient(object):
    '''
    API client using synchronized invocation.
    '''
    def __init__(self, app_key, app_secret, redirect_uri=None, response_type='code'):
        self.client_id = app_key
        self.client_secret = app_secret
        self.redirect_uri = redirect_uri
        self.response_type = response_type
        self.auth_url = 'https://open.t.qq.com/cgi-bin/oauth2/'
        self.api_url = 'https://open.t.qq.com/api/'
        self.access_token = None
        self.expires = 0.0

    def set_access_token(self, access_token, expires, openid):
        self.access_token = str(access_token)
        self.expires = float(expires)
        self.openid = str(openid)

    def get_authorize_url(self, redirect_uri=None, **kw):
        '''
        return the authroize url that should be redirect.
        '''
        redirect = redirect_uri if redirect_uri else self.redirect_uri
        if not redirect:
            raise APIError('21305', 'Parameter absent: redirect_uri', 'OAuth2 request')
        response_type = kw.pop('response_type', 'code')
        return '%s%s?%s' % (self.auth_url, 'authorize', \
                _encode_params(client_id = self.client_id, \
                        response_type = response_type, \
                        redirect_uri = redirect, **kw))

    def request_access_token(self, code, redirect_uri=None):
        '''
        return access token as object: {"access_token":"your-access-token","expires_in":12345678,"uid":1234}, expires_in is standard unix-epoch-time
        '''
        redirect = redirect_uri if redirect_uri else self.redirect_uri
        if not redirect:
            raise APIError('21305', 'Parameter absent: redirect_uri', 'OAuth2 request')
        r = _http_post('%s%s' % (self.auth_url, 'access_token'), \
                client_id = self.client_id, \
                client_secret = self.client_secret, \
                redirect_uri = redirect, \
                return_json = False, \
                code = code, grant_type = 'authorization_code')
        d = cgi.parse_qs(r, keep_blank_values=True)
        access_token = d['access_token'][0]
        current = int(time.time())
        expires = int(d['expires_in'][0]) + current
        openid = d['openid'][0]
        return JsonDict(access_token=access_token, expires=expires, expires_in=expires, openid=openid)

    def is_expires(self):
        return not self.access_token or time.time() > self.expires

    def __getattr__(self, attr):
        return _Callable(self, attr)

_METHOD_MAP = { 'GET': _HTTP_GET, 'POST': _HTTP_POST, 'UPLOAD': _HTTP_UPLOAD }

class _Executable(object):

    def __init__(self, client, method, path):
        self._client = client
        self._method = method
        self._path = path

    def __call__(self, **kw):
        method = _METHOD_MAP[self._method]
        if method==_HTTP_POST and 'pic' in kw:
            method = _HTTP_UPLOAD
        return _http_call('%s%s' % (self._client.api_url, self._path), method, self._client.access_token, access_token=self._client.access_token, openid=self._client.openid, oauth_consumer_key=self._client.client_id, oauth_version='2.a', **kw)

    def __str__(self):
        return '_Executable (%s %s)' % (self._method, self._path)

    __repr__ = __str__

class _Callable(object):

    def __init__(self, client, name):
        self._client = client
        self._name = name

    def __getattr__(self, attr):
        if attr=='get':
            return _Executable(self._client, 'GET', self._name)
        if attr=='post':
            return _Executable(self._client, 'POST', self._name)
        name = '%s/%s' % (self._name, attr)
        return _Callable(self._client, name)

    def __str__(self):
        return '_Callable (%s)' % self._name

    __repr__ = __str__
