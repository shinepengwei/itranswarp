#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

from gevent.pywsgi import WSGIServer

import os, re, cgi, sys, datetime, base64, functools, threading, logging, urllib, collections

# thread local object for storing request and response.
ctx = threading.local()

sys.path.append('.')

try:
    import json
except ImportError:
    import simplejson as json

def _unicode(s, encoding='utf-8'):
    return s.decode('utf-8')

def _quote(s, encoding='utf-8'):
    '''
    Url quote as str.

    >>> _quote('http://example/test?a=1+')
    'http%3A//example/test%3Fa%3D1%2B'
    >>> _quote(u'hello world!')
    'hello%20world%21'
    '''
    if isinstance(s, unicode):
        s = s.encode(encoding)
    return urllib.quote(s)

def _unquote(s, encoding='utf-8'):
    '''
    Url unquote as unicode.

    >>> _unquote('http%3A//example/test%3Fa%3D1+')
    u'http://example/test?a=1+'
    '''
    return urllib.unquote(s).decode(encoding)

def _unquote_plus(s, encoding='utf-8'):
    '''
    Url unquote_plus as unicode.

    >>> _unquote_plus('http%3A//example/test%3Fa%3D1+')
    u'http://example/test?a=1 '
    '''
    return urllib.unquote_plus(s).decode(encoding)

def _log(s):
    logging.info(s)

def jsonrpc(func):
    @functools.wraps(func)
    def _wrapper(*args, **kw):
        return func(*args, **kw)
    _wrapper.__web_jsonrpc__ = True
    return _wrapper

def _route_decorator_maker(path, allow_get, allow_post):
    '''
    A decorator that has args:

    @route('/')
    def index():
        pass
    '''
    def _decorator(func):
        @functools.wraps(func)
        def _wrapper(*args, **kw):
            return func(*args, **kw)
        _wrapper.__web_route__ = path
        _wrapper.__web_get__ = allow_get
        _wrapper.__web_post__ = allow_post
        return _wrapper
    return _decorator

def _route_decorator(func, allow_get, allow_post):
    '''
    A decorator that does not have args:

    @route
    def foo():
        pass
    '''
    @functools.wraps(func)
    def _wrapper(*args, **kw):
        return func(*args, **kw)
    _wrapper.__web_route__ = '/%s/%s' % (func.__module__.replace('.', '/'), func.__name__)
    _wrapper.__web_get__ = allow_get
    _wrapper.__web_post__ = allow_post
    return _wrapper

def route(func_or_path=None):
    '''
    @route decorator for both GET and POST.
    '''
    if callable(func_or_path):
        return _route_decorator(func_or_path, True, True)
    else:
        return _route_decorator_maker(func_or_path, True, True)

def get(func_or_path=None):
    '''
    @get decorator for GET only.
    '''
    if callable(func_or_path):
        return _route_decorator(func_or_path, True, False)
    else:
        return _route_decorator_maker(func_or_path, True, False)

def post(func_or_path=None):
    '''
    @post decorator for POST only.
    '''
    if callable(func_or_path):
        return _route_decorator(func_or_path, False, True)
    else:
        return _route_decorator_maker(func_or_path, False, True)

class HttpError(StandardError):
    pass

class BadRouteError(HttpError):
    pass

_re_route = re.compile(r'\<(\w*\:?\w*)\>')
_convert = {'int' : int, \
            'long' : long, \
            'float' : float, \
            'bool' : bool, \
            'str' : str, \
            'unicode' : lambda s: s.decode('utf-8'), \
            '' : lambda s: s.decode('utf-8') }

