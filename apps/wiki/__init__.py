#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import re, time, uuid, logging
from datetime import datetime

from transwarp.web import ctx, get, post, route, seeother, notfound, Template, Dict
from transwarp import db

from core.apis import *
from core.roles import *
from core.models import get_comments, create_comment

from core import texts, utils

from themes import theme

name = 'Wiki'

order = 20

menus = (
    ('-', 'Wikis'),
    ('all_wikis', 'Wikis'),
    ('add_wiki', 'Add Wiki'),
)

navigations = (
        dict(
            key='wiki',
            input='select',
            prompt='Wiki',
            description='Show wiki pages',
            fn_get_url=lambda value: '/wiki/%s' % value,
            fn_get_options=lambda: [(w.id, w.name) for w in _get_wikis()]
        ),
)

################################################################################
# Wiki Pages
################################################################################

class Wiki(db.Model):
    '''
    create table wiki (
        id varchar(50) not null,
        website_id varchar(50) not null,
        content_id varchar(50) not null,
        name varchar(100) not null,
        description varchar(2000) not null,
        creation_time real not null,
        modified_time real not null,
        version bigint not null,
        primary key(id),
        index idx_website_id(website_id)
    );
    '''

    id = db.StringField(primary_key=True, default=db.next_str)

    website_id = db.StringField(nullable=False, updatable=False)

    content_id = db.StringField(nullable=False)

    name = db.StringField(nullable=False)
    description = db.StringField(nullable=False)

    creation_time = db.FloatField(nullable=False, updatable=False, default=time.time)
    modified_time = db.FloatField(nullable=False, default=time.time)
    version = db.VersionField()

    def pre_update(self):
        self.modified_time = time.time()
        self.version = self.version + 1

class Wiki_Page(db.Model):
    '''
    create table wiki_page (
        id varchar(50) not null,
        website_id varchar(50) not null,
        wiki_id varchar(50) not null,
        parent_id varchar(50) not null,
        content_id varchar(50) not null,

        display_order int not null,
        name varchar(100) not null,

        creation_time real not null,
        modified_time real not null,
        version bigint not null,

        primary key(id),
        index idx_website_id(website_id),
        index idx_wiki_id(wiki_id)
    );
    '''

    id = db.StringField(primary_key=True, default=db.next_str)
    website_id = db.StringField(nullable=False, updatable=False)
    wiki_id = db.StringField(nullable=False, updatable=False)
    parent_id = db.StringField(nullable=False, updatable=False)

    content_id = db.StringField(nullable=False)

    display_order = db.IntegerField(nullable=False)
    name = db.StringField(nullable=False)

    creation_time = db.FloatField(nullable=False, updatable=False, default=time.time)
    modified_time = db.FloatField(nullable=False, default=time.time)
    version = db.VersionField()

    def pre_update(self):
        self.modified_time = time.time()
        self.version = self.version + 1

def _get_wikis():
    ' get all wikis of current website. '
    return Wiki.select('where website_id=? order by name, id', ctx.website.id)

def _get_wiki(wid):
    ' get wiki by id. raise APIPermissionError if wiki is not belong to current website. '
    wiki = Wiki.get_by_id(wid)
    if wiki.website_id != ctx.website.id:
        raise APIPermissionError('cannot get wiki that does not belong to current website.')
    return wiki

def _get_full_wiki(wid):
    wiki = _get_wiki(wid)
    wiki.content = utils.markdown2html(texts.get(wid))
    return wiki

@allow(ROLE_CONTRIBUTORS)
def all_wikis():
    ' show Wikis menu. '
    i = ctx.request.input(action='', id='')
    if i.action=='edit':
        wiki = _get_wiki(i.id)
        return Template('wikiform.html', form_title='Edit Wiki', form_action='/api/wikis/%s/update' % i.id, redirect='all_wikis', **wiki)
    if i.action=='pages':
        wiki = _get_wiki(i.id)
        return Template('wikipages.html', wiki=wiki)
    if i.action=='editpage':
        page = _get_full_wikipage(i.id)
        wiki = _get_wiki(page.wiki_id)
        return Template('wikipageform.html', wiki=wiki, page=page, form_action='/api/wikis/pages/%s/update' % page.id, redirect='all_wikis?action=pages&id=%s' % wiki.id)
    return Template('all_wikis.html', wikis=_get_wikis())

@allow(ROLE_EDITORS)
def add_wiki():
    ' show New Wiki menu. '
    return Template('wikiform.html', form_title='Add Wiki', form_action='/api/wikis/create', redirect='all_wikis')

@api
@allow(ROLE_GUESTS)
@get('/api/wikis')
def api_wikis_list():
    ' list all wikis of current website. '
    return dict(wikis=_get_wikis())

