#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import re, time, uuid, logging
from datetime import datetime

from transwarp.web import ctx, get, post, route, seeother, notfound, Template, Dict
from transwarp import db

from apiexporter import *
import setting, loader, plugin, html, counter

from plugin.theme import theme

from apps import menu

################################################################################
# Wiki Pages
################################################################################

def _get_wikis():
    ' get all wikis of current website. '
    return db.select('select * from wikis where website_id=? order by name, id', ctx.website.id)

def _get_wiki(wid):
    ' get wiki by id. raise APIPermissionError if wiki is not belong to current website. '
    wiki = db.select_one('select * from wikis where id=?', wid)
    if wiki.website_id != ctx.website.id:
        raise APIPermissionError('cannot get wiki that does not belong to current website.')
    return wiki

@api(role=ROLE_GUESTS)
@get('/api/wikis/list')
def api_list_wikis():
    ' list all wikis of current website. '
    return dict(wikis=_get_wikis())

@api(role=ROLE_GUESTS)
@get('/api/wikis/get')
def api_get_wiki():
    ' get wiki by id. '
    i = ctx.request.input(id='')
    if not i.id:
        raise APIValueError('id', 'id cannot be empty')
    return _get_wiki(i.id)

@api(role=ROLE_ADMINISTRATORS)
@post('/api/wikis/update')
def api_update_wiki():
    ' update wiki name, description, content by id. '
    i = ctx.request.input(id='')
    if not i.id:
        raise APIValueError('id', 'id cannot be empty')
    wiki = _get_wiki(i.id)
    kw = {}
    if 'name' in i:
        name = i.name.strip()
        if not name:
            raise APIValueError('name', 'name cannot be empty')
        kw['name'] = name
    if 'description' in i:
        kw['description'] = i.description.strip()
    if 'content' in i:
        kw['content'] = i.content.strip()
    if kw:
        kw['version'] = wiki.version + 1
        kw['modified_time'] = time.time()
        db.update_kw('wikis', 'id=?', i.id, **kw)
    return True

@api(role=ROLE_ADMINISTRATORS)
@post('/api/wikis/create')
def api_create_wiki():
    ' create a new wiki. '
    i = ctx.request.input(name='', description='', content='')
    name = i.name.strip()
    if not name:
        raise APIValueError('name', 'name cannot be empty')
    content = i.content.strip()
    if not content:
        raise APIValueError('content', 'content cannot be empty')
    current = time.time()
    wiki = Dict( \
        id=db.next_str(), \
        website_id=ctx.website.id, \
        name=name, \
        description=i.description.strip(), \
        content=content, \
        creation_time=current, \
        modified_time=current, \
        version=0)
    db.insert('wikis', **wiki)
    return wiki

@api(role=ROLE_ADMINISTRATORS)
@post('/api/wikis/delete')
def api_delete_wiki():
    ' delete a wiki by id. '
    i = ctx.request.input(id='')
    if not i.id:
        raise APIValueError('id', 'id cannot be empty.')
    wiki = _get_wiki(i.id)
    count = db.select_int('select count(id) from wiki_pages where wiki_id=?', wiki.id)
    if count > 0:
        raise APIValueError('id', 'cannot delete non-empty wiki.')
    db.update('delete from wikis where id=?', wiki.id)
    return True

@menu(ROLE_EDITORS, 'Wiki', 'All Wikis', group_order=30, name_order=0)
def wikis():
    ' show Wikis menu. '
    i = ctx.request.input(action='')
    if i.action=='edit':
        wiki = _get_wiki(i.id)
        return Template('templates/wikiform.html', form_title='Edit Wiki', form_action='/api/wikis/update', **wiki)
    if i.action=='pages':
        wiki = _get_wiki(i.id)
        return Template('templates/wikipages.html', wiki=wiki)
    if i.action=='editpage':
        page = _get_wikipage(i.id)
        wiki = _get_wiki(page.wiki_id)
        return Template('templates/wikipageform.html', wiki=wiki, page=page)
    return Template('templates/wikis.html', wikis=_get_wikis())

@menu(ROLE_EDITORS, 'Wiki', 'New Wiki', name_order=1)
def add_wiki():
    ' show New Wiki menu. '
    return Template('templates/wikiform.html', form_title='Add Wiki', form_action='/api/wikis/create')

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
    wp = db.select_one('select * from wiki_pages where id=?', wp_id)
    if wp.website_id != ctx.website.id:
        raise APIPermissionError('cannot get wiki page that is not belong to current website.')
    if wiki_id and wp.wiki_id != wiki_id:
        raise APIValueError('wiki_id', 'bad wiki id.')
    return wp

def _get_wikipages(wiki, returnDict=False):
    '''
    Get all wiki pages and return as tree. Each wiki page contains only id, website_id, wiki_id, parent_id, display_order, name and version.
    The return value is virtual root node.
    '''
    pages = db.select('select id, website_id, wiki_id, parent_id, display_order, name, version from wiki_pages where wiki_id=?', wiki.id)
    pdict = dict(((p.id, p) for p in pages))
    if returnDict:
        return pdict
    proot = Dict(id='')
    _tree_iter(pdict, proot)
    return proot.children

