#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

from transwarp.web import Dict
import util

def _get_all_nav_menus():
    menus = []
    modules = {}
    mdict = util.scan_submodules('apps')
    for mod in mdict.itervalues():
        f1 = getattr(mod, 'export_navigation_menus', None)
        if callable(f1):
            menus.extend([Dict(x) for x in f1()])
    return menus

_nav_menus = _get_all_nav_menus()

def get_navigation_menus():
    return _nav_menus[:]

def get_navigation_menu(mtype):
    for m in _nav_menus:
        if mtype==m.type:
            return m
    raise badrequest()
