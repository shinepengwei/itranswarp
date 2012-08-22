#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

from itranswarp.web import ctx, get, post, route, jsonrpc, Template, Page
from itranswarp import db
from iwarpsite import ThemeTemplate

@route('/latest')
def latest():
    i = ctx.request.input(page='1')
    page_size = 20
    page_total = db.select_int('select count(id) from articles')
    p = Page(int(i.page), page_size, page_total)
    articles = db.select('select * from articles order by creation_time desc, name limit ?,?', p.offset, p.limit)
    return ThemeTemplate('articles.html', articles=articles, page=p, __active_menu__='latest_articles')

@route('/category/<cat_id>')
def category(cat_id):
    i = ctx.request.input(page='1')
    page_size = 20
    page_total = db.select_int('select count(id) from articles where category_id=?', cat_id)
    p = Page(int(i.page), page_size, page_total)
    articles = db.select('select * from articles where category_id=? order by creation_time desc, name limit ?,?', cat_id, p.offset, p.limit)
    return ThemeTemplate('articles.html', articles=articles, page=p, __active_menu__='category-%s' % cat_id)

@route('/article/<art_id>')
def article(art_id):
    a = db.select_one('select * from articles where id=?', art_id)
    return ThemeTemplate('article.html', article=a, __title__=a.name, __active_menu__='category-%s' % a.category_id)

@route('/page/<page_id>')
def page(page_id):
    p = db.select_one('select * from pages where id=?', page_id)
    return ThemeTemplate('page.html', page=p, __title__=p.name, __active_menu__='page-%s' % page_id)

if __name__=='__main__':
    import doctest
    doctest.testmod()