class Route(object):

    def execute(self, **kw):
        return self.func(**kw)

    def _parse_var(self, var):
        if not var:
            raise BadRouteError('var name required')
        var_type = ''
        var_name = var
        pos = var.find(':')
        if pos!=(-1):
            var_type = var[:pos]
            var_name = var[pos+1:]
            if not var_type:
                raise BadRouteError('var type required before :')
            ch = var_type[0]
            if ch>='0' and ch<='9':
                raise BadRouteError('invalid var type')
        if not var_name:
            raise BadRouteError('var name required')
        ch = var_name[0]
        if ch>='0' and ch<='9':
            raise BadRouteError('invalid var name')
        return (var_type, var_name)

    def _parse_static(self, s):
        L = []
        for ch in s:
            if ch>='0' and ch<='9':
                L.append(ch)
            elif ch>='A' and ch<='Z':
                L.append(ch)
            elif ch>='a' and ch<='z':
                L.append(ch)
            else:
                L.append(r'\%s' % ch)
        return ''.join(L)

    def __init__(self, path, func):
        rl = ['^']
        vl = []
        var = False
        for s in _re_route.split(path):
            if var:
                var_type, var_name = self._parse_var(s)
                vl.append(var_type)
                rl.append(r'(?P<%s>.+)' % var_name if var_type=='path' else r'(?P<%s>[^\/]+)' % var_name)
            else:
                rl.append(self._parse_static(s))
            var = not var
        rl.append('$')

        self.str_route = path
        self.re_route = ''.join(rl)
        self.route = re.compile(self.re_route)
        self.types = vl
        self.static = len(vl)==0
        self.func = func

    def __str__(self):
        return '(path=%s, compiled=%s, types=%s)' % (self.str_route, self.re_route, str(self.types))

    __repr__ = __str__

_MIME_MAP = {
    '.html': 'text/html',
    '.htm': 'text/html',
    '.shtml': 'text/html',
    '.shtm': 'text/html',
    '.js': 'application/x-javascript',
    '.css': 'text/css',
    '.gif': 'image/gif',
    '.png': 'image/png',
    '.jpeg': 'image/jpeg',
    '.jpg': 'image/jpeg',
    '.jpe': 'image/jpeg',
    '.ico': 'image/x-icon',
}

def static_file_handler(path):
    # security check:
    if not path.startswith('/'):
        raise StandardError('403')
    fpath = os.path.join(ctx.document_root, path[1:])
    fext = os.path.splitext(fpath)[1]
    ctx.response.content_type = _MIME_MAP.get(fext.lower(), 'application/octet-stream')
    with open(fpath, 'r') as f:
        ctx.response.write(f.read())

def favicon_handler():
    return static_file_handler('/favicon.ico')

class MultipartFile(object):
    '''
    Multipart file storage.
    '''
    def __init__(self, storage):
        self.filename = _unicode(storage.filename)
        self.file = storage.file

class _InputDict(dict):
    '''
    Simple dict but support access as x.y style and list value.

    >>> d1 = _InputDict(x=u'100', y=u'200')
    >>> d1.x
    u'100'
    >>> d1['y']
    u'200'
    >>> d1['empty']
    Traceback (most recent call last):
        ...
    KeyError: 'empty'
    >>> d1.empty
    Traceback (most recent call last):
        ...
    KeyError: 'empty'
    >>> d2 = _InputDict(a=u'1', b=[u'X', u'Y', u'Z'])
    >>> d2.b
    u'X'
    >>> d2.gets('b')
    [u'X', u'Y', u'Z']
    >>> d2.gets('a')
    [u'1']
    >>> d2.gets('empty')
    Traceback (most recent call last):
        ...
    KeyError: 'empty'
    '''
    def __init__(self, **kw):
        d = {}
        ld = {}
        for k, v in kw.iteritems():
            if isinstance(v, list):
                d[k] = v[0]
                ld[k] = v
            else:
                d[k] = v
        super(_InputDict, self).__init__(**d)
        self._multidict = ld

    def __getattr__(self, key):
        return self[key]

    def gets(self, key):
        if key in self._multidict:
            return self._multidict[key][:]
        return [self[key]]

