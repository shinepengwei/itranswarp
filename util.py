#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' Util module '

import os, re, time, base64, hashlib, logging, functools, mimetypes

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from transwarp.web import ctx, get, post, Dict, Template, seeother, notfound, badrequest
from transwarp import db

def load_themes():

    def _is_theme(root, name):
        p = os.path.join(root, name)
        return os.path.isdir(p) and os.path.isfile(os.path.join(p, '__init__.py'))

    def _get_theme_info(name):
        m = load_module('themes.%s' % name)
        return Dict( \
            id = name, \
            name = getattr(m, 'name', name), \
            description = getattr(m, 'description', '(no description)'), \
            author = getattr(m, 'author', '(unknown)'), \
            version = getattr(m, 'version', '1.0'), \
            snapshot = '/themes/%s/static/snapshot.png' % name)

    root = os.path.join(ctx.application.document_root, 'themes')
    subs = os.listdir(root)
    L = [_get_theme_info(p) for p in subs if _is_theme(root, p)]
    return sorted(L, lambda x, y: -1 if x.name.lower() < y.name.lower() else 1)

def make_comment(ref_type, ref_id, user, content):
    '''
    Make a comment.

    Args:
        ref_type: the ref type, e.g. 'article'.
        ref_id: the ref id, e.g., article id.
        user: current user.
        content: comment content.
    Returns:
        the comment object as dict.
    '''
    cid = db.next_str()
    kw = dict(id=cid, ref_type=ref_type, ref_id=ref_id, user_id=user.id, image_url=user.image_url, name=user.name, content=content, creation_time=time.time(), version=0)
    db.insert('comments', **kw)
    return kw

def get_comments_desc(ref_id, max_results=20, after_id=None):
    '''
    Get comments by page.

    Args:
        ref_id: reference id.
        max_results: the max results.
        after_id: comments after id.
    Returns:
        comments as list.
    '''
    if max_results < 1 or max_results > 100:
        raise ValueError('bad max_results')
    if after_id:
        return db.select('select * from comments where ref_id=? and id < ? order by id desc limit ?', ref_id, after_id, max_results)
    return db.select('select * from comments where ref_id=? order by id desc limit ?', ref_id, max_results)

def get_comments(ref_id, page_index=1, page_size=20):
    '''
    Get comments by page.

    Args:
        page_index: page index from 1.
        page_size: page size.
    Returns:
        comments as list, has_next as bool.
    '''
    if page_index < 1:
        raise ValueError('bad page_index')
    if page_size < 1 or page_size > 100:
        raise ValueError('bad page_size')
    offset = (page_index - 1) * page_size
    logging.warn('offset=%s, page_size=%s' % (offset, page_size))
    cs = db.select('select * from comments where ref_id=? order by creation_time desc limit ?,?', ref_id, offset, page_size + 1)
    logging.warn('len()=%s' % len(cs))
    if len(cs) > page_size:
        return cs[:page_size], True
    return cs, False

