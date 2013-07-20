#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import os, sys

from transwarp import i18n

_LOCALES = ('zh_cn',)
_EXCLUDES = ('transwarp', 'static', 'docs', 'test')

def _safe_utf8(s):
    if isinstance(s, unicode):
        return s.encode('utf-8')
    return s

def gen(locale, dpath):
    output = '%s.txt' % locale
    if not i18n._RE_LOCALE_FILE.match(output):
        print 'Error: invalid locale.'
        exit(1)
    if not os.path.isdir(dpath):
        print 'dir not exist: %s' % dpath
        exit(1)
    i18ndir = os.path.join(dpath, 'i18n')
    if not os.path.isdir(i18ndir):
        print 'mkdir %s...' % i18ndir
        os.mkdir(i18ndir)
    i18nfile = os.path.join(i18ndir, output)
    new_i18n = i18n._extract_msg(dpath, locale, excludes=_EXCLUDES)
    if os.path.isfile(i18nfile):
        print 'load old %s...' % i18nfile
        exist_i18n = i18n._load(i18nfile)
        for k, v in exist_i18n.iteritems():
            new_i18n[k] = v
    print 'write to %s...' % i18nfile
    with open(i18nfile, 'w') as f:
        L = sorted(new_i18n.items(), cmp=lambda x, y: cmp(x[0].lower(), y[0].lower()))
        f.write('# auto-generated i18n file for %s:\n\n' % locale)
        for k, v in L:
            f.write('%s = %s\n' % (_safe_utf8(k), _safe_utf8(v)))

if __name__=='__main__':
    for loc in _LOCALES:
        gen(loc, os.path.abspath('.'))
