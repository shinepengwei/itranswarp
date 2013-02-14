#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' Setting module that store settings in database, do not check permissions. '

import time, base64, logging

from transwarp.web import ctx
from transwarp import db

def get_setting(kind, key, default=u''):
    '''
    Get setting by kind and key. Return default value u'' if not exist.
    '''
    ss = db.select('select value from settings where name=? and website_id=?', '%s:%s' % (kind, key), ctx.website.id)
    if ss:
        v = ss[0].value
        if v:
            return v
    return default

def get_setting_as_int(kind, key, default=0):
    '''
    Get setting as int.
    '''
    return int(get_setting(kind, key, default=u'0'))

def get_setting_as_boolean(kind, key, default=False):
    '''
    Get setting as boolean.
    '''
    return get_setting(kind, key, u'false').lower() == u'true'

def get_settings(kind, removePrefix=True):
    '''
    Return key, value as dict.
    '''
    L = db.select('select name, value from settings where kind=? and website_id=?', kind, ctx.website.id)
    d = {}
    if removePrefix:
        l = len(kind) + 1
        for s in L:
            d[s.name[l:]] = s.value
    else:
        for s in L:
            d[s.name] = s.value
    return d

def set_setting(kind, key, value):
    '''
    Set setting by kind, key and value.
    '''
    if len(kind)==0 or len(kind)>50 or len(key)==0 or len(key)>50:
        raise ValueError('invalid setting name.')
    if not isinstance(value, (str, unicode)):
        value = str(value)
    website_id = ctx.website.id
    name = '%s:%s' % (kind, key)
    settings = dict( \
        id = db.next_str(), \
        website_id = website_id, \
        kind = kind, \
        name = name, \
        value = value, \
        creation_time = time.time(), \
        version = 0)
    db.update('delete from settings where name=? and website_id=?', name, website_id)
    db.insert('settings', **settings)

@db.with_transaction
def set_settings(kind, **kw):
    '''
    set settings by kind and key-value pair.
    '''
    for k, v in kw.iteritems():
        set_setting(kind, k, v)

def delete_setting(kind, key):
    name = '%s:%s' % (kind, key)
    db.update('delete from settings where name=? and website_id=?', name, website_id)

def delete_settings(kind):
    db.update('delete from settings where kind=? and website_id=?', kind, website_id)

KIND_WEBSITE = 'website'

WEBSITE_DESCRIPTION = 'description'
WEBSITE_COPYRIGHT = 'copyright'
WEBSITE_TIMEZONE = 'timezone'
WEBSITE_DATE_FORMAT = 'dateformat'
WEBSITE_TIME_FORMAT = 'timeformat'
WEBSITE_DATETIME_FORMAT = 'datetimeformat'

KEYS_WEBSITE = set([WEBSITE_DESCRIPTION, WEBSITE_COPYRIGHT, WEBSITE_TIMEZONE, WEBSITE_DATE_FORMAT, WEBSITE_TIME_FORMAT])

DATE_FORMATS = [
    '%B %d, %Y',
    '%a, %b %d, %Y',
    '%b %d, %Y',
    '%m/%d/%Y',
    '%d/%m/%Y',
    '%Y-%m-%d',
    '%y-%m-%d',
]

TIME_FORMATS = [
    '%H:%M:%S',
    '%H:%M',
    '%I:%M %p',
]

DEFAULT_TIMEZONE = '+00:00'
TIMEZONES = [
    '-12:00',
    '-11:00',
    '-10:00',
    '-09:30',
    '-09:00',
    '-08:00',
    '-07:00',
    '-06:00',
    '-05:00',
    '-04:30',
    '-04:00',
    '-03:30',
    '-03:00',
    '-02:00',
    '-01:00',
    DEFAULT_TIMEZONE,
    '+01:00',
    '+02:00',
    '+03:00',
    '+03:30',
    '+04:00',
    '+04:30',
    '+05:00',
    '+05:30',
    '+05:45',
    '+06:00',
    '+06:30',
    '+07:00',
    '+08:00',
    '+09:00',
    '+09:30',
    '+10:00',
    '+10:30',
    '+11:00',
    '+11:30',
    '+12:00',
    '+12:45',
    '+13:00',
    '+14:00',
]

def get_website_settings():
    d = get_settings(KIND_WEBSITE)
    if not WEBSITE_DESCRIPTION in d:
        d[WEBSITE_DESCRIPTION] = u''
    if not WEBSITE_COPYRIGHT in d:
        d[WEBSITE_COPYRIGHT] = u''
    if not WEBSITE_TIMEZONE in d:
        d[WEBSITE_TIMEZONE] = DEFAULT_TIMEZONE
    if not WEBSITE_DATE_FORMAT in d:
        d[WEBSITE_DATE_FORMAT] = DATE_FORMATS[0]
    if not WEBSITE_TIME_FORMAT in d:
        d[WEBSITE_TIME_FORMAT] = TIME_FORMATS[0]
    d[WEBSITE_DATETIME_FORMAT] = '%s %s' % (d[WEBSITE_DATE_FORMAT], d[WEBSITE_TIME_FORMAT])
    return d

def set_website_settings(**kw):
    d = {}
    for k, v in kw.iteritems():
        if k in KEYS_WEBSITE:
            d[k] = v
    set_settings(KIND_WEBSITE, **d)
    return d

if __name__=='__main__':
    import doctest
    doctest.testmod()
 