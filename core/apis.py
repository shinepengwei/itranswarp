#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
JSON API definition.
'''

import re, time, json, logging, functools

from transwarp.web import ctx, get, post, forbidden, HttpError, Dict

class APIError(StandardError):
    '''
    the base APIError which contains error(required), data(optional) and message(optional).
    '''

    def __init__(self, error, data='', message=''):
        super(APIError, self).__init__(message)
        self.error = error
        self.data = data
        self.message = message

class APIValueError(APIError):
    '''
    Indicate the input value has error or invalid. The data specifies the error field of input form.
    '''
    def __init__(self, field, message=''):
        super(APIValueError, self).__init__('value:invalid', field, message)

class APIPermissionError(APIError):
    '''
    Indicate the api has no permission.
    '''
    def __init__(self, message=''):
        super(APIPermissionError, self).__init__('permission:forbidden', 'permission', message)

def api(func):
    '''
    A decorator that makes a function to json api, makes the return value as json.

    @api
    @post('/articles/create')
    def api_articles_create():
        return dict(id='123')
    '''
    @functools.wraps(func)
    def _wrapper(*args, **kw):
        ctx.response.content_type = 'application/json; charset=utf-8'
        try:
            time.sleep(1.5)
            return json.dumps(func(*args, **kw))
        except APIError, e:
            return json.dumps(dict(error=e.error, data=e.data, message=e.message))
        except Exception, e:
            logging.exception('Error when calling api function.')
            return json.dumps(dict(error='server:internal_error', data=e.__class__.__name__, message=e.message))
    return _wrapper

class Pagination(object):

    '''
    Pagination object for display pages.

    

    '''

    def __init__(self, item_count, page_index=1, page_size=10):
        '''
        Init Pagination by item_count, page_index and page_size.

        >>> p1 = Pagination(100, 1, 10)
        >>> p1.page_count
        10
        >>> p1.offset
        0
        >>> p1.limit
        10
        >>> p2 = Pagination(90, 9, 10)
        >>> p2.page_count
        9
        >>> p2.offset
        80
        >>> p2.limit
        10
        >>> p3 = Pagination(91, 10, 10)
        >>> p3.page_count
        10
        >>> p3.offset
        90
        >>> p3.limit
        1
        '''
        self.item_count = item_count
        self.page_size = page_size
        self.page_count = item_count // page_size + (1 if item_count % page_size > 0 else 0)

        if item_count == 0 or page_index < 1 or page_index > self.page_count:
            self.offset = 0
            self.limit = 0
            self.page_index = 1
        else:
            self.page_index = page_index
            self.offset = self.page_size * (page_index - 1)
            self.limit = self.page_size if page_index < self.page_count else (self.item_count - (self.page_count - 1) * self.page_size)

    def page_list(self, nearby=3):
        '''
        Return pagination list with smart choice.

        >>> p = Pagination(1000, 1)
        >>> p.page_list()
        [1, 2, 3, 4, None, 100]
        >>> p = Pagination(1000, 2)
        >>> p.page_list()
        [1, 2, 3, 4, 5, None, 100]
        >>> p = Pagination(1000, 3)
        >>> p.page_list()
        [1, 2, 3, 4, 5, 6, None, 100]
        >>> p = Pagination(1000, 4)
        >>> p.page_list()
        [1, 2, 3, 4, 5, 6, 7, None, 100]
        >>> p = Pagination(1000, 5)
        >>> p.page_list()
        [1, 2, 3, 4, 5, 6, 7, 8, None, 100]
        >>> p = Pagination(1000, 6)
        >>> p.page_list()
        [1, None, 3, 4, 5, 6, 7, 8, 9, None, 100]
        >>> p = Pagination(1000, 7)
        >>> p.page_list()
        [1, None, 4, 5, 6, 7, 8, 9, 10, None, 100]
        >>> p = Pagination(1000, 95)
        >>> p.page_list()
        [1, None, 92, 93, 94, 95, 96, 97, 98, None, 100]
        >>> p = Pagination(1000, 96)
        >>> p.page_list()
        [1, None, 93, 94, 95, 96, 97, 98, 99, 100]
        >>> p = Pagination(1000, 97)
        >>> p.page_list()
        [1, None, 94, 95, 96, 97, 98, 99, 100]
        >>> p = Pagination(1000, 98)
        >>> p.page_list()
        [1, None, 95, 96, 97, 98, 99, 100]
        >>> p = Pagination(1000, 99)
        >>> p.page_list()
        [1, None, 96, 97, 98, 99, 100]
        >>> p = Pagination(1000, 100)
        >>> p.page_list()
        [1, None, 97, 98, 99, 100]
        '''
        n_min = max(1, self.page_index - nearby)
        n_max = min(self.page_count, self.page_index + nearby)
        L = range(n_min, n_max + 1)
        if n_min > 1:
            L.insert(0, 1)
            if n_min > 2:
                L.insert(1, None)
        if n_max < self.page_count:
            if n_max < (self.page_count - 1):
                L.append(None)
            L.append(self.page_count)
        return L

if __name__=='__main__':
    import doctest
    doctest.testmod()
 