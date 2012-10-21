#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' Management of users, menus, media, etc. '

import os, re, time, logging, hashlib, mimetypes

from datetime import datetime
from StringIO import StringIO

try:
    import Image
except ImportError:
    from PIL import Image

import admin

from itranswarp.web import ctx, get, post, route, seeother, Template, jsonresult, UTC, Dict, Page, badrequest, UTC
from itranswarp import db, cache

import util

PAGE_SIZE = 20

def _get_custom_url(menu):
    url = menu.ref
    if url.startswith('http://') or url.startswith('https://'):
        return url
    raise ValueError('Bad url.')

def _get_avatar(email):
    return 'http://www.gravatar.com/avatar/%s' % hashlib.md5(str(email)).hexdigest()

def register_navigation_menus():
    return [
        dict(type='custom', name='Custom', description='Display a custom URL.', input_type='text', input_prompt='URL:', supplies='http://', handler=_get_custom_url),
    ]

def register_admin_menus():
    return [
        dict(order=0, title=u'Dashboard', items=[
            dict(title=u'Dashboard', role=0, handler='dashboard'),
#            dict(title=u'Updates', role=0, handler='dashboard'),
        ]),
        dict(order=400, title=u'Media', items=[
            dict(title=u'Media Library', role=0, handler='media'),
            dict(title=u'Add New Media', role=0, handler='add_media'),
        ]),
        dict(order=600, title=u'Users', items=[
            dict(title=u'Users', role=0, handler='users'),
            dict(title=u'Add New User', role=0, handler='add_user'),
            dict(title=u'Roles', role=0, handler='roles'),
        ]),
        dict(order=1000, title=u'Settings', items=[
            dict(title=u'General', role=0, handler='general'),
            dict(title=u'Menus', role=0, handler='menus'),
            dict(title=u'Widgets', role=0, handler='widgets'),
            dict(title=u'Layout', role=0, handler='menus'),
        ]),
        dict(order=1100, title=u'Plugins', items=[
            dict(title='Signins', role=0, handler='signins'),
            dict(title='Uploads', role=0, handler='uploads'),
        ]),
    ]

def dashboard():
    # find timestamp at today's 00:00
    site_timezone = util.get_setting('site_timezone', '+00:00')
    utc = datetime.utcfromtimestamp(time.time()).replace(tzinfo=UTC('+00:00'))
    now = utc.astimezone(UTC(site_timezone))
    h_end = int(time.mktime(now.replace(hour=0).timetuple())) // 3600
    keys = map(lambda x: '_TR_%d' % x, range(h_end - 336, h_end))
    results = map(lambda x: 0 if x is None else int(x), cache.client.gets(*keys))
    rs = [(24 * n, 24 * n + 24) for n in range(14)]
    days = [sum(results[l:h]) for l, h in rs]
    d = dict(
        articles = db.select_int('select count(id) from articles'),
        pages = db.select_int('select count(id) from pages'),
        media = db.select_int('select count(id) from media'),
        users = db.select_int('select count(id) from users'),
        two_weeks = str(days),
    )
    return Template('templates/dashboard.html', **d)

def signins():
    i = ctx.request.input(action='')
    if i.action=='edit':
        settings, description, enabled = util.get_plugin_settings('signin', i.id)
        return Template('templates/pluginform.html', plugin_type='signin', form_title=description, action='save_signin', id=i.id, name=i.id, settings=settings, enabled=enabled)
    providers = util.get_plugin_providers('signin')
    return Template('templates/signins.html', providers=providers)

@jsonresult
def save_signin():
    i = ctx.request.input(enabled='')
    util.save_plugin_settings('signin', i.id, i.enabled=='True', i)
    return dict(redirect='signins')

def order_signins():
    orders = ctx.request.gets('order')
    util.order_plugin_providers('signin', orders)
    raise seeother('signins')

def uploads():
    i = ctx.request.input(action='')
    if i.action=='edit':
        settings, description, enabled = util.get_plugin_settings('upload', i.id)
        return Template('templates/pluginform.html', plugin_type='upload', form_title=description, action='save_upload', id=i.id, name=i.id, settings=settings, enabled=enabled)
    providers = util.get_plugin_providers('upload')
    return Template('templates/uploads.html', providers=providers)