class Request(object):
    '''
    Request object for obtaining all http request information.
    '''

    def __init__(self, environ):
        self._environ = environ
        self._cache = {}

    def _fromcache(self, key, func, *args, **kw):
        r = self._cache.get(key)
        if r is None:
            r = func(*args, **kw)
        self._cache[key] = r
        return r

    def input(self, **kw):
        '''
        Get input from request.

        >>> from StringIO import StringIO
        >>> r = Request({'REQUEST_METHOD':'POST', 'wsgi.input':StringIO('a=1&b=M%20M&c=ABC&c=XYZ&e=')})
        >>> i = r.input(x=2008)
        >>> i.a
        u'1'
        >>> i.b
        u'M M'
        >>> i.c
        u'ABC'
        >>> i.x
        2008
        >>> i.gets('c')
        [u'ABC', u'XYZ']
        >>> i.get('d', u'100')
        u'100'
        >>> i.x
        2008
        '''
        def _get_input():
            def _convert_item(item):
                if isinstance(item, list):
                    return [_unicode(i.value) for i in item]
                if item.file:
                    # convert to file:
                    return MultipartFile(item)
                # single value:
                return _unicode(item.value)
            fs = cgi.FieldStorage(fp=self._environ['wsgi.input'], environ=self._environ, keep_blank_values=True)
            form = {}
            for key in fs:
                item = fs[key]
                form[key] = _convert_item(item)
            for k, v in kw.iteritems():
                if not k in form:
                    form[k] = v
            return _InputDict(**form)
        return self._fromcache('CACHED_INPUT', _get_input)

    def __getitem__(self, key):
        '''
        Get input parameter value. If the specified key has multiple value, the first one is returned.
        If the specified key is not exist, then raise KeyError.

        >>> from StringIO import StringIO
        >>> r = Request({'REQUEST_METHOD':'POST', 'wsgi.input':StringIO('a=1&b=M%20M&c=ABC&c=XYZ&e=')})
        >>> r['a']
        u'1'
        >>> r['c']
        u'ABC'
        >>> r['empty']
        Traceback (most recent call last):
            ...
        KeyError: 'empty'
        '''
        return self.input()[key]

    def get(self, key, default=None):
        '''
        The same as request[key], but return default value if key is not found.

        >>> from StringIO import StringIO
        >>> r = Request({'REQUEST_METHOD':'POST', 'wsgi.input':StringIO('a=1&b=M%20M&c=ABC&c=XYZ&e=')})
        >>> r.get('a')
        u'1'
        >>> r.get('empty')
        >>> r.get('empty', 'DEFAULT')
        'DEFAULT'
        '''
        return self.input().get(key, default)

    def gets(self, key):
        '''
        Get multiple values for specified key.

        >>> from StringIO import StringIO
        >>> r = Request({'REQUEST_METHOD':'POST', 'wsgi.input':StringIO('a=1&b=M%20M&c=ABC&c=XYZ&e=')})
        >>> r.gets('a')
        [u'1']
        >>> r.gets('c')
        [u'ABC', u'XYZ']
        >>> r.gets('empty')
        Traceback (most recent call last):
            ...
        KeyError: 'empty'
        '''
        return self.input().gets(key)

    def __iter__(self):
        '''
        Get all input parameter names.
        >>> from StringIO import StringIO
        >>> r = Request({'REQUEST_METHOD':'POST', 'wsgi.input':StringIO('a=1&b=M%20M&c=ABC&c=XYZ&e=')})
        >>> [key for key in r]
        ['a', 'c', 'b', 'e']
        '''
        return self.input().__iter__()

    @property
    def remote_addr(self):
        '''
        Get remote addr.

        >>> r = Request({'REMOTE_ADDR': '192.168.0.100'})
        >>> r.remote_addr
        '192.168.0.100'
        '''
        return self._environ.get('REMOTE_ADDR', '0.0.0.0')

    @property
    def query_string(self):
        '''
        Get raw query string as str. Return '' if no query string.

        >>> r = Request({'QUERY_STRING': 'a=1&c=2'})
        >>> r.query_string
        'a=1&c=2'
        >>> r = Request({})
        >>> r.query_string
        ''
        '''
        return self._environ.get('QUERY_STRING', '')

    @property
    def environ(self):
        '''
        Get raw environ as dict, both key, value are str.

        >>> r = Request({'REQUEST_METHOD': 'GET', 'wsgi.url_scheme':'http'})
        >>> r.environ.get('REQUEST_METHOD')
        'GET'
        >>> r.environ.get('wsgi.url_scheme')
        'http'
        >>> r.environ.get('SERVER_NAME')
        >>> r.environ.get('SERVER_NAME', 'unamed')
        'unamed'
        '''
        return self._environ

    @property
    def request_method(self):
        '''
        Get request method. The valid returned values are u'GET', u'POST', u'HEAD'.

        >>> r = Request({'REQUEST_METHOD': 'GET'})
        >>> r.request_method
        u'GET'
        >>> r = Request({'REQUEST_METHOD': 'POST'})
        >>> r.request_method
        u'POST'
        '''
        return unicode(self._environ.get('REQUEST_METHOD', 'GET'))

    @property
    def path_info(self):
        '''
        Get request path as unicode.

        >>> r = Request({'PATH_INFO': '/test/a%20b.html'})
        >>> r.path_info
        u'/test/a b.html'
        '''
        return _unquote_plus(self._environ.get('PATH_INFO', ''))

    @property
    def host(self):
        '''
        Get request host as unicode.

        >>> r = Request({'HTTP_HOST': 'localhost:8080'})
        >>> r.host
        u'localhost:8080'
        '''
        return unicode(self._environ.get('HTTP_HOST', ''))

    @property
    def headers(self):
        '''
        Get all HTTP headers with kv both unicode. The header names are 'XXX-XXX' uppercase.

        >>> r = Request({'HTTP_USER_AGENT': 'Mozilla/5.0', 'HTTP_ACCEPT': 'text/html'})
        >>> L = r.headers.items()
        >>> L.sort()
        >>> L
        [(u'ACCEPT', u'text/html'), (u'USER-AGENT', u'Mozilla/5.0')]
        '''
        def _headers():
            hdrs = {}
            for k, v in self._environ.iteritems():
                if k.startswith('HTTP_'):
                    # convert 'HTTP_ACCEPT_ENCODING' to 'ACCEPT-ENCODING'
                    hdrs[unicode(k[5:].replace('_', '-').upper())] = v.decode('utf-8')
            return hdrs
        return self._fromcache('CACHED_HTTP_HEADERS', _headers)

    def header(self, header, default=None):
        '''
        Get header from request as unicode, return None if not exist, or default if specified. 
        The header name is case-insensitive such as 'USER-AGENT' or u'content-type'.

        >>> r = Request({'HTTP_USER_AGENT': 'Mozilla/5.0', 'HTTP_ACCEPT': 'text/html'})
        >>> r.header('User-Agent')
        u'Mozilla/5.0'
        >>> r.header('USER-AGENT')
        u'Mozilla/5.0'
        >>> r.header(u'Accept')
        u'text/html'
        >>> r.header(u'Test')
        >>> r.header(u'Test', u'DEFAULT')
        u'DEFAULT'
        '''
        return self.headers.get(header.upper(), default)

    @property
    def cookies(self):
        '''
        Return all cookies as dict. Both the cookie name and values are unicode.

        >>> r = Request({'HTTP_COOKIE':'A=123; url=http%3A%2F%2Fwww.example.com%2F'})
        >>> r.cookies[u'A']
        u'123'
        >>> r.cookies[u'url']
        u'http://www.example.com/'
        '''
        def _cookies():
            cookies = self._environ.get('HTTP_COOKIE')
            cs = {}
            if cookies:
                for c in cookies.split(';'):
                    pos = c.find('=')
                    if pos>0:
                        cs[unicode(c[:pos].strip())] = _unquote(c[pos+1:])
            return cs
        return self._fromcache('CACHED_COOKIES', _cookies)

    def cookie(self, name, default=None):
        '''
        Return specified cookie value as unicode. Default to None if cookie not exists.

        >>> r = Request({'HTTP_COOKIE':'A=123; url=http%3A%2F%2Fwww.example.com%2F'})
        >>> r.cookie(u'A')
        u'123'
        >>> r.cookie(u'url')
        u'http://www.example.com/'
        >>> r.cookie(u'test')
        >>> r.cookie(u'test', u'DEFAULT')
        u'DEFAULT'
        '''
        return self.cookies.get(name, default)

