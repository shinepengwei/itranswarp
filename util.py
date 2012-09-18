#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import re, time, base64, hashlib, logging, functools

from itranswarp.web import ctx, get, post, route, jsonrpc, Dict, Template, seeother, notfound, badrequest
from itranswarp import db

import const

_REG_EMAIL = re.compile(r'^[0-9a-z]([\-\.\w]*[0-9a-z])*\@([0-9a-z][\-\w]*[0-9a-z]\.)+[a-z]{2,9}$')

_SESSION_COOKIE_NAME = '_auth_session_cookie'
_SESSION_COOKIE_KEY = '_SECURE_keyabc123xyz_BIND_'
_SESSION_COOKIE_EXPIRES = 31536000.0

def make_session_cookie(provider, uid, passwd, expires):
    '''
    Generate a secure client session cookie by constructing:
    base64(uid, expires, md5(auth_provider, uid, expires, passwd, salt)).
    Args:
      auth_provider: auth provider
      uid: user id.
      expires: unix-timestamp as float.
      passwd: user's password.
      salt: a secure string.
    Returns:
      base64 encoded cookie value as str.
    '''
    pvd = str(provider)
    sid = str(uid)
    exp = str(int(expires)) if expires else str(int(time.time() + 86400))
    secure = ':'.join([pvd, sid, exp, str(passwd), _SESSION_COOKIE_KEY])
    cvalue = ':'.join([pvd, sid, exp, hashlib.md5(secure).hexdigest()])
    logging.info('make cookie: %s' % cvalue)
    cookie = base64.urlsafe_b64encode(cvalue).replace('=', '_')
    ctx.response.set_cookie(_SESSION_COOKIE_NAME, cookie, expires=expires)

def extract_session_cookie():
    '''
    Decode a secure client session cookie and return uid, or None if invalid cookie. 
    Args:
      s: base64 encoded cookie value.
      get_passwd_by_uid: function that return password by uid.
      salt: a secure string.
    Returns:
      provider, user id as str, or None if cookie is invalid.
    '''
    def _get_passwd_by_uid(provider, userid):
        if provider==const.LOCAL_SIGNIN_PROVIDER:
            return db.select_one('select passwd from users where id=?', userid).passwd
        return db.select_one('select auth_token from auth_users where user_id=? and provider=?', userid, provider).auth_token
    s = ctx.request.cookie(_SESSION_COOKIE_NAME, '')
    logging.info('read cookie: %s' % s)
    if not s:
        return None
    if isinstance(s, unicode):
        s = s.encode('utf-8')
    ss = base64.urlsafe_b64decode(s.replace('_', '=')).split(':')
    logging.info('decode cookie: %s' % str(ss))
    if len(ss)!=4:
        return None
    provider, uid, exp, md5 = ss
    if float(exp) < time.time():
        return None
    expected = ':'.join([provider, uid, exp, str(_get_passwd_by_uid(provider, uid)), _SESSION_COOKIE_KEY])
    if hashlib.md5(expected).hexdigest()!=md5:
        return None
    return uid

def delete_session_cookie():
    ' delete the session cookie immediately '
    ctx.response.set_cookie(_SESSION_COOKIE_NAME, 'deleted', expires=time.time() - _SESSION_COOKIE_EXPIRES)

def get_menus():
    '''
    Get navigation menus.
    '''
    menus = db.select('select * from menus order by display_order, name')
    if menus:
        return menus
    current = time.time()
    menu = Dict(id=db.next_str(), name=u'Home', description=u'', type='latest_articles', display_order=0, ref='', url='/latest', creation_time=current, modified_time=current, version=0)
    db.insert('menus', **menu)
    return [menu]

def get_settings(kind=None):
    '''
    Get all settings.
    '''
    settings = dict()
    if kind:
        L = db.select('select name, value from settings where kind=?', kind)
    else:
        L = db.select('select name, value from settings')
    for s in L:
        settings[s.name] = s.value
    return settings

def get_setting(name, default=''):
    '''
    Get setting by name. Return default value '' if not exist.
    '''
    ss = db.select('select value from settings where name=?', name)
    if ss:
        return ss[0].value
    return default

def set_setting(name, value):
    '''
    Set setting by name and value.
    '''
    pos = name.find('_')
    if pos<=0:
        raise ValueError('bad setting name: %s must be xxx_xxx' % name)
    kind = name[:pos]
    current = time.time()
    if 0==db.update('update settings set value=?, modified_time=?, version=version+1 where name=?', value, current, name):
        st = dict(id=db.next_str(), kind=kind, name=name, value=value, creation_time=current, modified_time=current, version=0)
        db.insert('settings', **st)

def get_setting_search_provider():
    return get_setting('search_provider', 'google')

def get_setting_site_name():
    return get_setting('site_name', 'iTranswarp')

def get_setting_site_description():
    return get_setting('site_description', '')

def theme(path):
    '''
    ThemeTemplate uses 'themes/<active-theme>' + template path to get real template.
    '''
    def _decorator(func):
        @functools.wraps(func)
        def _wrapper(*args, **kw):
            r = func(*args, **kw)
            if isinstance(r, dict):
                theme = 'default'
                template_name = 'themes/%s/%s' % (theme, path)
                r['__get_theme_path__'] = lambda _templpath: 'themes/%s/%s' % (theme, _templpath)
                r['__menus__'] = db.select('select * from menus order by display_order, name')
                if not '__title__' in r:
                    r['__title__'] = 'iTranswarp'
                r.update(get_settings('site'))
                r['__layout_categories__'] = db.select('select * from categories order by display_order, name')
                return Template(template_name, **r)
            return r
        return _wrapper
    return _decorator

class ThemeTemplate(Template):
    '''
    ThemeTemplate uses 'themes/<active-theme>' + template path to get real template.
    '''
    def __init__(self, template_name, model=None, **kw):
        super(ThemeTemplate, self).__init__(template_name, model=model, **kw)
        theme = 'default'
        self.template_name = 'themes/%s/%s' % (theme, template_name)
        # init other models:
        self.model['__get_theme_path__'] = lambda page: 'themes/%s/%s' % (theme, page)
        self.model['__menus__'] = db.select('select * from menus order by display_order, name')
        if not '__title__' in self.model:
            self.model['__title__'] = 'iTranswarp'
        self.model.update(get_settings('site'))
        self.model['__layout_categories__'] = db.select('select * from categories order by display_order, name')

def validate_email(email):
    '''
    Validate email address. Make sure email is lowercase.

    >>> validate_email('michael@example.com')
    True
    >>> validate_email(u'michael.liao@example.com.cn')
    True
    >>> validate_email('michael-liao@staff.example-inc.com.hk')
    True
    >>> validate_email('007michael@staff.007.com.cn')
    True
    >>> validate_email('localhost')
    False
    >>> validate_email('@localhost')
    False
    >>> validate_email('michael@')
    False
    >>> validate_email('michael@localhost')
    False
    >>> validate_email('michael@local.host.')
    False
    >>> validate_email('-hello@example.local')
    False
    >>> validate_email('michael$name@local.local')
    False
    >>> validate_email('user.@example.com')
    False
    >>> validate_email('user-@example.com')
    False
    >>> validate_email('user-0@example-.com')
    False
    '''
    m = _REG_EMAIL.match(str(email))
    return not m is None

if __name__=='__main__':
    import doctest
    doctest.testmod()
 