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

class Plugin(object):

    def __init__(self, **kw):
        self._domain = kw.pop('domain', '')
        if not self._domain:
            raise ValueError('Missing param: domain.')
        self._client = storage.Client(accesskey=ACCESS_KEY, secretkey=SECRET_KEY, prefix=APP_NAME)

    @staticmethod
    def get_description():
        return 'Sina AppEngine Storage'

    @staticmethod
    def get_inputs():
        return (dict(key='domain', name='Domain', description='Website domain'),)

    @staticmethod
    def validate(**kw):
        pass

    def delete(self, ref):
        domain, key = ref.split(':', 1)
        self._client.delete(domain, key)

    def upload(self, fpath, fp):
        dt = datetime.now()
        logging.info('saving uploaded file to sae %s...' % fpath)
        url = self._client.put(self._domain,  fpath, storage.Object(fp))
        ref='%s:%s' % (self._domain, fpath)
        return url, ref