# all known response statues:
_RESPONSE_STATUSES = {
    # Informational
    100: 'Continue',
    101: 'Switching Protocols',
    102: 'Processing',

    # Successful
    200: 'OK',
    201: 'Created',
    202: 'Accepted',
    203: 'Non-Authoritative Information',
    204: 'No Content',
    205: 'Reset Content',
    206: 'Partial Content',
    207: 'Multi Status',
    226: 'IM Used',

    # Redirection
    300: 'Multiple Choices',
    301: 'Moved Permanently',
    302: 'Found',
    303: 'See Other',
    304: 'Not Modified',
    305: 'Use Proxy',
    307: 'Temporary Redirect',

    # Client Error
    400: 'Bad Request',
    401: 'Unauthorized',
    402: 'Payment Required',
    403: 'Forbidden',
    404: 'Not Found',
    405: 'Method Not Allowed',
    406: 'Not Acceptable',
    407: 'Proxy Authentication Required',
    408: 'Request Timeout',
    409: 'Conflict',
    410: 'Gone',
    411: 'Length Required',
    412: 'Precondition Failed',
    413: 'Request Entity Too Large',
    414: 'Request URI Too Long',
    415: 'Unsupported Media Type',
    416: 'Requested Range Not Satisfiable',
    417: 'Expectation Failed',
    418: "I'm a teapot",
    422: 'Unprocessable Entity',
    423: 'Locked',
    424: 'Failed Dependency',
    426: 'Upgrade Required',

    # Server Error
    500: 'Internal Server Error',
    501: 'Not Implemented',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Timeout',
    505: 'HTTP Version Not Supported',
    507: 'Insufficient Storage',
    510: 'Not Extended',
}

