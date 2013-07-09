#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import os, time, logging, mimetypes
from datetime import datetime

from transwarp.web import ctx, get, post, route, seeother, badrequest, Template, Dict, UTC_0
from transwarp import db

from core.apis import *
from core.roles import *
from core.models import get_comments, create_comment

from core import utils, thumbnails, texts

from plugins import stores

from themes import theme

name = 'Article'

order = 10

menus = (
    ('-', 'Articles'),
    ('all_articles', 'Articles'),
    ('add_article', 'Add Article'),
    ('-', 'Categories'),
    ('all_categories', 'Categories'),
    ('add_category', 'Add Category'),
    ('-', 'Pages'),
    ('all_pages', 'Pages'),
    ('add_page', 'Add Page'),
    ('-', 'Attachment'),
    ('all_attachments', 'Attachments'),
    ('add_attachment', 'Add Attachment'),
)

navigations = (
        dict(
            key='category',
            input='select',
            prompt='Category',
            description='Show articles of category',
            fn_get_url=lambda value: '/category/%s' % value,
            fn_get_options=lambda: [(cat.id, cat.name) for cat in _get_categories()]
        ),
        dict(
            key='page',
            input='select',
            prompt='Page',
            description='Show a static page',
            fn_get_url=lambda value: '/page/%s' % value,
            fn_get_options=lambda: [(page.id, page.name) for page in _get_pages()]
        ),
)

class Category(db.Model):
    '''
    create table category (
        id varchar(50) not null,

        website_id varchar(50) not null,

        display_order int not null,
        name varchar(50) not null,
        description varchar(100) not null,

        creation_time real not null,
        modified_time real not null,
        version bigint not null,

        primary key(id),
        index idx_website_id(website_id)
    );
    '''

    id = db.StringField(primary_key=True, default=db.next_str)

    website_id = db.StringField(nullable=False, updatable=False)

    display_order = db.IntegerField(nullable=False, default=0)
    name = db.StringField(nullable=False)
    description = db.StringField(nullable=False, default='')

    creation_time = db.FloatField(nullable=False, updatable=False, default=time.time)
    modified_time = db.FloatField(nullable=False, default=time.time)
    version = db.VersionField()

    def pre_update(self):
        self.modified_time = time.time()
        self.version = self.version + 1

class Article(db.Model):
    '''
    create table article (
        id varchar(50) not null,

        website_id varchar(50) not null,
        user_id varchar(50) not null,

        cover_type varchar(50) not null,
        cover_id varchar(50) not null,
        content_id varchar(50) not null,

        draft bool not null,
        user_name varchar(100) not null,
        name varchar(100) not null,
        tags varchar(1000) not null,
        summary varchar(1000) not null,

        publish_time real not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,

        primary key(id),
        index idx_website_id(website_id),
        index idx_publish_time(publish_time),
        index idx_user_id(user_id)
    );
    '''

    id = db.StringField(primary_key=True)

    website_id = db.StringField(nullable=False, updatable=False)
    user_id = db.StringField(nullable=False, updatable=False)

    cover_type = db.StringField(nullable=False, default='')
    cover_id = db.StringField(nullable=False, default='')
    content_id = db.StringField(nullable=False)

    draft = db.BooleanField(nullable=False)
    user_name = db.StringField(nullable=False)
    name = db.StringField(nullable=False)
    tags = db.StringField(nullable=False, default='')
    summary = db.StringField(nullable=False)

    publish_time = db.FloatField(nullable=False, default=0.0)
    creation_time = db.FloatField(nullable=False, updatable=False, default=time.time)
    modified_time = db.FloatField(nullable=False, default=time.time)
    version = db.VersionField()

    def pre_insert(self):
        self.creation_time = time.time() - 10
        if 'publish_time' not in self or self.publish_time <= 0.1:
            self.publish_time = self.creation_time

    def pre_update(self):
        self.modified_time = time.time()
        self.version = self.version + 1

