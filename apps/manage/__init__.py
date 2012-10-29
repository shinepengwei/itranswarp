#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import os, time, json, mimetypes

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

try:
    import Image
except ImportError:
    from PIL import Image

from itranswarp.web import ctx, get, post, route, jsonresult
from itranswarp import db
import util

@route('/make_comment')
@jsonresult
def make_comment():
    if ctx.user is None:
        return dict(error='Please sign in first.')
    i = ctx.request.input()
    ref_id = i.ref_id
    user_id = ctx.user.id
    image_url = ctx.user.image_url
    name = ctx.user.name
    content = i.content
    creation_time = time.time(),
    version = 0

@post('/api/media/upload')
@jsonresult
def api_media_upload():
    i = ctx.request.input(name='', description='')
    f = i.file
    return upload_media(i.name.strip(), i.description.strip(), f.filename, f.file)

def upload_media(name, description, fname, fp):
    if not name:
        name = os.path.splitext(fname)[0]
    ftype, mime = _guess_mime(fname)
    current = time.time()
    m = dict( \
            id = db.next_str(), \
            name = name, \
            description = description, \
            width = 0, \
            height = 0, \
            size = 0, \
            type = ftype, \
            mime = mime, \
            metadata = '', \
            ref = '', \
            url = '', \
            thumbnail = '', \
            creation_time = current, \
            modified_time = current, \
            version = 0 \
    )
    uname, uprovider = util.get_enabled_upload()
    if uname is None:
        return dict(error=_('No uploader selected'))
    fcontent = fp.read()
    fthumbnail = None
    m['uploader'] = uname
    m['size'] = len(fcontent)
    if ftype=='image':
        fthumbnail, additional = _create_thumbnail(fcontent)
        m.update(additional)
    uploader = util.create_upload_provider(uname)
    r = uploader.upload(fname, ftype, fcontent, fthumbnail)
    for k in r:
        if k in m:
            m[k] = r[k]
    db.insert('media', **m)
    return dict(redirect='media', filelink=r['url'])

def _guess_mime(fname):
    ext = os.path.splitext(fname)[1].lower()
    mime = mimetypes.types_map.get(ext, 'application/octet-stream')
    ftype = mime
    n = mime.find('/')
    if n!=(-1):
        ftype = mime[:n]
    return ftype, mime

def _create_thumbnail(fcontent):
    ' return thumbnail JPEG as str and dict contains width, height, metadata. '
    im = Image.open(StringIO(fcontent))
    w, h = im.size[0], im.size[1]
    d = dict(width=w, height=h)
    d['metadata'] = 'format=%s&mode=%s' % (im.format, im.mode)
    if w>90 and h>90:
        tw, th = min(w, 90), min(h, 90)
        im.thumbnail((tw, th), Image.ANTIALIAS)
    if im.mode != 'RGB':
        im = im.convert('RGB')
    return im.tostring('jpeg', 'RGB'), d