_RE_RESPONSE_STATUS = re.compile(r'^\d\d\d(\ [\w\ ]+)?$')

_RESPONSE_HEADERS = (
    'Accept-Ranges',
    'Age',
    'Allow',
    'Cache-Control',
    'Connection',
    'Content-Encoding',
    'Content-Language',
    'Content-Length',
    'Content-Location',
    'Content-MD5',
    'Content-Disposition',
    'Content-Range',
    'Content-Type',
    'Date',
    'ETag',
    'Expires',
    'Last-Modified',
    'Link',
    'Location',
    'P3P',
    'Pragma',
    'Proxy-Authenticate',
    'Refresh',
    'Retry-After',
    'Server',
    'Set-Cookie',
    'Strict-Transport-Security',
    'Trailer',
    'Transfer-Encoding',
    'Vary',
    'Via',
    'Warning',
    'WWW-Authenticate',
    'X-Frame-Options',
    'X-XSS-Protection',
    'X-Content-Type-Options',
    'X-Forwarded-Proto',
    'X-Powered-By',
    'X-UA-Compatible',
)

_RESPONSE_HEADER_DICT = {}

for hdr in _RESPONSE_HEADERS:
    _RESPONSE_HEADER_DICT[hdr.upper()] = hdr

_TIMEDELTA_ZERO = datetime.timedelta(0)

class UTC(datetime.tzinfo):
    '''
    A UTC tzinfo object.

    >>> tz = UTC()
    >>> tz.tzname(None)
    'UTC+0000'
    >>> tz = UTC(8)
    >>> tz.tzname(None)
    'UTC+0800'
    >>> tz = UTC(7, 30)
    >>> tz.tzname(None)
    'UTC+0730'
    >>> tz = UTC(-5, 30)
    >>> tz.tzname(None)
    'UTC-0530'
    '''

    def __init__(self, offset_hours=0, offset_minutes=0):
        self._utcoffset = datetime.timedelta(hours=offset_hours, minutes=offset_minutes)
        self._tzname = 'UTC%+03d%02d' % (offset_hours, offset_minutes)

    def utcoffset(self, dt):
        return self._utcoffset

    def dst(self, dt):
        return _TIMEDELTA_ZERO

    def tzname(self, dt):
        return self._tzname