class Article_Category(db.Model):
    '''
    create table article_category (
        id varchar(50) not null,

        website_id varchar(50) not null,
        article_id varchar(50) not null,
        category_id varchar(50) not null,
        article_category varchar(100) not null,

        publish_time real not null,
        creation_time real not null,
        version bigint not null,

        primary key(id),
        unique key uk_article_category(article_category),
        index idx_website_id(website_id),
        index idx_article_id(article_id),
        index idx_category_id(category_id)
    );
    '''

    id = db.StringField(primary_key=True, default=db.next_str)

    website_id = db.StringField(nullable=False, updatable=False)

    article_id = db.StringField(nullable=False, updatable=False)
    category_id = db.StringField(nullable=False, updatable=False)

    article_category = db.StringField(nullable=False, updatable=False)

    publish_time = db.FloatField(nullable=False, updatable=False)
    creation_time = db.FloatField(nullable=False, updatable=False)
    version = db.VersionField()

    def __init__(self, article, category):
        super(Article_Category, self).__init__()
        self.website_id = article.website_id
        self.article_id = article.id
        self.category_id = category.id
        self.article_category = '%s%s' % (self.article_id, self.category_id)
        self.publish_time = article.publish_time
        self.creation_time = article.creation_time

class Page(db.Model):
    '''
    create table page (
        id varchar(50) not null,
        website_id varchar(50) not null,

        cover_type varchar(50) not null,
        cover_id varchar(50) not null,
        content_id varchar(50) not null,

        draft bool not null,
        name varchar(100) not null,
        tags varchar(1000) not null,

        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        index idx_website_id(website_id)
    );
    '''

    id = db.StringField(primary_key=True)

    website_id = db.StringField(nullable=False, updatable=False)

    cover_type = db.StringField(nullable=False, default='')
    cover_id = db.StringField(nullable=False, default='')
    content_id = db.StringField(nullable=False)

    draft = db.BooleanField(nullable=False, default=False)
    name = db.StringField(nullable=False)
    tags = db.StringField(nullable=False, default='')

    creation_time = db.FloatField(nullable=False, updatable=False, default=time.time)
    modified_time = db.FloatField(nullable=False, default=time.time)
    version = db.VersionField()

    def pre_update(self):
        self.modified_time = time.time()
        self.version = self.version + 1

class Attachment(db.Model):
    '''
    create table attachment (
        id varchar(50) not null,

        website_id varchar(50) not null,
        user_id varchar(50) not null,

        resource_id varchar(50) not null,
        preview_resource_id varchar(50) not null,

        name varchar(50) not null,
        description varchar(100) not null,

        width int not null,
        height int not null,
        size bigint not null,

        mime varchar(50) not null,

        creation_time real not null,
        modified_time real not null,
        version bigint not null,

        primary key(id),
        index idx_website_id(website_id),
        index idx_creation_time(creation_time)
    );
    '''

    id = db.StringField(primary_key=True)

    website_id = db.StringField(nullable=False, updatable=False)
    user_id = db.StringField(nullable=False, updatable=False)

    resource_id = db.StringField(nullable=False, updatable=False)
    preview_resource_id = db.StringField(nullable=False, updatable=False)

    name = db.StringField(nullable=False)
    description = db.StringField(nullable=False, default='')

    width = db.IntegerField(nullable=False, default=0)
    height = db.IntegerField(nullable=False, default=0)
    size = db.IntegerField(nullable=False)

    mime = db.StringField(nullable=False)

    creation_time = db.FloatField(nullable=False, updatable=False, default=time.time)
    modified_time = db.FloatField(nullable=False, default=time.time)
    version = db.VersionField()

    def pre_update(self):
        self.modified_time = time.time()
        self.version = self.version + 1

def _summary(content):
    return utils.html2summary(utils.markdown2html(content), 500)

def _format_tags(tags):
    if tags:
        return u','.join([t.strip() for t in tags.split(u',')])
    return u''

################################################################################
# Categories
################################################################################

@get('/category/<cid>')
@theme('category.html')
def web_category(cid):
    return _web_category_p(cid, '1')

@get('/category/<cid>/<p>')
@theme('category.html')
def web_category_page(cid, p):
    return _web_category_p(cid, p)

@get('/articles/recent')
@theme('category.html')
def web_recent():
    limit = 20
    categories = _get_categories()
    articles = Article.select('where website_id=? and publish_time<? order by publish_time desc limit ?', ctx.website.id, time.time(), limit)
    return dict(articles=articles, categories=categories)

