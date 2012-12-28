#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import re, os, time, json, logging, hashlib, mimetypes
from datetime import datetime, timedelta

from transwarp.web import ctx, get, post, route, jsonresult, UTC, UTC_0, Template, Page, Dict, seeother, notfound
from transwarp import db, cache
from apps import menu_group, menu_item
from admin.helper import get_navigation_menu, get_navigation_menus
import util

PAGE_SIZE = 20

def export_navigation_menus():
    def _get_custom_url(menu):
        url = menu.ref
        if url.startswith('http://') or url.startswith('https://'):
            return url
        raise ValueError('Bad url.')
    # END def
    return [
        dict(
            type='custom',
            name='Custom',
            description='Display a custom URL',
            input_type='text',
            input_prompt='URL',
            supplies='http://',
            handler=_get_custom_url),
    ]

@menu_group('Dashboard', 0)
@menu_item('Overview', 0)
def overview():
    # find timestamp at today's 00:00
    site_timezone = util.get_setting('site_timezone', '+00:00')
    utc = datetime.utcfromtimestamp(time.time()).replace(tzinfo=UTC_0)
    now = utc.astimezone(UTC(site_timezone))
    site_dateformat = util.get_setting('site_dateformat', '%B %d, %Y')
    start_date = now - timedelta(days=15)
    end_date = now - timedelta(days=1)
    h_end = int(time.mktime(now.replace(hour=0).timetuple())) // 3600
    keys = map(lambda x: '_TR_%d' % x, range(h_end - 336, h_end))
    results = map(lambda x: 0 if x is None else int(x), cache.client.gets(*keys))
    rs = [(24 * n, 24 * n + 24) for n in range(14)]
    days = [sum(results[l:h]) for l, h in rs]
    d = dict(
        articles = db.select_int('select count(id) from articles'),
        pages = db.select_int('select count(id) from pages'),
        attachments = db.select_int('select count(id) from attachments'),
        users = db.select_int('select count(id) from users'),
        two_weeks = str(days),
        start_date = start_date.strftime(site_dateformat),
        end_date = end_date.strftime(site_dateformat),
    )
    return Template('templates/overview.html', **d)

def do_activate_theme():
    tid = ctx.request.input().id
    util.set_active_theme(tid)
    raise seeother('themes')

@menu_group('Appearance', 70)
@menu_item('Themes', 0)
def themes():
    default = util.get_active_theme()
    themes = util.load_themes()
    for t in themes:
        t.active = t.id==default
    return Template('templates/themes.html', themes=themes)

@menu_group('Plugins', 80)
@menu_item('Signin Plugins', 0)
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

@menu_group('Plugins')
@menu_item('Upload Plugins', 1)
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

@menu_group('Settings', 60)
@menu_item('General', 0)
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

@menu_group('Settings')
@menu_item('Email', 2)
def smtp():
    smtp_configs = util.get_settings(kind='smtp')
    return Template('templates/smtp.html', **smtp_configs)

@jsonresult
def do_save_smtp():
    i = ctx.request.input()
    smtp_sender_name = i.smtp_sender_name.strip().replace('<', '').replace('>', '')
    smtp_sender_email = i.smtp_sender_email.strip()
    if not util.validate_email(smtp_sender_email):
        return dict(error='Bad email address', error_field='smtp_sender_email')
    smtp_host = i.smtp_host.strip()
    smtp_username = i.smtp_username.strip()
    smtp_password = i.smtp_password
    smtp_tls = bool(i.get('smtp_tls', ''))
    smtp_port = i.smtp_port.strip()
    if smtp_port:
        try:
            p = int(smtp_port)
            if p<0 or p>65535:
                raise ValueError('bad port value')
        except ValueError:
            return dict(error='Invalid port', error_field='smtp_port')
    util.set_setting('smtp_sender_name', smtp_sender_name)
    util.set_setting('smtp_sender_email', smtp_sender_email)
    util.set_setting('smtp_host', smtp_host)
    util.set_setting('smtp_port', smtp_port)
    util.set_setting('smtp_username', smtp_username)
    util.set_setting('smtp_password', smtp_password)
    util.set_setting('smtp_tls', 'True' if smtp_tls else '')
    return dict(redirect='smtp')

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

@menu_group('Users', 50)
@menu_item('Roles', 2)
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
    if 'privileges' in i:
        privileges = i.gets('privileges')
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

@menu_group('Users', 20)
@menu_item('All Users', 0)
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

@menu_group('Users')
@menu_item('Add New User', 1)
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
    if user.name!=name:
        updates['name'] = name
    if user.email!=email:
        if db.select('select * from users where email=?', email):
            return dict(error=u'Email was in use by other', error_field='email')
        updates['email'] = email
        updates['verified'] = False
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

@get('/api/resource/url/<rid>')
def api_resource_url(rid):
    rs = db.select('select url from resources where id=?', rid)
    if rs:
        raise seeother(rs[0].url)
    raise notfound()

