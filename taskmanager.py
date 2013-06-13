#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

# taskmanager.py

import random, time, Queue
from multiprocessing.managers import BaseManager

if __name__=='__main__':
    task_queue = Queue.Queue()
    result_queue = Queue.Queue()

    class QueueManager(BaseManager):
        pass

    QueueManager.register('get_task_queue', callable=lambda: task_queue)
    QueueManager.register('get_result_queue', callable=lambda: result_queue)

    manager = QueueManager(address=('', 5000), authkey='abc')
    manager.start()
    task = manager.get_task_queue()
    result = manager.get_result_queue()
    # put task:
    for i in range(10):
        n = random.randint(0, 10000)
        print('Put task %d...' % n)
        task.put(n)
    # get result:
    print('Try get results...')
    for i in range(10):
        r = result.get(timeout=10)
        print('Result: %s' % r)
    manager.shutdown()
