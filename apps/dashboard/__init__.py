#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import re, time, uuid, logging, socket, struct, linecache
from datetime import datetime, timedelta

from transwarp.web import ctx, get, post, route, seeother, notfound, UTC, UTC_0, Template, Dict
from transwarp.mail import send_mail
from transwarp import db, task

from core.models import Website, User, create_user, Comment, delete_comment
from core.apis import api
from core.roles import *

name = 'Dashboard'

order = 0

menus = [
    ('-', 'Overview'),
    ('recent_comments', 'Comments'),
]

@allow(ROLE_EDITORS)
def recent_comments():
	cs = Comment.select('where website_id=? order by creation_time desc limit 100', ctx.website.id)
	return Template('recent_comments.html', comments=cs)
