#!/usr/bin/env python
# -*-coding: utf8 -*-

'''
Amazon S3 API by:

Michael Liao (askxuefeng@gmail.com)
'''

import re, os, sha, time, hmac, base64, hashlib, urllib, urllib2, mimetypes, logging

from datetime import datetime, timedelta, tzinfo
from StringIO import StringIO

class Plugin(object):

    name = 'Amazon S3'

    description = 'Amazon Simple Storage Service'

    def __init__(self, **kw):
        bucket = kw.get('bucket')
        access_key_id = kw.get('access_key_id')
        access_key_secret = kw.get('access_key_secret')
        if not bucket:
            raise ValueError('missing param: bucket')
        if not access_key_id:
            raise ValueError('missing param: access_key_id')
        if not access_key_secret:
            raise ValueError('missing param: access_key_secret')
        cname = kw.get('cname')
        self._client = Client(str(access_key_id), str(access_key_secret), str(bucket), bool(cname))

    @classmethod
    def get_inputs(cls):
        return (dict(key='bucket', name='Bucket', description='Bucket'),
            dict(key='access_key_id', name='Access Key ID', description='Access key id'),
            dict(key='access_key_secret', name='Access Key Secret', description='Access key secret'),
            dict(key='cname', name='Use CNAME', description='Use CNAME', input='checkbox'))

    @classmethod
    def validate(cls, **kw):
        pass

    def delete(self, ref):
        bucket, obj = self._client.names_from_url(ref)
        if obj:
            self._client.delete_object(obj, bucket=bucket)
        else:
            raise ValueError('Could not delete file which does not uploaded to Aliyun OSS.')

    def upload(self, fpath, fp):
        dt = datetime.now()
        logging.info('saving uploaded file to s3 %s...' % fpath)
        url = self._client.put_object(fpath, fp)
        return url, url

_URL = 'http://%s.s3.amazonaws.com/%s'

_RE_URL1 = re.compile(r'^http\:\/\/([\.\w]+)\.s3[\-\w]*\.amazonaws\.com\/(.+)$')
_RE_URL2 = re.compile(r'^http\:\/\/s3[\-\w]*\.amazonaws\.com\/([\.\w]+)\/(.+)$')
_RE_URL3 = re.compile(r'^http\:\/\/([\.\-\w]+)\/(.+)$')

class Client(object):

    def __init__(self, access_key_id, access_key_secret, bucket=None, cname=False):
        '''
        Init an S3 client with:

        Args:
            access_key_id: the access key id.
            access_key_secret: the access key secret.
            bucket: (optional) the default bucket name, or None.
            cname: (optional) specify weather use cname or not when generate url after PUT.
        '''
        self._access_key_id = access_key_id
        self._access_key_secret = access_key_secret
        self._bucket = bucket
        self._cname = cname

    def _check_key(self, key):
        if not key:
            raise IOError('Key cannot be empty.')
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if key.startswith('/') or key.startswith('\\'):
            raise IOError('Key cannot start with \"/\" or \"\\\"')
        return key

    def _check_bucket(self, bucket):
        if bucket:
            return bucket
        if self._bucket:
            return self._bucket
        raise IOError('Bucket is required but no default bucket specified.')

    def names_from_url(self, url):
        '''
        get bucket and object name from url.

        >>> c = Client('key', 'secret')
        >>> c.names_from_url('http://sample.s3.amazonaws.com/test/hello.html')
        ('sample', 'test/hello.html')
        >>> c.names_from_url('http://www.sample.com.s3.amazonaws.com/test/hello.html')
        ('www.sample.com', 'test/hello.html')
        >>> c.names_from_url('http://sample.s3-ap-northeast-1.amazonaws.com/test/hello.html')
        ('sample', 'test/hello.html')
        >>> c.names_from_url('http://s3.amazonaws.com/sample/test/hello.html')
        ('sample', 'test/hello.html')
        >>> c.names_from_url('http://s3-ap-northeast-1.amazonaws.com/sample/test/hello.html')
        ('sample', 'test/hello.html')
        >>> c.names_from_url('http://www.amazon.com/hello.html')
        ('www.amazon.com', 'hello.html')
        >>> c.names_from_url('http://www.amazon.com/')
        (None, None)
        '''
        m = _RE_URL1.match(url)
        if m:
            return m.groups()
        m = _RE_URL2.match(url)
        if m:
            return m.groups()
        m = _RE_URL3.match(url)
        if m:
            return m.groups()
        return None, None

    def list_buckets(self):
        '''
        Get all buckets.
        '''
        r = _api(self._access_key_id, self._access_key_secret, 'GET', '', '')
        L = []
        pos = 0
        while True:
            s, pos = _mid(r, '<Name>', '</Name>', pos)
            if s:
                L.append(s)
            else:
                break
        return L

    def get_object(self, key, bucket=None):
        '''
        Get file content.

        Args:
            key: object key.
            bucket: (optional) using default bucket name or override.
        Returns:
            str as file content.
        '''
        return _api(self._access_key_id, self._access_key_secret, 'GET', self._check_bucket(bucket), self._check_key(key))

    def put_object(self, key, payload, bucket=None):
        '''
        Upload file.

        Args:
            key: Object key.
            payload: str or file-like object as file content.
            bucket: (optional) using default bucket name or override.
        Returns:
            the url of uploaded file.
        '''
        r = _api(self._access_key_id, self._access_key_secret, 'PUT', self._check_bucket(bucket), self._check_key(key), payload)
        if self._cname:
            return 'http://%s/%s' % r
        return 'http://%s.s3.amazonaws.com/%s' % r

    def delete_object(self, key, bucket=None):
        '''
        Delete file.

        Args:
            key: object key.
            bucket: (optional) using default bucket name or override.
        '''
        _api(self._access_key_id, self._access_key_secret, 'DELETE', self._check_bucket(bucket), self._check_key(key))

