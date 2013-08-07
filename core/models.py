#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
Models for User, Website.
'''

import time, uuid, random, hashlib

from transwarp.web import ctx
from transwarp import db

from core.apis import APIValueError, APIPermissionError

class Website(db.Model):
    '''
    create table website (
        id varchar(50) not null,
        disabled bool not null,
        domain varchar(100) not null,
        timezone varchar(50) not null,
        dateformat varchar(50) not null,
        timeformat varchar(50) not null,
        name varchar(100) not null,
        description varchar(100) not null,
        copyright varchar(100) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        unique key uk_domain(domain),
        index idx_creation_time(creation_time)
    );
    '''

    id = db.StringField(primary_key=True, default=db.next_str)

    disabled = db.BooleanField(nullable=False, default=False)

    domain = db.StringField(nullable=False)

    timezone = db.StringField(nullable=False)

    dateformat = db.StringField(nullable=False)

    timeformat = db.StringField(nullable=False)

    name = db.StringField(nullable=False)

    description = db.StringField(nullable=False)

    copyright = db.StringField(nullable=False)

    creation_time = db.FloatField(nullable=False, updatable=False, default=time.time)

    modified_time = db.FloatField(nullable=False, default=time.time)

    version = db.VersionField()

    @property
    def datetimeformat(self):
        return '%s %s' % (self.dateformat, self.timeformat)

    def pre_update(self):
        self.modified_time = time.time()
        self.version = self.version + 1

class Comment(db.Model):
    '''
    create table comment (
        id varchar(50) not null,

        website_id varchar(50) not null,
        ref_id varchar(50) not null,
        ref_type varchar(50) not null,

        user_id varchar(50) not null,
        user_name varchar(100) not null,
        user_image_url varchar(1000) not null,

        content varchar(2000) not null,

        creation_time real not null,
        version bigint not null,

        primary key(id),
        index idx_website_ref_id(website_id, ref_id)
    );
    '''

    id = db.StringField(primary_key=True, default=db.next_str)

    website_id = db.StringField(nullable=False, updatable=False)
    ref_id = db.StringField(nullable=False, updatable=False)
    ref_type = db.StringField(nullable=False, updatable=False)

    user_id = db.StringField(nullable=False, updatable=False)
    user_name = db.StringField(nullable=False, updatable=False)
    user_image_url = db.StringField(nullable=False, updatable=False)

    content = db.StringField(nullable=False, updatable=False)

    creation_time = db.FloatField(nullable=False, updatable=False, default=time.time)
    version = db.VersionField()

def get_comments(ref_id, next_id=None, limit=20):
    if next_id:
        return Comment.select('where ref_id=? and id<? order by id desc limit ?', ref_id, next_id, limit)
    return Comment.select('where ref_id=? order by id desc limit ?', ref_id, limit)

def _encodehtml(s):
    return s.replace(u' ', u'&nbsp;').replace(u'<', u'&lt;').replace(u'>', u'&gt;')

def _safehtml(text):
    return u'<p>%s</p>' % u'</p><p>'.join([_encodehtml(s) for s in text.split('\n')])

def create_comment(ref_type, ref_id, content):
    if len(content)>1000:
        raise APIValueError('content', 'exceeded maximun length: 1000.')
    u = ctx.user
    c = Comment(website_id=ctx.website.id, user_id=u.id, user_name=u.name, user_image_url=u.image_url, ref_id=ref_id, ref_type=ref_type, content=_safehtml(content))
    c.insert()
    return c

def delete_comments(ref_id):
    db.update('delete from comment where website_id=? and ref_id=?', ctx.website.id, ref_id)

def delete_comment(cid):
    c = Comment.get_by_id(cid)
    if c.website_id==ctx.website.id:
        c.delete()
    else:
        raise APIPermissionError('Cannot delete comment not belong to this website.')

class User(db.Model):
    '''
    create table user (
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
    '''

    id = db.StringField(primary_key=True, default=db.next_str)

    website_id = db.StringField(nullable=False, updatable=False)

    locked = db.BooleanField(nullable=False, updatable=False, default=False)

    name = db.StringField(nullable=False)

    role_id = db.IntegerField(nullable=False)

    email = db.StringField(nullable=False, updatable=False)

    verified = db.BooleanField(nullable=False, default=False)

    passwd = db.StringField(nullable=False)

    image_url = db.StringField(nullable=False)

    creation_time = db.FloatField(nullable=False, updatable=False, default=time.time)

    modified_time = db.FloatField(nullable=False, default=time.time)

    version = db.VersionField()

    def pre_update(self):
        self.modified_time = time.time()
        self.version = self.version + 1

class Random(db.Model):
    '''
    create table random (
        id varchar(50) not null,
        website_id varchar(50) not null,
        value varchar(100) not null,
        expires_time real not null,
        primary key(id),
        unique key uk_value(value),
        index idx_expires_time(expires_time)
    );
    '''

    id = db.StringField(primary_key=True, default=db.next_str)

    website_id = db.StringField(nullable=False, updatable=False)

    value = db.StringField(nullable=False, updatable=False, default=lambda: '%s%s' % (uuid.uuid4().hex, random.randrange(100000000,999999999)))

    expires_time = db.FloatField(nullable=False, updatable=False, default=lambda: time.time() + 600)

def create_random():
    r = Random(website_id=ctx.website.id)
    r.insert()
    return r.value

def verify_random(value, delete=True):
    r = Random.select_one('where value=?', value)
    if r:
        if delete:
            r.delete()
        return True
    raise APIError('verify', 'random', 'invalid random value.')

def create_user(website_id, email, passwd, name, role_id, image_url=None, locked=False):
    user = User(
        website_id = website_id, \
        locked = locked,
        name = name,
        role_id = role_id,
        email = email,
        verified = False,
        passwd = passwd,
        image_url = image_url if image_url else 'http://www.gravatar.com/avatar/%s' % hashlib.md5(str(email)).hexdigest())
    user.insert()
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
    website = Website(
            id = db.next_str(),
            domain = domain,
            name = name)
    with db.transaction():
        website.insert()
        create_user(website.id, email, md5passwd, 'admin', ROLE_ADMINISTRATORS, locked=True)
    return passwd
