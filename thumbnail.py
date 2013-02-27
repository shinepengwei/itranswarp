#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' generate thumbnail for uploaded images '

import os, logging

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

try:
    import Image
except ImportError:
    from PIL import Image

def as_image(fcontent):
    return Image.open(StringIO(fcontent))

def create_thumbnail(im, max_width=90, max_height=90):
    '''
    create thumbnail JPEG as str with size no more than max_width and max_height, 
    and return dict contains:
        width: thumbnail width,
        height: thumbnail height,
        data: thumbnail data.
    '''
    w, h = im.size[0], im.size[1]
    meta = 'format=%s&mode=%s' % (im.format, im.mode)
    # calculate thumbnail width, height:
    tw = max_width
    th = tw * h / w
    if th > max_height:
        th = max_height
        tw = th * w / h
    if tw < 5:
        tw = 5
    if th < 5:
        th = 5
    im.thumbnail((tw, th), Image.ANTIALIAS)
    if im.mode != 'RGB':
        im = im.convert('RGB')
    return dict(width=tw, height=th, data=im.tostring('jpeg', 'RGB'))
