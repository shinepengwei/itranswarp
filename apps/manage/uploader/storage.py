#!/usr/bin/env python
# -*-coding: utf8 -*-

'''
SAE Storage API simplified by:
Michael Liao (askxuefeng@gmail.com)
'''

import json
import uuid
import urllib
import urllib2
try:
    from sae.const import ACCESS_KEY, SECRET_KEY, APP_NAME
except ImportError:
    ACCESS_KEY = ''
    SECRET_KEY = ''
    APP_NAME = ''

_STOR_BACKEND = 'http://stor.sae.sina.com.cn/storageApi.php'

class Client(object):

    def __init__(self, domain, prefix=None, access_key=None, secret_key=None):
        self._domain = domain
        self._prefix = prefix if prefix else APP_NAME
        self._access_key = access_key if access_key else ACCESS_KEY
        self._secret_key = secret_key if secret_key else SECRET_KEY

    def put(self, key_name, payload):
        self._http_call('uploadfile', payload, dom='%s-%s' % (self._prefix, self._domain), destfile=key_name)
        return self.url(key_name)

    def get(self, key_name):
        return self._http_call('getfilecontent', dom='%s-%s' % (self._prefix, self._domain), filename=key_name)

    def delete(self, key_name):
        self._http_call('delfile', dom='%s-%s' % (self._prefix, self._domain), filename=key_name)

    def url(self, key_name):
        return 'http://%s-%s.stor.sinaapp.com%s' % (self._prefix, self._domain, key_name)

    def _http_call(self, command, payload=None, **kw):
        qs = self._encode_params(act=command, ak=self._access_key, sk=self._secret_key, **kw)
        url = '%s?%s' % (_STOR_BACKEND, qs)
        body, boundary = (None, None) if not payload else self._encode_multipart('srcFile', payload)
        req = urllib2.Request(url, data=body)
        if boundary:
            req.add_header('Content-Type', 'multipart/form-data; boundary=%s' % boundary)
        resp = urllib2.urlopen(req)
        if resp.code != 200:
            raise StandardError('bad response: %s' % resp.code)
        body = resp.read()
        if command =='getfilecontent':
            return body
        rc = json.loads(body)
        errno = rc.get('errno', -1)
        if errno == 0:
            return rc.get('data', True)
        raise StandardError('errno: %s' % errno)

    def _encode_params(self, **kw):
        '''
        Encode parameters like 'a=1&b=2&c=3'.
        '''
        args = []
        for k, v in kw.iteritems():
            qv = v.encode('utf-8') if isinstance(v, unicode) else str(v)
            args.append('%s=%s' % (k, urllib.quote(qv)))
        return '&'.join(args)

    def _encode_multipart(self, name, filecontent, **kw):
        '''
        Build a multipart/form-data body with generated random boundary.

        Return (post_body, boundary)
        '''
        boundary = '----------%s' % uuid.uuid4().hex
        data = []
        for k, v in kw.iteritems():
            data.append('--%s' % boundary)
            data.append('Content-Disposition: form-data; name="%s"\r\n' % k)
            data.append(v.encode('utf-8') if isinstance(v, unicode) else v)
        data.append('--%s' % boundary)
        data.append('Content-Disposition: form-data; name="%s"; filename="hidden"' % name)
        data.append('Content-Type: application/octet-stream')
        data.append('Content-Length: %d\r\n' % len(filecontent))
        data.append(filecontent)
        data.append('--%s--\r\n' % boundary)
        return '\r\n'.join(data), boundary