@menu_group('Settings')
@menu_item('Menus', 1)
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
    fmenu = get_navigation_menu(i.type)
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
    fmenu = get_navigation_menu(i.type)
    ref = i.ref
    url = fmenu.handler(Dict(name=name, description=description, type=i.type, ref=ref))
    kw['type'] = i.type
    kw['ref'] = ref
    kw['url'] = url
    kw['modified_time'] = time.time()
    db.update_kw('menus', 'id=?', i.id, **kw)
    return dict(redirect='menus')

def do_delete_menu():
    menu = db.select_one('select id, url from menus where id=?', ctx.request.input().id)
    db.update('delete from menus where id=?', menu.id)
    raise seeother('menus')

@menu_group('Attachments', 40)
@menu_item('All Attachments', 0)
def attachments():
    i = ctx.request.input(page='1')
    total = db.select_int('select count(id) from attachments')
    page = Page(int(i.page), PAGE_SIZE, total)
    attachments = db.select('select * from attachments order by creation_time desc limit ?,?', page.offset, page.limit)
    return Template('templates/attachments.html', attachments=attachments, page=page)

@menu_group('Attachments')
@menu_item('Add Attachment', 1)
def add_attachment():
    return Template('templates/attachmentform.html', form_title=_('Add New Attachment'), action='do_add_attachment')

@post('/api/attachment/upload')
@jsonresult
def api_attachment_upload():
    if ctx.user is None:
        return dict(error='auth:failed')
    return do_add_attachment()

@jsonresult
def do_add_attachment():
    i = ctx.request.input(name='', description='')
    f = i.file
    ref_type = 'attachment'
    ref_id = db.next_str()
    current = time.time()
    fcontent = f.file.read()
    r1 = util.upload_resource(ref_type, ref_id, f.filename, fcontent)
    r2 = None
    width = 0
    height = 0
    metadata = ''
    if r1['mime'].startswith('image/'):
        td = util.create_thumbnail(fcontent)
        width, height, metadata = td['width'], td['height'], td['metadata']
        r2 = util.upload_resource(ref_type, ref_id, f.filename + '.jpg', td['thumbnail'])
    att = dict( \
            id = ref_id, \
            resource_id = r1['id'], \
            preview_resource_id = '' if r2 is None else r2['id'], \
            name = i.name.strip(), \
            description = i.description.strip(), \
            width = width, \
            height = height, \
            size = r1['size'], \
            mime = r1['mime'], \
            metadata = metadata, \
            creation_time = current, \
            modified_time = current, \
            version = 0 \
    )
    db.insert('attachments', **att)
    return dict(redirect='attachments', filelink='/api/resource/url/%s' % r1['id'])

def do_delete_attachment():
    aid = ctx.request['id']
    a = db.select_one('select * from attachments where id=?', aid)
    util.delete_resources('attachment', aid)
    db.update('delete from attachments where id=?', aid)
    raise seeother('attachments')

@menu_group('Plugins')
@menu_item('Imports', 3)
def imports():
    i = ctx.request.input(action='', page='1')
    if i.action=='upload':
        return Template('templates/importsform.html')
    total = db.select_int('select count(id) from tasks where queue=?', 'import_post')
    page = Page(int(i.page), PAGE_SIZE, total)
    tasks = [] if total==0 else task.get_tasks('import_post', offset=page.offset, limit=page.limit)
    for t in tasks:
        t.task_data = json.loads(t.task_data)
    return Template('templates/imports.html', tasks=tasks, page=page)

@jsonresult
def do_imports():
    i = ctx.request.input(type='')
    # check email and passwd:
    users = db.select('select id from users where email=? and passwd=?', i.email, hashlib.md5(str(i.passwd)).hexdigest())
    if not users:
        return dict(error='Bad email or password', error_field='email')
    f = i.file
    if i.type=='wordpress':
        from plugin import importwp
        importwp.import_wp(f.file, 'Basic %s' % (base64.b64encode('%s:%s' % (i.email, i.passwd))))
        return dict(redirect='imports')
    return dict(error='Import failed')

@menu_group('Plugins')
@menu_item('Exports', 2)
def exports():
    return Template('templates/exportsform.html')

def do_exports():
    i = ctx.request.input(type='xml')
    articles = db.select('select * from articles order by creation_time')
    cols = ('id', 'visible', 'user_id', 'user_name', 'category_id', 'name', 'tags', 'description', 'content', 'creation_time', 'modified_time', 'version')
    if i.type=='sql':
        pass
    if i.type=='xml':
        pass
    ctx.response.content_type = 'application/octet-stream'
    ctx.response.write('just a sample!')
    return None

#
# private functions
#

def _prepare_menus():
    menus = []
    for m in get_navigation_menus():
        menu = Dict(m)
        menu.supplies = m.supplies() if callable(m.supplies) else m.supplies
        menu.input_prompt = m.get('input_prompt', '')
        menus.append(menu)
    return menus

def _get_avatar(email):
    return 'http://www.gravatar.com/avatar/%s' % hashlib.md5(str(email)).hexdigest()
