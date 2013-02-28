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

import os, time, uuid, logging, mimetypes
from datetime import datetime

from transwarp.web import ctx, Dict
from transwarp import db

import setting, loader, plugin

_KIND = 'plugin.store'
_KEY = 'enabled'

def get_enabled_store_name():
    pname = setting.get_global_setting(_KIND, _KEY)
    if not pname:
        pname = 'localfile'
    if not pname in plugin.get_plugins('store'):
        return None
    return pname

def set_enabled_store_name(pname):
    if not pname in plugin.get_plugins('store'):
        raise IOError('cannot find enabled store.')
    setting.set_global_setting(_KIND, _KEY, pname)

def get_store_instance(pname):
    return plugin.get_plugin_instance('store', pname)

def get_enabled_store_instance():
    return get_store_instance(get_enabled_store_name())

def delete_resources(ref_id):
    db.update('update resources set deleted=? where ref_id=?', True, ref_id)

def delete_file(the_ref):
    ss = the_ref.split(':', 1)
    if len(ss) != 2:
        raise IOError('Bad ref')
    name, ref = ss
    get_store_instance(name).delete(ref)

def upload_file(ref_type, ref_id, filename, fcontent):
    fileext = os.path.splitext(filename)[1].lower()
    filesize = len(fcontent)
    dt = datetime.now()
    fpath = os.path.join(ctx.website.id, str(ref_type), str(dt.year), str(dt.month), str(dt.day), '%s%s' % (uuid.uuid4().hex, fileext))
    sname = get_enabled_store_name()
    url, the_ref = get_store_instance(sname).upload(fpath, fcontent)
    logging.info('uploaded file: %s' % url)
    ref = '%s:%s' % (sname, the_ref)
    r = Dict( \
        id = db.next_str(), \
        website_id = ctx.website.id, \
        ref_id = ref_id, \
        ref_type = ref_type, \
        deleted = False, \
        size = filesize, \
        filename = filename, \
        mime = mimetypes.types_map.get(fileext, 'application/octet-stream'), \
        ref = ref, \
        url = url, \
        creation_time = time.time(), \
        version = 0)
    db.insert('resources', **r)
    return r
