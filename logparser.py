#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import re, logging, collections, urlparse

logging.basicConfig(level=logging.INFO)

def main():
    lighttpd_format = r'%remote_addr %host %user %time "%request" %status %bytes "%referer" "%user_agent"'
    regex, cls = compile_format(lighttpd_format)
    with open('/Users/michael/access.log', 'rb') as f:
        parse(f, regex, cls)

    nginx_format = r'%remote_addr - %user %time "%request" %status %bytes "%referer" "%user_agent"'
    regex, cls = compile_format(nginx_format)
    with open('/Users/michael/shici.access.log', 'rb') as f:
        parse(f, regex, cls)

_FORMATS = {
    '%remote_addr' : (r'[0-9\.]+', 'remote address'),
    '%local_addr' : (r'[0-9\.]+', 'local address'),
    '%remote_host' : (r'[0-9a-zA-Z\-\.]+', 'name or address of remote-host'),
    '%host' : (r'[0-9a-zA-Z\-\.]+', 'HTTP request host name'),
    '%user' : (r'[^\s]+', 'authenticated user'),
    '%time' : (r'\[.+\]', 'timestamp of the request'),
    '%request' : (r'[^\"]+', 'request line'),
    '%status' : (r'\d+', 'status code'),
    '%bytes' : (r'\d+', 'bytes sent for the body'),
    '%referer' : (r'[^\"]*', 'the referer header'),
    '%user_agent' : (r'[^\"]*', 'the user-agent header'),
}

W3CLog = collections.namedtuple('W3CLog', 'remote_addr host time method url status bytes referer_host platform_name platform_version browser_name browser_version')

def restruct_line(line_tuple):
    r_remote_addr = getattr(line_tuple, 'remote_addr', '')
    r_host = getattr(line_tuple, 'host', '')
    r_time = getattr(line_tuple, 'time', '')
    r_request = getattr(line_tuple, 'request', '')
    r_status = getattr(line_tuple, 'status', '')
    r_bytes = getattr(line_tuple, 'bytes', '')
    r_referer = getattr(line_tuple, 'referer', '')
    r_user_agent = getattr(line_tuple, 'user_agent', '')

    p_time = r_time
    p_referer_host = parse_host(r_referer) if r_referer else ''
    p_platform_name, p_platform_version, p_browser_name, p_browser_version = parse_user_agent(r_user_agent)
    return W3CLog(r_remote_addr, r_host, p_time, '', r_request, r_status, r_bytes, p_referer_host, p_platform_name, p_platform_version, p_browser_name, p_browser_version)

_RE_AGENT = re.compile('[\(\)\;]+')

_PLATFORMS = { \
    'windows nt 5.0' : ('Windows', '2000'), \
    'windows nt 5.1' : ('Windows', 'XP'), \
    'windows nt 5.2' : ('Windows', '2003'), \
    'windows nt 6.0' : ('Windows', 'Vista'), \
    'windows nt 6.1' : ('Windows', '7'), \
    'windows nt 6.2' : ('Windows', '8'), \
    'macintosh' : ('Mac', ''), \
    'ipad' : ('iPad', ''), \
    'iphone' : ('iPhone', ''), \
    'blackberry' : ('Black Berry', ''), \
    'ubuntu' : ('Linux', ''), \
}

_PREFIX_PLATFORMS = ( \
    ('symbianos/', 'Symbian', ''), \
    ('android/2.1', 'Android', '2.1'), \
    ('android/2.2', 'Android', '2.2'), \
    ('android/2.3', 'Android', '2.3'), \
    ('android 2.1', 'Android', '2.1'), \
    ('android 2.2', 'Android', '2.2'), \
    ('android 2.3', 'Android', '2.3'), \
    ('android 3.2', 'Android', '3.2'), \
    ('android 4.0', 'Android', '4.0'), \
    ('android 4.1', 'Android', '4.1'), \
)

_PREFIX_BROWSERS_1 = ( \
    ('safari', 'Safari', ''), \
)

_PREFIX_BROWSERS_2 = ( \
    ('chrome/', 'Chrome', ''), \
    ('firefox/', 'Firefox', ''), \

    ('googlebot/', 'Google Bot', ''), \
    ('baiduspider/', 'Baidu Bot', ''), \
    ('bingbot/', 'Bing Bot', ''), \
    ('sosospider/', 'Soso Bot', ''), \
    ('youdaobot/', 'Youdao Bot', ''), \
    ('yahoo!', 'Yahoo Bot', ''), \

    ('python-urllib/', 'Python', ''), \
)

