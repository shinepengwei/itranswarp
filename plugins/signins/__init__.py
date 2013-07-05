#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
The signin plugin enables user to signin from 3rd-part like facebook, twitter, etc.
'''

import os, time, uuid, urllib, logging, mimetypes
from datetime import datetime

from transwarp.web import ctx, Dict
from transwarp import db

from core import http, settings

import plugins

_KIND = 'plugins.plugins'
_KEY_ENABLED = 'enabled'

_CACHE = {}
_INSTANCE_CACHE = {}

def create_signin_instance(pid):
    p = plugins.get_plugin('signins', pid)
    if p.id in get_enabled_signin_ids():
        ss = plugins.get_plugin_settings('signins', pid)
        return p.Plugin(**ss)
    return None

def get_signins():
    ss = plugins.get_plugins('signins', True)
    ids = get_enabled_signin_ids()
    for s in ss:
        s.enabled = s.id in ids
    return ss

def is_enabled(sid):
    ids = get_enabled_signin_ids()
    return sid in ids

def get_enabled_signins():
    return filter(lambda s: is_enabled(s.id), get_signins())

def get_enabled_signin_ids():
    pids = settings.get_setting(_KIND, _KEY_ENABLED)
    if not pids:
        return []
    return pids.split(',')

def set_signin_enabled(pid, enabled):
    if not pid in plugins.get_plugins('signins'):
        raise IOError('cannot find plugin: %s' % pid)
    pids = get_enabled_signin_ids()
    if enabled and pid not in pids:
        pids.append(pid)
    if not enabled:
        pids.remove(pid)
    settings.set_setting(_KIND, _KEY_ENABLED, ','.join(pids))


##########
## TODO
##########

def get_signin_instance(pid):
    return plugins.get_plugin_instance('plugins', pid)

def get_enabled_signin_instances():
    pass
