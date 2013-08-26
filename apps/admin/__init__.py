#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
global administration for super administrators.
'''

import re, time, uuid, logging, socket, struct, linecache
from datetime import datetime, timedelta

from transwarp.web import ctx, get, post, route, seeother, notfound, UTC, UTC_0, Template, Dict
from transwarp.mail import send_mail
from transwarp import db, task

from core.models import Website, User
from core.apis import api, APIValueError
from core.roles import *
from core import utils, settings

import plugins
from plugins import signins, stores

name = 'Global'

order = 2000000

menus = [
    ('-', 'Global'),
    ('admin_stores', 'Stores'),
    ('admin_signins', 'Signins'),
]

@get('/ab')
def ab_test():
    return '<html><head><title>200 OK</title></head><body><h1>AB Test</h1></body></html>'

################################################################################
# Global - Stores
################################################################################

@allow(ROLE_SUPER_ADMINS)
def admin_stores():
    i = ctx.request.input(action='')
    if i.action=='edit':
        p = plugins.get_plugin('stores', i.id)
        ss = plugins.get_plugin_settings('stores', i.id, is_global=True)
        inputs = p.Plugin.get_inputs()
        for ip in inputs:
            ip['value'] = ss.get(ip['key'], '')
        return Template('pluginform.html', plugin=p, plugin_type='stores', inputs=inputs, submit_url='/api/admin/stores/%s/update' % p.id, cancel_url='?action=')
    return Template('stores.html', plugins=plugins.get_plugins('stores', True), enabled=stores.get_enabled_store_id())

@api
@allow(ROLE_SUPER_ADMINS)
@post('/api/admin/stores/<pid>/enable')
def api_admin_stores_enable(pid):
    if not pid:
        raise APIValueError('id', 'id is empty.')
    p = plugins.get_plugin('stores', pid)
    stores.set_enabled_store_id(pid)
    return True

@api
@allow(ROLE_SUPER_ADMINS)
@post('/api/admin/stores/<pid>/update')
def api_admin_stores_update(pid):
    if not pid:
        raise APIValueError('id', 'invalid plugin id.')
    i = ctx.request.input()
    plugins.set_plugin_settings('stores', pid, is_global=True, **i)
    return True

################################################################################
# Global - Signins
################################################################################

@allow(ROLE_ADMINISTRATORS)
def admin_signins():
    i = ctx.request.input(action='', id='')
    if i.action=='edit':
        p = plugins.get_plugin('signins', i.id)
        ss = plugins.get_plugin_settings('signins', i.id)
        inputs = p.Plugin.get_inputs()
        for ip in inputs:
            ip['value'] = ss.get(ip['key'], '')
        return Template('pluginform.html', plugin=p, plugin_type='signins', inputs=inputs, submit_url='/api/admin/signins/%s/update' % p.id, cancel_url='?action=')
    return Template('signins.html', plugins=signins.get_signins(), is_enabled=signins.is_enabled)

@api
@allow(ROLE_ADMINISTRATORS)
@post('/api/admin/signins/<pid>/enable')
def api_admin_signins_enable(pid):
    if not pid:
        raise APIValueError('id', 'id is empty.')
    signins.set_signin_enabled(pid, True)
    return True

@api
@allow(ROLE_ADMINISTRATORS)
@post('/api/admin/signins/<pid>/disable')
def api_admin_signins_disable(pid):
    if not pid:
        raise APIValueError('id', 'id is empty.')
    signins.set_signin_enabled(pid, False)
    return True

@api
@allow(ROLE_ADMINISTRATORS)
@post('/api/admin/signins/<pid>/update')
def api_admin_signins_update(pid):
    if not pid:
        raise APIValueError('id', 'invalid plugin id.')
    i = ctx.request.input()
    plugins.set_plugin_settings('signins', pid, **i)
    return True
