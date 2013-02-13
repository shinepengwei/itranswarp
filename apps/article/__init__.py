#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import os, time, logging, mimetypes

from transwarp.web import ctx, get, post, route, jsonrpc, seeother, jsonresult, Template, Page, Dict
from transwarp import db

from apiexporter import *
from plugin import store
import thumbnail

from util import theme

from apps import menu

################################################################################
# Categories
################################################################################

def get_category(category_id):
    cat = db.select_one('select * from categories where id=?', category_id)
    if cat.website_id != ctx.website.id:
        raise APIPermissionError('cannot get category that does not belong to current website.')
    return cat

def categories():
    i = ctx.request.input(action='')
    if i.action=='add':
        return Template('templates/categoryform.html', form_title='Add new category', form_action='/api/categories/create')
    if i.action=='edit':
        cat = get_category(i.id)
        return Template('templates/categoryform.html', form_title='Edit category', form_action='/api/categories/update', **cat)
    if i.action=='delete':
        api_delete_category()
        raise seeother('categories')
    return Template('templates/categories.html', categories=get_categories())

def get_categories():
    cats = db.select('select * from categories where website_id=? order by display_order, name', ctx.website.id)
    if not cats:
        logging.info('create default uncategorized...')
        current = time.time()
        uncategorized = Dict(id=db.next_str(), \
            website_id=ctx.website.id, \
            name='Uncategorized', description='', \
            locked=True, display_order=0, \
            creation_time=current, modified_time=current, \
            version=0)
        db.insert('categories', **uncategorized)
        cats = [uncategorized]
    return cats

@api(role=ROLE_GUESTS)
@get('/api/categories/list')
def api_list_categories():
    return get_categories()

@api(role=ROLE_GUESTS)
@get('/api/categories/get')
def api_get_category():
    i = ctx.request.input(id='')
    if not i.id:
        raise APIValueError('id', 'id cannot be empty')
    return get_category(i.id)

@api(role=ROLE_ADMINISTRATORS)
@post('/api/categories/create')
def api_create_category():
    i = ctx.request.input(name='', description='')
    name = i.name.strip()
    description = i.description.strip()
    if not name:
        raise APIValueError('name', 'name cannot be empty')
    num = len(get_categories())
    if num >= 100:
        raise APIError('operation:failed', 'category', 'cannot create new category for the maximum number of categories was reached.')
    logging.info('create new category...')
    current = time.time()
    cat = Dict(id=db.next_str(), \
            website_id=ctx.user.website_id, \
            name=name, description=description, \
            locked=False, display_order=num, \
            creation_time=current, modified_time=current, \
            version=0)
    db.insert('categories', **cat)
    return cat

@api(role=ROLE_ADMINISTRATORS)
@post('/api/categories/update')
def api_update_category():
    i = ctx.request.input(id='', name='', description='')
    name = i.name.strip()
    description = i.description.strip()
    if not i.id:
        raise APIValueError('id', 'id cannot be empty')
    if not name:
        raise APIValueError('name', 'name cannot be empty')
    logging.info('update category...')
    cat = get_category(i.id)
    db.update_kw('categories', 'id=?', i.id, name=name, description=description, modified_time=time.time())
    return True

@api(role=ROLE_ADMINISTRATORS)
@post('/api/categories/delete')
def api_delete_category():
    i = ctx.request.input(id='')
    if not i.id:
        raise APIValueError('id', 'id cannot be empty')
    cat = get_category(i.id)
    if cat.locked:
        raise APIError('operation:failed', 'category', 'cannot delete category that is locked.')
    uncategorized = db.select_one('select id from categories where website_id=? and locked=?', ctx.website.id, True)
    db.update('delete from categories where id=?', i.id)
    db.update('update articles set category_id=? where category_id=?', uncategorized.id, i.id)
    return True

@api(role=ROLE_ADMINISTRATORS)
@post('/api/categories/sort')
def api_sort_category():
    ids = ctx.request.gets('id')
    cats = get_categories()
    l = len(cats)
    if l != len(ids):
        raise APIValueError('id', 'bad id list.')
    sets = set([c.id for c in cats])
    odict = dict()
    n = 0
    for o in ids:
        if not o in sets:
            raise APIValueError('id', 'some id was invalid.')
        odict[o] = n
        n = n + 1
    with db.transaction():
        for c in cats:
            db.update('update categories set display_order=? where id=?', odict.get(c.id, l), c.id)
    return True

################################################################################
# Articles
################################################################################

