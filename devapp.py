#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
A WSGI app for DEV ONLY.

Commands for init mysql db:

> create database itranswarp;
> create user 'www-data'@'localhost' identified by 'www-data';
> grant all privileges on itranswarp.* to 'www-data'@'localhost' identified by 'www-data';

or for production mode:

> grant select,insert,update,delete on itranswarp.* to 'www-data'@'localhost' identified by 'www-data';
'''

import logging; logging.basicConfig(level=logging.DEBUG)

from wsgiref.simple_server import make_server

import wsgi

if __name__=='__main__':
    logging.info('application will start...')
    server = make_server('127.0.0.1', 8080, wsgi.create_app(debug=True))
    server.serve_forever()
