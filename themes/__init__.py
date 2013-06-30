#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
Theme definition.
'''

import functools

from transwarp.web import ctx, Template

from core import settings
from core.navs import get_navigations

def _get_active_theme():
    return 'default'

def _init_theme(path, model):
    theme = _get_active_theme()
    model['__theme_path__'] = '/themes/%s' % theme
    model['__get_theme_file__'] = lambda f: '/themes/%s/%s' % (theme, f)
    model['__custom_header__'] = settings.get_text(settings.KIND_WEBSITE, settings.KEY_CUSTOM_HEADER)
    model['__custom_footer__'] = settings.get_text(settings.KIND_WEBSITE, settings.KEY_CUSTOM_FOOTER)
    model['__menus__'] = []
    model['__navigations__'] = get_navigations()
    model['__website__'] = ctx.website
    model['__user__'] = ctx.user
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