def _web_category_p(cid, p):
    page_index = int(p)
    if p < 1:
        raise badrequest()
    category = _get_category(cid)
    categories = _get_categories()
    count = _get_articles_count(cid)
    page = Pagination(count, page_index)
    articles = _get_articles(page, category_id=cid)
    return dict(category=category, categories=categories, articles=articles, page=page)

@get('/article/<aid>')
@theme('article.html')
def _web_article(aid):
    article = _get_full_article(aid)
    categories = _get_categories()
    return dict(categories=categories, article=article, comments=get_comments(ref_id=aid))

def _get_category(category_id):
    cat = Category.get_by_id(category_id)
    if not cat:
        raise APIValueError('id', 'Invalid category id.')
    if cat.website_id != ctx.website.id:
        raise APIPermissionError('cannot get category that does not belong to current website.')
    return cat

def _get_categories(return_dict=False):
    cats = Category.select('where website_id=? order by display_order, name', ctx.website.id)
    if return_dict:
        return dict(((c.id, c) for c in cats))
    return cats

@api
@get('/api/categories')
def api_categoris_list():
    return _get_categories()

@api
@get('/api/categories/<cid>')
def api_category_get(cid):
    if not cid:
        raise APIValueError('id', 'id cannot be empty')
    return _get_category(cid)

@api
@allow(ROLE_EDITORS)
@post('/api/categories/create')
def api_category_create():
    i = ctx.request.input(name='', description='')
    if not i.name.strip():
        raise APIValueError('name', 'Name cannot be empty.')
    cats = _get_categories()
    count = len(cats)
    if count >= 100:
        raise APIValueError('', 'Too many categories.')
    max_disp = 0 if count == 0 else cats[-1].display_order + 1
    c = Category(website_id=ctx.website.id, name=i.name.strip(), description=i.description.strip(), display_order=max_disp)
    c.insert()
    return c

@api
@allow(ROLE_ADMINISTRATORS)
@post('/api/categories/<cid>/update')
def api_category_update(cid):
    i = ctx.request.input(name='', description='')
    name = i.name.strip()
    description = i.description.strip()
    if not cid:
        raise APIValueError('id', 'id cannot be empty')
    if not name:
        raise APIValueError('name', 'name cannot be empty')
    logging.info('update category...')
    cat = _get_category(cid)
    cat.name = name
    cat.description = description
    cat.update()
    return True

@api
@allow(ROLE_ADMINISTRATORS)
@post('/api/categories/<cid>/delete')
def api_category_delete(cid):
    if not cid:
        raise APIValueError('id', 'id is empty.')
    c = _get_category(cid)
    c.delete()
    db.update('delete from article_category where category_id=?', cid)
    return True

@api
@allow(ROLE_ADMINISTRATORS)
@post('/api/categories/sort')
def api_sort_categories():
    ids = ctx.request.gets('id')
    cats = _get_categories()
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
            db.update('update category set display_order=?, version=version + 1 where id=?', odict.get(c.id, l), c.id)
    return True

@allow(ROLE_SUBSCRIBERS)
def all_categories():
    i = ctx.request.input(action='')
    if i.action=='edit':
        c = _get_category(i.id)
        return Template('categoryform.html', form_title=_('Edit Category'), form_action='/api/categories/%s/update' % c.id, **c)
    return Template('categories.html', categories=_get_categories())

@allow(ROLE_ADMINISTRATORS)
def add_category():
    return Template('categoryform.html', form_title=_('Add Category'), form_action='/api/categories/create')

################################################################################
# Articles
################################################################################

def _get_article_categories(article_id):
    acs = db.select('select category_id from article_category where article_id=?', article_id)
    return [ac.category_id for ac in acs]

def _get_full_article(article_id):
    a = _get_article(article_id)
    a.content = utils.markdown2html(texts.get(a.id))
    return a

def _get_article(article_id):
    a = Article.get_by_id(article_id)
    if a:
        if a.website_id==ctx.website.id:
            a.categories = _get_article_categories(article_id)
            return a
        raise APIPermissionError('cannot get article.')
    raise APIValueError('id', 'article not found.')