def _create_wiki_page(wiki_id, parent_id, display_order, name, content):
    current = time.time()
    p = dict(id=db.next_str(), \
        website_id=ctx.website.id, \
        wiki_id=wiki_id, \
        parent_id=parent_id, \
        display_order=display_order, \
        name=name, \
        content=content, \
        creation_time=current, \
        modified_time=current, \
        version=0)
    db.insert('wiki_pages', **p)
    return p

@api(role=ROLE_GUESTS)
@get('/api/wikipages/list')
def api_list_wikipages():
    '''
    Get wiki pages as tree list, without content.
    '''
    i = ctx.request.input(id='')
    if not i.id:
        raise APIValueError('id', 'id cannot be empty.')
    wiki = _get_wiki(i.id)
    return _get_wikipages(wiki)

@theme('wiki.html')
@route('/wiki/<wiki_id>')
def wiki_by_id(wiki_id):
    wiki = _get_wiki(wiki_id)
    pages = _get_wikipages(wiki)
    return dict(__navigation__=('/wiki/%s' % wiki_id,), \
        wiki=wiki, pages=pages, wiki_name=wiki.name, wiki_content=html.to_html(wiki), \
        read_count=counter.inc(wiki.id))

@theme('wiki.html')
@route('/wiki/<wiki_id>/<page_id>')
def wiki_page_by_id(wiki_id, page_id):
    wiki = _get_wiki(wiki_id)
    page = _get_wikipage(page_id, wiki_id)
    pages = _get_wikipages(wiki)
    return dict(__navigation__=('/wiki/%s' % wiki_id,), \
        wiki=wiki, pages=pages, page=page, wiki_name=page.name, wiki_content=html.to_html(page), \
        read_count=counter.inc(page.id))

@api(role=ROLE_EDITORS)
@post('/api/wikipages/create')
def api_create_wikipage():
    i = ctx.request.input(wiki_id='', name='', content='')
    if not 'parent_id' in i:
        raise APIValueError('parent_id', 'bad parameter: parent_id')
    if not i.wiki_id:
        raise APIValueError('wiki_id', 'bad parameter: wiki_id')
    if not i.name.strip():
        raise APIValueError('name', 'invalid name')
    if not i.content.strip():
        raise APIValueError('content', 'invalid content')
    wiki = _get_wiki(i.wiki_id)
    if i.parent_id:
        p_page = _get_wikipage(i.parent_id, wiki.id)
    num = db.select_int('select count(id) from wiki_pages where wiki_id=? and parent_id=?', wiki.id, i.parent_id)
    return _create_wiki_page(wiki.id, i.parent_id, num, i.name.strip(), i.content)

@api(role=ROLE_EDITORS)
@post('/api/wikipages/update')
def api_update_wikipage():
    i = ctx.request.input(id='')
    if not i.id:
        raise APIValueError('id', 'bad parameter: id')
    page = _get_wikipage(i.id)
    kw = {}
    if 'name' in i:
        if not i.name.strip():
            raise APIValueError('name', 'invalid name')
        kw['name'] = i.name.strip()
    if 'content' in i:
        if not i.content.strip():
            raise APIValueError('content', 'invalid content')
        kw['content'] = i.content.strip()
    if kw:
        kw['modified_time'] = time.time()
        kw['version'] = page.version + 1
        db.update_kw('wiki_pages', 'id=?', i.id, **kw)
    return True

@api(role=ROLE_EDITORS)
@post('/api/wikipages/move')
def api_move_wikipages():
    i = ctx.request.input(id='', index='')
    if not i.id:
        raise APIValueError('id', 'bad parameter id.')
    if not 'move_to' in i:
        raise APIValueError('move_to', 'bad parameter move_to.')
    if not i.index:
        raise APIValueError('index', 'bad parameter index.')
    try:
        index = int(i.index)
    except ValueError:
        raise APIValueError('index', 'bad parameter index.')
    # get the 2 pages:
    moving_page = _get_wikipage(i.id)
    wiki = _get_wiki(moving_page.wiki_id)
    parent_page = None # root
    if i.move_to:
        parent_page = _get_wikipage(i.move_to, wiki.id)
    # check to prevent recursive:
    pages = _get_wikipages(wiki, returnDict=True)
    if parent_page:
        p = parent_page
        while p.parent_id != '':
            if p.parent_id==moving_page.id:
                raise APIValueError('move_to', 'Will cause recursive.')
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
            db.update('update wiki_pages set display_order=? where id=?', n, p.id)
            n = n + 1
        db.update('update wiki_pages set parent_id=? where id=?', parent_id, moving_page.id)
    return True

@api(role=ROLE_EDITORS)
@post('/api/wikipages/delete')
def api_delete_wikipage():
    i = ctx.request.input(id='')
    if not i.id:
        raise APIValueError('id', 'bad parameter: id')
    page = _get_wikipage(i.id)
    if db.select_int('select count(id) from wiki_pages where wiki_id=? and parent_id=?', page.wiki_id, page.id) > 0:
        raise APIPermissionError('cannot delete non empty page.')
    db.update('delete from wiki_pages where id=?', page.id)
    return True

################################################################################
# Navs
################################################################################

def get_nav_definitions():
    return [
        dict(
            id='wiki',
            input='select',
            prompt='Wiki',
            description='Show a wiki',
            get_url=lambda value: '/wiki/%s' % value,
            options=[(w.id, w.name) for w in _get_wikis()]
        )]

if __name__=='__main__':
    import doctest
    doctest.testmod()
