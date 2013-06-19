#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' store big text. '

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
    texts = BigText.select_one('where ref_id=? order by creation_time desc limit ?', ref_id, 1)
    if texts:
        return texts[0].value
    return default

def set(ref_id, text):
    t = BigText(website_id=ctx.website.id, ref_id=ref_id, value=text)
    t.insert()
