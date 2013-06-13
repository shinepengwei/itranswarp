#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import re, sys, time, random, hashlib

from transwarp.web import ctx, get, post, forbidden, Template
from transwarp import db, task

from apiexporter import *

CREATE_TABLES = [
r'''
    create table registrations (
        id varchar(50) not null,
        domain varchar(100) not null,
        name varchar(100) not null,
        email varchar(100) not null,
        checked bool not null,
        verified bool not null,
        verification varchar(50) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        unique key uk_domain(domain),
        index idx_creation_time(creation_time)
    );
''',
r'''
    create table websites (
        id varchar(50) not null,
        disabled bool not null,
        domain varchar(100) not null,
        name varchar(100) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        unique key uk_domain(domain),
        index idx_creation_time(creation_time)
    );
''',
r'''
    create table users (
        id varchar(50) not null,
        website_id varchar(50) not null,
        locked bool not null,
        name varchar(100) not null,
        role_id int not null,
        email varchar(100) not null,
        verified bool not null,
        passwd varchar(100) not null,
        image_url varchar(1000) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        unique key uk_email(email),
        index idx_website_id(website_id),
        index idx_creation_time(creation_time)
    );
''',
r''' ???
    create table auth_users (
        id varchar(50) not null,
        website_id varchar(50) not null,
        source_id varchar(50) not null,
        part_id varchar(50) not null,
        locked bool not null,
        name varchar(100) not null,
        image_url varchar(1000) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        unique key uk_website_(website_id, , ),
        index idx_website_id(website_id),
        index idx_creation_time(creation_time)
    );
''',
r'''
    create table navigations (
        id varchar(50) not null,
        website_id varchar(50) not null,
        display_order int not null,
        kind varchar(50) not null,
        name varchar(50) not null,
        description varchar(100) not null,
        ref varchar(1000) not null,
        url varchar(1000) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        index idx_website_id(website_id)
    );
''',
r'''
    create table resources (
        id varchar(50) not null,
        website_id varchar(50) not null,
        ref_id varchar(50) not null,
        ref_type varchar(50) not null,
        deleted bool not null,
        size bigint not null,
        filename varchar(50) not null,
        mime varchar(50) not null,
        ref varchar(1000) not null,
        url varchar(1000) not null,
        creation_time real not null,
        version bigint not null,
        primary key(id),
        index idx_website_id(website_id),
        index idx_ref_id(ref_id)
    );
''',
r'''
    create table attachments (
        id varchar(50) not null,
        website_id varchar(50) not null,
        user_id varchar(50) not null,
        resource_id varchar(50) not null,
        preview_resource_id varchar(50) not null,
        name varchar(50) not null,
        description varchar(100) not null,
        width int not null,
        height int not null,
        size bigint not null,
        mime varchar(50) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        index idx_website_id(website_id)
    );
''',
r'''
    create table settings (
        id varchar(50) not null,
        website_id varchar(50) not null,
        kind varchar(50) not null,
        name varchar(100) not null,
        value varchar(1000) not null,
        creation_time real not null,
        version bigint not null,
        primary key(id),
        index idx_name_website_id(name, website_id),
        index idx_kind_website_id(kind, website_id)
    );
''',
r'''
    create table texts (
        id varchar(50) not null,
        website_id varchar(50) not null,
        kind varchar(50) not null,
        name varchar(50) not null,
        value text not null,
        creation_time real not null,
        version bigint not null,
        primary key(id),
        index idx_name_website_id(name, website_id),
        index idx_kind_website_id(kind, website_id)
    );
''',
r'''
    create table categories (
        id varchar(50) not null,
        website_id varchar(50) not null,
        locked bool not null,
        display_order int not null,
        name varchar(50) not null,
        description varchar(100) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        index idx_website_id(website_id)
    );
''',
r'''
    create table articles (
        id varchar(50) not null,
        website_id varchar(50) not null,
        user_id varchar(50) not null,
        category_id varchar(50) not null,
        draft bool not null,
        user_name varchar(100) not null,
        name varchar(100) not null,
        tags varchar(1000) not null,
        read_count bigint not null,
        summary mediumtext not null,
        content mediumtext not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        index idx_website_id(website_id),
        index idx_category_id(category_id),
        index idx_user_id(user_id)
    );
''',
r'''
    create table category_articles (
        id varchar(50) not null,
        website_id varchar(50) not null,
        category_id varchar(50) not null,
        article_id varchar(50) not null,
        creation_time real not null,
        index idx_website_category_id(website_id, category_id),
    );
''',
r'''
    create table pages (
        id varchar(50) not null,
        website_id varchar(50) not null,
        draft bool not null,
        name varchar(100) not null,
        tags varchar(1000) not null,
        read_count bigint not null,
        content mediumtext not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        index idx_website_id(website_id)
    );
''',
r'''-- not init in db yet
    create table albums (
        id varchar(50) not null,
        website_id varchar(50) not null,
        locked bool not null,
        cover_photo_id varchar(50) not null,
        cover_resource_id varchar(50) not null,
        photo_count int not null,
        display_order int not null,
        name varchar(50) not null,
        description varchar(100) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        index idx_website_id(website_id),
        index idx_display_order(display_order)
    );
''',
r'''
    create table wikis (
        id varchar(50) not null,
        website_id varchar(50) not null,
        name varchar(100) not null,
        description varchar(100) not null,
        content mediumtext not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        index idx_website_id(website_id)
    );
''',
r'''
    create table wiki_pages (
        id varchar(50) not null,
        website_id varchar(50) not null,
        wiki_id varchar(50) not null,
        parent_id varchar(50) not null,
        display_order int not null,
        name varchar(100) not null,
        content mediumtext not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        index idx_website_id(website_id),
        index idx_wiki_id(wiki_id)
    );
''',
r'''-- not init in db yet
    create table photos (
        id varchar(50) not null,
        website_id varchar(50) not null,
        album_id varchar(50) not null,
        origin_resource_id varchar(50) not null,
        large_resource_id varchar(50) not null,
        medium_resource_id varchar(50) not null,
        small_resource_id varchar(50) not null,
        preview_resource_id varchar(50) not null,
        display_order int not null,
        name varchar(50) not null,
        description varchar(100) not null,
        width int not null,
        height int not null,
        size bigint not null,
        geo_lat real not null,
        geo_lng real not null,
        metadata varchar(1000) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        index idx_website_id(website_id),
        index idx_album_id(album_id),
        index idx_display_order(display_order),
        index idx_creation_time(creation_time)
    );
''',
task.__SQL__,
]

