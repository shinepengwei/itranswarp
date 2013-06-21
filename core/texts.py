#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' store big text. '

import time

from transwarp.web import ctx
from transwarp import db

class BigText(db.Model):
    '''
    create table bigtext (
        id varchar(50) not null,
        website_id varchar(50) not null,
        ref_id varchar(50) not null,
        value text not null,
        creation_time real not null,
        primary key(id),
        index idx_creation_time(creation_time),
        index idx_ref_id(ref_id)
    );
    '''

    id = db.StringField(primary_key=True)

    website_id = db.StringField(nullable=False, updatable=False)

    ref_id = db.StringField(nullable=False, updatable=False)

    value = db.StringField(nullable=False)

    creation_time = db.FloatField(nullable=False, updatable=False, default=time.time)

def get(ref_id, default=''):
    t = BigText.select_one('where ref_id=? order by creation_time desc limit ?', ref_id, 1)
    if t:
        return t.value
    return default

def set(ref_id, content_id, text):
    t = BigText(id=content_id, website_id=ctx.website.id, ref_id=ref_id, value=text)
    t.insert()

def delete(ref_id):
    db.update('delete from bigtext where ref_id=?', ref_id)