@jsonresult
def save_upload():
    i = ctx.request.input(enabled='')
    enabled = i.enabled=='True'
    util.save_plugin_settings('upload', i.id, enabled, i)
    if enabled:
        # set other uploads enabled=False:
        names = [n for n in util.get_plugin_providers('upload', names_only=True) if n!=i.id]
        for n in names:
            util.save_plugin_setting_enabled('upload', n, False)
    return dict(redirect='uploads')

def general():
    TIMEZONES = [
        '-12:00',
        '-11:00',
        '-10:00',
        '-09:30',
        '-09:00',
        '-08:00',
        '-07:00',
        '-06:00',
        '-05:00',
        '-04:30',
        '-04:00',
        '-03:30',
        '-03:00',
        '-02:00',
        '-01:00',
        '+00:00',
        '+01:00',
        '+02:00',
        '+03:00',
        '+03:30',
        '+04:00',
        '+04:30',
        '+05:00',
        '+05:30',
        '+05:45',
        '+06:00',
        '+06:30',
        '+07:00',
        '+08:00',
        '+09:00',
        '+09:30',
        '+10:00',
        '+10:30',
        '+11:00',
        '+11:30',
        '+12:00',
        '+12:45',
        '+13:00',
        '+14:00',
    ]
    DATE_FORMATS = [
        '%B %d, %Y',
        '%a, %b %d, %Y',
        '%b %d, %Y',
        '%m/%d/%Y',
        '%d/%m/%Y',
        '%Y-%m-%d',
        '%y-%m-%d',
    ]
    TIME_FORMATS = [
        '%H:%M:%S',
        '%H:%M',
        '%I:%M %p',
    ]
    settings = util.get_settings()
    site_timezone = settings.pop('site_timezone', '+00:00')
    if not site_timezone in TIMEZONES:
        site_timezone = '+00:00'
    site_dateformat = settings.pop('site_dateformat', DATE_FORMATS[0])
    site_timeformat = settings.pop('site_timeformat', TIME_FORMATS[0])
    dt_format = '%s %s' % (site_dateformat, site_timeformat)
    utc = datetime.utcfromtimestamp(time.time()).replace(tzinfo=UTC('+00:00'))
    now = utc.astimezone(UTC(site_timezone))
    date_examples = zip(DATE_FORMATS, [now.strftime(f) for f in DATE_FORMATS])
    time_examples = zip(TIME_FORMATS, [now.strftime(f) for f in TIME_FORMATS])
    return Template('templates/general.html', \
        current=(utc.year, utc.month, utc.day, utc.hour, utc.minute, utc.second), \
        date_examples=date_examples, time_examples=time_examples, timezones=TIMEZONES, \
        site_dateformat=site_dateformat, site_timeformat=site_timeformat, \
        local_example=now.strftime(dt_format), utc_example=utc.strftime(dt_format), \
        site_timezone=site_timezone, \
        **settings)

@jsonresult
def do_save_settings():
    settings = util.get_settings()
    for k, v in ctx.request.input().iteritems():
        if k in settings and settings[k]==v:
            continue
        util.set_setting(k, v)
    return dict(redirect='general')

def _get_roles():
    roles = db.select('select * from roles order by id')
    if roles:
        return roles
    current = time.time()
    role_admin = Dict(id=0, locked=True, name=u'Administrator', privileges='', creation_time=current, modified_time=current, version=0)
    role_guest = Dict(id=100000000, locked=True, name=u'Guest', privileges='', creation_time=current, modified_time=current, version=0)
    db.insert('roles', **role_admin)
    db.insert('roles', **role_guest)
    return [role_admin, role_guest]

def roles():
    i = ctx.request.input(action='')
    if i.action=='edit':
        role = db.select_one('select * from roles where id=?', i.id)
        return Template('templates/roleform.html', form_title=_('Edit Role'), action='do_edit_role', **role)
    if i.action=='add':
        return Template('templates/roleform.html', form_title=_('Add New Role'), action='do_add_role')
    if i.action=='delete':
        pass
    return Template('templates/roles.html', roles=_get_roles())

