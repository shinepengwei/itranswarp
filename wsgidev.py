#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
A WSGI app for DEV ONLY.

Start dev server:

$ python wsgidev.py
'''

import logging; logging.basicConfig(level=logging.DEBUG)

from wsgiref.simple_server import make_server

import wsgi

if __name__=='__main__':
    logging.info('application will start...')
    server = make_server('127.0.0.1', 8080, wsgi.create_app(debug=True))
    server.serve_forever()