_UTC_0 = UTC(0)

class Response(object):

    def __init__(self):
        self._status = '200 OK'
        self._headers = {'CONTENT-TYPE': 'text/html; charset=utf-8'}
        self._output = []
        self._cookies = {}

    @property
    def headers(self):
        '''
        Return response headers as [(key1, value1), (key2, value2)...].

        >>> r = Response()
        >>> r.headers
        [('Content-Type', 'text/html; charset=utf-8')]
        '''
        return [(_RESPONSE_HEADER_DICT.get(k, k), v) for k, v in self._headers.iteritems()]

    def header(self, name):
        '''
        Get header by name.

        >>> r = Response()
        >>> r.header('content-type')
        'text/html; charset=utf-8'
        >>> r.header('CONTENT-type')
        'text/html; charset=utf-8'
        >>> r.header('X-Powered-By')
        '''
        key = name.upper()
        if not key in _RESPONSE_HEADER_DICT:
            key = name
        return self._headers.get(key)

    def unset_header(self, name):
        '''
        Unset header by name and value.

        >>> r = Response()
        >>> r.header('content-type')
        'text/html; charset=utf-8'
        >>> r.unset_header('CONTENT-type')
        >>> r.header('content-type')
        >>> r.unset_header('content-TYPE')
        '''
        key = name.upper()
        if not key in _RESPONSE_HEADER_DICT:
            key = name
        if key in self._headers:
            del self._headers[key]

    def set_header(self, name, value):
        '''
        Set header by name and value.

        >>> r = Response()
        >>> r.header('content-type')
        'text/html; charset=utf-8'
        >>> r.set_header('CONTENT-type', 'image/png')
        >>> r.header('content-TYPE')
        'image/png'
        '''
        key = name.upper()
        if not key in _RESPONSE_HEADER_DICT:
            key = name
        self._headers[key] = value

    @property
    def content_type(self):
        '''
        Get content type from response. This is a shortcut for header('Content-Type').

        >>> r = Response()
        >>> r.content_type
        'text/html; charset=utf-8'
        >>> r.content_type = 'application/json'
        >>> r.content_type
        'application/json'
        '''
        return self.header('CONTENT-TYPE')

    @content_type.setter
    def content_type(self, value):
        '''
        Set content type for response. This is a shortcut for set_header('Content-Type', value).
        '''
        self.set_header('CONTENT-TYPE', value)

    def set_cookie(self, name, value, max_age=None, expires=None, path='/', domain=None, secure=False, http_only=False):
        '''
        Set a cookie.

        Args:
          name: the cookie name.
          value: the cookie value.
          max_age: optional, seconds of cookie's max age.
          expires: optional, unix timestamp, datetime or date object that indicate an absolute time of the 
                   expiration time of cookie. Note that if expires specified, the max_age will be ignored.
          path: the cookie path, default to '/'.
          domain: the cookie domain, default to None.
          secure: if the cookie secure, default to False.
          http_only: if the cookie is for http only, default to False.

        >>> r = Response()
        >>> r.set_cookie('company', 'Abc, Inc.', max_age=3600)
        >>> r._cookies
        {'company': 'company=Abc%2C%20Inc.; Max-Age=3600; Path=/'}
        >>> r.set_cookie('company', r'Example="Limited"', expires=1342274794.123, path='/sub/')
        >>> r._cookies
        {'company': 'company=Example%3D%22Limited%22; Expires=Sat, 14 Jul 12 14:06:34 GMT; Path=/sub/'}
        >>> dt = datetime.datetime(2012, 7, 14, 22, 6, 34, tzinfo=UTC(8))
        >>> r.set_cookie('company', 'Expires', expires=dt)
        >>> r._cookies
        {'company': 'company=Expires; Expires=Sat, 14 Jul 12 14:06:34 GMT; Path=/'}
        '''
        L = ['%s=%s' % (_quote(name), _quote(value))]
        if expires is not None:
            if isinstance(expires, (float, int, long)):
                L.append('Expires=%s' % datetime.datetime.fromtimestamp(expires, _UTC_0).strftime('%a, %d %b %y %H:%M:%S GMT'))
            if isinstance(expires, (datetime.date, datetime.datetime)):
                L.append('Expires=%s' % expires.astimezone(_UTC_0).strftime('%a, %d %b %y %H:%M:%S GMT'))
        elif isinstance(max_age, (int, long)):
            L.append('Max-Age=%d' % max_age)
        L.append('Path=%s' % path)
        if domain:
            L.append('Domain=%s' % domain)
        if secure:
            L.append('Secure')
        if http_only:
            L.append('HttpOnly')
        self._cookies[name] = '; '.join(L)

    def unset_cookie(self, name):
        '''
        Unset a cookie.

        >>> r = Response()
        >>> r.set_cookie('company', 'Abc, Inc.', max_age=3600)
        >>> r._cookies
        {'company': 'company=Abc%2C%20Inc.; Max-Age=3600; Path=/'}
        >>> r.unset_cookie('company')
        >>> r._cookies
        {}
        '''
        if name in self._cookies:
            del self._cookies[name]

    @property
    def status_code(self):
        '''
        Get response status code as int.

        >>> r = Response()
        >>> r.status_code
        200
        >>> r.status = 404
        >>> r.status_code
        404
        >>> r.status = '500 Internal Error'
        >>> r.status_code
        500
        '''
        return int(self._status[:3])

    @property
    def status(self):
        '''
        Get response status. Default to '200 OK'.

        >>> r = Response()
        >>> r.status
        '200 OK'
        >>> r.status = 404
        >>> r.status
        '404 Not Found'
        >>> r.status = '500 SERVER ERR'
        >>> r.status
        '500 SERVER ERR'
        '''
        return self._status

    @status.setter
    def status(self, value):
        '''
        Set response status as int or str.

        >>> r = Response()
        >>> r.status = 404
        >>> r.status
        '404 Not Found'
        >>> r.status = '500 ERR'
        >>> r.status
        '500 ERR'
        >>> r.status = u'403 Denied'
        >>> r.status
        '403 Denied'
        >>> r.status = 99
        Traceback (most recent call last):
          ...
        ValueError: Bad response code: 99
        >>> r.status = 'ok'
        Traceback (most recent call last):
          ...
        ValueError: Bad response code: ok
        >>> r.status = [1, 2, 3]
        Traceback (most recent call last):
          ...
        TypeError: Bad type of response code.
        '''
        if isinstance(value, (int, long)):
            if value>=100 and value<=999:
                st = _RESPONSE_STATUSES.get(value, '')
                if st:
                    self._status = '%d %s' % (value, st)
                else:
                    self._status = str(value)
            else:
                raise ValueError('Bad response code: %d' % value)
        elif isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, str):
            if _RE_RESPONSE_STATUS.match(value):
                self._status = value
            else:
                raise ValueError('Bad response code: %s' % value)
        else:
            raise TypeError('Bad type of response code.')

    @property
    def body(self):
        '''
        Get response body as list.
        '''
        return self._output

    def write(self, value):
        self._output.append(value)

    def reset(self):
        self._output[:] = []