@jsonresult
def do_add_role():
    i = ctx.request.input()
    name = i.name.strip()
    # check:
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    privileges = []
    if 'privileges' in request:
        privileges = request.gets('privileges')
    # check:
    max_id = db.select_one('select max(id) as m from roles where id<100000000').m
    current = time.time()
    role = Dict(id=max_id+1, locked=False, name=name, privileges=','.join(privileges), creation_time=current, modified_time=current, version=0)
    db.insert('roles', **role)
    return dict(redirect='roles')

@jsonresult
def do_edit_role():
    i = ctx.request.input()
    role_id = int(i.id)
    name = i.name.strip()
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    role = db.select_one('select * from roles where id=?', role_id)
    if role.locked:
        return dict(error=u'Cannot edit this role', error_field='')
    privileges = []
    if 'privileges' in request:
        privileges = request.gets('privileges')
    # check:
    db.update_kw('roles', 'id=?', role_id, name=name, privileges=','.join(privileges), modified_time=time.time())
    return dict(redirect='roles')

def do_delete_role():
    role_id = int(request.input().id)
    if role_id==0:
        raise badrequest()
    db.update('delete from roles where id=?', role_id)
    raise seeother('roles')

def users():
    i = ctx.request.input(action='', role='', page='1')
    if i.action=='edit':
        user = db.select_one('select * from users where id=?', i.id)
        return Template('templates/userform.html', roles=_get_roles(), form_title=_('Edit User'), action='do_edit_user', **user)
    total = db.select_int('select count(id) from users where role=?', int(i.role)) if i.role else db.select_int('select count(id) from users')
    page = Page(int(i.page), PAGE_SIZE, total)
    users = None
    if i.role:
        users=db.select('select * from users where role=? order by creation_time desc limit ?,?', int(i.role), page.offset, page.limit)
    else:
        users=db.select('select * from users order by creation_time desc limit ?,?', page.offset, page.limit)
    return Template('templates/users.html', roles=_get_roles(), role=i.role, users=users, page=page)

def add_user():
    return Template('templates/userform.html', roles=_get_roles(), form_title=_('Add New User'), action='do_add_user')

_RE_PASSWD = re.compile(r'^[0-9a-f]{32}$')

@jsonresult
def do_edit_user():
    i = ctx.request.input()
    name = i.name.strip()
    role = int(i.role)
    email = i.email.strip().lower()
    passwd = i.passwd
    # check:
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    if not email:
        return dict(error=u'Email cannot be empty', error_field='email')
    if passwd:
        m = _RE_PASSWD.match(passwd)
        if not m:
            return dict(error=u'Invalid form', error_field='')
    user = db.select_one('select * from users where id=?', i.id)
    updates = {}
    if user.email!=email:
        if db.select('select * from users where email=?', email):
            return dict(error=u'Email was in use by other', error_field='email')
        updates['email'] = email
    if user.role!=role:
        if user.locked:
            return dict(error=u'Cannot change role.', error_field='role')
        updates['role'] = role
    if passwd:
        updates['passwd'] = passwd
    if updates:
        db.update_kw('users', 'id=?', i.id, **updates)
    return dict(redirect='users')

def do_delete_user():
    uid = ctx.request['id']
    db.update('delete from users where id=?', uid)
    raise seeother('users')

@jsonresult
def do_add_user():
    i = ctx.request.input()
    name = i.name.strip()
    role = int(i.role)
    email = i.email.strip().lower()
    passwd = i.passwd
    # check:
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    if not email:
        return dict(error=u'Email cannot be empty', error_field='email')
    if not util.validate_email(email):
        return dict(error=u'Invalid email', error_field='email')
    if not passwd:
        return dict(error=u'Password cannot be empty', error_field='passwd1')
    m = _RE_PASSWD.match(passwd)
    if not m:
        return dict(error=u'Invalid form', error_field='')
    # logic:
    if db.select('select id from users where email=?', email):
        return dict(error=u'Email is exist', error_field='email')
    current = time.time()
    user = Dict(id=db.next_str(), name=name, role=role, email=email, passwd=passwd, verified=False, image_url=_get_avatar(email), creation_time=current, modified_time=current, version=0)
    db.insert('users', **user)
    return dict(redirect='users')

