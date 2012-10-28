#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import urlparse
from xml.dom import minidom
try:
    import json
except ImportError:
    import simplejson as json

from itranswarp import db, task

def import_wp(f):
    items = parse_wp(f)
    for item in items:
        task.create_task('import_post', item['title'], json.dumps(item))
    return len(items)

def parse_wp(f):
    doc = minidom.parse(f)
    link = value_of_xpath(doc, 'rss/channel/wp:base_site_url')
    if not link:
        link = value_of_xpath(doc, 'rss/channel/wp:base_blog_url')
    if not link:
        link = value_of_xpath(doc, 'rss/channel/link')
    if not link:
        raise ValueError('Could not find link.')
    site = urlparse.urlparse(link).netloc
    L = []
    cs = nodes_of_xpath(doc, 'rss/channel/item')
    for c in cs:
        L.append(dict(
            source = 'wordpress',
            site = site,
            title = value_of_xpath(c, 'title'),
            url = value_of_xpath(c, 'link'),
            pubDate = value_of_xpath(c, 'pubDate'),
            content = value_of_xpath(c, 'content:encoded')))
    return L

def _firstchild(node, name):
    for c in node.childNodes:
        if c.nodeType==minidom.Node.ELEMENT_NODE and c.nodeName==name:
            return c
    return None

def value_of_node(node):
    for c in node.childNodes:
        if c.nodeType==minidom.Node.TEXT_NODE or c.nodeType==minidom.Node.CDATA_SECTION_NODE:
            return c.nodeValue
    return u''

def _children(node, name):
    return [c for c in node.childNodes if c.nodeType==c.ELEMENT_NODE and c.nodeName==name]

def value_of_xpath(node, path):
    n = node_of_xpath(node, path)
    if n:
        return value_of_node(n)
    return u''

def node_of_xpath(node, path):
    n = node
    for p in path.split('/'):
        n = _firstchild(n, p)
        if n is None:
            return None
    return n

def nodes_of_xpath(node, path):
    n = node
    ps = path.split('/')
    for p in ps[:-1]:
        n = _firstchild(n, p)
        if n is None:
            return []
    return _children(n, ps[-1])
