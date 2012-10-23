#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' Management of articles, pages. '

import time
import logging

from itranswarp.web import ctx, get, post, route, seeother, Template, jsonresult, Dict, Page, badrequest
from itranswarp import db

from apps.article import internal_add_article, is_category_exist

PAGE_SIZE = 5

def _get_latest_url(menu):
    return '/latest'

def _get_cat_url(menu):
    return '/category/%s' % menu.ref

def _get_page_url(menu):
    return '/page/%s' % menu.ref

def _nav_category_supplies():
    return [(c.id, c.name) for c in _get_categories()]

def _nav_page_supplies():
    return [(p.id, p.name) for p in _get_pages()]

def register_navigation_menus():
    return [
        dict(type='latest_articles', name='Latest', description='Display latest articles on home page.', input_type=None, supplies=None, handler=_get_latest_url),
        dict(type='category', name='Category', description='Display articles belong to the specified category.', input_type='select', input_prompt='Category:', supplies=_nav_category_supplies, handler=_get_cat_url),
        dict(type='page', name='Static Page', description='Display a static page.', input_type='select', input_prompt='Static Page:', supplies=_nav_page_supplies, handler=_get_page_url),
    ]

def register_admin_menus():
    return [
        dict(order=100, title=u'Articles', items=[
            dict(title=u'Articles', role=0, handler='articles'),
            dict(title=u'Add New Article', role=0, handler='add_article'),
            dict(title=u'Categories', role=0, handler='categories'),
        ]),
        dict(order=200, title=u'Pages', items=[
            dict(title=u'Pages', role=0, handler='pages'),
            dict(title=u'Add New Page', role=0, handler='add_page'),
        ]),
    ]

def articles():
    i = ctx.request.input(action='', page='1', category='')
    if i.action=='edit':
        kw = db.select_one('select * from articles where id=?', i.id)
        return Template('templates/articleform.html', categories=_get_categories(), form_title=_('Edit Article'), action='do_edit_article', **kw)
    category = ''
    if i.category:
        category = db.select_one('select id from categories where id=?', i.category).id
    total = db.select_int('select count(id) from articles where category_id=?', i.category) if i.category else db.select_int('select count(id) from articles')
    page = Page(int(i.page), PAGE_SIZE, total)
    selects = 'id,name,category_id,visible,tags,creation_time,modified_time,version'
    al = None
    if category:
        al = db.select('select %s from articles where category_id=? order by creation_time desc limit ?,?' % selects, category, page.offset, page.limit)
    else:
        al = db.select('select %s from articles order by creation_time desc limit ?,?' % selects, page.offset, page.limit)
    return Template('templates/articles.html', articles=al, page=page, category=category, categories=_get_categories())

def _get_pages(selects='id, name'):
    return db.select('select %s from pages order by creation_time desc' % selects)

def pages():
    i = ctx.request.input(action='')
    if i.action=='edit':
        kw = db.select_one('select * from pages where id=?', i.id)
        return Template('templates/articleform.html', static=True, form_title=_('Edit Page'), action='do_edit_page', **kw)
    selects = 'id,name,visible,tags,creation_time,modified_time,version'
    ps = _get_pages(selects=selects)
    return Template('templates/pages.html', pages=ps)

def do_delete_article():
    db.update('delete from articles where id=?', request['id'])
    raise seeother('articles')

def do_delete_page():
    db.update('delete from pages where id=?', request['id'])
    raise seeother('pages')

def add_article():
    return Template('templates/articleform.html', static=False, categories=_get_categories(), form_title=_('Add New Article'), action='do_add_article')

def add_page():
    return Template('templates/articleform.html', static=True, form_title=_('Add New Page'), action='do_add_page')

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
    if not is_category_exist(category_id):
        return dict(error=u'Invalid category', error_field='category_id')
    ar = db.select_one('select version from articles where id=?', i.id)
    db.update_kw('articles', 'id=?', i.id, category_id=category_id, name=name, tags=tags, content=content, modified_time=time.time(), version=ar.version+1)
    return dict(redirect='articles')

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
def do_add_article():
    i = ctx.request.input()
    r = internal_add_article(i.name, i.tags, i.category_id, i.content)
    if 'error' in r:
        return r
    return dict(redirect='articles')

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

def _get_categories():
    cats = db.select('select * from categories order by display_order, name')
    if not cats:
        logging.info('create default uncategorized...')
        current = time.time()
        uncategorized = Dict(id=db.next_str(), name='Uncategorized', description='', locked=True, display_order=0, creation_time=current, modified_time=current, version=0)
        db.insert('categories', **uncategorized)
        cats = [uncategorized]
    return cats

def categories():
    i = ctx.request.input(action='')
    if i.action=='add':
        return Template('templates/categoryform.html', form_title=_('Add New Category'), action='do_add_category')
    if i.action=='edit':
        cat = db.select_one('select * from categories where id=?', i.id)
        return Template('templates/categoryform.html', form_title=_('Edit Category'), action='do_edit_category', **cat)
    return Template('templates/categories.html', categories=_get_categories())

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
    cats = _get_categories()
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

if __name__=='__main__':
    import doctest
    doctest.testmod()
