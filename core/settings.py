#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' Setting module that store settings in database, do not check permissions. '

import time, base64, logging

from transwarp.web import ctx
from transwarp import db

_GLOBAL = '__global__'

KIND_WEBSITE = 'website'

KEY_CUSTOM_HEADER = 'custom_header'
KEY_CUSTOM_FOOTER = 'custom_footer'

class Setting(db.Model):
    '''
    create table setting (
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
    '''

    id = db.StringField(primary_key=True, default=db.next_str)

    website_id = db.StringField(nullable=False, updatable=False)

    kind = db.StringField(nullable=False, updatable=False)

    name = db.StringField(nullable=False, updatable=False)

    value = db.StringField(nullable=False, updatable=False)

    creation_time = db.FloatField(nullable=False, updatable=False, default=time.time)

    version = db.VersionField()

class BigSetting(db.Model):
    '''
    create table bigsetting (
        id varchar(50) not null,
        website_id varchar(50) not null,
        kind varchar(50) not null,
        name varchar(100) not null,
        value text not null,
        creation_time real not null,
        version bigint not null,
        primary key(id),
        index idx_name_website_id(name, website_id),
        index idx_kind_website_id(kind, website_id)
    );
    '''

    id = db.StringField(primary_key=True)

    website_id = db.StringField(nullable=False, updatable=False)

    kind = db.StringField(nullable=False, updatable=False)

    name = db.StringField(nullable=False, updatable=False)

    value = db.StringField(nullable=False)

    creation_time = db.FloatField(nullable=False, updatable=False, default=time.time)

    version = db.VersionField()

def set_text(kind, key, value):
    '''
    Set text by kind, key and value.
    '''
    if len(kind)==0 or len(kind)>50 or len(key)==0 or len(key)>50:
        raise ValueError('invalid setting name.')
    if not isinstance(value, (str, unicode)):
        value = str(value)
    name = '%s:%s' % (kind, key)

    bs = BigSetting( \
        id = db.next_str(), \
        website_id = ctx.website.id, \
        kind = kind, \
        name = name, \
        value = value)
    db.update('delete from bigsetting where name=? and website_id=?', name, ctx.website.id)
    bs.insert()

def get_text(kind, key, default=u''):
    '''
    Get text by kind and key. Return default value u'' if not exist.
    '''
    name = '%s:%s' % (kind, key)
    bs = BigSetting.select_one('where name=? and website_id=?', name, ctx.website.id)
    return bs.value if bs else default

def _get_setting(website_id, kind, key, default=u''):
    name = '%s:%s' % (kind, key)
    s = Setting.select_one('where name=? and website_id=?', name, website_id)
    return s.value if s else default

def get_setting(kind, key, default=u''):
    '''
    Get setting by kind and key. Return default value u'' if not exist.
    '''
    return _get_setting(ctx.website.id, kind, key, default)

def get_global_setting(kind, key, default=u''):
    return _get_setting(_GLOBAL, kind, key, default)

def _get_settings(website_id, kind, removePrefix=True):
    '''
    Return key, value as dict.
    '''
    ss = Setting.select('where kind=? and website_id=?', kind, website_id)
    d = {}
    if removePrefix:
        l = len(kind) + 1
        for s in ss:
            d[s.name[l:]] = s.value
    else:
        for s in L:
            d[s.name] = s.value
    return d

def get_settings(kind, removePrefix=True):
    return _get_settings(ctx.website.id, kind, removePrefix)

def get_global_settings(kind, removePrefix=True):
    return _get_settings(_GLOBAL, kind, removePrefix)

def _set_setting(website_id, kind, key, value):
    '''
    Set setting by kind, key and value.
    '''
    if len(kind)==0 or len(kind)>50 or len(key)==0 or len(key)>50:
        raise ValueError('invalid setting name.')
    if not isinstance(value, (str, unicode)):
        value = str(value)
    name = '%s:%s' % (kind, key)
    s = Setting( \
        website_id = website_id, \
        kind = kind, \
        name = name, \
        value = value)
    s.insert()

@db.with_transaction
def set_setting(kind, key, value):
    _delete_setting(ctx.website.id, kind, key)
    _set_setting(ctx.website.id, kind, key, value)

