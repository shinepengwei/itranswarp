#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' development-mode configurations '

db = {
    'type': 'mysql',
    'schema': 'itrans',
    'host': 'localhost',
    'port': 3306,
    'user': 'www-data',
    'password': 'www-data',
}

cache = {
    'type': 'redis',
    'host': 'localhost',
}
