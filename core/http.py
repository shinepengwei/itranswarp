#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' Http utils such as get referer from request. '

import urllib, urllib2, logging

from transwarp.web import ctx

def get_referer(excludes=None):
    hh = 'http://%s/' % ctx.request.host
    sh = 'https://%s/' % ctx.request.host
    r = ctx.request.header('referer', '/')
    if r.startswith(hh):
        # http://mydomain/...
        r = r[len(hh)-1:]
    elif r.startswith(sh):
        # https://mydomain/...
        r = r[len(sh)-1:]
    elif r.startswith('http://') or r.startswith('https://'):
        # other websites:
        r = '/'
    if excludes and r.startswith(excludes):
        r = '/'
    return r

def get_redirect(excludes=None):
    '''
    Get redirect url from parameter 'redirect'. 
    If argument not found, try using Referer header. 
    If the url starts with excludes, at least the path '/' will be returned.
    '''
    redirect = ctx.request.get('redirect', '')
    if not redirect:
        redirect = get_referer(excludes)
    return redirect

def encode_params(**kw):
    ' do url-encode parameters '
    args = []
    for k, v in kw.iteritems():
        qv = v.encode('utf-8') if isinstance(v, unicode) else str(v)
        args.append('%s=%s' % (k, urllib.quote(qv)))
    return '&'.join(args)

def http_get(url, authorization=None, **kw):
    return http_method('GET', url, authorization, **kw)

def http_post(url, authorization=None, **kw):
    return http_method('POST', url, authorization, **kw)

def http_method(method, url, authorization=None, **kw):
    '''
    send an http request and expect to return a json object if no error.
    '''
    params = encode_params(**kw)
    http_url = '%s?%s' % (url, params) if method=='GET' else url
    http_body = None if method=='GET' else params
    logging.info('%s: %s' % (method, http_url))
    if method=='POST':
        logging.info('body: %s' % params)
    req = urllib2.Request(http_url, data=http_body)
    if authorization:
        req.add_header('Authorization', authorization)
    try:
        resp = urllib2.urlopen(req)
        r = resp.read()
        logging.info('200: %s' % r)
        return 200, r
    except urllib2.HTTPError, e:
        code = e.code
        r = e.read()
        logging.warning('%s: %s' % (code, r))
        return code, r
