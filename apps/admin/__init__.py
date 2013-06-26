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
        return Template('pluginform.html', plugin=p, plugin_type='stores', inputs=inputs, submit_url='/api/admin/plugin/update', cancel_url='?action=')
    return Template('stores.html', plugins=plugins.get_plugins('stores', True), enabled=plugins.stores.get_enabled_store_id())

@api
@allow(ROLE_SUPER_ADMINS)
@post('/api/admin/store/enable')
def api_admin_store_enable():
    i = ctx.request.input(id='')
    if not i.id:
        raise APIValueError('id', 'id is empty.')
    p = plugins.get_plugin('stores', i.id)
    plugins.stores.set_enabled_store_id(i.id)
    return True

@allow(ROLE_SUPER_ADMINS)
def admin_signins():
    plugins.get_plugins('stores', True)
    #return Template('userform.html', form_title=_('Add User'), form_action='/api/user/create', redirect='all_users', roles=_get_role_list(), role_id=ROLE_SUBSCRIBERS, can_change_role=True)

@api
@allow(ROLE_SUPER_ADMINS)
@post('/api/admin/plugin/update')
def api_admin_plugin_update():
    i = ctx.request.input(type='', id='')
    if not i.type:
        raise APIValueError('type', 'invalid plugin type.')
    p_type = i.pop('type')
    if not i.id:
        raise APIValueError('id', 'invalid plugin id.')
    p_id = i.pop('id')
    plugins.set_plugin_settings(p_type, p_id, **i)
    return True