class Template(object):

    def __init__(self, template_name=None, **kw):
        self.template_name = template_name
        self.model = kw

def _init_mako(templ_dir, **kw):
    '''
    Render using mako.

    >>> tmpl_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'test')
    >>> func = _init_mako(tmpl_path)
    >>> r = func('mako-test.html', names=['Michael', 'Tracy'])
    >>> r.replace('\\n', '')
    '<p>Hello, Michael.</p><p>Hello, Tracy.</p>'
    '''
    from mako.lookup import TemplateLookup
    lookup = TemplateLookup(directories=[templ_dir], output_encoding='utf-8', **kw)
    def _render(name, **model):
        return lookup.get_template(name).render(**model)
    return _render

def _init_jinja2(templ_dir, **kw):
    '''
    Render using jinja2.

    >>> tmpl_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'test')
    >>> func = _init_jinja2(tmpl_path)
    >>> r = func('jinja2-test.html', names=['Michael', 'Tracy'])
    >>> r.replace('\\n', '')
    '<p>Hello, Michael.</p><p>Hello, Tracy.</p>'
    '''
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(templ_dir, **kw))
    def _render(name, **model):
        return env.get_template(name).render(**model).encode('utf-8')
    return _render

def _init_cheetah(templ_dir, **kw):
    '''
    Render using cheetah.

    >>> tmpl_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'test')
    >>> func = _init_cheetah(tmpl_path)
    >>> r = func('cheetah-test.html', names=['Michael', 'Tracy'])
    >>> r.replace('\\n', '')
    '<p>Hello, Michael.</p><p>Hello, Tracy.</p>'
    '''
    from Cheetah.Template import Template
    def _render(name, **model):
        return str(Template(file=os.path.join(templ_dir, name), searchList=[model]))
    return _render

