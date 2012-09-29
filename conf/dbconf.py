#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

# database configuration file

# database type: mysql, sqlite3:
DB_TYPE = 'mysql'

# schema name:
DB_SCHEMA = 'itranswarp'

# user and password:
DB_USER = 'www-data'
DB_PASSWORD = 'www-data'

# database host:
DB_HOST = 'localhost'

# database port, default to 0 (using default port):
DB_PORT = 3306

# any other keyword args:
DB_ARGS = {'use_unicode': True, 'charset': 'utf8'}
