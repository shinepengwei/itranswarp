#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import json, time

from transwarp import db, task, mail

from apiexporter import *

def send_mail(to_addr, subject, body, high_priority=True):
    queue = QUEUE_MAIL_HIGH if high_priority else QUEUE_MAIL_LOW
    data = dict(to=to_addr, subject=subject, body=body)
    task.create_task(queue=queue, name='Send mail to %s' % to_addr, task_data=json.dumps(data))

if __name__=='__main__':
    import doctest
    doctest.testmod()
 