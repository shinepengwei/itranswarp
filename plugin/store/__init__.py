#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
The store plugin makes file store in local, AWS, or other places.

You define a custom storage by defining a class:

class Plugin(object):

    def __init__(self, **kw):
        # pass

    @staticmethod
    def get_name():
        return 'Local File Storage'

    @staticmethod
    def get_settings():
        return ()

    @staticmethod
    def validate(**kw):
        pass

    def delete(self, ref):
        ref: the file reference.

    def upload(self, ftype, fext, fp):
        ftype: the storage type like 'photo', 'attrachment';
        fext: the file extension like '.jpg', '.mp4';
        fp: the file content of file-like object.
        returns:
            dict(url=the file access url, ref=the file reference that used for deletion)

raise any IOError when failed.
'''

import os, uuid, logging
from datetime import datetime

from transwarp.web import Dict

import setting, loader, plugin

_KIND = 'plugin.store'
_KEY = 'enabled'

def get_enabled_store_name():
    pname = setting.get_setting(_KIND, _KEY)
    if not pname:
        pname = 'localfile'
    if not pname in plugin.get_plugins('store'):
        return None
    return pname

def set_enabled_store_name(pname):
    if not pname in plugin.get_plugins('store'):
        raise IOError('cannot find enabled store.')
    setting.set_setting(_KIND, _KEY, pname)

def get_store_instance(pname):
    return plugin.get_plugin_instance('store', pname)

def get_enabled_store_instance():
    return get_store_instance(get_enabled_store_name())

def upload_file(ftype, fext, fp):
    dt = datetime.now()
    fpath = os.path.join(str(ftype), str(dt.year), str(dt.month), str(dt.day), '%s%s' % (uuid.uuid4().hex, fext))
    url, ref = get_enabled_store_instance().upload(fpath, fp)
    return url, '%s.%s' % (get_enabled_store_name(), ref)

def delete_file(the_ref):
    ss = the_ref.split('.', 1)
    if len(ss) != 2:
        raise IOError('Bad ref')
    name, ref = ss
    get_store_instance(name).delete(ref)
