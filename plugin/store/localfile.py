#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
Upload files to local dir /static/upload/
'''

import os, uuid, shutil, logging
from datetime import datetime

from transwarp.web import ctx

class Plugin(object):

    def __init__(self, **kw):
        self._document_root = ctx.request.document_root
        logging.info('init local uploader: set document_root: %s' % self._document_root)
        self._upload_dir = os.path.join(self._document_root, 'static', 'upload')
        if not os.path.isdir(self._upload_dir):
            os.makedirs(self._upload_dir)

    @staticmethod
    def get_description():
        return 'Local File System Storage'

    @staticmethod
    def get_inputs():
        return ()

    @staticmethod
    def validate(**kw):
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