def _install_template_engine(name, templ_dir, **kw):
    name = str(name).lower()
    if name=='mako':
        return _init_mako(templ_dir, **kw)
    if name=='jinja2':
        return _init_jinjia2(templ_dir, **kw)
    if name=='cheetah':
        return _init_cheetah(templ_dir, **kw)
    raise StandardError('no such template engine: %s' % name)

class WSGIApplication(object):

    def __init__(self, modules, document_root=None, encoding='utf-8', template_engine=None):
        static_routes = {}
        re_routes = []
        for mod in modules:
            last = mod.rfind('.')
            name = mod if last==(-1) else mod[:last]
            spam = __import__(mod, globals(), locals(), [name])
            for p in dir(spam):
                f = getattr(spam, p)
                if callable(f):
                    print '=== %s ===' % f.__name__
                    print getattr(f, '__web_jsonrpc__', None)
                    route = getattr(f, '__web_route__', None)
                    if route:
                        r = Route(route, f)
                        if r.static:
                            static_routes[r.str_route] = r
                            _log('found static route: %s' % route)
                        else:
                            re_routes.append(r)
                            _log('found regex route: %s' % route)
        # append '^/static/.*$' to serv static files:
        re_routes.append(Route('/static/<path:path>', static_file_handler))
        # append '^/favicon.ico$' to serv fav icon:
        re_routes.append(Route('/favicon.ico', favicon_handler))

        self.static_routes = static_routes
        self.re_routes = re_routes

        if document_root is None:
            # suppose document_root is ../web.py:
            document_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.document_root = document_root

        if isinstance(template_engine, basestring):
            self.template_render = _install_template_engine(template_engine)
        elif callable(template_engine):
            self.template_render = template_engine

    def __call__(self, environ, start_response):
        path_info = environ['PATH_INFO']
        kw = None
        r = self.static_routes.get(path_info, None)
        if r:
            _log('matched static route: %s' % path_info)
        else:
            for rt in self.re_routes:
                m = rt.route.match(path_info)
                if m:
                    r = rt
                    kw = m.groupdict()
                    _log('matched regex route: %s' % path_info)
                    break
        if not r:
            _log('no route matched: %s' % path_info)
            raise HttpError('404')

        global ctx
        ctx.document_root = self.document_root
        ctx.request = Request(environ)
        ctx.response = Response()
        ret = r.execute() if kw is None else r.execute(**kw)
        # TODO:
        # if ret instance of Template...
        if isinstance(ret, str):
            ctx.response.write(ret)
        elif isinstance(ret, unicode):
            ctx.response.write(ret.encode('utf-8'))
        start_response(ctx.response.status, ctx.response.headers)
        return ctx.response.body
 
    def run(self):
        server = WSGIServer(('0.0.0.0', 8080), self)
        server.serve_forever()

if __name__=='__main__':
    import doctest
    doctest.testmod()
 