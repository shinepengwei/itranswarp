#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import re, time, logging, socket, struct
from datetime import datetime

from transwarp.web import ctx, get, post, route, seeother, notfound, UTC, Template, Dict
from transwarp import db

from apiexporter import *
import setting, loader

import plugin
from plugin import store

from apps import menu

################################################################################
# Navs
################################################################################

def get_nav_definitions():
    return [
        dict(
            id='custom',
            input='text',
            prompt='Custom Link',
            description='Custom link like http://www.google.com',
            get_url=lambda value: value,
        )]

def _get_navigation(nav_id):
    nav = db.select_one('select * from navigations where id=?', nav_id)
    if nav.website_id!=ctx.website.id:
        raise APIValueError('id', 'invalid id')
    return nav

def _get_all_nav_definitions():
    L = []
    for name, mod in loader.scan_submodules('apps').iteritems():
        func = getattr(mod, 'get_nav_definitions', None)
        if callable(func):
            try:
                L.extend(func())
            except Exception, e:
                logging.exception('Failed to get navigations from module: %s' % name)
    L.sort(cmp=lambda a,b: cmp(a['id'], b['id']))
    return L

@api(role=ROLE_ADMINISTRATORS)
@post('/api/navigations/update')
def api_update_navigation():
    i = ctx.request.input(id='', name='')
    if not i.id:
        raise APIValueError('id', 'id cannot be empty')
    name = i.name.strip()
    if not name:
        raise APIValueError('name', 'name cannot be empty')
    nav = _get_navigation(i.id)
    if nav.name != name:
        db.update('update navigations set name=? where id=?', name, i.id)
    return True

@api(role=ROLE_ADMINISTRATORS)
@post('/api/navigations/create')
def api_create_navigation():
    i = ctx.request.input(kind='', name='', value='')
    if not i.kind:
        raise APIValueError('kind', 'kind cannot be empty')
    name = i.name.strip()
    if not name:
        raise APIValueError('name', 'name cannot be empty')
    for nav in _get_all_nav_definitions():
        if nav['id']==i.kind:
            url = nav['get_url'](i.value)
            if not url:
                raise APIValueError('url', 'url cannot be empty')
            max_disp = db.select_int('select max(display_order) from navigations where website_id=?', ctx.website.id)
            if max_disp is None:
                max_disp = 0
            current = time.time()
            navigation = dict(
                id = db.next_str(),
                website_id = ctx.website.id,
                display_order = 1 + max_disp,
                kind = i.kind,
                name = name,
                description = '',
                url = url,
                creation_time = current,
                modified_time = current,
                version = 0)
            db.insert('navigations', **navigation)
            return True
    raise ValueError('id', 'invalid id')

@api(role=ROLE_ADMINISTRATORS)
@post('/api/navigations/sort')
def api_sort_navigations():
    ids = ctx.request.gets('id')
    navs = loader.load_navigations()
    l = len(navs)
    if l != len(ids):
        raise APIValueError('id', 'bad id list.')
    sets = set([n.id for n in navs])
    odict = dict()
    n = 0
    for o in ids:
        if not o in sets:
            raise APIValueError('id', 'some id was invalid.')
        odict[o] = n
        n = n + 1
    with db.transaction():
        for n in navs:
            db.update('update navigations set display_order=? where id=?', odict.get(n.id, l), n.id)
    return True

def navigations():
    i = ctx.request.input(action='')
    if i.action=='add':
        return Template('templates/navigationform.html', navigations=_get_all_nav_definitions())
    if i.action=='delete':
        nav = _get_navigation(i.id)
        db.update('delete from navigations where id=?', i.id)
        raise seeother('navigations?ts=%s' % time.time())
    return Template('templates/navigations.html', navigations=loader.load_navigations())

################################################################################
# Settings
################################################################################

class DNSError(StandardError):
    pass

RE_IP = re.compile(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
RE_NAME = re.compile(r'[a-z0-9\-]+')

_DNS_MSG_ID = 1

def _get_nameservers():
    '''
    Get nameservers from /etc/resolv.conf.

    >>> _get_nameservers()
    ['10.0.1.1']
    '''
    L = []
    with open('/etc/resolv.conf', 'r') as f:
        for line in f.readlines():
            l = line.strip().lower()
            if not l or l.startswith('#'):
                continue
            ss = l.split()
            if len(ss)==2 and ss[0]=='nameserver' and RE_IP.match(ss[1]):
                L.append(ss[1])
    return L

def _send_udp(ip, msg):
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3.0)
        sock.sendto(msg, (ip, 53))
        return sock.recv(512)
    finally:
        if sock:
            sock.close()

