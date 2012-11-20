#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import time, logging

from transwarp.web import ctx, get, post, route, jsonrpc, seeother, jsonresult, Template, Page, Dict
from transwarp import db

from util import theme, make_comment, get_comments, get_setting_site_name

from apps import menu_group, menu_item

PAGE_SIZE = 20

def export_navigation_menus():
    return [
        dict(
            type='latest_articles',
            name='Latest',
            description='Display latest articles',
            input_type=None,
            supplies=None,
            handler=lambda menu: '/latest'),
        dict(
            type='category',
            name='Category',
            description='Display articles belong to the specified category',
            input_type='select',
            input_prompt='Category',
            supplies=lambda: [(c.id, c.name) for c in _do_get_categories()],
            handler=lambda menu: '/category/%s' % menu.ref),
        dict(
            type='page',
            name='Static Page',
            description='Display a static page',
            input_type='select',
            input_prompt='Static Page',
            supplies=lambda: [(p.id, p.name) for p in _get_pages()],
            handler=lambda menu: '/page/%s' % menu.ref),    
    ]

@get('/api/categories')
@jsonresult
def api_get_categories():
    if ctx.user is None:
        return dict(error='bad authentication')
    return _do_get_categories()

@menu_group('Articles')
@menu_item('Categories', 2)
def categories():
    i = ctx.request.input(action='')
    if i.action=='add':
        return Template('templates/categoryform.html', form_title=_('Add New Category'), action='do_add_category')
    if i.action=='edit':
        cat = db.select_one('select * from categories where id=?', i.id)
        return Template('templates/categoryform.html', form_title=_('Edit Category'), action='do_edit_category', **cat)
    return Template('templates/categories.html', categories=_do_get_categories())

@jsonresult
def do_add_category():
    i = ctx.request.input()
    name = i.name.strip()
    description = i.description.strip()
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    logging.info('create new category...')
    current = time.time()
    cat = Dict(id=db.next_str(), name=name, description=description, locked=False, \
            display_order=db.select_one('select count(id) as num from categories').num, \
            creation_time=current, modified_time=current, version=0)
    db.insert('categories', **cat)
    return dict(redirect='categories')

@jsonresult
def do_edit_category():
    i = ctx.request.input()
    name = i.name.strip()
    description = i.description.strip()
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    logging.info('update category...')
    db.update_kw('categories', 'id=?', i.id, name=name, description=description, modified_time=time.time())
    return dict(redirect='categories')

def do_delete_category():
    cat_id = ctx.request.input().id
    cat = db.select_one('select id,locked from categories where id=?', cat_id)
    if cat.locked:
        raise badrequest()
    uncategorized = db.select_one('select id from categories where locked=?', True)
    db.update('delete from categories where id=?', cat_id)
    db.update('update articles set category_id=? where category_id=?', uncategorized.id, cat_id)
    raise seeother('categories')

def order_categories():
    orders = ctx.request.gets('order')
    cats = _do_get_categories()
    l = len(cats)
    if l!=len(orders):
        raise badrequest()
    odict = dict()
    n = 0
    for o in orders:
        odict[o] = n
        n = n + 1
    with db.transaction():
        for c in cats:
            db.update('update categories set display_order=? where id=?', odict.get(c.id, l), c.id)
    raise seeother('categories')

@post('/api/article/create')
@jsonresult
def api_add_article():
    if ctx.user is None:
        return dict(error='bad authentication')
    i = ctx.request.input(name='', tags='', category_id='', content='', creation_time=None)
    return _do_add_article(i.name, i.tags, i.category_id, ctx.user.id, i.content, i.creation_time)

@menu_group('Articles', 10)
@menu_item('All Articles', 0)
def articles():
    i = ctx.request.input(action='', page='1', category='')
    if i.action=='edit':
        kw = db.select_one('select * from articles where id=?', i.id)
        return Template('templates/articleform.html', categories=_do_get_categories(), form_title=_('Edit Article'), action='do_edit_article', **kw)
    category = ''
    if i.category:
        category = db.select_one('select id from categories where id=?', i.category).id
    total = db.select_int('select count(id) from articles where category_id=?', i.category) if i.category else db.select_int('select count(id) from articles')
    page = Page(int(i.page), PAGE_SIZE, total)
    selects = 'id,name,category_id,visible,user_id,user_name,creation_time,modified_time,version'
    al = None
    if category:
        al = db.select('select %s from articles where category_id=? order by creation_time desc limit ?,?' % selects, category, page.offset, page.limit)
    else:
        al = db.select('select %s from articles order by creation_time desc limit ?,?' % selects, page.offset, page.limit)
    return Template('templates/articles.html', articles=al, page=page, category=category, categories=_do_get_categories())

@menu_group('Articles')
@menu_item('Add New Article', 1)
def add_article():
    return Template('templates/articleform.html', static=False, categories=_do_get_categories(), form_title=_('Add New Article'), action='do_add_article')

@jsonresult
def do_add_article():
    i = ctx.request.input()
    r = _do_add_article(i.name, i.tags, i.category_id, ctx.user.id, i.content)
    if 'error' in r:
        return r
    return dict(redirect='articles')

