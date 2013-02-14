#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import functools

def menu(group, name, order=0):
    def _decorator(func):
        @functools.wraps(func)
        def _wrapper():
            return func()
        _wrapper.__menu_group__ = group
        _wrapper.__menu_name__ = name
        _wrapper.__menu_order__ = order
        return _wrapper
    return _decorator
