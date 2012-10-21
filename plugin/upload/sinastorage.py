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

    def delete(self, ref):
        self._client.delete(self._domain, ref)

    def upload(self, fname, ftype, fcontent, fthumbnail):
        dt = datetime.now()
        dirs = (str(dt.year), str(dt.month), str(dt.day))
        ext = os.path.splitext(fname)[1].lower()
        name = uuid.uuid4().hex
        iname = '%s%s' % (name, ext)
        pname = '%s.thumbnail.jpg' % (name)
        fpath = os.path.join(p, iname)
        ppath = os.path.join(p, pname)
        logging.info('saving uploaded file to sae %s...' % fpath)
        url = self._client.put(self._domain, fpath, fcontent)
        ref = '/static/upload/%s/%s' % ('/'.join(dirs), iname)
        r = dict(url=url, ref=ref)
        if fthumbnail:
            logging.info('saving thumbnail file to sae %s...' % ppath)
            r['thumbnail'] = self._client.put(self._domain, ppath, fcontent)
        return r
