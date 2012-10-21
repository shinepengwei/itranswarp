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
        self._client = storage.Client(accesskey=ACCESS_KEY, secretkey=SECRET_KEY, prefix=APP_NAME)

    @staticmethod
    def get_name():
        return 'SAE Storage Uploader'

    @staticmethod
    def get_description():
        return 'Upload files to Sina AppEngine Storage'

    @staticmethod
    def get_settings():
        return (dict(key='domain', name='Domain', description='Website domain'),)

    def delete(self, ref):
        domain, key = ref.split(':', 1)
        self._client.delete(domain, key)

    def upload(self, fname, ftype, fcontent, fthumbnail):
        dt = datetime.now()
        dirs = (str(dt.year), str(dt.month), str(dt.day))
        ext = os.path.splitext(fname)[1].lower()
        name = uuid.uuid4().hex
        iname = '%s%s' % (name, ext)
        pname = '%s.thumbnail.jpg' % (name)
        path = os.path.join(*dirs)
        fpath = os.path.join(path, iname)
        ppath = os.path.join(path, pname)
        logging.info('saving uploaded file to sae %s...' % fpath)
        url = self._client.put(self._domain,  fpath, storage.Object(fcontent))
        r = dict(url=url, ref='%s:%s' % (self._domain, fpath))
        if fthumbnail:
            logging.info('saving thumbnail file to sae %s...' % ppath)
            r['thumbnail'] = self._client.put(self._domain,  ppath, storage.Object(fthumbnail))
        return r
