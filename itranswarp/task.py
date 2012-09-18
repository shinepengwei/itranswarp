#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
Task queue module for distributed async task.

SQL:

create table tasks (
    id varchar(50) not null,
    queue varchar(50) not null,
    name varchar(50) not null,
    callback varchar(1000) not null,
    timeout bigint not null,
    status varchar(50) not null,
    max_retry int not null,
    retried int not null,
    creation_time real not null,
    execution_time real not null,
    execution_start_time real not null,
    execution_end_time real not null,
    execution_expired_time real not null,
    version bigint not null,
    task_data blob not null,
    task_result blob not null,
    primary key(id),
    index(execution_time)
);

A task statuses:

pending -> executing -> done -+-> notify
   |            |             |
   +-------- retry ? -> error +
'''

import os, sys, time, uuid, random, datetime, functools, threading, logging, collections
from itranswarp.web import Dict
from itranswarp import db

logging.basicConfig(level=logging.INFO)

_DEFAULT_QUEUE = 'default'

_PENDING = 'pending'
_EXECUTING = 'executing'
_ERROR = 'error'
_DONE = 'done'

def create_task(queue, name, callback, task_data=None, max_retry=3, execution_time=None, timeout=60):
    if not queue:
        queue = _DEFAULT_QUEUE
    if not name:
        name = 'unamed'
    if callback is None:
        callback = ''
    if callback and not callback.startswith('http://') and not callback.startswith('https://'):
        return dict(error='cannot_create_task', description='invalid callback')
    if task_data is None:
        task_data = ''
    if max_retry < 0:
        max_retry = 0
    if timeout <= 0:
        return dict(error='cannot_create_task', description='invalid timeout')
    current = time.time()
    if execution_time is None:
        execution_time = current
    task = Dict( \
        id=db.next_id(), \
        queue=queue, \
        name=name, \
        callback=callback, \
        timeout=timeout, \
        status=_PENDING, \
        max_retry=max_retry, \
        retried=0, \
        creation_time=current, \
        execution_time=execution_time, \
        execution_start_time=0.0, \
        execution_end_time=0.0, \
        execution_expired_time=0.0, \
        task_data=task_data,
        task_result='',
        version=0)
    db.insert('tasks', **task)

def _do_fetch_task(queue):
    task = None
    current = time.time()
    with db.transaction():
        tasks = db.select('select * from tasks where execution_time<? and queue=? and status=? order by execution_time limit ?', current, queue, _PENDING, 1)
        if tasks:
            task = tasks[0]
    if not task:
        return None
    expires = current + task.timeout
    with db.transaction():
        if 0==db.update('update tasks set status=?, execution_start_time=?, execution_expired_time=?, version=version+1, where id=? and version=?', _EXECUTING, current, expires, task.id, task.version)
            raise ConflictError()
    return dict(id=task.id, data=task.task_data, version=task.version+1)

def fetch_task(queue):
    if not queue:
        queue = _DEFAULT_QUEUE
    for n in range(3):
        try:
            return _do_fetch_task(queue)
        except ConflictError:
            sleep(random.random() / 4)
    return None

def set_task_result(task_id, success, task_result=None):
    pass

def set_task_timeout(task_id):
    pass

def delete_task(task_id):
    db.update('delete from tasks where id=?', task_id)

def notify_task(task):
    pass

if __name__=='__main__':
    sys.path.append('.')
    dbpath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'doc_test.sqlite3.db')
    _log(dbpath)
    if os.path.isfile(dbpath):
        os.remove(dbpath)
    init('sqlite3', dbpath)
    update('create table user (id int primary key, name text, email text, passwd text, last_modified real)')
    import doctest
    doctest.testmod()
    os.remove(dbpath)
