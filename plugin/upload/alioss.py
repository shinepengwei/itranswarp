#!/usr/bin/env python
# -*-coding: utf8 -*-

'''
Aliyun OSS Storage Uploader

Michael Liao (askxuefeng@gmail.com)
'''

__author__ = 'Michael Liao'

import re, os, sha, time, uuid, hmac, base64, hashlib, urllib, urllib2, mimetypes, logging

from datetime import datetime, timedelta, tzinfo
from StringIO import StringIO

class Provider(object):

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
        self._client = Client(str(access_key_id), str(access_key_secret), str(bucket))

    @staticmethod
    def get_name():
        return 'Aliyun OSS Uploader'

    @staticmethod
    def get_description():
        return 'Upload files to Aliyun OSS'

    @staticmethod
    def get_settings():
        return (dict(key='bucket', name='Bucket', description='Bucket'),
                dict(key='access_key_id', name='Access Key ID', description='Access key id'),
                dict(key='access_key_secret', name='Access Key Secret', description='Access key secret'))

    def delete(self, ref):
        if ref.startswith('alioss:'):
            ref = ref[7:]
        bucket, obj = self._client.names_from_url(ref)
        if obj:
            self._client.delete_object(obj, bucket=bucket)
        else:
            raise ValueError('Could not delete file which does not uploaded to Aliyun OSS.')

    def upload(self, fname, ftype, fcontent, fthumbnail):
        dt = datetime.now()
        dirs = (str(dt.year), str(dt.month), str(dt.day))
        ext = str(os.path.splitext(fname)[1]).lower()
        name = uuid.uuid4().hex
        iname = '%s%s' % (name, ext)
        pname = '%s.thumbnail.jpg' % (name)
        path = os.path.join(*dirs)
        fpath = os.path.join(path, iname)
        ppath = os.path.join(path, pname)
        logging.info('saving uploaded file to oss %s...' % fpath)
        url = self._client.put_object(fpath, fcontent)
        r = dict(url=url, ref='alioss:%s' % url)
        if fthumbnail:
            logging.info('saving thumbnail file to oss %s...' % ppath)
            r['thumbnail'] = self._client.put_object(ppath, fthumbnail)
        return r

_HOST = 'storage.aliyun.com'
_URL = 'http://%s.oss.aliyuncs.com/%s'

_RE_URL1 = re.compile(r'^http\:\/\/(\w+)\.oss\.aliyuncs\.com\/+(.+)$')
_RE_URL2 = re.compile(r'^http\:\/\/storage\.aliyun\.com/(\w+)\/+(.+)$')

class StorageError(StandardError):
    pass

class Client(object):

    def __init__(self, access_key_id, access_key_secret, bucket=None):
        self._access_key_id = access_key_id
        self._access_key_secret = access_key_secret
        self._bucket = bucket

    def _check_obj(self, obj):
        if not obj:
            raise StorageError('ObjectName', 'Object cannot be empty.')
        if isinstance(obj, unicode):
            obj = obj.encode('utf-8')
        if obj.startswith('/') or obj.startswith('\\'):
            raise StorageError('ObjectName', 'Object name cannot start with \"/\" or \"\\\"')
        return obj

    def _check_bucket(self, bucket):
        if bucket:
            return bucket
        if self._bucket:
            return self._bucket
        raise StorageError('BucketName', 'Bucket is required but no default bucket specified.')

    def names_from_url(self, url):
        '''
        get bucket and object name from url.

        >>> c = Client('key', 'secret')
        >>> c.names_from_url('http://sample.oss.aliyuncs.com/test/hello.html')
        ('sample', 'test/hello.html')
        >>> c.names_from_url('http://storage.aliyun.com/sample/test/hello.html')
        ('sample', 'test/hello.html')
        >>> c.names_from_url('http://www.aliyun.com/')
        (None, None)
        '''
        m = _RE_URL1.match(url)
        if m:
            return m.groups()
        m = _RE_URL2.match(url)
        if m:
            return m.groups()
        return None, None

    def get_object(self, obj, bucket=None):
        '''
        Get file content.

        Returns:
            str as file content.
        '''
        return _api(self._access_key_id, self._access_key_secret, 'GET', self._check_bucket(bucket), self._check_obj(obj))

    def put_object(self, obj, payload, bucket=None):
        '''
        Upload file.

        Args:
            obj: Object name.
            payload: str or file-like object as file content.
        Returns:
            the url of uploaded file.
        '''
        return _api(self._access_key_id, self._access_key_secret, 'PUT', self._check_bucket(bucket), self._check_obj(obj), payload)

    def delete_object(self, obj, bucket=None):
        '''
        Delete file.
        '''
        _api(self._access_key_id, self._access_key_secret, 'DELETE', self._check_bucket(bucket), self._check_obj(obj))

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
    return datetime.fromtimestamp(time.time(), _GMT).strftime('%a, %0d %b %Y %H:%M:%S GMT')

_APPLICATION_OCTET_STREAM = 'application/octet-stream'

def _guess_content_type(obj):
    n = obj.rfind('.')
    if n==(-1):
        return _APPLICATION_OCTET_STREAM
    return mimetypes.types_map.get(obj[n:], _APPLICATION_OCTET_STREAM)

def _signature(access_key_id, access_key_secret, bucket, obj, verb, content_md5, content_type, date, headers=None):
    '''
    Make signature for args.
    '''
    L = [verb, content_md5, content_type, date]
    if headers:
        L.extend(headers)
    L.append('/%s/%s' % (bucket, obj))
    h = hmac.new(access_key_secret, '\n'.join(L), sha)
    return base64.b64encode(h.digest())

_METHOD_MAP = dict(
        GET=lambda: 'GET',
        DELETE=lambda: 'DELETE',
        PUT=lambda: 'PUT')

def _mid(s, start, end):
    n1 = s.find(start)
    if n1==(-1):
        return ''
    n2 = s.find(end, n1 + len(start))
    if n2==(-1):
        return ''
    return s[n1 + len(start) : n2]

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
        code = _mid(xml, '<Code>', '</Code>')
        msg = _mid(xml, '<Message>', '</Message>')
        raise StorageError(code, msg)

def _api(access_key_id, access_key_secret, verb, bucket, obj, payload=None, headers=None):
    host = '%s.oss.aliyuncs.com' % bucket
    path = '/%s' % obj
    date = _current_datetime()
    content_md5 = ''
    content_type = _guess_content_type(obj)
    authorization = _signature(access_key_id, access_key_secret, bucket, obj, verb, content_md5, content_type, date)
    if headers is None:
        headers = dict()
    headers['Content-Type'] = content_type
    headers['Date'] = date
    headers['Authorization'] = 'OSS %s:%s' % (access_key_id, authorization)
    r = _httprequest(host, verb, path, payload, headers)
    if verb=='PUT':
        return _URL % (bucket, obj)
    return r
