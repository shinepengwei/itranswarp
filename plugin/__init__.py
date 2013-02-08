#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
The plugin makes features added to system dynamically.

You define a plugin by defining a class:

class Plugin(object):

    def __init__(self, **kw):
        # init plugin with kw while both key-value are strings (values are unicode).
        pass

    @staticmethod
    def get_description():
        # the display name of this plugin
        return 'Sample Plugin'

    @staticmethod
    def get_settings():
        # a list contains dict that tells how to display setting form.
        return ()

    @staticmethod
    def validate(**kw):
        # validate the settings when user saved the settings of this plugin.
        pass

    # other functions that requires...

raise any IOError when failed.
'''

import os, uuid, logging
from datetime import datetime

from transwarp.web import Dict

import setting, loader

_PLUGIN_CACHE = dict()

def _load_plugins(ptype):
    D = dict()
    for pname, mod in loader.scan_submodules('plugin.%s' % ptype).iteritems():
        try:
            keys = frozenset([i['key'] for i in mod.Plugin.get_inputs()])
            s = Dict(id=pname, name=pname, description=mod.Plugin.get_description(), keys=keys, Plugin=mod.Plugin)
            D[pname] = s
            logging.info('Load plugin: %s.%s' % (ptype, pname))
        except:
            logging.exception('Failed to load plugin: %s.%s' % (ptype, pname))
    return D

def get_plugins(ptype, return_list=False):
    ps = _PLUGIN_CACHE.get(ptype)
    if not ps:
        ps = _load_plugins(ptype)
        _PLUGIN_CACHE[ptype] = ps
    if return_list:
        return sorted(ps.values(), lambda p1, p2: cmp(p1.name, p2.name))
    return ps

def get_plugin(ptype, pname):
    return get_plugins(ptype)[pname]

def get_plugin_instance(ptype, pname):
    # FIXME: not cached:
    p = get_plugin(ptype, pname)
    return p.Plugin(**get_plugin_settings(ptype, pname))

def get_plugin_settings(ptype, pname):
    return setting.get_settings('plugin.%s.%s' % (ptype, pname))

def set_plugin_settings(ptype, pname, **kw):
    p = get_plugin(ptype, pname)
    p.Plugin.validate(**kw)
    setting.set_settings('plugin.%s.%s' % (ptype, pname), **kw)