def articles():
    i = ctx.request.input(action='', page='1')
    if i.action=='edit':
        article = get_article(i.id)
        return Template('templates/articleform.html', form_title='Edit article', form_action='/api/articles/update', categories=get_categories(), static=False, **article)
    if i.action=='delete':
        api_delete_article()
        raise seeother('articles')
    page = int(i.page)
    previous = page > 1
    next = False
    articles = get_articles(page, 51, published_only=False)
    if len(articles)==51:
        articles = articles[:-1]
        next = True
    return Template('templates/articles.html', page=page, previous=previous, next=next, categories=get_categories(), articles=articles)

def add_article():
    return Template('templates/articleform.html', form_title='Add new article', form_action='/api/articles/create', categories=get_categories(), static=False)

def _format_tags(tags):
    if tags:
        return u','.join([t.strip() for t in tags.split(u',')])
    return u''

def get_article(article_id):
    article = db.select_one('select * from articles where id=?', article_id)
    if article.website_id != ctx.website.id:
        raise APIPermissionError('cannot get article that does not belong to current website.')
    if article.draft and (ctx.user is None or ctx.user.role_id==ROLE_GUESTS):
        raise APIPermissionError('cannot get draft article.')
    return article

def count_articles(published_only=True):
    if published_only:
        return db.select_int('select count(id) from articles where website_id=? and draft=?', ctx.website.id, False)
    return db.select_int('select count(id) from articles where website_id=?', ctx.website.id)

def get_articles(page=1, limit=20, published_only=True):
    offset = (page - 1) * limit
    if published_only:
        return db.select('select * from articles where website_id=? and draft=? order by id desc limit ?,?', ctx.website.id, False, offset, limit)
    return db.select('select * from articles where website_id=? order by id desc limit ?,?', ctx.website.id, offset, limit)

@api(role=ROLE_GUESTS)
@get('/api/articles/get')
def api_get_article():
    i = ctx.request.input(id='')
    if not i.id:
        raise APIValueError('id', 'id cannot be empty')
    return get_article(i.id)

@api(role=ROLE_GUESTS)
@get('/api/articles/count')
def api_count_articles():
    '''
    Get article number.

    Args:
        published_only: true for counting published articles, false for counting all articles. default to true.
    '''
    i = ctx.request.input(published_only='true')
    published_only = ctx.user is None or ctx.user.role_id==ROLE_GUESTS or boolean(i.published_only)
    return count_articles(published_only)

@api(role=ROLE_GUESTS)
@get('/api/articles/list')
def api_list_articles():
    i = ctx.request.input(page='1', size='20', published_only='true')
    page = int(i.page)
    size = int(i.size)
    if page < 1:
        raise APIValueError('page', 'page invalid.')
    if size < 1 or size > 100:
        raise APIValueError('size', 'size invalid.')
    published_only = ctx.user is None or ctx.user.role_id==ROLE_GUESTS or boolean(i.published_only)
    articles = get_articles(page=page, limit=size+1, published_only=published_only)
    if len(articles)==size+1:
        return dict(articles=articles[:-1], page=page, previous=page>2, next=True)
    return dict(articles=articles, page=page, previous=page>2, next=False)

@api(role=ROLE_CONTRIBUTORS)
@post('/api/articles/create')
def api_create_article():
    i = ctx.request.input(category_id='', name='', tags='', content='', draft='')
    name = i.name.strip()
    content = i.content.strip()
    category_id = i.category_id
    if not name:
        raise APIValueError('name', 'name cannot be empty.')
    if not content:
        raise APIValueError('content', 'content cannot be empty.')
    if not category_id:
        raise APIValueError('category_id', 'category_id cannot be empty.')
    cat = get_category(category_id)
    draft = True
    if ctx.user.role_id < ROLE_CONTRIBUTORS:
        draft = True if i.draft else False
    current = time.time()
    article = Dict( \
        id=db.next_str(), \
        website_id=ctx.website.id, \
        user_id=ctx.user.id, \
        user_name=ctx.user.name, \
        category_id=category_id, \
        draft=draft, \
        name=name, \
        tags=_format_tags(i.tags), \
        description='', \
        content=content, \
        creation_time=current, \
        modified_time=current, \
        version=0)
    db.insert('articles', **article)
    return article

@api(role=ROLE_CONTRIBUTORS)
@post('/api/articles/update')
def api_update_article():
    time.sleep(1);
    i = ctx.request.input(id='')
    if not i.id:
        raise APIValueError('id', 'id cannot be empty.')
    article = get_article(i.id)
    kw = {}
    if 'name' in i:
        name = i.name.strip()
        if not name:
            raise APIValueError('name', 'name cannot be empty.')
        kw['name'] = name
    if 'content' in i:
        content = i.content.strip()
        if not content:
            raise APIValueError('content', 'content cannot be empty.')
        kw['content'] = content
    if 'category_id' in i:
        category_id = i.category_id
        cat = get_category(category_id)
        kw['category_id'] = category_id
    if 'tags' in i:
        kw['tags'] = _format_tags(i.tags)
    if 'draft' in i:
        draft = boolean(i.draft)
        if not draft and ctx.user.role_id==ROLE_CONTRIBUTORS:
            raise APIPermissionError('cannot publish article for contributors.')
        kw['draft'] = draft
    if kw:
        kw['modified_time'] = time.time()
        db.update_kw('articles', 'id=?', i.id, **kw)
    return True