@api
@allow(ROLE_GUESTS)
@get('/api/wikis/<wid>')
def api_wikis_get(wid):
    if not wid:
        raise APIValueError('id', 'id cannot be empty')
    return _get_wiki(wid)

@api
@allow(ROLE_EDITORS)
@post('/api/wikis/<wid>/update')
def api_wikis_update(wid):
    ' update wiki name, description, content by id. '
    if not wid:
        raise APIValueError('id', 'id cannot be empty')
    i = ctx.request.input()
    wiki = _get_wiki(wid)
    if 'name' in i:
        name = i.name.strip()
        if not name:
            raise APIValueError('name', 'name cannot be empty')
        wiki.name = name
    if 'description' in i:
        wiki.description = i.description.strip()
    content = None
    if 'content' in i:
        content = i.content.strip()
        if not content:
            raise APIValueError('content', 'content cannot be empty')
    with db.transaction():
        if content:
            content_id = db.next_str()
            wiki.content_id = content_id
            texts.set(wid, content_id, content)
        wiki.update()
    return dict(result=True)

@api
@allow(ROLE_EDITORS)
@post('/api/wikis/create')
def api_wikis_create():
    ' create a new wiki. '
    i = ctx.request.input(name='', description='', content='')
    name = i.name.strip()
    if not name:
        raise APIValueError('name', 'name cannot be empty')
    content = i.content.strip()
    if not content:
        raise APIValueError('content', 'content cannot be empty')
    wiki_id = db.next_str()
    content_id = db.next_str()
    wiki = Wiki( \
        id=wiki_id, \
        website_id=ctx.website.id, \
        name=name, \
        description=i.description.strip(), \
        content_id=content_id)
    texts.set(wiki_id, content_id, content)
    wiki.insert()
    return wiki

@api
@allow(ROLE_EDITORS)
@post('/api/wikis/<wid>/delete')
def api_wikis_delete(wid):
    ' delete a wiki by id. '
    if not wid:
        raise APIValueError('id', 'id cannot be empty.')
    wiki = _get_wiki(wid)
    count = Wiki_Page.count('where wiki_id=?', wiki.id)
    if count > 0:
        raise APIValueError('id', 'cannot delete non-empty wiki.')
    wiki.delete()
    return dict(result=True)

def _tree_iter(nodes, root):
    rid = root.id
    root.children = []
    for nid in nodes.keys():
        node = nodes[nid]
        if node.parent_id==rid:
            root.children.append(node)
            nodes.pop(nid)
    if root.children:
        root.children.sort(cmp=lambda n1, n2: -1 if n1.display_order < n2.display_order else 1)
        for ch in root.children:
            _tree_iter(nodes, ch)

def _get_wikipage(wp_id, wiki_id=None):
    '''
    get a wiki page by id. raise APIPermissionError if wiki is not belong to current website.
    if the wiki_id is not None, it also check if the page belongs to wiki.
    '''
    wp = Wiki_Page.get_by_id(wp_id)
    if wp.website_id != ctx.website.id:
        raise APIPermissionError('cannot get wiki page that is not belong to current website.')
    if wiki_id and wp.wiki_id != wiki_id:
        raise APIValueError('wiki_id', 'bad wiki id.')
    return wp

def _get_full_wikipage(wp_id, wiki_id=None):
    wp = _get_wikipage(wp_id, wiki_id)
    wp.content = texts.get(wp.id)
    return wp

def _get_wikipages(wiki, returnDict=False):
    '''
    Get all wiki pages and return as tree. Each wiki page contains only id, website_id, wiki_id, parent_id, display_order, name and version.
    The return value is virtual root node.
    '''
    pages = Wiki_Page.select('where wiki_id=?', wiki.id)
    pdict = dict(((p.id, p) for p in pages))
    if returnDict:
        return pdict
    proot = Dict(id='')
    _tree_iter(pdict, proot)
    return proot.children

def _create_wiki_page(wiki_id, parent_id, display_order, name, content):
    wp_id = db.next_str()
    content_id = db.next_str()
    texts.set(wp_id, content_id, content)
    p = Wiki_Page( \
        id=wp_id, \
        website_id=ctx.website.id, \
        wiki_id=wiki_id, \
        parent_id=parent_id, \
        display_order=display_order, \
        name=name, \
        content_id=content_id)
    p.insert()
    return p

@api
@allow(ROLE_GUESTS)
@get('/api/wikis/<wid>/pages')
def api_wikis_pages(wid):
    '''
    Get wiki pages as tree list, without content.
    '''
    if not wid:
        raise APIValueError('id', 'id cannot be empty.')
    wiki = _get_wiki(wid)
    return _get_wikipages(wiki)

