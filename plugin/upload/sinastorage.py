#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
Upload files to SAE storage.
'''

import os
import uuid
import shutil
import logging
import Image
from datetime import datetime

try:
    from sae.const import ACCESS_KEY, SECRET_KEY, APP_NAME
    from sae import storage
except ImportError:
    ACCESS_KEY = ''
    SECRET_KEY = ''
    APP_NAME = ''
    storage = None

class Provider(object):

    def __init__(self, **kw):
        self._domain = kw.pop('domain', '')
        if not self._domain:
            raise ValueError('Missing param: domain.')
        self._client = storage.Client()

    @staticmethod
    def get_name():
        return 'SAE Storage Uploader'

    @staticmethod
    def get_description():
        return 'Upload files to Sina AppEngine Storage'

    @staticmethod
    def get_settings():
        return (dict(key='domain', name='Domain', description='Website domain'),
                dict(key='app_name', name='App Name', description='App name'),
                dict(key='access_key', name='Access Key', description='Access key'),
                dict(key='secret_key', name='Secret Key', description='Secret key'))

    def can_handle(fname, ftype):
        return True

    def _get_metadata(self, fpath, ppath, d):
        im = Image.open(fpath)
        w, h = im.size[0], im.size[1]
        d['width'], d['height'] = w, h
        d['metadata'] = 'format=%s&mode=%s' % (im.format, im.mode)
        if w>90 and h>90:
            tw, th = min(w, 90), min(h, 90)
            im.thumbnail((tw, th), Image.ANTIALIAS)
        if ppath:
            if im.mode != 'RGB':
                im = im.convert('RGB')
            im.save(ppath, 'JPEG')

    def delete(self, ref):
        self._client.delete(self._domain, ref)

    def upload(self, fname, ftype, fp):
        dt = datetime.now()
        dirs = (str(dt.year), str(dt.month), str(dt.day))
        ext = os.path.splitext(fname)[1].lower()
        name = uuid.uuid4().hex
        iname = '%s%s' % (name, ext)
        pname = '%s.thumbnail.jpg' % (name)
        fpath = os.path.join(p, iname)
        ppath = os.path.join(p, pname)
        logging.info('saving uploaded file to %s...' % fpath)
        with open(fpath, 'w') as fo:
            shutil.copyfileobj(fp, fo)
        ref = '/static/upload/%s/%s' % ('/'.join(dirs), iname)
        r = dict(size=os.path.getsize(fpath))
        if ftype=='image':
            self._get_metadata(fpath, ppath, r)
            r['thumbnail'] = '/static/upload/%s/%s' % ('/'.join(dirs), pname)
        r['url'] = ref
        r['ref'] = ref
        return r