@api(role=ROLE_AUTHORS)
@post('/api/articles/delete')
def api_delete_article():
    i = ctx.request.input(id='')
    if not i.id:
        raise APIValueError('id', 'id cannot be empty.')
    article = get_article(i.id)
    if ctx.user.role_id == ROLE_AUTHORS and article.user_id != ctx.user.id:
        raise APIPermissionError('cannot delete article that belong to other')
    db.update('delete from articles where id=?', i.id)
    return True

################################################################################
# Pages
################################################################################

def pages():
    i = ctx.request.input(action='')
    if i.action=='edit':
        page = get_page(i.id)
        return Template('/templates/articleform.html', form_title='Edit Page', form_action='/api/pages/update', static=True, **page)
    if i.action=='delete':
        api_delete_page()
        raise seeother('pages')
    return Template('templates/pages.html', pages=get_pages())

def add_page():
    return Template('templates/articleform.html', form_title='Add New Page', form_action='/api/pages/create', static=True)

def get_page(page_id):
    page = db.select_one('select * from pages where id=?', page_id)
    if page.website_id != ctx.website.id:
        raise APIPermissionError('cannot get page that does not belong to current website.')
    if page.draft and (ctx.user is None or ctx.user.role_id==ROLE_GUESTS):
        raise APIPermissionError('cannot get draft page.')
    return page

def get_pages(published_only=True):
    if published_only:
        return db.select('select * from pages where website_id=? and draft=? order by id desc', ctx.website.id, False)
    return db.select('select * from pages where website_id=? order by id desc', ctx.website.id)

@api(role=ROLE_GUESTS)
@get('/api/pages/list')
def api_list_pages():
    i = ctx.request.input(page='1', size='20', published_only='true')
    page = int(i.page)
    size = int(i.size)
    if page < 1:
        raise APIValueError('page', 'page invalid.')
    if size < 1 or size > 100:
        raise APIValueError('size', 'size invalid.')
    published_only = ctx.user is None or ctx.user.role_id==ROLE_GUESTS or boolean(i.published_only)
    return get_pages(published_only)

@api(role=ROLE_GUESTS)
@get('/api/pages/get')
def api_get_page():
    i = ctx.request.input(id='')
    if not i.id:
        raise APIValueError('id', 'id cannot be empty')
    return get_page(i.id)

@api(role=ROLE_ADMINISTRATORS)
@post('/api/pages/create')
def api_create_page():
    i = ctx.request.input(name='', tags='', content='', draft='false')
    name = i.name.strip()
    content = i.content.strip()
    if not name:
        raise APIValueError('name', 'name cannot be empty.')
    if not content:
        raise APIValueError('content', 'content cannot be empty.')
    draft = boolean(i.draft)
    current = time.time()
    page = Dict( \
        id=db.next_str(), \
        website_id=ctx.website.id, \
        draft=draft, \
        name=name, \
        tags=_format_tags(i.tags), \
        content=content, \
        creation_time=current, \
        modified_time=current, \
        version=0)
    db.insert('pages', **page)
    return page

@api(role=ROLE_ADMINISTRATORS)
@post('/api/pages/update')
def api_update_page():
    i = ctx.request.input(id='')
    if not i.id:
        raise APIValueError('id', 'id cannot be empty.')
    page = get_page(i.id)
    kw = {}
    if 'name' in i:
        name = i.name.strip()
        if not name:
            raise APIValueError('name', 'name cannot be empty.')
        kw['name'] = name
    if 'content' in i:
        content = i.content.strip()
        if not content:
            raise APIValueError('content', 'content cannot be empty.')
        kw['content'] = content
    if 'tags' in i:
        kw['tags'] = _format_tags(i.tags)
    if 'draft' in i:
        kw['draft'] = boolean(i.draft)
    if kw:
        kw['modified_time'] = time.time()
        db.update_kw('pages', 'id=?', i.id, **kw)
    return True

@api(role=ROLE_ADMINISTRATORS)
@post('/api/pages/delete')
def api_delete_page():
    i = ctx.request.input(id='')
    if not i.id:
        raise APIValueError('id', 'id cannot be empty.')
    page = get_page(i.id)
    db.update('delete from pages where id=?', i.id)
    return True

