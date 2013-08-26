#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import re, time, uuid, logging, socket, struct, linecache
from datetime import datetime, timedelta

from transwarp.web import ctx, get, post, route, seeother, notfound, UTC, UTC_0, Template, Dict
from transwarp.mail import send_mail
from transwarp import db, task

from core.models import Website, User, create_user, delete_comment
from core.navs import Navigation, get_navigations
from core.apis import *
from core.roles import *
from core import utils, settings

name = 'Settings'

order = 1000000

menus = [
    ('-', 'Website'),
    ('general', 'General'),
    ('navigation', 'Navigation'),
    ('advanced', 'Advanced'),
    ('-', 'Users'),
    ('all_users', 'All Users'),
    ('add_user', 'Add User'),
    ('profile', 'My Profile'),
]

navigations = (
        dict(
            key='custom',
            input='text',
            prompt='Custom Link',
            description='Custom link like http://www.google.com',
            fn_get_url=lambda value: value,
        ),
)

################################################################################
# Comments
################################################################################

@api
@allow(ROLE_EDITORS)
@post('/api/comments/<cid>/delete')
def api_comment_delete(cid):
    delete_comment(cid)

################################################################################
# Navigation
################################################################################

def _get_navigation(nav_id):
    nav = Navigation.get_by_id(nav_id)
    if not nav or nav.website_id!=ctx.website.id:
        raise APIValueError('id', 'invalid id')
    return nav

@get('/')
def web_index():
    nav = get_navigations()
    if nav:
        raise seeother(nav[0].url)
    return '<html><body><h1>This website is not configured.</h1><p><a href="/auth/signin?redirect=/manage/">Sign In and Configure</a></p></body></html>'

@api
@allow(ROLE_ADMINISTRATORS)
@post('/api/navigation/create')
def api_navigation_create():
    from core import manage
    i = ctx.request.input(kind='', name='', value='')
    if not i.kind:
        raise APIValueError('kind', 'kind cannot be empty')
    name = i.name.strip()
    if not name:
        raise APIValueError('name', 'name cannot be empty')
    for navdef in manage.get_nav_definitions():
        if navdef.key == i.kind:
            url = navdef.fn_get_url(i.value)
            if not url:
                raise APIValueError('url', 'url cannot be empty')
            max_disp = db.select_int('select max(display_order) from navigation where website_id=?', ctx.website.id)
            if max_disp is None:
                max_disp = 0
            nav = Navigation(
                website_id = ctx.website.id,
                display_order = 1 + max_disp,
                kind = i.kind,
                name = name,
                description = '',
                url = url)
            nav.insert()
            return nav
    raise ValueError('kind', 'invalid kind')

@api
@allow(ROLE_ADMINISTRATORS)
@post('/api/navigation/update')
def api_navigation_update():
    i = ctx.request.input(id='')
    if not i.id:
        raise APIValueError('id', 'id cannot be empty')
    nav = _get_navigation(i.id)
    if 'name' in i:
        name = i.name.strip()
        if not name:
            raise APIValueError('name', 'name cannot be empty')
        nav.name = name
    if 'description' in i:
        description = i.description.strip()
        nav.description = description
    nav.update()
    return True

@api
@allow(ROLE_ADMINISTRATORS)
@post('/api/navigation/delete')
def api_navigation_delete():
    i = ctx.request.input(id='')
    if not i.id:
        raise APIValueError('id', 'id cannot be empty')
    nav = _get_navigation(i.id)
    nav.delete()
    return True

@api
@allow(ROLE_ADMINISTRATORS)
@post('/api/navigation/sort')
def api_navigation_sort():
    ids = ctx.request.gets('id')
    navs = get_navigations()
    l = len(navs)
    if l != len(ids):
        raise APIValueError('id', 'bad id list.')
    sets = set([n.id for n in navs])
    odict = dict()
    n = 0
    for o in ids:
        if not o in sets:
            raise APIValueError('id', 'some id was invalid.')
        odict[o] = n
        n = n + 1
    with db.transaction():
        for n in navs:
            db.update('update navigation set display_order=? where id=?', odict.get(n.id, l), n.id)
    return True

