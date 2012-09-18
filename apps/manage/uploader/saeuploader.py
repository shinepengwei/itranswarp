#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
Upload files to local dir /static/upload/
'''

import os
import uuid
import shutil
import logging
import Image
from datetime import datetime

from sae.const import ACCESS_KEY, SECRET_KEY, APP_NAME
from sae import storage

class Uploader(object):

    def __init__(self, **kw):
        self._domain = kw.pop('domain', '')
        if not self._domain:
            raise ValueError('Missing param: domain.')
        self._client = storage.Client()

    @property
    def settings(self):
        return [
            dict(name='Domain', key='domain', default='', required=True),
            dict(name='Access Key', key='access_key', default='', required=False),
            dict(name='Secret Key', key='secret_key', default='', required=False),
            dict(name='App Name', key='app_name', default='', required=False),
        ]

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