################################################################################
# Attachments
################################################################################

def delete_attachment(attr_id):
    att = db.select_one('select * from attachments where id=?', attr_id)
    if att.website_id != ctx.website.id:
        raise APIPermissionError('Cannot delete resource that not belong to current website.')
    # FIXME: check user_id:
    store.delete_resources(attr_id)
    db.update('delete from attachments where id=?', attr_id)

@api(role=ROLE_CONTRIBUTORS)
@post('/api/attachments/upload')
def api_upload_attachment():
    i = ctx.request.input(name='', description='', link='')
    name = i.name.strip()
    description = i.description.strip()
    f = i.file
    ref_type = 'attachment'
    ref_id = db.next_str()
    fcontent = f.file.read()
    filename = f.filename
    fext = os.path.splitext(filename)[1]

    preview = None
    w = h = 0
    res = store.upload_file(ref_type, ref_id, filename, fcontent)
    if res.mime.startswith('image/'):
        try:
            logging.info('it seems an image was uploaded, so try to get size...')
            im = thumbnail.as_image(fcontent)
            w, h = im.size[0], im.size[1]
            logging.info('size got: %d x %d' % (w, h))
            if w > 160 or h > 120:
                logging.info('creating thumbnail for uploaded image (size %d x %d)...' % (w, h))
                tn = thumbnail.create_thumbnail(im, 160, 120)
                pw, ph, pcontent = tn['width'], tn['height'], tn['data']
                logging.info('thumbnail was created successfully with size %d x %d.' % (w, h))
                preview = store.upload_file(ref_type, ref_id, filename, fcontent)
            else:
                logging.info('No need to create thumbnail.')
                preview = res
        except:
            logging.exception('error when creating thumbnail.')

    current = time.time()
    attr = Dict( \
        id = ref_id, \
        website_id = ctx.website.id, \
        user_id = ctx.user.id, \
        resource_id = res.id, \
        preview_resource_id = preview and preview.id or '', \
        name = name, \
        description = description, \
        width = w, \
        height = h, \
        size = res.size, \
        mime = res.mime, \
        creation_time = current, \
        modified_time = current, \
        version = 0)
    db.insert('attachments', **attr)
    if i.link==u't':
        attr.filelink = '/api/resources/url?id=%s' % attr.resource_id
    return attr

def add_attachment():
    return Template('templates/attachmentform.html')

def attachments():
    i = ctx.request.input(action='', page='1', size='20')
    if i.action=='delete':
        delete_attachment(i.id)
        raise seeother('attachments')
    page = int(i.page)
    size = int(i.size)
    num = db.select_int('select count(id) from attachments where website_id=?', ctx.website.id)
    if page < 1:
        raise APIValueError('page', 'page invalid.')
    if size < 1 or size > 100:
        raise APIValueError('size', 'size invalid.')
    offset = (page - 1) * size
    atts = db.select('select * from attachments where website_id=? order by id desc limit ?,?', ctx.website.id, offset, size+1)
    next = False
    if len(atts)>size:
        atts = atts[:-1]
        next = True
    return Template('templates/attachments.html', attachments=atts, page=page, previous=page>2, next=next)

s=r'''



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
    return dict(articles=articles, page=p, __active_menu__='category%s latest_articles' % cat_id)

@route('/article/<art_id>')
@theme('article.html')
def article(art_id):
    a = db.select_one('select * from articles where id=?', art_id)
    cs = get_comments_desc(art_id, 21)
    next_comment_id = None
    if len(cs)==21:
        next_comment_id = cs[-1].id
        cs = cs[:-1]
    return dict(article=a, comments=cs, next_comment_id=next_comment_id, __title__=a.name, __active_menu__='category%s latest_articles' % a.category_id)

@get('/article/<art_id>/comments')
@jsonresult
def get_comments(art_id):
    after_id = ctx.request.input(next_comment_id=None).next_comment_id
    next_id = None
    cs = get_comments_desc(art_id, 21, after_id)
    if len(cs)==21:
        next_id = cs[-2].id
        cs = cs[:-1]
    return dict(next_comment_id=next_id, comments=cs)

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
    c = make_comment('article', a.id, user, u''.join(L))
    raise seeother('/article/%s#comments' % i.article_id)

@route('/page/<page_id>')
@theme('page.html')
def page(page_id):
    p = db.select_one('select * from pages where id=?', page_id)
    return dict(page=p, __title__=p.name, __active_menu__='page%s' % page_id)
'''

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

if __name__=='__main__':
    import doctest
    doctest.testmod()