@api
@allow(ROLE_EDITORS)
@post('/api/wikis/<wid>/pages/create')
def api_wikis_pages_create(wid):
    if not wid:
        raise APIValueError('wiki_id', 'bad parameter: wiki_id')
    i = ctx.request.input(name='', content='')
    if not 'parent_id' in i:
        raise APIValueError('parent_id', 'bad parameter: parent_id')
    name = i.name.strip()
    if not name:
        raise APIValueError('name', 'invalid name')
    content = i.content.strip()
    if not content:
        raise APIValueError('content', 'invalid content')
    wiki = _get_wiki(wid)
    if i.parent_id:
        p_page = _get_wikipage(i.parent_id, wiki.id)
    num = Wiki_Page.count('where wiki_id=? and parent_id=?', wiki.id, i.parent_id)
    return _create_wiki_page(wiki.id, i.parent_id, num, name, content)

@api
@allow(ROLE_EDITORS)
@post('/api/wikis/pages/<wpid>/update')
def api_update_wikipage(wpid):
    if not wpid:
        raise APIValueError('id', 'bad parameter: id')
    i = ctx.request.input()
    page = _get_wikipage(wpid)
    if 'name' in i:
        if not i.name.strip():
            raise APIValueError('name', 'invalid name')
        page.name = i.name.strip()
    content = None
    if 'content' in i:
        content = i.content.strip()
        if not content:
            raise APIValueError('content', 'invalid content')
    if content:
        content_id = db.next_str()
        page.content_id = content_id
        texts.set(wpid, content_id, content)
    page.update()
    return dict(result=True)

@api
@allow(ROLE_EDITORS)
@post('/api/wikis/pages/<wpid>/move/<target_id>')
def api_wikis_pages_move(wpid, target_id):
    '''
    Move wiki page from one node to another.
    '''
    if not wpid:
        raise APIValueError('id', 'bad parameter id.')
    if not target_id:
        raise APIValueError('target_id', 'bad parameter target_id.')
    i = ctx.request.input(index='')
    if not i.index:
        raise APIValueError('index', 'bad parameter index.')
    try:
        index = int(i.index)
    except ValueError:
        raise APIValueError('index', 'bad parameter index.')
    # get the 2 pages:
    moving_page = _get_wikipage(wpid)
    wiki = _get_wiki(moving_page.wiki_id)
    parent_page = None
    if target_id=='ROOT':
        parent_page = None # root node
    else:
        parent_page = _get_wikipage(target_id, wiki.id)
    # check to prevent recursive:
    pages = _get_wikipages(wiki, returnDict=True)
    if parent_page:
        p = parent_page
        while p.parent_id != '':
            if p.parent_id==moving_page.id:
                raise APIValueError('target_id', 'Will cause recursive.')
            p = pages[p.parent_id]
    # get current children:
    parent_id = parent_page.id if parent_page else ''
    L = [p for p in pages.itervalues() if p.parent_id==parent_id and p.id!=moving_page.id]
    L.sort(cmp=lambda p1, p2: -1 if p1.display_order<p2.display_order else 1)
    # insert at index N:
    L.insert(index, moving_page)
    # update display order:
    with db.transaction():
        n = 0
        for p in L:
            db.update('update wiki_page set display_order=? where id=?', n, p.id)
            n = n + 1
        db.update('update wiki_page set parent_id=? where id=?', parent_id, moving_page.id)
    return dict(result=True)

@api
@allow(ROLE_EDITORS)
@post('/api/wikis/pages/<wpid>/delete')
def api_wikis_pages_delete(wpid):
    if not wpid:
        raise APIValueError('id', 'bad parameter: id')
    page = _get_wikipage(wpid)
    if Wiki_Page.count('where wiki_id=? and parent_id=?', page.wiki_id, page.id) > 0:
        raise APIPermissionError('cannot delete non empty page.')
    page.delete()
    return dict(result=True)

@theme('wiki.html')
@get('/wiki/<wiki_id>')
def web_wiki_byid(wiki_id):
    wiki = _get_wiki(wiki_id)
    pages = _get_wikipages(wiki)
    return dict(wiki=wiki, pages=pages, wiki_name=wiki.name, wiki_content=utils.cached_markdown2html(wiki))

@theme('wiki.html')
@get('/wiki/<wiki_id>/<page_id>')
def web_wiki_page_byid(wiki_id, page_id):
    wiki = _get_wiki(wiki_id)
    page = _get_wikipage(page_id, wiki_id)
    pages = _get_wikipages(wiki)
    return dict(wiki=wiki, pages=pages, page=page, wiki_name=page.name, wiki_content=utils.cached_markdown2html(page))

if __name__=='__main__':
    import doctest
    doctest.testmod()
