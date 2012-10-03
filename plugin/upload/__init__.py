#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import util

KEY_SELECTED_UPLOAD = 'plugin.selected_upload'

def get_selected_upload():
    '''
    Get selected upload plugin and return (name, Provider class), or (None, None) if no such setting.
    '''
    name = util.get_setting(KEY_SELECTED_UPLOAD, '')
    if name:
        try:
            return name, util.load_module('plugin.upload.%s' % name).Provider
        except ImportError:
            pass
    return None, None

def set_selected_upload(upload_id):
    util.set_setting(KEY_SELECTED_UPLOAD, upload_id)
