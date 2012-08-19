#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

from itranswarp.web import ctx, get, post, route, jsonrpc, Template
from itranswarp import db

@route('/article')
def index():
    return Template('templates/article/index.html')

@route('/article/category/<cat_id>')
def category(cat_id):
    i = ctx.request.input(page='1')
    page_index = int(i.page)
    page_size = 20
    page_total = db.select_one('select count(id) as num from articles where category_id=?', cat_id).num
    page(page_index, page_size, page_total)

@route('/article/post/<art_id>')
def article(art_id):
    pass

if __name__=='__main__':
    import doctest
    doctest.testmod()
