#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import functools

from transwarp.web import ctx, Template

import setting, loader

def get_themes():
    return ['default']

def get_active_theme():
    return 'default'

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

