#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
The plugin makes features added to system dynamically.

You define a plugin by defining a class like SamplePlugin.
'''

import os, uuid, logging
from datetime import datetime

from transwarp.web import Dict

from core import settings, utils

class SamplePlugin(object):

    def __init__(self, **kw):
        # init plugin with kw while both key-value are strings (values are unicode).
        pass

    name = 'Sample Plugin'

    description = 'A sample plugin.'

    # a list contains dict that tells how to display setting form.
    settings = ()

    @classmethod
    def validate(cls, **kw):
        # validate the settings when saved the settings of this plugin.
        if 'debug' in kw:
            raise ValueError('debug mode not allowed.')

_PLUGIN_CACHE = dict()

def _load_plugins(ptype):
    D = dict()
    for pid, mod in utils.scan_submodules('plugins.%s' % ptype).iteritems():
        try:
            keys = frozenset([i['key'] for i in mod.Plugin.get_inputs()])
            s = Dict(id=pid, name=mod.Plugin.name, description=mod.Plugin.description, keys=keys, Plugin=mod.Plugin)
            D[pid] = s
            logging.info('Load plugin: %s.%s' % (ptype, pid))
        except:
            logging.exception('Failed to load plugin: %s.%s' % (ptype, pid))
    return D

def get_plugins(ptype, return_list=False):
    ps = _PLUGIN_CACHE.get(ptype)
    if not ps:
        ps = _load_plugins(ptype)
        _PLUGIN_CACHE[ptype] = ps
    if return_list:
        return sorted(ps.values(), lambda p1, p2: cmp(p1.name, p2.name))
    return ps

def get_plugin(ptype, pid):
    return get_plugins(ptype)[pid]

def get_plugin_instance(ptype, pid):
    # FIXME: not cached:
    p = get_plugin(ptype, pid)
    return p.Plugin(**get_plugin_settings(ptype, pid))

def get_plugin_settings(ptype, pid):
    return settings.get_global_settings('plugins.%s.%s' % (ptype, pid))

def set_plugin_settings(ptype, pid, **kw):
    p = get_plugin(ptype, pid)
    p.Plugin.validate(**kw)
    settings.set_global_settings('plugins.%s.%s' % (ptype, pid), **kw)
