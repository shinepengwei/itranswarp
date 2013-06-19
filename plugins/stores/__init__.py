#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
The store plugin makes file store in local, AWS, or other places.
'''

import os, time, uuid, logging, mimetypes
from datetime import datetime

from transwarp.web import ctx, Dict
from transwarp import db

from core import settings

import plugins

class Resource(db.Model):
    '''
    create table resource (
        id varchar(50) not null,
        website_id varchar(50) not null,

        ref_id varchar(50) not null,
        ref_type varchar(50) not null,
        ref_store varchar(1000) not null,

        deleted bool not null,
        size bigint not null,
        filename varchar(50) not null,
        mime varchar(50) not null,
        url varchar(1000) not null,

        creation_time real not null,
        version bigint not null,

        primary key(id),
        index idx_website_id(website_id),
        index idx_ref_id(ref_id),
        index idx_creation_time(creation_time)
    );
    '''

    id = db.StringField(primary_key=True, default=db.next_str)

    website_id = db.StringField(nullable=False, updatable=False)

    ref_id = db.StringField(nullable=False, updatable=False)

    ref_type = db.StringField(nullable=False, updatable=False)

    ref_store = db.StringField(nullable=False, updatable=False)

    deleted = db.BooleanField(nullable=False, default=False)

    size = db.IntegerField(nullable=False, updatable=False)

    filename = db.StringField(nullable=False, updatable=False)

    mime = db.StringField(nullable=False, updatable=False)

    url = db.StringField(nullable=False, updatable=False)

    creation_time = db.FloatField(nullable=False, updatable=False, default=time.time)

    version = db.VersionField()

_KIND = 'plugins.stores'
_KEY = 'enabled'

def get_enabled_store_id():
    pid = settings.get_global_setting(_KIND, _KEY)
    if not pid:
        pid = 'localfile'
    if not pid in plugins.get_plugins('stores'):
        return None
    return pid

def set_enabled_store_id(pid):
    if not pid in plugin.get_plugins('stores'):
        raise IOError('cannot find store: %s' % pid)
    settings.set_global_setting(_KIND, _KEY, pid)

def get_store_instance(pid):
    return plugin.get_plugin_instance('stores', pid)

def get_enabled_store_instance():
    return get_store_instance(get_enabled_store_id())

def delete_resources(ref_id):
    '''
    Delete resources associated with the reference id.
    '''
    db.update('update resource set deleted=? where ref_id=?', True, ref_id)

def delete_file(ref_store):
    '''
    Delete file by ref_store.
    '''
    ss = ref_store.split(':', 1)
    if len(ss) != 2:
        raise IOError('Bad ref_store')
    name, ref = ss
    get_store_instance(name).delete(ref)

def upload_file(ref_type, ref_id, filename, filecontent):
    '''
    upload file and return created Resource model. The uploaded file path depends on current store plugin.
    '''
    fileext = os.path.splitext(filename)[1].lower()
    filesize = len(fcontent)
    dt = datetime.now()
    fpath = os.path.join(ctx.website.id, str(ref_type), str(dt.year), str(dt.month), str(dt.day), '%s%s' % (uuid.uuid4().hex, fileext))
    pid = get_enabled_store_id()
    url, ref = get_store_instance(pid).upload(fpath, filecontent)
    logging.info('uploaded file: %s' % url)
    r = Resource( \
        website_id = ctx.website.id, \
        ref_id = ref_id, \
        ref_type = ref_type, \
        ref_store = '%s:%s' % (pid, ref), \
        size = filesize, \
        filename = filename, \
        mime = mimetypes.types_map.get(fileext, 'application/octet-stream'), \
        url = url)
    r.insert()
    return r
