#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
Website navigations.
'''

import time

from transwarp.web import ctx
from transwarp import db

class Navigation(db.Model):
    '''
    create table navigation (
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
    '''

    id = db.StringField(primary_key=True, default=db.next_str)

    website_id = db.StringField(nullable=False, updatable=False)

    display_order = db.IntegerField(nullable=False, default=0)
    kind = db.StringField(nullable=False, updatable=False)
    name = db.StringField(nullable=False)
    description = db.StringField(nullable=False, default='')

    ref = db.StringField(nullable=False, updatable=False, default='')
    url = db.StringField(nullable=False)

    creation_time = db.FloatField(nullable=False, updatable=False, default=time.time)
    modified_time = db.FloatField(nullable=False, default=time.time)
    version = db.VersionField()

    def pre_update(self):
        self.modified_time = time.time()
        self.version = self.version + 1

def get_navigations():
    return Navigation.select('where website_id=? order by display_order, name', ctx.website.id)
