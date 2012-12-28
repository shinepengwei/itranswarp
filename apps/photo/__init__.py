#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import os, time, logging

from transwarp.web import ctx, get, post, route, jsonrpc, seeother, badrequest, jsonresult, Template, Page, Dict
from transwarp import db

import util

from apps import menu_group, menu_item

PAGE_SIZE = 30

def export_navigation_menus():
    return [
        dict(
            type='albums',
            name='Albums',
            description='Display albums',
            input_type=None,
            supplies=None,
            handler=lambda menu: '/albums'),
        dict(
            type='album',
            name='Album',
            description='Display photos belong to the specified album',
            input_type='select',
            input_prompt='Album',
            supplies=lambda: [(c.id, c.name) for c in _do_get_albums()],
            handler=lambda menu: '/album/%s' % menu.ref),
    ]

@get('/api/albums')
@jsonresult
def api_get_albums():
    if ctx.user is None:
        return dict(error='bad authentication')
    return _do_get_albums()

@jsonresult
def do_edit_album():
    i = ctx.request.input()
    name = i.name.strip()
    description = i.description.strip()
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    logging.info('update album...')
    db.update_kw('albums', 'id=?', i.id, name=name, description=description, modified_time=time.time())
    return dict(redirect='albums')

def do_delete_album():
    alb_id = ctx.request.input().id
    alb = db.select_one('select id,locked from albums where id=?', alb_id)
    if alb.locked:
        raise badrequest()
    uncategorized = db.select_one('select id from albums where locked=?', True)
    db.update('delete from albums where id=?', alb_id)
    db.update('update photos set album_id=? where album_id=?', uncategorized.id, alb_id)
    raise seeother('albums')

def order_albums():
    orders = ctx.request.gets('order')
    als = _do_get_albums()
    l = len(als)
    if l!=len(orders):
         raise badrequest()
    odict = dict()
    n = 0
    for o in orders:
        odict[o] = n
        n = n + 1
    with db.transaction():
        for a in als:
            db.update('update albums set display_order=? where id=?', odict.get(a.id, l), a.id)
    raise seeother('albums')

@post('/api/album/create')
@jsonresult
def api_add_album():
    if ctx.user is None:
        return dict(error='auth:failed')
    return _do_add_album(i.name, i.description)

@post('/api/photo/upload')
@jsonresult
def api_upload_photo():
    if ctx.user is None:
        return dict(error='auth:failed')
    return do_add_photo()

def do_add_photo():
    i = ctx.request.input(name='', description='', geo_lat='0.0', geo_lng='0.0')
    geo_lat = float(i.geo_lat)
    geo_lng = float(i.geo_lng)
    album_id = i.album_id
    album = db.select_one('select * from albums where id=?', album_id)
    f = i.file
    f_ext = os.path.splitext(f.filename)[1].lower()
    ref_type = 'photo'
    ref_id = db.next_str()
    current = time.time()
    fcontent = f.file.read()

    th = util.create_thumbnail(fcontent, 160, 120)
    width, height, metadata = th['width'], th['height'], th['metadata']
    img_preview = th['thumbnail']
    resources = dict(preview=img_preview)
    # generate large, medium and small impage:
    img_small = img_medium = img_large = fcontent
    if width > 320 or height > 240:
        img_small = util.create_thumbnail(fcontent, 320, 240)['thumbnail']
        resources['small'] = img_small
    if width > 640 or height > 480:
        img_medium = util.create_thumbnail(fcontent, 640, 480)['thumbnail']
        resources['medium'] = img_medium
    if width > 1280 or height > 960:
        img_large = util.create_thumbnail(fcontent, 1280, 960)['thumbnail']
        resources['large'] = img_large
    # original:
    ro = util.upload_resource(ref_type, ref_id, f.filename, fcontent)
    # preview:
    rp = util.upload_resource(ref_type, ref_id, 'preview.jpg', img_preview)
    rs = rm = rl = None
    if 'small' in resources:
        rs = util.upload_resource(ref_type, ref_id, 'small.jpg', img_small)
    else:
        rs = ro
    if 'medium' in resources:
        rm = util.upload_resource(ref_type, ref_id, 'medium.jpg', img_medium)
    else:
        rm = ro
    if 'large' in resources:
        rl = util.upload_resource(ref_type, ref_id, 'large.jpg', img_large)
    else:
        rl = ro
    photo = dict( \
            id = ref_id, \
            album_id = album_id, \
            origin_resource_id = ro['id'], \
            large_resource_id = rl['id'], \
            medium_resource_id = rm['id'], \
            small_resource_id = rs['id'], \
            preview_resource_id = rp['id'], \
            display_order = album.photo_count, \
            name = i.name.strip(), \
            description = i.description.strip(), \

            width = width, \
            height = height, \
            size = len(fcontent), \
            metadata = metadata, \
            geo_lat = geo_lat, \
            geo_lng = geo_lng, \

            creation_time = current, \
            modified_time = current, \
            version = 0 \
    )
    db.insert('photos', **photo)
    if album.cover_photo_id:
        db.update('update albums set photo_count=(select count(id) from photos where album_id=?) where id=?', album_id, album_id)
    else:
        db.update('update albums set photo_count=(select count(id) from photos where album_id=?), cover_photo_id=?, cover_resource_id=? where id=?', album_id, photo['id'], photo['preview_resource_id'], album_id)
    return photo