@jsonresult
def do_edit_article():
    i = ctx.request.input()
    name = i.name.strip()
    tags = i.tags.strip()
    content = i.content.strip()
    category_id = i.category_id
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    if not content:
        return dict(error=u'Content cannot be empty', error_field='')
    if not _is_category_exist(category_id):
        return dict(error=u'Invalid category', error_field='category_id')
    ar = db.select_one('select version from articles where id=?', i.id)
    db.update_kw('articles', 'id=?', i.id, category_id=category_id, name=name, tags=tags, content=content, modified_time=time.time(), version=ar.version+1)
    return dict(redirect='articles')

def do_delete_article():
    db.update('delete from articles where id=?', ctx.request['id'])
    raise seeother('articles')

@menu_group('Pages', 20)
@menu_item('All Pages', 0)
def pages():
    i = ctx.request.input(action='')
    if i.action=='edit':
        kw = db.select_one('select * from pages where id=?', i.id)
        return Template('templates/articleform.html', static=True, form_title=_('Edit Page'), action='do_edit_page', **kw)
    selects = 'id,name,visible,tags,creation_time,modified_time,version'
    ps = _get_pages(selects=selects)
    return Template('templates/pages.html', pages=ps)

def do_delete_page():
    db.update('delete from pages where id=?', ctx.request['id'])
    raise seeother('pages')

@menu_group('Pages')
@menu_item('Add New Page', 1)
def add_page():
    return Template('templates/articleform.html', static=True, form_title=_('Add New Page'), action='do_add_page')

@jsonresult
def do_edit_page():
    i = ctx.request.input()
    name = i.name.strip()
    tags = i.tags.strip()
    content = i.content.strip()
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    if not content:
        return dict(error=u'Content cannot be empty', error_field='')
    pg = db.select_one('select version from pages where id=?', i.id)
    db.update_kw('pages', 'id=?', i.id, name=name, tags=tags, content=content, modified_time=time.time(), version=pg.version+1)
    return dict(redirect='pages')

@jsonresult
def do_add_page():
    i = ctx.request.input()
    name = i.name.strip()
    tags = i.tags.strip()
    content = i.content.strip()
    if not name:
        return dict(error=_('Name cannot be empty'), error_field='name')
    if not content:
        return dict(error=_('Content cannot be empty'), error_field='')
    current = time.time()
    page = dict(id=db.next_str(), visible=True, name=name, tags=tags, content=content, creation_time=current, modified_time=current, version=0)
    db.insert('pages', **page)
    return dict(redirect='pages')

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
    site_name = get_setting_site_name()
    L = [
r'''<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title><![CDATA[%s]]></title>
    <image>
      <link>http://%s/</link>
      <url>http://%s/favicon.ico</url>
    </image>
    <description><![CDATA[%s]]></description>
    <link>http://%s/</link>
    <generator>iTranswarp</generator>
    <copyright><![CDATA[Copyright &copy; %s]]></copyright>
    <pubDate>%s</pubDate>
''']
    articles = db.select('select * from articles order by creation_time desc limit ?', limit)
    for a in articles:
        L.append(r'''    <item>
      <title><![CDATA[%s]]></title>
      <link>http://%s%s</link>
      <guid>http://%s%s</guid>
      <author><![CDATA[%s]]></author>
      <pubDate>%s</pubDate>
      <description><![CDATA[%s]]></description>
      <category />
    </item>
''')
    L.append(r'''  </channel>
</rss>
''')
    return ''.join(L)

#
# private functions
#

def _get_pages(selects='id, name'):
    return db.select('select %s from pages order by creation_time desc' % selects)

def _is_category_exist(category_id):
    cats = db.select('select id from categories where id=?', category_id)
    return len(cats) > 0

def _do_get_categories():
    cats = db.select('select * from categories order by display_order, name')
    if not cats:
        logging.info('create default uncategorized...')
        current = time.time()
        uncategorized = Dict(id=db.next_str(), name='Uncategorized', description='', locked=True, display_order=0, creation_time=current, modified_time=current, version=0)
        db.insert('categories', **uncategorized)
        cats = [uncategorized]
    return cats

def _do_add_article(name, tags, category_id, user_id, content, creation_time=None):
    name = name.strip()
    tags = tags.strip()
    content = content.strip()
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    if not content:
        return dict(error=u'Content cannot be empty', error_field='content')
    if not user_id:
        return dict(errur=u'Missing user_id', error_field='user_id')
    if not _is_category_exist(category_id):
        return dict(error=u'Invalid category', error_field='category_id')
    u = db.select_one('select * from users where id=?', user_id)
    if u.role!=0:
        return dict(error=u'User cannot post article')
    user_name = u.name
    description = 'a short description...'
    current = float(creation_time) if creation_time else time.time()
    article = dict(id=db.next_str(), visible=True, name=name, tags=tags, category_id=category_id, user_id=user_id, user_name=user_name, description=description, content=content, creation_time=current, modified_time=current, version=0)
    db.insert('articles', **article)
    return dict(article=article)

if __name__=='__main__':
    import doctest
    doctest.testmod()
