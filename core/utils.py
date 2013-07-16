#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
Utils.
'''

import os, re, json, time, logging, calendar, functools
from datetime import datetime

from HTMLParser import HTMLParser
from htmlentitydefs import name2codepoint

import markdown2

from transwarp.web import ctx, UTC
from transwarp import cache

from core.apis import APIValueError
from core import texts

def load_module(module_name):
    '''
    Load a module and return the module reference.
    '''
    pos = module_name.rfind('.')
    if pos==(-1):
        return __import__(module_name, globals(), locals(), [module_name])
    return __import__(module_name, globals(), locals(), [module_name[pos+1:]])

def scan_submodules(module_name):
    '''
    Scan sub modules and import as dict (key=module name, value=module).

    >>> ms = scan_submodules('apps')
    >>> type(ms['article'])
    <type 'module'>
    >>> ms['article'].__name__
    'apps.article'
    >>> type(ms['website'])
    <type 'module'>
    >>> ms['website'].__name__
    'apps.website'
    '''
    web_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mod_path = os.path.join(web_root, *module_name.split('.'))
    if not os.path.isdir(mod_path):
        raise IOError('No such file or directory: %s' % mod_path)
    dirs = os.listdir(mod_path)
    mod_dict = {}
    for name in dirs:
        if name=='__init__.py':
            continue
        p = os.path.join(mod_path, name)
        if os.path.isfile(p) and name.endswith('.py'):
            pyname = name[:-3]
            mod_dict[pyname] = __import__('%s.%s' % (module_name, pyname), globals(), locals(), [pyname])
        if os.path.isdir(p) and os.path.isfile(os.path.join(mod_path, name, '__init__.py')):
            mod_dict[name] = __import__('%s.%s' % (module_name, name), globals(), locals(), [name])
    return mod_dict

def cached_func(key=None, timeout=3600, use_ctx=True):
    '''
    Make function result cached. the cache key is:
      non-arg function: 'WebsiteId--FunctionName'
      args function: 'WebsiteId--FunctionName--Arg1--Arg2--ArgN'

    >>> import time
    >>> @cached_func(timeout=2)
    ... def get_time():
    ...     return int(time.time() * 1000)
    >>> n1 = get_time()
    >>> time.sleep(1.0)
    >>> n2 = get_time()
    >>> n1==n2
    True
    >>> time.sleep(2.0)
    >>> n3 = get_time()
    >>> n1==n3
    False
    '''
    def _decorator(func):
        @functools.wraps(func)
        def _wrapper(*args):
            sk = key or func.__name__
            s = '%s--%s' % (ctx.website.id, sk) if use_ctx else sk
            if args:
                L = [s]
                L.extend(args)
                s = '--'.join(L)
            r = cache.client.get(s)
            if r is None:
                logging.debug('Cache not found for key: %s' % s)
                r = func(*args)
                cache.client.set(s, r, timeout)
            return r
        return _wrapper
    return _decorator

_RE_MD5 = re.compile(r'^[0-9a-f]{32}$')
#_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

def check_md5_passwd(passwd):
    pw = str(passwd)
    if _RE_MD5.match(pw) is None:
        raise APIValueError('passwd', 'Invalid password.')
    return pw

_REG_EMAIL = re.compile(r'^[0-9a-z]([\-\.\w]*[0-9a-z])*\@([0-9a-z][\-\w]*[0-9a-z]\.)+[a-z]{2,9}$')

def check_email(email):
    '''
    Validate email address and return formated email.

    >>> check_email('michael@example.com')
    'michael@example.com'
    >>> check_email(' Michael@example.com ')
    'michael@example.com'
    >>> check_email(' michael@EXAMPLE.COM\\n\\n')
    'michael@example.com'
    >>> check_email(u'michael.liao@EXAMPLE.com.cn')
    'michael.liao@example.com.cn'
    >>> check_email('michael-liao@staff.example-inc.com.hk')
    'michael-liao@staff.example-inc.com.hk'
    >>> check_email('007michael@staff.007.com.cn')
    '007michael@staff.007.com.cn'
    >>> check_email('localhost')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    >>> check_email('@localhost')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    >>> check_email('michael@')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    >>> check_email('michael@localhost')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    >>> check_email('michael@local.host.')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    >>> check_email('-hello@example.local')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    >>> check_email('michael$name@local.local')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    >>> check_email('user.@example.com')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    >>> check_email('user-@example.com')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    >>> check_email('user-0@example-.com')
    Traceback (most recent call last):
      ...
    APIValueError: Invalid email address.
    '''
    e = str(email).strip().lower()
    if _REG_EMAIL.match(e) is None:
        raise APIValueError('email', 'Invalid email address.')
    return e

class _MyHTMLParser(HTMLParser):

    def __init__(self, maxchars=1500):
        HTMLParser.__init__(self)
        self._tag_stack = []
        self._buffer = []
        self._htmllength = maxchars
        self._stop = False
        self._last_is_pre = False
        self._last_is_script = False

    def enough(self):
        return self._stop

    def flush(self):
        ' Return html as unicode '
        L = []
        L.extend(self._buffer)
        for s in reversed(self._tag_stack):
            L.append(u'</%s>' % s)
        return u''.join(L)

    def handle_starttag(self, tag, attrs):
        if self._stop:
            return
        if tag=='script':
            self._last_is_script = True
            return
        s = u'<%s %s>' % (tag, u' '.join([u'%s="%s"' % (k, v) for k, v in attrs])) if attrs else u'<%s>' % tag
        length = len(s) + len(tag) + 3 # add length for </tag>
        if self._htmllength >= length:
            self._tag_stack.append(tag)
            self._last_is_pre = tag=='pre'
            self._last_is_script = False
            self._buffer.append(s)
            self._htmllength = self._htmllength - length
        else:
            self._stop = True

    def handle_endtag(self, tag):
        if self._stop:
            return
        if self._tag_stack and self._tag_stack[-1]==tag:
            self._tag_stack.pop()
            self._buffer.append(u'</%s>' % tag)
            self._last_is_pre = False
            self._last_is_script = False
        else:
            logging.warn('ERROR when parsing tag.')

    def handle_startendtag(self, tag, attrs):
        if self._stop:
            return
        if tag=='script':
            return
        if tag=='br' or tag=='hr' or tag=='img':
            s = u'<%s %s />' % (tag, u' '.join([u'%s="%s"' % (k, v) for k, v in attrs])) if attrs else u'<%s />' % tag
            self._last_is_pre = False
            if self._htmllength >= len(s):
                self._buffer.append(s)
                self._htmllength = self._htmllength - len(s)
            else:
                self._stop = True
        else:
            self.handle_starttag(tag, attrs)
            self.handle_endtag(tag)

    def handle_data(self, data):
        if self._stop or self._last_is_script:
            return
        s = data if self._last_is_pre else data.strip()
        if self._htmllength >= len(s):
            self._buffer.append(s)
            self._htmllength = self._htmllength - len(s)
        else:
            s = s[:self._htmllength]
            self._buffer.append(s)
            self._htmllength = 0
            self._stop = True

    def handle_comment(self, data):
        pass

    def handle_entityref(self, name):
        if self._stop or self._last_is_script:
            return
        s = u'&%s;' % name
        if self._htmllength >= len(s):
            self._buffer.append(s)
            self._htmllength = self._htmllength - len(s)
        else:
            self._stop = True

    def handle_charref(self, name):
        if self._stop or self._last_is_script:
            return
        s = u'&#%s;' % name
        if self._htmllength >= len(s):
            self._buffer.append(s)
            self._htmllength = self._htmllength - len(s)
        else:
            self._stop = True

_RE_END_PARA = re.compile(ur'(\<\/p\>)|(\<\/div\>)|(\<\/pre\>)')

def markdown2html(md):
    if isinstance(md, str):
        md = md.decode('utf-8')
    return unicode(markdown2.markdown(md))

def cached_markdown2html(obj):
    # FIXME: not cached yet...
    key = '%s-%s' % (obj.id, obj.version)
    html = markdown2html(texts.get(obj.id))
    return html

def html2summary(html, maxchars=1800):
    if len(html) <= maxchars:
        return html
    L = _RE_END_PARA.split(html)
    parser = _MyHTMLParser(maxchars)
    for s in L:
        if s:
            parser.feed(s)
            if parser.enough():
                break
    return parser.flush()

def datetime2timestamp(s, tz=None):
    '''
    Parse datetime with timezone, default to local time.

    >>> datetime2timestamp('1970-1-1 8:00:00')
    0
    >>> datetime2timestamp('1970-1-1 8:00:00', '+8:00')
    0
    >>> datetime2timestamp('1970-1-1 7:00:00', '+7:00')
    0
    >>> datetime2timestamp('2013-7-15 12:18:00')
    1373861880
    >>> datetime2timestamp('2013-7-15 12:18:00', '+8:00')
    1373861880
    >>> datetime2timestamp('2013-7-15 11:18:00', '+7:00')
    1373861880
    '''
    # localtime with timezone:
    lt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
    if tz:
        utc = lt.replace(tzinfo=UTC(tz))
        return calendar.timegm(utc.utctimetuple())
    return int(time.mktime(lt.timetuple()))

if __name__=='__main__':
    cache.client = cache.MemcacheClient('localhost')
    ctx.website = Dict(id='123000')
    import doctest
    doctest.testmod()
 