def _prepare_menus():
    menus = []
    for m in admin.get_navigation_menus():
        menu = Dict(m)
        menu.supplies = m.supplies() if callable(m.supplies) else m.supplies
        menu.input_prompt = m.get('input_prompt', '')
        menus.append(menu)
    return menus

def menus():
    i = ctx.request.input(action='')
    if i.action=='edit':
        menu = db.select_one('select * from menus where id=?', i.id)
        return Template('templates/menuform.html', form_title=_('Edit Menu'), action='do_edit_menu', menus=_prepare_menus(), **menu)
    if i.action=='add':
        return Template('templates/menuform.html', form_title=_('Add Menu'), action='do_add_menu', menus=_prepare_menus())
    return Template('templates/menus.html', menus=util.get_menus())

def order_menus():
    orders = ctx.request.gets('order')
    menus = util.get_menus()
    l = len(menus)
    if l!=len(orders):
        raise badrequest()
    odict = dict()
    n = 0
    for o in orders:
        odict[o] = n
        n = n + 1
    with db.transaction():
        for m in menus:
            db.update('update menus set display_order=? where id=?', odict.get(m.id, l), m.id)
    raise seeother('menus')

@jsonresult
def do_add_menu():
    i = ctx.request.input(ref='')
    name = i.name.strip()
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    description = i.description.strip()
    fmenu = admin.get_navigation_menu(i.type)
    ref = i.ref
    url = fmenu.handler(Dict(name=name, description=description, type=i.type, ref=ref))
    count = db.select_one('select count(id) as num from menus').num
    current = time.time()
    menu = Dict(id=db.next_str(), name=name, description=description, type=i.type, display_order=count, ref=ref, url=url, creation_time=current, modified_time=current, version=0)
    db.insert('menus', **menu)
    return dict(redirect='menus')

@jsonresult
def do_edit_menu():
    i = ctx.request.input(ref='')
    menu = db.select_one('select * from menus where id=?', i.id)
    kw = dict()
    name = i.name.strip()
    if not name:
        return dict(error=u'Name cannot be empty', error_field='name')
    if name!=menu.name:
        kw['name'] = name
    description = i.description.strip()
    if description!=menu.description:
        kw['description'] = description
    fmenu = admin.get_navigation_menu(i.type)
    ref = i.ref
    url = fmenu.handler(Dict(name=name, description=description, type=i.type, ref=ref))
    kw['type'] = i.type
    kw['ref'] = ref
    kw['url'] = url
    kw['modified_time'] = time.time()
    db.update_kw('menus', 'id=?', i.id, **kw)
    return dict(redirect='menus')

def do_delete_menu():
    menu = db.select_one('select id, url from menus where id=?', request.input().id)
    db.update('delete from menus where id=?', menu.id)
    raise seeother('menus')

def media():
    i = ctx.request.input(page='1')
    total = db.select_int('select count(id) from media')
    page = Page(int(i.page), PAGE_SIZE, total)
    media = db.select('select * from media order by creation_time desc limit ?,?', page.offset, page.limit)
    return Template('templates/media.html', media=media, page=page)

def add_media():
    return Template('templates/mediaform.html', form_title=_('Add Media'), action='do_add_media')

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

@jsonresult
def do_add_media():
    i = ctx.request.input(name='', description='')
    description = i.description.strip()
    f = i.file
    fname = f.filename
    name = i.name.strip()
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
    fcontent = f.file.read()
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

def do_delete_media():
    mid = ctx.request['id']
    m = db.select_one('select * from media where id=?', mid)
    uploader = util.create_upload_provider(m.uploader)
    uploader.delete(m.ref)
    db.update('delete from media where id=?', mid)
    raise seeother('media')

@jsonresult
def do_get_media():
    i = ctx.request.input(type='', page_index='1', page_size='20')

if __name__=='__main__':
    import doctest
    doctest.testmod()