def _get_articles_count(category_id=''):
    if category_id:
        cat = _get_category(category_id)
        return Article_Category.count('where category_id=?', category_id)
    return Article.count('where website_id=?', ctx.website.id)

def _get_articles(page, category_id=''):
    if category_id:
        cat = _get_category(category_id)
        acs = db.select('select article_id from article_category where category_id=? order by publish_time desc limit ?,?', category_id, page.offset, page.limit)
        return [_get_article(ac.article_id) for ac in acs]
    ats = db.select('select id from article where website_id=? order by publish_time desc limit ?,?', ctx.website.id, page.offset, page.limit)
    return [_get_article(a.id) for a in ats]

@api
@get('/api/articles')
def api_articles_list():
    i = ctx.request.input(category_id='', page='1')
    page_index = int(i.page)
    category_id = i.category_id
    category = _get_category(category_id) if category_id else None
    count = _get_articles_count(category_id)
    page = Pagination(count, page_index)
    # FIXME: return page:
    return _get_articles(page, category_id)

@allow(ROLE_CONTRIBUTORS)
def all_articles():
    i = ctx.request.input(action='', id='', category_id='', page='1')
    if i.action=='edit':
        a = _get_article(i.id)
        a.content = texts.get(a.id)
        return Template('articleform.html', form_title=_('Edit Article'), form_action='/api/articles/%s/update' % a.id, redirect='all_articles', static=False, category_list=_get_categories(), can_publish=_can_publish_article(), **a)
    page_index = int(i.page)
    category_id = i.category_id
    category = _get_category(category_id) if category_id else None
    count = _get_articles_count(category_id)
    page = Pagination(count, page_index)
    articles = _get_articles(page, category_id)
    return Template('all_articles.html', articles=articles, page=page, category=category, category_list=_get_categories(), can_create=_can_create_article(), can_edit=_can_edit_article, can_delete=_can_delete_article, can_publish=_can_publish_article())

@api
@get('/api/articles/<aid>')
def api_article_get(aid):
    if not aid:
        raise APIValueError('id', 'id is empty.')
    return _get_article(aid)

@api
@post('/api/articles/<aid>/comments/create')
def api_article_comment_create(aid):
    if not aid:
        raise APIValueError('id', 'id is empty.')
    if not ctx.user:
        raise APIPermissionError('user not sign in.')
    i = ctx.request.input(content='')
    content = i.content.strip()
    if not content:
        raise APIValueError('content', 'content is empty.')
    a = _get_article(aid)
    return create_comment(aid, content)

def _can_create_article():
    return ctx.user.role_id <= ROLE_CONTRIBUTORS

def _can_delete_article(article):
    if ctx.user.role_id <= ROLE_EDITORS:
        return True
    if article.user_id == ctx.user.id and article.draft:
        return True
    return False

def _can_edit_article(article):
    if ctx.user.role_id <= ROLE_EDITORS:
        return True
    if article.user_id == ctx.user.id and article.draft:
        return True
    return False

def _can_publish_article():
    return ctx.user.role_id <= ROLE_EDITORS

@api
@allow(ROLE_CONTRIBUTORS)
@post('/api/articles/create')
def api_article_create():
    i = ctx.request.input(name='', content='', tags='', draft='')
    if not _can_create_article():
        raise APIPermissionError('cannot create article.')

    name = i.name.strip()
    content = i.content
    if not name:
        raise APIValueError('name', 'name cannot be empty.')
    if not content:
        raise APIValueError('content', 'content cannot be empty.')
    summary = _summary(content)
    draft = i.draft.strip().lower() == 'true' and _can_publish_article()
    cat_ids = i.gets('category_id')
    cat_dict = _get_categories(return_dict=True)
    category_list = []
    for cid in cat_ids:
        if not cid in cat_dict:
            raise APIValueError('category_id', 'bad category.')
        category_list.append(cat_dict[cid])
    ref_id = db.next_str()
    content_id = db.next_str()
    article = Article( \
        id=ref_id, \
        website_id=ctx.website.id, \
        content_id=content_id, \
        user_id=ctx.user.id, \
        user_name=ctx.user.name, \
        draft=draft, \
        name=name, \
        summary=summary, \
        tags=_format_tags(i.tags))
    with db.transaction():
        article.insert()
        texts.set(article.id, content_id, content)
        # update Article_Category:
        db.update('delete from article_category where article_id=?', article.id)
        if category_list:
            for category in category_list:
                Article_Category(article, category).insert()
    return article

