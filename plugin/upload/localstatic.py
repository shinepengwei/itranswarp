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

    @staticmethod
    def get_settings():
        return (dict(key='domain', name='Domain', description='Website domain'),)

    def delete(self, ref):
        fpath = '%s%s' % (self._document_root, ref)
        logging.info('delete uploaded file: %s' % fpath)
        if os.path.isfile(fpath):
            os.remove(fpath)

    def upload(self, fname, ftype, fcontent, fthumbnail):
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
            fo.write(fcontent)
        url = '/static/upload/%s/%s' % ('/'.join(dirs), iname)
        r = dict(url=url, ref=url)
        if fthumbnail:
            with open(ppath, 'w') as fo:
                fo.write(fthumbnail)
            r['thumbnail'] = '/static/upload/%s/%s' % ('/'.join(dirs), pname)
        return r