_PREFIX_BROWSERS_3 = ( \
    ('opera/', 'Opera', ''), \
    ('maxthon/', 'Maxthon', ''), \
    ('qqbrowser/', 'QQ Browser', ''), \
    ('tencenttraveler', 'QQ Browser', ''), \
    ('360se', '360 Browser', ''), \
    ('baidubrowser', 'Baidu Browser', ''), \
    ('theworld', 'TheWorld Browser', ''), \
)

_IE = { \
    'msie 10.0' : ('IE', '10'), \
    'msie 9.0' : ('IE', '9'), \
    'msie 8.0' : ('IE', '8'), \
    'msie 7.0' : ('IE', '7'), \
    'msie 7.0b' : ('IE', '7'), \
    'msie 6.1' : ('IE', '6'), \
    'msie 6.01' : ('IE', '6'), \
    'msie 6.0' : ('IE', '6'), \
}

_BROWSERS_FIND_IN_UA = (('sogou web spider', 'Sogou Bot'), ('spider', 'Unknown Bot'), ('bot', 'Unknown Bot'),)

_RE_UA_FINDALL = re.compile(r'\(([^\)]*)\)')
_RE_UA_SPLIT = re.compile(r'\([^\)]*\)')

def parse_user_agent(agent):
    platform = ''
    pversion = ''
    browser = browser1 = browser2 = browser3 = ''
    bversion = ''
    ua = agent.lower()
    ss1 = _RE_UA_SPLIT.split(ua)
    ss2 = _RE_UA_FINDALL.findall(ua)
    L = []
    for s in ss1:
        L.extend(s.strip().split(' '))
    for s in ss2:
        L.extend([p.strip() for p in s.strip().split(';')])

    for s in L:
        pf = _PLATFORMS.get(s)
        if pf:
            platform, pversion = pf
        else:
            for pr, n, v in _PREFIX_PLATFORMS:
                if s.startswith(pr):
                    platform, pversion = n, v
                    break

        # is MSIE?
        br = _IE.get(s, None)
        if br:
            browser, bversion = br
        else:
            if not browser1:
                for pr, n, v in _PREFIX_BROWSERS_1:
                    if s.startswith(pr):
                        browser1, bversion = n, v
                        break
            if not browser2:
                for pr, n, v in _PREFIX_BROWSERS_2:
                    if s.startswith(pr):
                        browser2, bversion = n, v
                        break
            if not browser3:
                for pr, n, v in _PREFIX_BROWSERS_3:
                    if s.startswith(pr):
                        browser3, bversion = n, v
                        break
    if not browser:
        browser = browser3 or browser2 or browser1
    if not browser:
        for s, n in _BROWSERS_FIND_IN_UA:
            if s in ua:
                browser = n
                break

    n = ua.find('curl')
    if n!=(-1):
        print agent
        print
    #    print agent
    #    print L
    #    print platform, ',', browser, ',', version
    #    print
    return platform, pversion, browser, bversion

def parse_host(url):
    r = urlparse.urlparse(url)
    if r.scheme=='http' or r.scheme=='https':
        host = r.netloc
        n = host.find(':')
        return host if n==(-1) else host[:n]
    return ''

def add_st(d, s):
    d[s] = d.get(s, 0) + 1

def parse(fp, regex, tuplecls):
    pf = {}
    bn = {}

    while True:
        line = fp.readline()
        if not line:
            break
        p = parse_line(line.strip(), regex, tuplecls)
        r = restruct_line(p)
        if not r.browser_name.endswith(' Bot'):
            add_st(pf, r.platform_name)
        add_st(bn, r.browser_name)
    print pf
    print bn

def single_word(word):
    L = []
    for ch in word:
        if ch >= 'a' and ch <= 'z':
            L.append(ch)
        elif ch >= 'A' and ch <= 'Z':
            L.append(ch)
        elif ch >= '0' and ch <= '9':
            L.append(ch)
        else:
            L.append(r'\%s' % ch)
    return ''.join(L)

def compile_format(format):
    L = ['^']
    names = []
    for f in format.split(' '):
        if f:
            has_quotes = f.startswith(r'"') and f.endswith(r'"')
            if has_quotes:
                f = f[1:-1]
                L.append(r'\"')
            r = _FORMATS.get(f, (None, None))[0]
            if r:
                L.append('(%s)' % r)
                names.append(f[1:])
            else:
                L.append(single_word(f))
            if has_quotes:
                L.append(r'\"')
            L.append(r'\s+')
    if L[-1]=='\s+':
        L.pop()
    L.append('$')
    s = ''.join(L)
    logging.info('compile format: %s' % format)
    r = re.compile(s)
    logging.info('compiled ok: %s' % s)
    return r, collections.namedtuple('RawLog', ' '.join(names))

def parse_line(line, regex, tuplecls):
    m = regex.match(line)
    if m:
        return tuplecls(*m.groups())
    return None

if __name__=='__main__':
    main()