def main():
    if raw_input('To install iTranswarp, type Y and press ENTER: ')!='Y':
        print 'Install cancelled.'
        exit(1)
    print 'Prepare to install iTranswarp...'
    try:
        print 'Checking Python version...', _check_version()
        print 'Checking Python Imaging Library...', _check_pil()
        print 'Checking Redis...', _check_redis()
        host = raw_input('Database host (localhost): ')
        port = raw_input('Database port (3306): ')
        user = raw_input('Database user (root): ')
        dbpass = raw_input('Database password: ')
        if port=='':
            port = '3306'
        db.init(db_type='mysql', db_schema='itrans', \
                db_host=host or 'localhost', db_port=int(port), \
                db_user=user or 'root', db_password=dbpass, \
                use_unicode=True, charset='utf8')
        print 'Creating tables . . .',
        for sql in CREATE_TABLES:
            if not sql.startswith('--'):
                db.update(sql)
                print '.',
        print '\nInit database ok.'
        email = raw_input('Super admin email: ').strip().lower()
        passwd = raw_input('Super admin password: ')
        passwd = hashlib.md5(passwd).hexdigest()
        create_website(email, 'iTranswarp', 'localhost')
        if db.select_int('select count(*) from mysql.user where user=?', 'www-data')==0:
            db.update('create user \'www-data\'@\'localhost\' identified by \'www-data\'')
        db.update('grant select,insert,update,delete on itrans.* to \'www-data\'@\'localhost\' identified by \'www-data\'')
        db.update('update users set role_id=0, passwd=? where email=?', passwd, email)
        print 'Install successfully!'
    except Exception, e:
        print 'Install failed:', e.message
        raise

def _check_installed():
    L = db.select('show tables')
    tables = [x.values()[0] for x in L]
    return u'users' in tables

def _check_version():
    v = '%d.%d' % (sys.version_info[0], sys.version_info[1])
    if v=='2.7':
        return v
    raise StandardError('Expected version 2.7 but %s.' % v)

def _check_redis():
    try:
        from redis import StrictRedis
        return 'OK'
    except ImportError:
        pass
    raise StandardError('Redis client is not installed.')

def _check_memcached():
    try:
        import memcache
        return 'OK'
    except ImportError:
        pass
    try:
        import pylibmc
        return 'OK'
    except ImportError:
        pass
    raise StandardError('Memcache client is not installed.')

def _check_pil():
    try:
        import Image
        return 'OK'
    except ImportError:
        pass
    try:
        from PIL import Image
        return 'OK'
    except ImportError:
        pass
    raise StandardError('PIL is not installed.')

def create_user(website_id, email, passwd, name, role_id, locked=False):
    current = time.time()
    user = dict(
        id=db.next_str(),
        website_id=website_id,
        locked=locked,
        name=name,
        role_id=role_id,
        email=email,
        verified=False,
        passwd=passwd,
        image_url='http://www.gravatar.com/avatar/%s' % hashlib.md5(str(email)).hexdigest(),
        creation_time=current,
        modified_time=current,
        version=0)
    db.insert('users', **user)
    return user

def create_website(email, name, domain):
    # generate password:
    L = []
    for i in range(10):
        n = int(random.random() * 62)
        if n < 10:
            L.append(chr(n + 48))
        elif n < 36:
            L.append(chr(n + 55))
        else:
            L.append(chr(n + 61))
    passwd = ''.join(L)
    md5passwd = hashlib.md5(passwd).hexdigest()
    current = time.time()
    website = dict(
            id=db.next_str(),
            disabled=False,
            domain=domain,
            name=name,
            creation_time=current,
            modified_time=current,
            version=0)
    with db.transaction():
        db.insert('websites', **website)
        create_user(website['id'], email, md5passwd, name, ROLE_ADMINISTRATORS, locked=True)
    return passwd

if __name__=='__main__':
    main()
