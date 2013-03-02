#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import functools

from apiexporter import *

def menu(role, group, name, group_order=(-1), name_order=(-1)):
    def _decorator(func):
        @functools.wraps(func)
        def _wrapper():
            if ctx.user.role_id > role:
                raise APIPermissionError('No permission.')
            return func()
        _wrapper.__role__ = role
        _wrapper.__menu_group__ = group
        _wrapper.__menu_name__ = name
        _wrapper.__group_order__ = group_order
        _wrapper.__name_order__ = name_order
        return _wrapper
    return _decorator