class _Answer(object):

    def __init__(self, data):
        self._data = data
        self._position = 0
        self._length = len(data)

    def __getitem__(self, key):
        return self._data[key]

    def read_byte(self):
        if self._position > self._length:
            raise DNSError('end of response')
        r = ord(self._data[self._position])
        self._position = self._position + 1
        return r

    def read_short(self):
        b1 = self.read_byte()
        b2 = self.read_byte()
        return (b1 << 8) | b2

    def read(self, n):
        if self._position + n > self._length:
            raise DNSError('Bad DNS response.')
        s = self._data[self._position : self._position + n]
        self._position = self._position + n
        return s

    def skip(self, n):
        if self._position + n > self._length:
            raise DNSError('Bad DNS response.')
        self._position = self._position + n

    def read_qname_at(self, offset):
        if offset > self._length:
            raise DNSError('Bad DNS response.')
        old_position = self._position
        self._position = offset
        L = []
        while True:
            l = self.read_byte()
            if l==0:
                break
            if (l & 0xc0)==0xc0:
                raise DNSError('Bad DNS response.')
            s = self.read(l)
            L.append(s)
        self._position = old_position
        return L

    def read_qname(self, qname_only=False, query_only=False):
        L = []
        while True:
            l = self.read_byte()
            if l==0:
                break
            if (l & 0xc0)==0xc0:
                # pointer:
                offset = self.read_byte()
                L.extend(self.read_qname_at(offset))
                break
            else:
                s = self.read(l)
                L.append(s)
        qname = '.'.join(L)
        if qname_only:
            return qname
        qtype = self.read_short()
        if qtype!=5:
            raise DNSError('DNS server does not return CNAME record.')
        qclass = self.read_short()
        if query_only:
            return qname
        # skip ttl:
        self.skip(4)
        rdlength = self.read_short()
        if not rdlength:
            raise DNSError('Bad DNS response.')
        # parse rdata:
        L = []
        while True:
            l = self.read_byte()
            if l==0:
                break
            if (l & 0xc0)==0xc0:
                # pointer:
                offset = self.read_byte()
                L.extend(self.read_qname_at(offset))
                break
            else:
                s = self.read(l)
                L.append(s)
        cname = '.'.join(L)
        return qname, cname

def _parse_answer(msg_id, answer):
    an = _Answer(answer)
    if msg_id != an.read_short():
        raise DNSError('Bad DNS response.')
    flag = an.read_short()
    if (flag & 0x8000)==0:
        raise DNSError('Bad DNS response.')
    if flag & 0x0200:
        raise DNSError('Bad DNS response.')
    if flag & 0x0007:
        raise DNSError('Bad DNS response.')
    qdcount = an.read_short()
    ancount = an.read_short()
    nscount = an.read_short()
    arcount = an.read_short()
    if ancount!=1:
        raise DNSError('No CNAME record from DNS server.')
    for x in range(qdcount):
        an.read_qname(query_only=True)
    qname, cname = an.read_qname()
    return cname

def _lookup_cname(domain):
    '''
    A DNS packet:
    0----------15 16---------31
    | 0x3e 0x31 | | 0x00 0x00 |

    >>> _lookup_cname('-example.com')
    Traceback (most recent call last):
        ...
    DNSError: bad domain name
    '''
    global _DNS_MSG_ID
    if len(domain)>50:
        raise DNSError('Domain name too long.')
    names = domain.split('.')
    if len(names)<=1:
        raise DNSError('Bad domain name.')
    qname_cache = []
    for name in names:
        if not name:
            raise DNSError('Bad domain name.')
        if name.startswith('-') or name.endswith('-') or not RE_NAME.match(name):
            raise DNSError('Bad domain name.')
        qname_cache.append(chr(len(name)))
        qname_cache.append(name)
    qname_cache.append('\x00')
    qname = ''.join(qname_cache)
    # ID:
    msg_id = _DNS_MSG_ID & 0xffff
    _DNS_MSG_ID = msg_id + 1
    # QR = 0 (1 bit, query)
    # Opcode = 0000 (4 bit, standard query)
    # AA = 0 (1 bit, ignored in query)
    # TC = 0 (1 bit, not truncated)
    # RD = 1 (1 bit, recursion desired)
    # RA = 0 (1 bit, recursion available, ignored in query)
    # Z = 000 (3 bit, reserved)
    # RCODE = 0000 (4 bit, ignored in query)
    flag = 0x0100 # 0000 0001 0000 0000
    qdcount = 1 # 16 bit, only 1 question
    ancount = 0 # 16 bit, only in response
    nscount = 0 # 16 bit, only in response
    arcount = 0 # 16 bit, no additional records section
    qtype = 5 # for the canonical name
    qclass = 1 # for internet
    msg = struct.pack('>HHHHHH%dsHH' % len(qname), msg_id, flag, qdcount, ancount, nscount, arcount, qname, qtype, qclass)
    dns_servers = _get_nameservers()
    for dns_server in dns_servers:
        try:
            answer = _send_udp(dns_server, msg)
            cname = _parse_answer(msg_id, answer)
            return cname
        except Exception, e:
            pass
    raise DNSError('Cannot lookup domain.')