_TIMEDELTA_ZERO = timedelta(0)

class GMT(tzinfo):

    def utcoffset(self, dt):
        return _TIMEDELTA_ZERO

    def dst(self, dt):
        return _TIMEDELTA_ZERO

    def tzname(self, dt):
        return 'GMT'

_GMT = GMT()

def _current_datetime():
    return datetime.fromtimestamp(time.time(), _GMT).strftime('%a, %0d %b %Y %H:%M:%S +0000')

_APPLICATION_OCTET_STREAM = 'application/octet-stream'

def _guess_content_type(obj):
    n = obj.rfind('.')
    if n==(-1):
        return _APPLICATION_OCTET_STREAM
    return mimetypes.types_map.get(obj[n:], _APPLICATION_OCTET_STREAM)

def _signature(access_key_id, access_key_secret, bucket, key, verb, content_md5, content_type, date, headers=None):
    '''
    Make signature for args.

    >>> access_key_id = 'AKIAIOSFODNN7EXAMPLE'
    >>> access_key_secret = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
    >>> _signature(access_key_id, access_key_secret, 'johnsmith', 'photos/puppy.jpg', 'PUT', '', 'image/jpeg', 'Tue, 27 Mar 2007 21:15:45 +0000')
    'MyyxeRY7whkBe+bq8fHCL/2kKUg='
    >>> _signature(access_key_id, access_key_secret, 'dictionary', 'fran%C3%A7ais/pr%c3%a9f%c3%a8re', 'GET', '', '', 'Wed, 28 Mar 2007 01:49:49 +0000')
    'DNEZGsoieTZ92F3bUfSPQcbGmlM='
    '''
    L = [verb, content_md5, content_type, date]
    if headers:
        L.extend(headers)
    L.append('/%s/%s' % (bucket, key) if bucket else '/%s' % key)
    str_to_sign = '\n'.join(L)
    h = hmac.new(access_key_secret, str_to_sign, sha)
    return base64.b64encode(h.digest())

_METHOD_MAP = dict(
        GET=lambda: 'GET',
        DELETE=lambda: 'DELETE',
        PUT=lambda: 'PUT')

def _mid(s, start_tag, end_tag, from_pos=0):
    '''
    Search string s to find substring starts with start_tag and ends with end_tag.

    Returns:
        The substring and next search position.
    '''
    n1 = s.find(start_tag, from_pos)
    if n1==(-1):
        return '', -1
    n2 = s.find(end_tag, n1 + len(start_tag))
    if n2==(-1):
        return '', -1
    return s[n1 + len(start_tag) : n2], n2 + len(end_tag)

def _httprequest(host, verb, path, payload, headers):
    data = None
    if payload:
        data = payload if isinstance(payload, str) else payload.read()
    url = 'http://%s%s' % (host, path)
    opener = urllib2.build_opener(urllib2.HTTPHandler)
    request = urllib2.Request(url, data=data)
    request.get_method = _METHOD_MAP[verb]
    if data:
        request.add_header('Content-Length', len(data))
    for k, v in headers.iteritems():
        request.add_header(k, v)
    try:
        response = opener.open(request)
        if verb=='GET':
            return response.read()
    except urllib2.URLError, e:
        logging.info('URLError: %s' % url)
        logging.info('Reason: %s' % e.reason)
        raise
    except urllib2.HTTPError, e:
        xml = e.read()
        logging.info('HTTPError: %s' % xml)
        code = _mid(xml, '<Code>', '</Code>')[0]
        if code=='TemporaryRedirect':
            endpoint = _mid(xml, '<Endpoint>', '</Endpoint>')[0]
            # resend http request:
            logging.warn('resend http request to endpoint: %s' % endpoint)
            return _httprequest(endpoint, verb, path, payload, headers)
        msg = _mid(xml, '<Message>', '</Message>')[0]
        raise IOError('Code: %s, Message: %s' % (code, msg))

def _api(access_key_id, access_key_secret, verb, bucket, key, payload=None, headers=None):
    host = '%s.s3.amazonaws.com' % bucket if bucket else 's3.amazonaws.com'
    path = '/%s' % key
    date = _current_datetime()
    content_md5 = ''
    content_type = '' if verb=='GET' else _guess_content_type(key)
    authorization = _signature(access_key_id, access_key_secret, bucket, key, verb, content_md5, content_type, date)
    if headers is None:
        headers = dict()
    if content_type:
        headers['Content-Type'] = content_type
    headers['Date'] = date
    headers['Authorization'] = 'AWS %s:%s' % (access_key_id, authorization)
    r = _httprequest(host, verb, path, payload, headers)
    if verb=='PUT':
        return (bucket, key)
    return r

if __name__ == '__main__':
    import doctest
    doctest.testmod()
