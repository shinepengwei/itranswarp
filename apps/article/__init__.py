#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

from itranswarp.web import ctx, get, post, route, jsonrpc, Template, Page
from itranswarp import db

from util import theme

@route('/latest')
@theme('articles.html')
def latest():
    i = ctx.request.input(page='1')
    page_size = 20
    page_total = db.select_int('select count(id) from articles')
    p = Page(int(i.page), page_size, page_total)
    articles = db.select('select * from articles order by creation_time desc, name limit ?,?', p.offset, p.limit)
    return dict(articles=articles, page=p, __active_menu__='latest_articles')

@route('/category/<cat_id>')
@theme('articles.html')
def category(cat_id):
    i = ctx.request.input(page='1')
    page_size = 20
    page_total = db.select_int('select count(id) from articles where category_id=?', cat_id)
    p = Page(int(i.page), page_size, page_total)
    articles = db.select('select * from articles where category_id=? order by creation_time desc, name limit ?,?', cat_id, p.offset, p.limit)
    return dict(articles=articles, page=p, __active_menu__='category%s' % cat_id)

@route('/article/<art_id>')
@theme('article.html')
def article(art_id):
    a = db.select_one('select * from articles where id=?', art_id)
    return dict(article=a, __title__=a.name, __active_menu__='category%s' % a.category_id)

@route('/page/<page_id>')
@theme('page.html')
def page(page_id):
    p = db.select_one('select * from pages where id=?', page_id)
    return dict(page=p, __title__=p.name, __active_menu__='page%s' % page_id)

@get('/feed')
def rss():
    ctx.response.content_type = 'application/rss+xml'
    limit = 20
    L = [r'''<?xml version="1.0"?>
<rss version="2.0">
<channel>
<title>%s</title>
<image>
<link>http://%s/</link>
<url>http://%s/favicon.ico</url>
</image>
<description>%s</description>
<link>http://%s/</link>
<generator>iTranswarp</generator>
<copyright><![CDATA[Copyright &copy; %s]]></copyright>
<pubDate>%s</pubDate>''']
    articles = db.select('select * from articles order by creation_time desc limit ?', limit)
    for a in articles:
        L.append(r'''<item>
<title><![CDATA[%s]]></title>
<link>http://%s%s</link>
<guid>http://%s%s</guid>
<author><![CDATA[%s]]></author>
<pubDate>%s</pubDate>
<description><![CDATA[%s]]></description>
<category />
</item>''')
    L.append(r'</channel></rss>')
    return ''.join(L)

if __name__=='__main__':
    import doctest
    doctest.testmod()
