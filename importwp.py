#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import os, re, json, time, uuid, urllib, urllib2, mimetypes

from datetime import datetime

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from transwarp import db, task, urlfetch
from transwarp.web import UTC, UTC_0

from apps.manage import upload_media
from apps.article import do_get_categories
import util

from conf import dbconf

kwargs = dict([(s, getattr(dbconf, s)) for s in dir(dbconf) if s.startswith('DB_')])
dbargs = kwargs.pop('DB_ARGS', {})
db.init(db_type = kwargs['DB_TYPE'],
        db_schema = kwargs['DB_SCHEMA'],
        db_host = kwargs['DB_HOST'],
        db_port = kwargs.get('DB_PORT', 0),
        db_user = kwargs.get('DB_USER'),
        db_password = kwargs.get('DB_PASSWORD'),
        **dbargs)

def main():
    uname, up = util.get_enabled_upload()
    t = task.fetch_task('import_post')
    if t:
        data = json.loads(t.task_data)
        pubDate = data['pubDate']
        site = data['site']
        content = data['content']
        print site, content
        urls = _extract_link(content, site)
        print urls
        replacedict = dict()
        for u in urls:
            url = str(u[1:-1])
            if os.path.splitext(url)[1]=='':
                continue
            fname = os.path.split(url)[1]
            content_type, fcontent = urlfetch.fetch(url)
            mime, body = _encode_multipart(fname, fcontent, name=os.path.splitext(fname)[0])
            newurl = _upload(data['authorization'], mime, body)
            print newurl
            replacedict[u] = ur'"%s"' % newurl
        print replacedict
        newcontent = content
        for k, v in replacedict.iteritems():
            newcontent = newcontent.replace(k, v)
        newcontent = _fix_content(newcontent)
        #print newcontent
        r = _post(data['authorization'], name=data['title'], category_id=do_get_categories()[0].id, content=newcontent, creation_time=_parse_date(pubDate))
        print 'task done!'
        task.set_task_result(t.id, True)

def _fix_content(c):
    lines = c.replace(u'\r', u'').split(u'\n')
    L = []
    ispre = False
    for line in lines:
        l = line.strip()
        if not ispre and not l:
            print '>>> empty line, continue'
            continue
        ll = l.lower()
        print '>>> len = ', len(ll), ', ll =', ll
        if ispre and not ll.endswith(ur'</pre>'):
            print '>>> pre', line.rstrip()
            L.append(line.rstrip())
        else:
            if ll.startswith(ur'<pre') and ll.endswith(ur'</pre>'):
                print '>>> single <pre>...</pre>', l
                L.append(l)
                continue
            if ll.startswith(ur'<pre'):
                print '>>> start <pre>', l
                ispre = True
                L.append(l)
                continue
            if ll.endswith(ur'</pre>'):
                print '>>> end </pre>', l
                ispre = False
                L.append(l)
                continue
            if ll.startswith(ur'<') and not ll.startswith(ur'<a') and not ll.startswith(ur'<img'):
                print '>>> html <x>', l
                L.append(l)
            else:
                print '>>> add <p>', l
                L.append(ur'<p>%s</p>' % l)
    return u'\n'.join(L)

def _post(auth, **kw):
    print auth
    L = []
    for k, v in kw.iteritems():
        L.append('%s=%s' % (k, _safe_encode(v)))
    data = '&'.join(L)
    url = 'http://127.0.0.1:8080/api/article/create'
    request = urllib2.Request(url, data=data, headers={'Authorization': auth})
    opener = urllib2.build_opener(urllib2.HTTPHandler)
    response = opener.open(request)
    r = json.loads(response.read())
    return r

def _upload(auth, content_type, data):
    url = 'http://127.0.0.1:8080/api/media/upload'
    request = urllib2.Request(url, data=data, headers={'Authorization': auth, 'Content-Type': content_type, 'Content-Length': '%d' % len(data)})
    opener = urllib2.build_opener(urllib2.HTTPHandler)
    response = opener.open(request)
    r = json.loads(response.read())
    if 'error' in r:
        raise StandardError(r['error'])
    return r['filelink']

def _safe_encode(s):
    if isinstance(s, str):
        return urllib.quote(s)
    if isinstance(s, unicode):
        return urllib.quote(s.encode('utf-8'))
    return urllib.quote(str(s))

def _encode_multipart(fname, fcontent, **kw):
    LIMIT = '--------------------%s--' % uuid.uuid4().hex
    CRLF = '\r\n'
    L = []
    for key, value in kw.iteritems():
        L.append('--%s' % LIMIT)
        L.append('Content-Disposition: form-data; name="%s"' % key)
        L.append('')
        L.append(value)
    L.append('--%s' % LIMIT)
    L.append('Content-Disposition: form-data; name="file"; filename="%s"' % fname)
    L.append('Content-Type: %s' % _guess_mime(fname))
    L.append('')
    L.append(fcontent)
    L.append('--%s--' % LIMIT)
    L.append('')
    body = CRLF.join(L)
    content_type = 'multipart/form-data; boundary=%s' % LIMIT
    return content_type, body

def _guess_ext(mime):
    n = mime.find(';')
    if n!=(-1):
        mime = mime[:n]
    return mimetypes.guess_extension(mime)

_RE_TZ = re.compile('^[\+\-][0-9]{4}$')

def _parse_date(s):
    ' parse date like Mon, 14 Feb 2011 12:38:02 +0000 '
    tz = UTC_0
    t = s[:-5]
    if _RE_TZ.match(t):
        tz = UTC('%s:%s' % (t[:3], t[3:]))
    pt = '%a, %d %b %Y %H:%M:%S'
    return time.mktime(datetime.strptime(s[:-6], pt).replace(tzinfo=UTC_0).timetuple())

def _make_re(site):
    s = site.replace('.', '\\.').replace('-', '\\-')
    return re.compile(ur'\"https?\:\/\/%s\/[^\"]*\"' % s)

def _extract_link(content, site):
    regex = _make_re(site)
    L = regex.findall(content)
    return frozenset(L)

def _guess_mime(fname):
    ext = os.path.splitext(fname)[1].lower()
    return mimetypes.types_map.get(ext, 'application/octet-stream')

def parse_wp(f):
    doc = load(f)
    link = value_of_xpath(doc, 'rss/channel/wp:base_site_url')
    if not link:
        link = value_of_xpath(doc, 'rss/channel/wp:base_blog_url')
    if not link:
        link = value_of_xpath(doc, 'rss/channel/link')
    if not link:
        raise ValueError('Could not find link.')
    L = []
    cs = nodes_of_xpath(doc, 'rss/channel/item')
    for c in cs:
        L.append(dict(
            source = 'wordpress',
            site = link,
            title = value_of_xpath(c, 'title'),
            url = value_of_xpath(c, 'link'),
            pubDate = value_of_xpath(c, 'pubDate'),
            content = value_of_xpath(c, 'content:encoded')))
    return L

if __name__=='__main__':
    main()