@api
@allow(ROLE_CONTRIBUTORS)
@post('/api/articles/<aid>/update')
def api_article_update(aid):
    i = ctx.request.input()
    if not aid:
        raise APIValueError('id', 'id is empty.')
    article = _get_article(aid)
    if not _can_edit_article(article):
        raise APIPermissionError('cannot edit article.')
    if 'draft' in i:
        draft = i.draft.strip().lower()=='true'
        if draft==False and not _can_publish_article():
            raise APIPermissionError('cannot publish article')
        article.draft = draft
    if 'name' in i:
        name = i.name.strip()
        if not name:
            raise APIValueError('name', 'name cannot be empty.')
        article.name = name
    content = None
    if 'content' in i:
        content = i.content
        if not content:
            raise APIValueError('content', 'content cannot be empty.')
    if 'tags' in i:
        article.tags = _format_tags(i.tags)
    # get category:
    cat_ids = i.gets('category_id')
    cat_dict = _get_categories(return_dict=True)
    category_list = []
    for cid in cat_ids:
        if not cid in cat_dict:
            raise APIValueError('category_id', 'bad category.')
        category_list.append(cat_dict[cid])
    with db.transaction():
        if content:
            content_id = db.next_str()
            article.content_id = content_id
            article.summary = _summary(content)
            texts.set(article.id, content_id, content)
        article.update()
        if cat_ids:
            # update Article_Category:
            db.update('delete from article_category where article_id=?', article.id)
            if category_list:
                for category in category_list:
                    Article_Category(article, category).insert()
    return dict(id=aid)

@api
@allow(ROLE_AUTHORS)
@post('/api/articles/<aid>/delete')
def api_article_delete(aid):
    if not aid:
        raise APIValueError('id', 'id is empty.')
    article = _get_article(aid)
    if not _can_delete_article(article):
        raise APIPermissionError('cannot delete article.')
    with db.transaction():
        article.delete()
        texts.delete(aid)
        # update Article_Category:
        db.update('delete from article_category where article_id=?', aid)
    return True

@allow(ROLE_CONTRIBUTORS)
def add_article():
    return Template('articleform.html', form_title=_('Add Article'), form_action='/api/articles/create', redirect='all_articles', static=False, categories=frozenset(), category_list=_get_categories(), can_publish=_can_publish_article())

################################################################################
# Pages
################################################################################

def _get_page(page_id):
    p = Page.get_by_id(page_id)
    if p:
        if p.website_id==ctx.website.id:
            return p
        raise APIPermissionError('cannot get page.')
    raise APIValueError('id', 'page not found.')

def _get_pages():
    return Page.select('where website_id=? order by id desc', ctx.website.id)

@api
@get('/api/pages')
def api_page_list():
    return _get_pages()

@api
@get('/api/pages/<pid>')
def api_page_get(pid):
    if not pid:
        raise APIValueError('id', 'id is empty.')
    return _get_page(pid)

@api
@allow(ROLE_ADMINISTRATORS)
@post('/api/pages/create')
def api_page_create():
    i = ctx.request.input(name='', tags='', content='', draft='false')
    name = i.name.strip()
    content = i.content
    if not name:
        raise APIValueError('name', 'name cannot be empty.')
    if not content:
        raise APIValueError('content', 'content cannot be empty.')
    draft = i.draft.lower() == 'true'
    ref_id = db.next_str()
    content_id = db.next_str()
    page = Page( \
        id=ref_id, \
        website_id=ctx.website.id, \
        content_id=content_id, \
        draft=draft, \
        name=name, \
        tags=_format_tags(i.tags))
    page.insert()
    texts.set(page.id, content_id, content)
    return page

@api
@allow(ROLE_ADMINISTRATORS)
@post('/api/pages/<pid>/delete')
def api_page_delete(pid):
    if not pid:
        raise APIValueError('id', 'id is empty.')
    p = _get_page(pid)
    p.delete()
    texts.delete(pid)
    return True

