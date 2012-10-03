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

from itranswarp.web import ctx

class Provider(object):

    def __init__(self, **kw):
        self._document_root = ctx.request.document_root
        logging.info('init local uploader: set document_root: %s' % self._document_root)
        self._upload_dir = os.path.join(self._document_root, 'static', 'upload')
        if not os.path.isdir(self._upload_dir):
            os.makedirs(self._upload_dir)

    @staticmethod
    def get_name():
        return 'Local Uploader'

    @staticmethod
    def get_description():
        return 'Upload files to local directory'

    def can_handle(fname, ftype):
        return True

    @staticmethod
    def get_settings():
        return (dict(key='domain', name='Domain', description='Website domain'),)

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
        fpath = '%s%s' % (self._document_root, ref)
        logging.info('delete uploaded file: %s' % fpath)
        if os.path.isfile(fpath):
            os.remove(fpath)

    def upload(self, fname, ftype, fp):
        dt = datetime.now()
        dirs = (str(dt.year), str(dt.month), str(dt.day))
        p = os.path.join(self._upload_dir, *dirs)
        if not os.path.isdir(p):
            os.makedirs(p)
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
