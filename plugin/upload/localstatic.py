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
from datetime import datetime

from transwarp.web import ctx

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
        return 'Upload files to local directory /static/upload/'

    @staticmethod
    def get_settings():
        return ()

    def delete(self, ref):
        fpath = '%s%s' % (self._document_root, ref)
        logging.info('delete uploaded file: %s' % fpath)
        if os.path.isfile(fpath):
            os.remove(fpath)

    def upload(self, ftype, fext, fcontent):
        dt = datetime.now()
        fdir = os.path.join(self._upload_dir, str(ftype), str(dt.year), str(dt.month), str(dt.day))
        if not os.path.isdir(fdir):
            os.makedirs(fdir)
        fpath = os.path.join(fdir, '%s%s' % (uuid.uuid4().hex, fext))
        logging.info('saving uploaded file to %s...' % fpath)
        with open(fpath, 'w') as fo:
            fo.write(fcontent)
        url = '/%s' % fpath
        return dict(url=url, ref=url)
