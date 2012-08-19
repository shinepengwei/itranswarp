#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
A gevent app
'''

from gevent import monkey; monkey.patch_all()
from gevent.pywsgi import WSGIServer

import logging
logging.basicConfig(level=logging.INFO)

import os
import sys
sys.path.append(os.path.abspath('.'))

from itranswarp import web
from itranswarp import db

if __name__=='__main__':
    db.init('mysql', 'itranswarp', 'root', 'video-tx', host='localhost')
    application = web.WSGIApplication(('index', 'admin', 'apps.manage', 'apps.article',), template_engine='jinja2', DEBUG=True)
    server = WSGIServer(('0.0.0.0', 8080), application)
    server.serve_forever()
