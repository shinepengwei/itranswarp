#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import functools
import util

def menu_group(name, order=(-1)):
    def _decorator(func):
        @functools.wraps(func)
        def _wrapper():
            return func()
        _wrapper.__groupname__ = name
        _wrapper.__grouporder__ = order
        return _wrapper
    return _decorator

def menu_item(name, order=(-1)):
    def _decorator(func):
        @functools.wraps(func)
        def _wrapper():
            return func()
        _wrapper.__itemname__ = name
        _wrapper.__itemorder__ = order
        return _wrapper
    return _decorator
