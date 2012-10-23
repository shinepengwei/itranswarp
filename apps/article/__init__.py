#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import time

from itranswarp.web import ctx, get, post, route, jsonrpc, seeother, jsonresult, Template, Page
from itranswarp import db

from util import theme, make_comment, get_comments

def is_category_exist(category_id):
    cats = db.select('select id from categories where id=?', category_id)
    return len(cats) > 0

def internal_add_article(name, tags, category_id, content):
    name = name.strip()
    tags = tags.strip()
    content = content.strip()
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    if not content:
        return dict(error=u'Content cannot be empty', error_field='content')
    if not is_category_exist(category_id):
        return dict(error=u'Invalid category', error_field='category_id')
    current = time.time()
    article = dict(id=db.next_str(), visible=True, name=name, tags=tags, category_id=category_id, content=content, creation_time=current, modified_time=current, version=0)
    db.insert('articles', **article)
    return dict(article=article)

@jsonresult
@post('/api/article')
def api_add_article():
    auth = ctx.request.header['Authorization']
    # check auth...
    i = ctx.request.input(name='', tags='', category_id='', content='')
    r = internal_add_article(i.name, i.tags, i.category_id, i.content)
    if 'error' in r:
        return r
    return r

@route('/latest')
@theme('articles.html')
def latest():
    i = ctx.request.input(page='1')
    page_size = 20
    page_total = db.select_int('select count(id) from articles')
    p = Page(int(i.page), page_size, page_total)
    articles = db.select('select * from articles order by creation_time desc limit ?,?', p.offset, p.limit)
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
    cs, has_next = get_comments(art_id, 1)
    return dict(article=a, comments=cs, next_page=2 if has_next else 0, __title__=a.name, __active_menu__='category%s' % a.category_id)

@post('/article/comment')
def comment():
    user = ctx.user
    if user is None:
        return dict(error='Please sign in first')
    i = ctx.request.input(content='')
    c = i.content.strip()
    if not c:
        return dict(error='Comment cannot be empty')
    a = db.select_one('select id from articles where id=?', i.article_id)
    L = [u'<p>%s</p>' % p.replace(u'\r', u'').replace(u'&', u'&amp;').replace(u' ', u'&nbsp;').replace(u'<', u'&lt;').replace(u'>', u'&gt;') for p in c.split(u'\n')]
    c = make_comment(a.id, user, u''.join(L))
    raise seeother('/article/%s#comments' % i.article_id)

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
