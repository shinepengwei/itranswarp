#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
Store files.
'''

import os, time, uuid, hashlib, mimetypes
from datetime import datetime

from transwarp import db

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

class Store(object):

    @classmethod
    def get_inputs(cls):
        return ()

    @classmethod
    def validate(cls, **kw):
        pass

    def delete(self, ref):
        fpath = '%s%s' % (self._document_root, ref)
        logging.info('delete uploaded file: %s' % fpath)
        if os.path.isfile(fpath):
            os.remove(fpath)

    def upload(self, fpath, fp):
        dt = datetime.now()
        fpath1, ffile = os.path.split(fpath)
        fdir = os.path.join(self._upload_dir, fpath1)
        if not os.path.isdir(fdir):
            os.makedirs(fdir)
        ffullpath = os.path.join(fdir, ffile)
        logging.info('saving uploaded file to %s...' % ffullpath)
        with open(ffullpath, 'w') as fo:
            fo.write(fp)
        url = '/static/upload/%s' % fpath
        return url, url

_KIND = 'plugin.store'
_KEY = 'enabled'

def get_enabled_store_name():
    pname = settings.get_global_setting(_KIND, _KEY)
    if not pname:
        pname = 'localfile'
    if not pname in plugin.get_plugins('store'):
        return None
    return pname

def set_enabled_store_name(pname):
    if not pname in plugin.get_plugins('store'):
        raise IOError('cannot find enabled store.')
    settings.set_global_setting(_KIND, _KEY, pname)

def get_store_instance(pname):
    return plugin.get_plugin_instance('store', pname)

def get_enabled_store_instance():
    return get_store_instance(get_enabled_store_name())

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
    sname = get_enabled_store_name()
    url, ref = get_store_instance(sname).upload(fpath, filecontent)
    logging.info('uploaded file: %s' % url)
    r = Resource( \
        website_id = ctx.website.id, \
        ref_id = ref_id, \
        ref_type = ref_type, \
        ref_store = '%s:%s' % (sname, ref), \
        size = filesize, \
        filename = filename, \
        mime = mimetypes.types_map.get(fileext, 'application/octet-stream'), \
        url = url)
    r.insert()
    return r
