#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import os, logging, functools

from transwarp.web import ctx, Template

import setting, loader

_KIND_THEME = 'theme'
_KEY_THEME = 'active_theme'

_themes = None

def get_themes():
    global _themes
    if not _themes:
        L = []
        # scan folders:
        init_path = os.path.abspath(__file__)
        theme_dir = os.path.split(init_path)[0]
        d = loader.scan_submodules('plugin.theme')
        for k, v in d.iteritems():
            if os.path.isdir(os.path.join(theme_dir, k)):
                try:
                    L.append(dict(id=k, \
                                  name=getattr(v, 'name', k), \
                                  description=getattr(v, 'description', 'No description'), \
                                  author=getattr(v, 'author', 'unknown'), \
                                  url=getattr(v, 'url', '')))
                except BaseException:
                    logging.warning('load theme %s failed.' % k)
        logging.info('load themes: %s' % str(L))
        _themes = L
    return _themes

def get_active_theme():
    s = setting.get_setting(_KIND_THEME, _KEY_THEME)
    return s or 'default'

def set_active_theme(theme_id):
    for t in get_themes():
        if t['id'] == theme_id:
            setting.set_setting(_KIND_THEME, _KEY_THEME, theme_id)
            return
    raise ValueError('Invalid theme id: %s' % theme_id)

def _init_theme(path, model):
    theme = get_active_theme()
    model['__theme_path__'] = '/plugin/theme/%s' % theme
    model['__get_theme_path__'] = lambda _templpath: 'plugin/theme/%s/%s' % (theme, _templpath)
    model['__menus__'] = []
    model['__settings__'] = setting.get_website_settings()
    model['__navigations__'] = loader.load_navigations()
    model['__website__'] = ctx.website
    model['__user__'] = ctx.user
    model['__ctx__'] = ctx
    return 'plugin/theme/%s/%s' % (theme, path), model

def theme(path):
    '''
    ThemeTemplate uses 'plugin/theme/<active-theme>' + template path to get real template.
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
    ThemeTemplate uses 'plugin/theme/<active-theme>' + template path to get real template.
    '''
    def __init__(self, path, model=None, **kw):
        templ_path, m = _init_theme(path, r)
        super(ThemeTemplate, self).__init__(templ_path, m, **kw)