@db.with_transaction
def set_global_setting(kind, key, value):
    _delete_setting(_GLOBAL, kind, key)
    _set_setting(_GLOBAL, kind, key, value)

def _set_settings(website_id, kind, **kw):
    '''
    set settings by kind and key-value pair.
    '''
    for k, v in kw.iteritems():
        _set_setting(website_id, kind, k, v)

@db.with_transaction
def set_settings(kind, **kw):
    _delete_settings(ctx.website.id, kind)
    _set_settings(ctx.website.id, kind, **kw)

@db.with_transaction
def set_global_settings(kind, **kw):
    _delete_settings(_GLOBAL, kind)
    _set_settings(_GLOBAL, kind, **kw)

def _delete_setting(website_id, kind, key):
    name = '%s:%s' % (kind, key)
    db.update('delete from setting where name=? and website_id=?', name, website_id)

def delete_setting(kind, key):
    _delete_setting(ctx.website.id, kind, key)

def delete_global_setting(kind, key):
    _delete_setting(_GLOBAL, kind, key)

def _delete_settings(website_id, kind):
    db.update('delete from setting where kind=? and website_id=?', kind, website_id)

def delete_settings(kind):
    _delete_settings(ctx.website.id, kind)

DATE_FORMATS = [
    u'%B %d, %Y',
    u'%a, %b %d, %Y',
    u'%b %d, %Y',
    u'%m/%d/%Y',
    u'%d/%m/%Y',
    u'%Y-%m-%d',
    u'%y-%m-%d',
]

TIME_FORMATS = [
    u'%H:%M:%S',
    u'%H:%M',
    u'%I:%M %p',
]

DEFAULT_TIMEZONE = u'+00:00'

TIMEZONES = [
    u'-12:00',
    u'-11:00',
    u'-10:00',
    u'-09:30',
    u'-09:00',
    u'-08:00',
    u'-07:00',
    u'-06:00',
    u'-05:00',
    u'-04:30',
    u'-04:00',
    u'-03:30',
    u'-03:00',
    u'-02:00',
    u'-01:00',
    DEFAULT_TIMEZONE,
    u'+01:00',
    u'+02:00',
    u'+03:00',
    u'+03:30',
    u'+04:00',
    u'+04:30',
    u'+05:00',
    u'+05:30',
    u'+05:45',
    u'+06:00',
    u'+06:30',
    u'+07:00',
    u'+08:00',
    u'+09:00',
    u'+09:30',
    u'+10:00',
    u'+10:30',
    u'+11:00',
    u'+11:30',
    u'+12:00',
    u'+12:45',
    u'+13:00',
    u'+14:00',
]

KIND_SMTP = 'smtp'

SMTP_HOST = 'host'
SMTP_PORT = 'port'
SMTP_USE_TLS = 'use_tls'
SMTP_USERNAME = 'username'
SMTP_PASSWD = 'passwd'
SMTP_FROM_ADDR = 'from_addr'

KEYS_SMTP = set([SMTP_HOST, SMTP_PORT, SMTP_USE_TLS, SMTP_USERNAME, SMTP_PASSWD, SMTP_FROM_ADDR])

def get_smtp_settings():
    d = get_global_settings(KIND_SMTP)
    if not SMTP_HOST in d:
        d[SMTP_HOST] = u'localhost'
    if not SMTP_PORT in d:
        d[SMTP_PORT] = u'0'
    if not SMTP_USE_TLS in d:
        d[SMTP_USE_TLS] = u''
    if not SMTP_USERNAME in d:
        d[SMTP_USERNAME] = u''
    if not SMTP_PASSWD in d:
        d[SMTP_PASSWD] = u''
    if not SMTP_FROM_ADDR in d:
        d[SMTP_FROM_ADDR] = u''
    return d

def set_smtp_settings(**kw):
    d = {}
    for k, v in kw.iteritems():
        if k in KEYS_SMTP:
            d[k] = v
    set_global_settings(KIND_SMTP, **d)
    return d

if __name__=='__main__':
    import doctest
    doctest.testmod()
