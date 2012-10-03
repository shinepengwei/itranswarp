#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' Util module '

import os, re, time, base64, hashlib, logging, functools

from itranswarp.web import ctx, get, post, route, jsonrpc, Dict, Template, seeother, notfound, badrequest
from itranswarp import db

import const

_REG_EMAIL = re.compile(r'^[0-9a-z]([\-\.\w]*[0-9a-z])*\@([0-9a-z][\-\w]*[0-9a-z]\.)+[a-z]{2,9}$')

_SESSION_COOKIE_NAME = '_auth_session_cookie'
_SESSION_COOKIE_KEY = '_SECURE_keyabc123xyz_BIND_'
_SESSION_COOKIE_EXPIRES = 31536000.0

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
    >>> type(ms['manage'])
    <type 'module'>
    >>> ms['manage'].__name__
    'apps.manage'
    '''
    web_root = os.path.dirname(os.path.abspath(__file__))
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

def _load_plugin_settings(plugin_type, provider_name, provider_cls):
    stored = get_settings(kind='%s.%s' % (plugin_type, provider_name), remove_prefix=True)
    settings = list(provider_cls.get_settings())
    for setting in settings:
        setting['value'] = stored.get(setting['key'], '')
    return settings, int(stored.get('order', 100000 + ord(provider_name[0]))), bool(stored.get('enabled', ''))

def save_plugin_settings(plugin_type, name, enabled, settings):
    provider = load_module('plugin.%s.%s' % (plugin_type, name)).Provider
    set_setting(name='%s.%s_enabled' % (plugin_type, name), value='True' if enabled else '')
    for setting in provider.get_settings():
        key = setting['key']
        set_setting(name='%s.%s_%s' % (plugin_type, name, key), value=settings.get(key, ''))

def create_signin_provider(name):
    provider = load_module('plugin.signin.%s' % name)
    return provider.Provider(**get_settings(kind='signin.%s' % name, remove_prefix=True))

def create_upload_provider(name):
    provider = load_module('plugin.upload.%s' % name)
    return provider.Provider(**get_settings(kind='upload.%s' % name, remove_prefix=True))

def get_plugin_settings(plugin_type, name):
    provider = load_module('plugin.%s.%s' % (plugin_type, name)).Provider
    settings, order, enabled = _load_plugin_settings(plugin_type, name, provider)
    return settings, provider.get_description(), enabled

def order_plugin_providers(plugin_type, orders):
    providers = get_plugin_providers(plugin_type, names_only=True)
    n = 0
    for name in orders:
        if name in providers:
            set_setting(name='%s.%s_order' % (plugin_type, name), value=str(n))
            n = n + 1

def get_plugin_providers(plugin_type, names_only=False):
    '''
    Get plugin providers as list.
    '''
    ps = scan_submodules('plugin.%s' % plugin_type)
    if names_only:
        return ps.keys()
    providers = []
    for mod_name, mod in ps.iteritems():
        settings, order, enabled = _load_plugin_settings(plugin_type, mod_name, mod.Provider)
        provider = dict(name=mod.Provider.get_name(), description=mod.Provider.get_description(), settings=settings)
        provider['id'] = mod_name
        provider['order'] = order
        provider['enabled'] = enabled
        providers.append(provider)
    return sorted(providers, key=lambda p: p['order'])

def make_session_cookie(provider, uid, passwd, expires):
    '''
    Generate a secure client session cookie by constructing: 
    base64(uid, expires, md5(auth_provider, uid, expires, passwd, salt)).
    
    Args:
        auth_provider: auth provider.
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

    Returns:
        user id as str, or None if cookie is invalid.
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
    ' delete the session cookie immediately. '
    ctx.response.delete_cookie(_SESSION_COOKIE_NAME)

def get_menus():
    '''
    Get navigation menus as list, each element is a Dict object.
    '''
    menus = db.select('select * from menus order by display_order, name')
    if menus:
        return menus
    current = time.time()
    menu = Dict(id=db.next_str(), name=u'Home', description=u'', type='latest_articles', display_order=0, ref='', url='/latest', creation_time=current, modified_time=current, version=0)
    db.insert('menus', **menu)
    return [menu]

def get_settings(kind=None, remove_prefix=False):
    '''
    Get all settings.
    '''
    settings = dict()
    if kind:
        L = db.select('select name, value from settings where kind=?', kind)
    else:
        L = db.select('select name, value from settings')
    for s in L:
        key = s.name[s.name.find('_')+1:] if remove_prefix else s.name
        settings[key] = s.value
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

def _init_theme(path, model):
    theme = 'default'
    model['__theme_path__'] = '/themes/%s' % theme
    model['__get_theme_path__'] = lambda _templpath: 'themes/%s/%s' % (theme, _templpath)
    model['__menus__'] = db.select('select * from menus order by display_order, name')
    if not '__title__' in model:
        model['__title__'] = 'iTranswarp'
    model.update(get_settings('site'))
    model['ctx'] = ctx
    model['__layout_categories__'] = db.select('select * from categories order by display_order, name')
    return 'themes/%s/%s' % (theme, path), model

def theme(path):
    '''
    ThemeTemplate uses 'themes/<active-theme>' + template path to get real template.
    '''
    def _decorator(func):
        @functools.wraps(func)
        def _wrapper(*args, **kw):
            r = func(*args, **kw)
            if isinstance(r, dict):
                templ_path, model = _init_theme(path, r)
                return Template(templ_path, model)
            return r
        return _wrapper
    return _decorator

class ThemeTemplate(Template):
    '''
    ThemeTemplate uses 'themes/<active-theme>' + template path to get real template.
    '''
    def __init__(self, path, model=None, **kw):
        templ_path, m = _init_theme(path, r)
        super(ThemeTemplate, self).__init__(templ_path, m, **kw)

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
 