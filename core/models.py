#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
Models for User, Website.
'''

import time, hashlib

from transwarp import db

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

def create_user(website_id, email, passwd, name, role_id, locked=False):
    user = User(
        website_id = website_id, \
        locked = locked,
        name = name,
        role_id = role_id,
        email = email,
        verified = False,
        passwd = passwd,
        image_url = 'http://www.gravatar.com/avatar/%s' % hashlib.md5(str(email)).hexdigest())
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
