#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import util

def get_enabled_upload():
    '''
    Get selected upload plugin and return (name, Provider class), or (None, None) if no such setting.
    '''
    providers = [p for p in util.get_plugin_providers('upload') if p['enabled']]
    if providers:
        pid = providers[0]['id']
        try:
            return pid, util.load_module('plugin.upload.%s' % pid).Provider
        except ImportError:
            pass
    return None, None