@allow(ROLE_ADMINISTRATORS)
def navigation():
    from core import manage
    i = ctx.request.input(action='', id='')
    if i.action=='add':
        return Template('navigation_add.html', definitions=manage.get_nav_definitions())
    if i.action=='edit':
        nav = _get_navigation(i.id)
        return Template('navigation_edit.html', **nav)
    return Template('navigations.html', navigations=get_navigations())

################################################################################
# Website
################################################################################

@api
@get('/api/website')
def api_website():
    return ctx.website

@api
@allow(ROLE_ADMINISTRATORS)
@post('/api/website/update')
def api_website_update():
    i = ctx.request.input()
    w = Website.get_by_id(ctx.website.id)
    update_w = False
    for key in ('name', 'description', 'copyright'):
        if key in i:
            value = i[key].strip()
            if value:
                setattr(w, key, value)
                update_w = True
    if 'timezone' in i and i.timezone in settings.TIMEZONES:
        w.timezone = i.timezone
        update_w = True
    if 'dateformat' in i and i.dateformat in settings.DATE_FORMATS:
        w.dateformat = i.dateformat
        update_w = True
    if 'timeformat' in i and i.timeformat in settings.TIME_FORMATS:
        w.timeformat = i.timeformat
        update_w = True
    if update_w:
        w.update()
    if settings.KEY_CUSTOM_HEADER in i:
        settings.set_text(settings.KIND_WEBSITE, settings.KEY_CUSTOM_HEADER, i[settings.KEY_CUSTOM_HEADER])
    if settings.KEY_CUSTOM_FOOTER in i:
        settings.set_text(settings.KIND_WEBSITE, settings.KEY_CUSTOM_FOOTER, i[settings.KEY_CUSTOM_FOOTER])
    return dict(result=True)

@allow(ROLE_ADMINISTRATORS)
def general():
    w = Website.get_by_id(ctx.website.id)
    if not w.timezone:
        w.timezone = settings.DEFAULT_TIMEZONE
    if not w.dateformat:
        w.dateformat = settings.DATE_FORMATS[0]
    if not w.timeformat:
        w.timeformat = settings.TIME_FORMATS[0]
    dt = w.datetimeformat
    utc = datetime.utcfromtimestamp(time.time()).replace(tzinfo=UTC('+00:00'))
    now = utc.astimezone(UTC(w.timezone))
    date_examples = zip(settings.DATE_FORMATS, [now.strftime(f) for f in settings.DATE_FORMATS])
    time_examples = zip(settings.TIME_FORMATS, [now.strftime(f) for f in settings.TIME_FORMATS])
    return Template('general.html', \
        utc_example=utc.strftime(dt), \
        local_example=now.strftime(dt), \
        timezones=settings.TIMEZONES, \
        date_examples=date_examples, \
        time_examples=time_examples, \
        **w)

@allow(ROLE_ADMINISTRATORS)
def advanced():
    custom_header = settings.get_text(settings.KIND_WEBSITE, settings.KEY_CUSTOM_HEADER)
    custom_footer = settings.get_text(settings.KIND_WEBSITE, settings.KEY_CUSTOM_FOOTER)
    return Template('advanced.html', custom_header=custom_header, custom_footer=custom_footer)

################################################################################
# Users
################################################################################

@allow(ROLE_CONTRIBUTORS)
def all_users():
    i = ctx.request.input(action='')
    if i.action=='edit':
        u = _get_user(i.id)
        return Template('userform.html', form_title=_('Edit User'), form_action='/api/user/update', redirect='all_users', can_change_role=_can_change_role(u), roles=_get_role_list(min(ROLE_ADMINISTRATORS, u.role_id)), **u)
    return Template('all_users.html', users=_get_users(), ROLE_ADMINISTRATORS=ROLE_ADMINISTRATORS, get_role_name=_get_role_name, can_update_user=_can_update_user, can_delete_user=_can_delete_user, can_change_role=_can_change_role)

