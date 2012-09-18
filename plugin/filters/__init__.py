#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

from itranswarp.web import ctx
from itranswarp import db
import util

def load_user():
    ctx.user = None
    uid = util.extract_session_cookie()
    if uid:
        users = db.select('select * from users where id=?', uid)
        if users:
            ctx.user = users[0]
