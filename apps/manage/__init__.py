#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

from itranswarp.web import ctx, route, jsonresult

@route('/make_comment')
@jsonresult
def make_comment():
    if ctx.user is None:
        return dict(error='Please sign in first.')
    i = ctx.request.input()
    ref_id = i.ref_id
    user_id = ctx.user.id
    image_url = ctx.user.image_url
    name = ctx.user.name
    content = i.content
    creation_time = time.time(),
    version = 0