def domain():
    i = ctx.request.input(action='')
    error = None
    if i.action=='update':
        domain = str(i.domain.strip().lower())
        if ctx.website.domain!=domain:
            # check cname:
            cname = None
            try:
                cname = _lookup_cname(domain)
                if cname!='host.itranswarp.com':
                    error = 'CNAME is set to \"%s\" rather than \"host.itranswarp.com\"' % cname
            except Exception, e:
                error = e.message
            if cname=='host.itranswarp.com':
                db.update('update websites set domain=? where id=?', domain, ctx.website.id)
                raise seeother('http://%s/auth/signin' % domain)
    return Template('templates/domain.html', error=error, domain=ctx.website.domain)

@api(role=ROLE_GUESTS)
@get('/api/settings/website/gets')
def api_get_website_settings():
    return setting.get_website_settings()

@api(role=ROLE_ADMINISTRATORS)
@post('/api/settings/website/update')
def api_update_website_settings():
    i = ctx.request.input()
    name = i.pop('name', '').strip()
    if not name:
        raise APIValueError('name', 'Name cannot be empty')
    # update website name for table 'website':
    setting.set_website_settings(**i)
    db.update('update websites set name=? where id=?', name, ctx.website.id)
    return True

def general():
    ss = setting.get_website_settings()
    # set website name from table 'website':
    ss['name'] = ctx.website.name
    dt = ss[setting.WEBSITE_DATETIME_FORMAT]
    utc = datetime.utcfromtimestamp(time.time()).replace(tzinfo=UTC('+00:00'))
    now = utc.astimezone(UTC(ss[setting.WEBSITE_TIMEZONE]))
    date_examples = zip(setting.DATE_FORMATS, [now.strftime(f) for f in setting.DATE_FORMATS])
    time_examples = zip(setting.TIME_FORMATS, [now.strftime(f) for f in setting.TIME_FORMATS])
    return Template('templates/general.html', \
        utc_example=utc.strftime(dt), \
        local_example=now.strftime(dt), \
        timezones=setting.TIMEZONES, \
        date_examples=date_examples, \
        time_examples=time_examples, \
        **ss)

################################################################################
# Store
################################################################################

@api(role=ROLE_SUPER_ADMINS)
@post('/api/plugin/store/settings/update')
def api_update_plugin_store_settings():
    i = ctx.request.input()
    if not i.id:
        raise APIValueError('id', 'id must not be empty')
    plugin.set_plugin_settings('store', i.id, **i)
    return True

def storages():
    i = ctx.request.input(action='')
    if i.action=='edit':
        pl = plugin.get_plugin('store', i.id)
        settings = plugin.get_plugin_settings('store', i.id)
        inputs = pl.Plugin.get_inputs()
        for ip in inputs:
            ip['value'] = settings.get(ip['key'], '')
        return Template('templates/pluginform.html', form_title=pl.description, id=i.id, inputs=inputs, submit_url='/api/plugin/store/settings/update', cancel_url='storages')
    if i.action=='enable':
        store.set_enabled_store_name(i.id)
        raise seeother('storages')
    return Template('templates/storages.html', plugins=plugin.get_plugins('store', return_list=True), enabled=store.get_enabled_store_name())

@api(role=ROLE_GUESTS)
@get('/api/resources/url')
def api_url_resource():
    i = ctx.request.input(id='')
    if not i.id:
        raise notfound()
    r = db.select_one('select website_id, url, deleted from resources where id=?', i.id)
    if r.deleted or r.website_id != ctx.website.id:
        raise notfound()
    ctx.response.header('Cache-Control: max-age=36000')
    raise seeother(r.url)

if __name__=='__main__':
    import doctest
    #doctest.testmod()
    _lookup_cname('txest.liaoxuefeng.com')