def set_cover():
    i = ctx.request.input()
    album = db.select_one('select * from albums where id=?', i.album_id)
    photo = db.select_one('select * from photos where id=?', i.ids)
    if photo.album_id!=album.id:
        return dict(error='bad_request')
    db.update('update albums set cover_photo_id=?, cover_resource_id=? where id=?', photo.id, photo.preview_resource_id, album.id)
    return dict(redirect='albums?action=list&id=%s' % album.id)

def do_delete_photos():
    ids = ctx.request.gets('ids')
    album_id = ctx.request['album_id']
    album = db.select_one('select * from albums where id=?', album_id)
    resources = set()
    remove_cover = False
    for pid in ids:
        photo = db.select_one('select * from photos where id=?', pid)
        if photo.album_id!=album_id:
            raise badrequest()
        if pid==album.cover_photo_id:
            remove_cover = True
        resources.add(photo.origin_resource_id)
        resources.add(photo.large_resource_id)
        resources.add(photo.medium_resource_id)
        resources.add(photo.small_resource_id)
        resources.add(photo.preview_resource_id)
    with db.transaction():
        for pid in ids:
            db.update('delete from photos where id=?', pid)
        for rid in resources:
            db.update('update resources set deleted=? where id=?', True, rid)
    if remove_cover:
        db.update('update albums set photo_count=(select count(id) from photos where album_id=?), cover_photo_id=?, cover_resource_id=? where id=?', album_id, '', '', album_id)
    else:
        db.update('update albums set photo_count=(select count(id) from photos where album_id=?) where id=?', album_id, album_id)
    raise seeother('albums?action=list&id=%s' % album_id)

@menu_group('Albums', 40)
@menu_item('All Albums', 0)
def albums():
    i = ctx.request.input(action='', page='1', album='')
    if i.action=='edit':
        kw = db.select_one('select * from albums where id=?', i.id)
        return Template('templates/albumform.html', form_title=_('Edit Album'), action='do_edit_album', **kw)
    if i.action=='list':
        album = db.select_one('select * from albums where id=?', i.id)
        photos = db.select('select * from photos where album_id=? order by creation_time desc', i.id)
        return Template('templates/photos.html', album=album, photos=photos)
    return Template('templates/albums.html', albums=_do_get_albums())

@menu_group('Albums')
@menu_item('Add New Album', 1)
def add_album():
    return Template('templates/albumform.html', form_title=_('Add New Album'), action='do_add_album')

