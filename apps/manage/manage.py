#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
    SQL:

    create table users (
        id varchar(50) not null,
        locked bool not null,
        name varchar(50) not null,
        role int not null,
        email varchar(50) not null,
        passwd varchar(32) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        unique key email(email)
    );

    create table roles (
        id int not null,
        locked bool not null,
        name varchar(50) not null,
        privileges varchar(1000) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id)
    );

    create table menus (
        id varchar(50) not null,
        name varchar(50) not null,
        description varchar(100) not null,
        type varchar(50) not null,
        display_order int not null,
        ref varchar(1000) not null,
        url varchar(1000) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id)
    );

    create table media (
        id varchar(50) not null,
        name varchar(50) not null,
        description varchar(100) not null,
        width int not null,
        height int not null,
        size bigint not null,
        type varchar(50) not null,
        mime varchar(50) not null,
        metadata varchar(1000) not null,
        ref varchar(1000) not null,
        url varchar(1000) not null,
        thumbnail varchar(1000) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id)
    );
'''

import os
import re
import time
import logging

import admin

from itranswarp.web import ctx, get, post, route, seeother, Template, jsonresult, Dict, Page, badrequest
from itranswarp import db

PAGE_SIZE = 5

def _get_custom_url(menu):
    url = menu.ref
    if url.startswith('http://') or url.startswith('https://'):
        return url
    raise ValueError('Bad url.')

def register_navigation_menus():
    return [
        dict(type='custom', name='Custom', description='Display a custom URL.', input_type='text', input_prompt='URL:', supplies='http://', handler=_get_custom_url),
    ]

def register_admin_menus():
    return [
        dict(order=0, title=u'Dashboard', items=[
            dict(title=u'Dashboard', role=0, handler='dashboard'),
            dict(title=u'Updates', role=0, handler='dashboard'),
        ]),
        dict(order=400, title=u'Media', items=[
            dict(title=u'Library', role=0, handler='media'),
            dict(title=u'Add New Media', role=0, handler='add_media'),
        ]),
        dict(order=600, title=u'Users', items=[
            dict(title=u'Users', role=0, handler='users'),
            dict(title=u'Add New User', role=0, handler='add_user'),
            dict(title=u'Roles', role=0, handler='roles'),
        ]),
        dict(order=1000, title=u'Settings', items=[
            dict(title=u'General', role=0, handler='general'),
            dict(title=u'Menus', role=0, handler='menus'),
        ]),
    ]

def dashboard(user, request, response):
    return Template('templates/dashboard.html')

def general(user, request, response):
    return Template('templates/general.html')

def _get_roles():
    roles = db.select('select * from roles order by id')
    if roles:
        return roles
    current = time.time()
    role = Dict(id=0, locked=True, name=u'Administrator', privileges='', creation_time=current, modified_time=current, version=0)
    db.insert('roles', **role)
    return [role]

def roles(user, request, response):
    i = request.input(action='')
    if i.action=='edit':
        role = db.select_one('select * from roles where id=?', i.id)
        return Template('templates/roleform.html', form_title=u'Edit Role', action='do_edit_role', **role)
    if i.action=='add':
        return Template('templates/roleform.html', form_title=u'Add New Role', action='do_add_role')
    if i.action=='delete':
        pass
    return Template('templates/roles.html', roles=_get_roles())

@jsonresult
def do_add_role(user, request, response):
    i = request.input()
    name = i.name.strip()
    # check:
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    privileges = []
    if 'privileges' in request:
        privileges = request.gets('privileges')
    # check:
    max_id = db.select_one('select max(id) as m from roles').m
    current = time.time()
    role = Dict(id=max_id+1, locked=False, name=name, privileges=','.join(privileges), creation_time=current, modified_time=current, version=0)
    db.insert('roles', **role)
    return dict(redirect='roles')

@jsonresult
def do_edit_role(user, request, response):
    i = request.input()
    role_id = int(i.id)
    if role_id==0:
        return dict(error=u'Cannot edit administrator role', error_field='')
    name = i.name.strip()
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    privileges = []
    if 'privileges' in request:
        privileges = request.gets('privileges')
    # check:
    db.update_kw('roles', 'id=?', role_id, name=name, privileges=','.join(privileges), modified_time=time.time())
    return dict(redirect='roles')

def do_delete_role(user, request, response):
    role_id = int(request.input().id)
    if role_id==0:
        raise badrequest()
    db.update('delete from roles where id=?', role_id)
    raise seeother('roles')

def users(user, request, response):
    i = request.input(action='', role='', page='1')
    if i.action=='edit':
        user = db.select_one('select * from users where id=?', i.id)
        return Template('templates/userform.html', roles=_get_roles(), form_title=u'Edit User', action='do_edit_user', **user)
    total = db.select_int('select count(id) from users where role=?', int(i.role)) if i.role else db.select_int('select count(id) from users')
    page = Page(int(i.page), PAGE_SIZE, total)
    users = None
    if i.role:
        users=db.select('select * from users where role=? order by creation_time desc limit ?,?', int(i.role), page.offset, page.limit)
    else:
        users=db.select('select * from users order by creation_time desc limit ?,?', page.offset, page.limit)
    return Template('templates/users.html', roles=_get_roles(), role=i.role, users=users, page=page)

def add_user(user, request, response):
    return Template('templates/userform.html', roles=_get_roles(), form_title=u'Add New User', action='do_add_user')

_RE_PASSWD = re.compile(r'^[0-9a-f]{32}$')

@jsonresult
def do_edit_user(user, request, response):
    i = request.input()
    name = i.name.strip()
    role = int(i.role)
    email = i.email.strip().lower()
    passwd = i.passwd
    # check:
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    if not email:
        return dict(error=u'Email cannot be empty', error_field='email')
    if passwd:
        m = _RE_PASSWD.match(passwd)
        if not m:
            return dict(error=u'Invalid form', error_field='')
    user = db.select_one('select * from users where id=?', i.id)
    updates = {}
    if user.email!=email:
        if db.select('select * from users where email=?', email):
            return dict(error=u'Email was in use by other', error_field='email')
        updates['email'] = email
    if user.role!=role:
        if user.locked:
            return dict(error=u'Cannot change role.', error_field='role')
        updates['role'] = role
    if passwd:
        updates['passwd'] = passwd
    if updates:
        db.update_kw('users', 'id=?', i.id, **updates)
    return dict(redirect='users')

def do_delete_user(user, request, response):
    uid = request['id']
    db.update('delete from users where id=?', uid)
    raise seeother('users')

@jsonresult
def do_add_user(user, request, response):
    i = request.input()
    name = i.name.strip()
    role = int(i.role)
    email = i.email.strip().lower()
    passwd = i.passwd
    # check:
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    if not email:
        return dict(error=u'Email cannot be empty', error_field='email')
    if not passwd:
        return dict(error=u'Password cannot be empty', error_field='passwd1')
    m = _RE_PASSWD.match(passwd)
    if not m:
        return dict(error=u'Invalid form', error_field='')
    # logic:
    if db.select('select id from users where email=?', email):
        return dict(error=u'Email is exist', error_field='email')
    current = time.time()
    user = Dict(id=db.next_str(), name=name, role=role, email=email, passwd=passwd, creation_time=current, modified_time=current, version=0)
    db.insert('users', **user)
    return dict(redirect='users')

def _get_menus():
    menus = db.select('select * from menus order by display_order, name')
    if menus:
        return menus
    current = time.time()
    menu = Dict(id=db.next_str(), name=u'Home', description=u'', type='latest_articles', display_order=0, ref='', url='/', creation_time=current, modified_time=current, version=0)
    db.insert('menus', **menu)
    return [menu]

def _prepare_menus():
    menus = []
    for m in admin.get_navigation_menus():
        menu = Dict(m)
        menu.supplies = m.supplies() if callable(m.supplies) else m.supplies
        menu.input_prompt = m.get('input_prompt', '')
        menus.append(menu)
    return menus

def menus(user, request, response):
    i = request.input(action='')
    if i.action=='edit':
        menu = db.select_one('select * from menus where id=?', i.id)
        return Template('templates/menuform.html', form_title=u'Edit Menu', action='do_edit_menu', menus=_prepare_menus(), **menu)
    if i.action=='add':
        return Template('templates/menuform.html', form_title=u'Add Menu', action='do_add_menu', menus=_prepare_menus())
    return Template('templates/menus.html', menus=_get_menus())

def order_menus(user, request, response):
    orders = request.gets('order')
    menus = _get_menus()
    l = len(menus)
    if l!=len(orders):
        raise badrequest()
    odict = dict()
    n = 0
    for o in orders:
        odict[o] = n
        n = n + 1
    with db.transaction():
        for m in menus:
            db.update('update menus set display_order=? where id=?', odict.get(m.id, l), m.id)
    raise seeother('menus')

@jsonresult
def do_add_menu(user, request, response):
    i = request.input(ref='')
    name = i.name.strip()
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    description = i.description.strip()
    fmenu = admin.get_navigation_menu(i.type)
    ref = i.ref
    url = fmenu.handler(Dict(name=name, description=description, type=i.type, ref=ref))
    count = db.select_one('select count(id) as num from menus').num
    current = time.time()
    menu = Dict(id=db.next_str(), name=name, description=description, type=i.type, display_order=count, ref=ref, url=url, creation_time=current, modified_time=current, version=0)
    db.insert('menus', **menu)
    return dict(redirect='menus')

@jsonresult
def do_edit_menu(user, request, response):
    i = request.input(ref='')
    menu = db.select_one('select * from menus where id=?', i.id)
    kw = dict()
    name = i.name.strip()
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    if name!=menu.name:
        kw['name'] = name
    description = i.description.strip()
    if description!=menu.description:
        kw['description'] = description
    fmenu = admin.get_navigation_menu(i.type)
    ref = i.ref
    url = fmenu.handler(Dict(name=name, description=description, type=i.type, ref=ref))
    kw['type'] = i.type
    kw['ref'] = ref
    kw['url'] = url
    kw['modified_time'] = time.time()
    db.update_kw('menus', 'id=?', i.id, **kw)
    return dict(redirect='menus')

def do_delete_menu(user, request, response):
    menu = db.select_one('select id, url from menus where id=?', request.input().id)
    db.update('delete from menus where id=?', menu.id)
    raise seeother('menus')

def media(user, request, response):
    media = db.select('select * from media order by creation_time desc')
    return Template('templates/media.html', media=media)

def add_media(user, request, response):
    return Template('templates/mediaform.html', form_title=u'Add Media', action='do_add_media')

_MIME_ALIAS = {
    '.jpeg': '.jpg',
    '.jpe': '.jpg',
    '.html': '.htm',
    '.mpa': '.mp3',
    '.mp2': '.mp3',
    '.dot': '.doc',
    '.xlt': '.xls',
    '.xla': '.xls',
    '.pot': '.ppt',
    '.pps': '.ppt',
    '.ppa': '.ppt',
    '.dotx': '.docx',
    '.xlsx': '.docx',
    '.xltx': '.docx',
    '.pptx': '.docx',
    '.potx': '.docx',
    '.ppsx': '.docx',
}

_MIME = {
    '.png': ('image', 'image/png'),
    '.gif': ('image', 'image/gif'),
    '.jpg': ('image', 'image/jpeg'),
    '.ico': ('image', 'image/x-icon'),

    '.mp3': ('audio', 'audio/mpeg'),
    '.aac': ('audio', 'audio/aac'),

    '.flv': ('video', 'video/x-flv'),
    '.mp4': ('video', 'video/mp4'),

    '.txt': ('text', 'text/plain'),
    '.htm': ('text', 'text/html'),
    '.xml': ('text', 'text/xml'),

    '.gz': ('application', 'application/x-gzip'),
    '.tar': ('application', 'application/x-tar'),
    '.pdf': ('application', 'application/pdf'),
    '.zip': ('application', 'application/zip'),
    '.rar': ('application', 'application/x-rar-compressed'),
    '.swf': ('application', 'application/x-shockwave-flash'),

    '.doc': ('application', 'application/msword'),
    '.xls': ('application', 'application/vnd.ms-excel'),
    '.ppt': ('application', 'application/vnd.ms-powerpoint'),

    '.docx': ('application', 'application/vnd.openxmlformats'),

    '.key': ('application', 'application/vnd.apple.keynote'),
    '.pages': ('application', 'application/vnd.apple.pages'),
    '.numbers': ('application', 'application/vnd.apple.numbers'),
}

def _guess_mime(fname):
    ext = os.path.splitext(fname)[1].lower()
    ext = _MIME_ALIAS.get(ext, ext)
    return _MIME.get(ext, ('binary', 'application/octet-stream'))

@jsonresult
def do_add_media(user, request, response):
    i = request.input(name='', description='')
    description = i.description.strip()
    f = i.file
    fname = f.filename
    name = i.name.strip()
    if not name:
        name = os.path.splitext(fname)[0]
    ftype, mime = _guess_mime(fname)
    current = time.time()
    m = dict( \
            id = db.next_str(), \
            name = name, \
            description = description, \
            width = 0, \
            height = 0, \
            size = 0, \
            type = ftype, \
            mime = mime, \
            metadata = '', \
            ref = '', \
            url = '', \
            thumbnail = '', \
            creation_time = current, \
            modified_time = current, \
            version = 0 \
    )
    from apps.manage.uploader import localuploader
    uploader = localuploader.Uploader(document_root=ctx.document_root)
    r = uploader.upload(fname, ftype, f.file)
    for k in r:
        if k in m:
            m[k] = r[k]
    db.insert('media', **m)
    return dict(redirect='media', filelink=r['url'])

def do_delete_media(user, request, response):
    mid = request['id']
    m = db.select_one('select * from media where id=?', mid)
    from apps.manage.uploader import localuploader
    uploader = localuploader.Uploader(document_root=ctx.document_root)
    uploader.delete(m.ref)
    db.update('delete from media where id=?', mid)
    raise seeother('media')

@jsonresult
def do_get_media(user, request, response):
    i = request.input(type='', page_index='1', page_size='20')

if __name__=='__main__':
    import doctest
    doctest.testmod()
