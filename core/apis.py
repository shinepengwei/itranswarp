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
