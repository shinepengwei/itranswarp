#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
Build release package.
'''

from datetime import datetime
from fabric.api import *

env.user = 'ubuntu'
env.hosts = ['aws.itranswarp.com']

_TAR_FILE = 'itranswarp.tar.gz'
_REMOTE_TMP_TAR = '/tmp/%s' % _TAR_FILE

_REMOTE_DIST_LINK = '/srv/itranswarp.com/www'
_REMOTE_DIST_DIR = '/srv/itranswarp.com/www-%s' % datetime.now().strftime('%y-%m-%d_%H.%M.%S')

def build(*files):
    includes = ['apps', 'core', 'i18n', 'plugins', 'static', 'templates', 'themes', 'transwarp', 'conf_prod.py', 'favicon.ico', 'markdown2.py', 'wsgi.py', 'wsgiapp.py']
    includes.extend(files)
    excludes = ['.*', '*.pyc', '*.pyo', '*.psd', 'static/css/less/*', 'static/upload/*']
    local('rm -f %s' % _TAR_FILE)
    cmd = ['tar', '--dereference', '-czvf', _TAR_FILE]
    cmd.extend(['--exclude=\'%s\'' % ex for ex in excludes])
    cmd.extend(includes)
    local(' '.join(cmd))

def scp():
    local('ssh-add /Users/michael/.ssh/michaelonamazon.pem')
    run('rm -f %s' % _REMOTE_TMP_TAR)
    put(_TAR_FILE, _REMOTE_TMP_TAR)
    run('sudo mkdir %s' % _REMOTE_DIST_DIR)
    with cd(_REMOTE_DIST_DIR):
        run('sudo tar -xzvf %s' % _REMOTE_TMP_TAR)
    run('sudo chown -R www-data:www-data %s' % _REMOTE_DIST_DIR)
    run('sudo rm -f %s' % _REMOTE_DIST_LINK)
    run('sudo ln -s %s %s' % (_REMOTE_DIST_DIR, _REMOTE_DIST_LINK))
    run('sudo chown www-data:www-data %s' % _REMOTE_DIST_LINK)
    with settings(warn_only=True):
        run('sudo supervisorctl stop itranswarp')
        run('sudo supervisorctl start itranswarp')

def build_gunicorn():
    build()
    scp()
