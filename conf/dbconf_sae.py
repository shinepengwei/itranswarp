#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import sae.const

# database configuration file for SAE

DB_TYPE = 'mysql'

# schema name:
DB_SCHEMA = sae.const.MYSQL_DB

# user and password:
DB_USER = sae.const.MYSQL_USER
DB_PASSWORD = sae.const.MYSQL_PASS

# database host:
DB_HOST = sae.const.MYSQL_HOST

# database port, default to 0 (using default port):
DB_PORT = int(sae.const.MYSQL_PORT)

# any other keyword args:
DB_ARGS = {'use_unicode': True, 'charset': 'utf8'}
