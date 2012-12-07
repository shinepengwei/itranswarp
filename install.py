#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import re, sys, time, hashlib

from transwarp.web import ctx, get, post, forbidden, Template, jsonresult
from transwarp import db, task

import util

CREATE_TABLES = [
r'''
    create table users (
        id varchar(50) not null,
        locked bool not null,
        name varchar(50) not null,
        role int not null,
        email varchar(50) not null,
        verified bool not null,
        passwd varchar(32) not null,
        image_url varchar(1000) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        unique key uk_email(email),
        index idx_creation_time(creation_time)
    );
''',
r'''
    create table auth_users (
        id varchar(200) not null,
        user_id varchar(50) not null,
        provider varchar(50) not null,
        name varchar(50) not null,
        image_url varchar(1000) not null,
        auth_token varchar(2000) not null,
        expired_time real not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id)
    );
''',
r'''
    create table auth_emails (
        id varchar(50) not null,
        user_id varchar(50) not null,
        email varchar(50) not null,
        auth_token varchar(50) not null,
        expired_time real not null,
        creation_time real not null,
        primary key(id),
        index idx_user_id(user_id),
        index idx_creation_time(creation_time)
    );
''',
r'''
    create table auth_passwd (
        id varchar(50) not null,
        user_id varchar(50) not null,
        auth_token varchar(50) not null,
        expired_time real not null,
        creation_time real not null,
        primary key(id),
        index idx_user_id(user_id),
        index idx_creation_time(creation_time)
    );
''',
r'''
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
''',
r'''
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
        primary key(id),
        index idx_creation_time(creation_time)
    );
''',
r'''
    create table resources (
        id varchar(50) not null,
        name varchar(50) not null,
        description varchar(100) not null,
        width int not null,
        height int not null,
        size bigint not null,
        type varchar(50) not null,
        mime varchar(50) not null,
        metadata varchar(1000) not null,
        uploader varchar(50) not null,
        ref varchar(1000) not null,
        url varchar(1000) not null,
        thumbnail varchar(1000) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        index idx_creation_time(creation_time)
    );
''',
r'''
    create table settings (
        id varchar(50) not null,
        kind varchar(50) not null,
        name varchar(50) not null,
        value varchar(1000) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        unique key uk_name(name),
        index idx_kind(kind)
    );
''',
r'''
    create table texts (
        id varchar(50) not null,
        kind varchar(50) not null,
        name varchar(50) not null,
        value text not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        unique key uk_name(name),
        index idx_kind(kind)
    )
''',
r'''
    create table comments (
        id varchar(50) not null,
        ref_type varchar(50) not null,
        ref_id varchar(50) not null,
        user_id varchar(50) not null,
        image_url varchar(1000) not null,
        name varchar(50) not null,
        content text not null,
        creation_time real not null,
        version bigint not null,
        primary key(id),
        index idx_ref_id(ref_id),
        index idx_user_id(user_id),
        index idx_creation_time(creation_time)
    );
''',
r'''
    create table categories (
        id varchar(50) not null,
        locked bool not null,
        display_order int not null,
        name varchar(50) not null,
        description varchar(100) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        index idx_display_order(display_order)
    );
''',
r'''
    create table articles (
        id varchar(50) not null,
        visible bool not null,
        name varchar(50) not null,
        tags varchar(1000) not null,
        category_id varchar(50) not null,
        user_id varchar(50) not null,
        user_name varchar(50) not null,
        description varchar(1000) not null,
        content mediumtext not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        index idx_category_id(category_id),
        index idx_user_id(user_id),
        index idx_creation_time(creation_time)
    );
''',
r'''
    create table pages (
        id varchar(50) not null,
        visible bool not null,
        name varchar(50) not null,
        tags varchar(1000) not null,
        content mediumtext not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        index idx_creation_time(creation_time)
    );
''',
task.__SQL__,
]

def _check_installed():
    L = db.select('show tables')
    tables = [x.values()[0] for x in L]
    return u'users' in tables

def _check_version():
    v = sys.version_info
    return v[0], v[1]

def _check_redis():
    try:
        from redis import StrictRedis
        return True
    except ImportError:
        pass
    return False

def _check_memcached():
    try:
        import memcache
        return True
    except ImportError:
        pass
    try:
        import pylibmc
        return True
    except ImportError:
        pass
    return False

def _check_pil():
    try:
        import Image
        return True
    except ImportError:
        pass
    try:
        from PIL import Image
        return True
    except ImportError:
        pass
    return False

def _check_system():
    return dict(pil=_check_pil())

@get('/install')
def install():
    if _check_installed():
        raise forbidden()
    return Template('templates/install/welcome.html')

@post('/install')
@jsonresult
def install_user():
    if _check_installed():
        return dict(error='CANNOT install because the web site was already installed.')
    _check_system()
    i = ctx.request.input()
    name = i.name.strip()
    if not name:
        return dict(error='Name cannot be empty', error_field='name')
    email = i.email.strip().lower()
    if not email:
        return dict(error='Email cannot be empty', error_field='email')
    if not util.validate_email(email):
        return dict(error='Bad email address', error_field='email')
    passwd = str(i.passwd)
    m = re.match(r'^[0-9a-f]{32}$', passwd)
    if not m:
        return dict(error='Bad password')
    try:
        for sql in CREATE_TABLES:
            db.update(sql.replace('\n', ' '))
    except BaseException:
        return dict(error='CANNOT create table in MySQL. Please check the privileges of database user!')
    current = time.time()
    user = dict( \
            id=db.next_str(),
            locked=True,
            name=name,
            role=0,
            email=email,
            verified=False,
            passwd=passwd,
            image_url='http://www.gravatar.com/avatar/%s' % hashlib.md5(str(email)).hexdigest(),
            creation_time=current,
            modified_time=current,
            version=0)
    db.insert('users', **user)
    return user