def _do_add_album(name, description, locked=False):
    ' add a new album and return the album object newly created. '
    current = time.time()
    display_order = db.select_int('select count(id) from albums')
    album = Dict(id=db.next_str(), locked=locked, name=name, description=description, cover_photo_id='', cover_resource_id='', photo_count=0, display_order=display_order, creation_time=current, modified_time=current, version=0)
    db.insert('albums', **album)
    return album

@jsonresult
def do_add_album():
    i = ctx.request.input()
    _do_add_album(i.name, i.description)
    return dict(redirect='albums')

@route('/albums')
@util.theme('albums.html')
def get_albums():
    albums = _do_get_albums()
    return dict(albums=albums, __active_menu__='albums')

@route('/album/<album_id>')
@util.theme('album.html')
def get_album(album_id):
    album = db.select_one('select * from albums where id=?', album_id)
    photos = db.select('select * from photos where album_id=? order by id desc', album_id)
    return dict(album=album, photos=photos, __active_menu__='album%s albums' % album_id)

@route('/photo/<photo_id>')
@util.theme('photo.html')
def get_photo(photo_id):
    photo = db.select_one('select * from photos where id=?', photo_id)
    album = db.select_one('select * from albums where id=?', photo.album_id)
    photos = db.select('select * from photos where album_id=? order by id desc', photo.album_id)
    return dict(album=album, photo=photo, photos=photos, __active_menu__='album%s albums' % photo.album_id)

@get('/photo/<photo_id>/comments')
@jsonresult
def get_comments(photo_id):
    after_id = ctx.request.input(next_comment_id=None).next_comment_id
    next_id = None
    cs = get_comments_desc(photo_id, 21, after_id)
    if len(cs)==21:
        next_id = cs[-2].id
        cs = cs[:-1]
    return dict(next_comment_id=next_id, comments=cs)

@post('/photo/comment')
def comment():
    user = ctx.user
    if user is None:
        return dict(error='Please sign in first')
    # i = ctx.request.input(content='')
    # c = i.content.strip()
    # if not c:
    #     return dict(error='Comment cannot be empty')
    # a = db.select_one('select id from articles where id=?', i.article_id)
    # L = [u'<p>%s</p>' % p.replace(u'\r', u'').replace(u'&', u'&amp;').replace(u' ', u'&nbsp;').replace(u'<', u'&lt;').replace(u'>', u'&gt;') for p in c.split(u'\n')]
    # c = make_comment('article', a.id, user, u''.join(L))
    # raise seeother('/article/%s#comments' % i.article_id)

#
# private functions
#

def _is_album_exist(album_id):
    albums = db.select('select id from albums where id=?', album_id)
    return len(albums) > 0

def _do_get_albums():
    L = db.select('select * from albums order by display_order, name')
    if L:
        return L
    return [_do_add_album('Uncategorized', '', True)]

def _do_add_photo(name, tags, category_id, user_id, content, creation_time=None):
    name = name.strip()
    # tags = tags.strip()
    # content = content.strip()
    # if not name:
    #     return dict(error=u'Name cannot be empty', error_field='name')
    # if not content:
    #     return dict(error=u'Content cannot be empty', error_field='content')
    # if not user_id:
    #     return dict(errur=u'Missing user_id', error_field='user_id')
    # if not _is_category_exist(category_id):
    #     return dict(error=u'Invalid category', error_field='category_id')
    # u = db.select_one('select * from users where id=?', user_id)
    # if u.role!=0:
    #     return dict(error=u'User cannot post article')
    # user_name = u.name
    # description = 'a short description...'
    # current = float(creation_time) if creation_time else time.time()
    # article = dict(id=db.next_str(), visible=True, name=name, tags=tags, category_id=category_id, user_id=user_id, user_name=user_name, description=description, content=content, creation_time=current, modified_time=current, version=0)
    # db.insert('articles', **article)
    # return dict(article=article)

if __name__=='__main__':
    import doctest
    doctest.testmod()