@api
@allow(ROLE_ADMINISTRATORS)
@post('/api/pages/<pid>/update')
def api_page_update(pid):
    i = ctx.request.input()
    if not pid:
        raise APIValueError('id', 'id is empty.')
    p = _get_page(pid)
    if 'name' in i:
        name = i.name.strip()
        if not name:
            raise APIValueError('name', 'name cannot be empty.')
        p.name = name
    content = None
    if 'content' in i:
        content = i.content
        if not content:
            raise APIValueError('content', 'content cannot be empty.')
    if 'tags' in i:
        p.tags = _format_tags(i.tags)
    if content:
        content_id = db.next_str()
        p.content_id = content_id
        texts.set(p.id, content_id, content)
    p.update()
    return True

@allow(ROLE_SUBSCRIBERS)
def all_pages():
    i = ctx.request.input(action='', id='')
    if i.action=='edit':
        p = _get_page(i.id)
        p.content = texts.get(p.id)
        return Template('articleform.html', form_title=_('Edit Page'), form_action='/api/pages/%s/update' % p.id, redirect='all_pages', static=True, **p)
    return Template('all_pages.html', pages=_get_pages())

@allow(ROLE_ADMINISTRATORS)
def add_page():
    return Template('articleform.html', form_title=_('Add Page'), form_action='/api/pages/create', redirect='all_pages', static=True)

################################################################################
# Attachments
################################################################################

@allow(ROLE_SUBSCRIBERS)
def all_attachments():
    i = ctx.request.input(action='', page='1')
    if i.action=='delete':
        delete_attachment(i.id)
        raise seeother('all_attachments')
    page_index = int(i.page)
    num = Attachment.count('where website_id=?', ctx.website.id)
    page = Pagination(num, page_index)
    atts = Attachment.select('where website_id=? order by id desc limit ?,?', ctx.website.id, page.offset, page.limit)
    return Template('all_attachments.html', attachments=atts, page=page)

@allow(ROLE_CONTRIBUTORS)
def add_attachment():
    return Template('attachmentform.html')

@api
@allow(ROLE_CONTRIBUTORS)
@post('/api/attachments/create')
def api_attachment_upload():
    i = ctx.request.input(name='', description='', return_link='', file=None)
    if not i.file:
        raise APIValueError('file', 'Invalid multipart post.')
    name = i.name.strip()
    description = i.description.strip()
    f = i.file
    ref_type = 'attachment'
    ref_id = db.next_str()
    fcontent = f.file.read()
    filename = f.filename
    fext = os.path.splitext(filename)[1]
    if not name:
        name = os.path.splitext(os.path.split(filename)[1])[0]

    preview = None
    w = h = 0
    res = stores.upload_file(ref_type, ref_id, filename, fcontent)
    if res.mime.startswith('image/'):
        try:
            logging.info('it seems an image was uploaded, so try to get size...')
            im = thumbnails.as_image(fcontent)
            w, h = im.size[0], im.size[1]
            logging.info('size got: %d x %d' % (w, h))
            if w > 160 or h > 120:
                logging.info('creating thumbnail for uploaded image (size %d x %d)...' % (w, h))
                tn = thumbnails.create_thumbnail(im, 160, 120)
                pw, ph, pcontent = tn['width'], tn['height'], tn['data']
                logging.info('thumbnail was created successfully with size %d x %d.' % (w, h))
                preview = stores.upload_file(ref_type, ref_id, '%s.jpg' % filename, pcontent)
            else:
                logging.info('No need to create thumbnail.')
                preview = res
        except:
            logging.exception('error when creating thumbnail.')

    atta = Attachment( \
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
        mime = res.mime)
    atta.insert()
    if i.return_link==u't':
        atta.filelink = '/api/resources/%s/url' % atta.resource_id
    return atta

@api
@allow(ROLE_EDITORS)
@post('/api/attachments/<aid>/delete')
def api_attachment_delete(aid):
    if not aid:
        raise APIValueError('id', 'id is empty')
    atta = Attachment.get_by_id(aid)
    if not atta or atta.website_id != ctx.website.id:
        raise APIValueError('id', 'not found')
    stores.delete_resources(aid)
    atta.delete()
    return True

if __name__=='__main__':
    import doctest
    doctest.testmod()
