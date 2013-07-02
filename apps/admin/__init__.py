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

from core.models import Website, User, create_user
from core.apis import api, APIValueError
from core.roles import *
from core import utils, settings

import plugins

name = 'Global'

order = 2000000

menus = [
    ('-', 'Global'),
    ('admin_stores', 'Stores'),
    ('admin_signins', 'Signins'),
]

################################################################################
# Global
################################################################################

@allow(ROLE_SUPER_ADMINS)
def admin_stores():
    i = ctx.request.input(action='')
    if i.action=='edit':
        p = plugins.get_plugin('stores', i.id)
        ss = plugins.get_plugin_settings('stores', i.id)
        inputs = p.Plugin.get_inputs()
        for ip in inputs:
            ip['value'] = ss.get(ip['key'], '')
        return Template('pluginform.html', plugin=p, plugin_type='stores', inputs=inputs, submit_url='/api/admin/plugins/%s/update' % p.id, cancel_url='?action=')
    return Template('stores.html', plugins=plugins.get_plugins('stores', True), enabled=plugins.stores.get_enabled_store_id())

@api
@allow(ROLE_SUPER_ADMINS)
@post('/api/admin/stores/<pid>/enable')
def api_admin_store_enable(pid):
    if not pid:
        raise APIValueError('id', 'id is empty.')
    p = plugins.get_plugin('stores', pid)
    plugins.stores.set_enabled_store_id(pid)
    return True

@allow(ROLE_SUPER_ADMINS)
def admin_signins():
    return Template('signins.html', plugins=plugins.get_plugins('signins', True))

@api
@allow(ROLE_SUPER_ADMINS)
@post('/api/admin/plugins/<pid>/update')
def api_admin_plugin_update(pid):
    if not pid:
        raise APIValueError('id', 'invalid plugin id.')
    i = ctx.request.input(type='')
    if not i.type:
        raise APIValueError('type', 'invalid plugin type.')
    ptype = i.pop('type')
    plugins.set_plugin_settings(ptype, pid, **i)
    return True