@allow(ROLE_ADMINISTRATORS)
def add_user():
    return Template('userform.html', form_title=_('Add User'), form_action='/api/user/create', redirect='all_users', roles=_get_role_list(), role_id=ROLE_SUBSCRIBERS, can_change_role=True)

def _get_users():
    return User.select('where website_id=? order by creation_time desc', ctx.website.id)

def _get_role_name(role_id):
    return ROLE_NAMES.get(role_id, 'Invalid Role')

def _get_user(user_id):
    u = User.get_by_id(user_id)
    if not u or u.website_id != ctx.website.id:
        raise APIValueError('id', 'Invalid user')
    return u

def _can_update_user(user):
    if ctx.user.role_id > ROLE_ADMINISTRATORS:
        # non-admin user can update its own profile:
        return ctx.user.id==user.id
    # admin user:
    return True

def _can_delete_user(user):
    if user.locked:
        return False
    if ctx.user.role_id > ROLE_ADMINISTRATORS:
        # non-admin user cannot delete:
        return False
    # admin user can delete others but not self:
    return ctx.user.id != user.id

def _can_change_role(user):
    if user.locked:
        # cannot change role of default ADMIN:
        return False
    if ctx.user.role_id > ROLE_ADMINISTRATORS:
        # non-admin user cannot change role:
        return False
    return True

@api
@allow(ROLE_ADMINISTRATORS)
@post('/api/user/create')
def api_user_create():
    i = ctx.request.input()
    email = utils.check_email(i.email)
    name = i.name.strip()
    if not name:
        raise APIValueError('name', 'Name cannot be empty.')
    role_id = int(i.role_id)
    if role_id==ROLE_SUPER_ADMINS or role_id not in ROLE_NAMES:
        raise APIValueError('role_id', 'Invalid role.')
    passwd = utils.check_md5_passwd(i.passwd)
    if User.select_one('where email=?', email):
        raise APIValueError('email', 'Email is alreay exist.')
    u = create_user(ctx.website.id, email, passwd, name, role_id)
    u.passwd = '******' # clear password
    return u

@api
@allow(ROLE_ADMINISTRATORS)
@post('/api/user/delete')
def api_user_delete():
    i = ctx.request.input(id='')
    if i.id:
        u = _get_user(i.id)
        if not _can_delete_user(u):
            raise APIPermissionError('Cannot delete locked user.')
        u.delete()
        return True
    raise APIValueError('id', 'User not found.')

@api
@allow(ROLE_CONTRIBUTORS)
@post('/api/user/update')
def api_user_update():
    i = ctx.request.input(id='')
    u = _get_user(i.id)
    if not _can_update_user(u):
        raise APIPermissionError('Cannot update user')
    if 'name' in i:
        name = i.name.strip()
        if not name:
            raise APIValueError('name', 'User name cannot be empty.')
        u.name = name
    if 'role_id' in i:
        role_id = int(i.role_id)
        if role_id<=0 or role_id not in ROLE_NAMES:
            raise APIValueError('role_id', 'Invalid role id')
        if not _can_change_role(u):
            raise APIPermissionError('Cannot change role of user')
        u.role_id = role_id
    if 'passwd' in i:
        passwd = i.passwd
        utils.check_md5_passwd(passwd)
        u.passwd = passwd
    u.update()
    return True

def _get_role_list(starts_from=ROLE_ADMINISTRATORS):
    ids = [r for r in ROLE_NAMES.keys() if r >= starts_from]
    ids.sort()
    return [Dict(id=rid, name=ROLE_NAMES[rid]) for rid in ids]

@allow(ROLE_SUBSCRIBERS)
def profile():
    i = ctx.request.input(info='')
    u = _get_user(ctx.user.id)
    return Template('userform.html', form_title=_('My Profile'), form_action='/api/user/update', can_change_role=_can_change_role(u), redirect='profile?info=ok', roles=_get_role_list(min(ROLE_ADMINISTRATORS, u.role_id)), info=i.info, **u)