class Page(object):
    '''
    Page object that can be used for calculate pagination.
    '''

    def __init__(self, page_index, page_size, total):
        '''
        Init Page object with:
            page_index: starts from 1.
            page_size: page size, at least 1.
            total: total items, non-negative value.
        '''
        if page_index < 1:
            raise ValueError('page_index must be greater than 0')
        if page_size < 1:
            raise ValueError('page_size must be greater than 0')
        if total < 0:
            raise ValueError('total must be non-negative')
        self._total = total
        self._index = page_index
        self._size = page_size
        if total > 0:
            page_count = total // page_size + (0 if (total % page_size)==0 else 1)
            if page_index > page_count:
                raise ValueError('page_index is out of range [1..%s]' % page_count)
            offset = page_size * (page_index - 1)
            limit = page_size if page_index < page_count else total - (page_index - 1) * page_size
            self._offset = offset
            self._limit = limit
            self._pages = page_count
        else:
            self._offset = 0
            self._limit = 0
            self._pages = 0

    @property
    def offset(self):
        '''
        The offset of first item of current page.

        >>> Page(1, 10, 99).offset
        0
        >>> Page(2, 10, 99).offset
        10
        >>> Page(3, 15, 99).offset
        30
        >>> Page(1, 10, 0).offset
        0
        '''
        return self._offset

    @property
    def limit(self):
        '''
        The number of items of current page.

        >>> Page(1, 10, 99).limit
        10
        >>> Page(2, 10, 99).limit
        10
        >>> Page(10, 10, 91).limit
        1
        >>> Page(10, 10, 99).limit
        9
        >>> Page(10, 10, 100).limit
        10
        >>> Page(1, 10, 0).limit
        0
        '''
        return self._limit

    @property
    def index(self):
        '''
        The current page index.

        >>> Page(1, 10, 99).index
        1
        >>> Page(2, 10, 99).index
        2
        >>> Page(10, 10, 99).index
        10
        >>> Page(11, 10, 99).index
        Traceback (most recent call last):
            ...
        ValueError: page_index is out of range [1..10]
        '''
        return self._index

    @property
    def size(self):
        '''
        The page size.

        >>> Page(1, 5, 100).size
        5
        >>> Page(1, 10, 100).size
        10
        >>> Page(1, 0, 100).size
        Traceback (most recent call last):
            ...
        ValueError: page_size must be greater than 0
        '''
        return self._size

    @property
    def pages(self):
        '''
        Get how many pages.

        >>> Page(1, 10, 0).pages
        0
        >>> Page(1, 10, 1).pages
        1
        >>> Page(1, 10, 9).pages
        1
        >>> Page(1, 10, 10).pages
        1
        >>> Page(1, 10, 11).pages
        2
        >>> Page(1, 10, 19).pages
        2
        >>> Page(1, 10, 20).pages
        2
        >>> Page(1, 10, 21).pages
        3
        >>> Page(1, 10, 100).pages
        10
        >>> Page(1, 10, 101).pages
        11
        '''
        return self._pages

    @property
    def empty(self):
        '''
        Test if should show "no items to display".

        >>> Page(1, 10, 0).empty
        True
        >>> Page(1, 10, 1).empty
        False
        '''
        return self._pages==0

    @property
    def total(self):
        '''
        Get total items.

        >>> Page(1, 10, 0).total
        0
        >>> Page(1, 10, 99).total
        99
        '''
        return self._total

    @property
    def previous(self):
        '''
        Get previous page index. 0 if no previous.

        >>> Page(1, 10, 100).previous
        0
        >>> Page(2, 10, 100).previous
        1
        '''
        return (self._index - 1) if self._index > 1 else 0

    @property
    def next(self):
        '''
        Get next page index. 0 if no next.

        >>> Page(1, 10, 100).next
        2
        >>> Page(10, 10, 100).next
        0
        '''
        return (self._index + 1) if self._index < self._pages else 0

    def nearby(self, number=5):
        '''
        Get nearby page indexes as list. For example, current page index is 10, 
        the nearby() returns [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15].

        >>> Page(1, 10, 1000).nearby()
        [1, 2, 3, 4, 5, 6]
        >>> Page(2, 10, 1000).nearby()
        [1, 2, 3, 4, 5, 6, 7]
        >>> Page(6, 10, 1000).nearby()
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        >>> Page(7, 10, 1000).nearby()
        [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        >>> Page(95, 10, 1000).nearby()
        [90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100]
        >>> Page(96, 10, 1000).nearby()
        [91, 92, 93, 94, 95, 96, 97, 98, 99, 100]
        >>> Page(99, 10, 1000).nearby()
        [94, 95, 96, 97, 98, 99, 100]
        >>> Page(100, 10, 1000).nearby()
        [95, 96, 97, 98, 99, 100]
        >>> Page(6, 10, 1000).nearby(3)
        [3, 4, 5, 6, 7, 8, 9]
        >>> Page(6, 10, 1000).nearby(1)
        [5, 6, 7]
        >>> Page(1, 10, 0).nearby()
        []
        '''
        if number < 1:
            raise ValueError('number must be greater than 0.')
        if self._pages==0:
            return []
        lower = self._index - number
        higher = self._index + number
        if lower < 1:
            lower = 1
        if higher > self._pages:
            higher = self._pages
        return range(lower, higher + 1)

if __name__=='__main__':
    import doctest
    doctest.testmod()
 