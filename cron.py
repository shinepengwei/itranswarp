#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' cron job '

import json, time

import logging; logging.basicConfig(level=logging.DEBUG)

from datetime import datetime

from transwarp import db, task, mail

from apiexporter import *

import setting

def cron_job():
    print 'cron job start...'
    t = task.fetch_task(QUEUE_MAIL_HIGH)
    if t is None:
        t = task.fetch_task(QUEUE_MAIL_LOW)
    if t is None:
        return
    logging.info('task loaded: id=%s, execution_id=%s' % (t['id'], t['execution_id']))
    d = json.loads(t.task_data)
    # send mail:
    ss = setting.get_smtp_settings()
    conf = (ss[setting.SMTP_HOST], int(ss[setting.SMTP_PORT]), ss[setting.SMTP_USERNAME], ss[setting.SMTP_PASSWD], bool(ss[setting.SMTP_USE_TLS]))
    from_addr = ss[setting.SMTP_FROM_ADDR]
    to_addr = d['to']
    try:
        mail.send_mail(conf, from_addr, d['to'], d['subject'], d['body'])
    except Exception, e:
        logging.exception('Send mail failed.')
        task.set_task_result(t['id'], t['execution_id'], False)
    else:
        task.set_task_result(t['id'], t['execution_id'], True, 'sent at %s' % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

def cron_loop():
    while True:
        time.sleep(10)
        try:
            cron_job()
        except BaseException, e:
            logging.exception('Cron error.')

if __name__=='__main__':
    import conf_prod
    db.init(db_type = conf_prod.db.get('type', 'mysql'), \
            db_schema = conf_prod.db.get('schema', 'itranswarp'), \
            db_host = conf_prod.db.get('host', 'localhost'), \
            db_port = conf_prod.db.get('port', 3306), \
            db_user = conf_prod.db.get('user', 'www-data'), \
            db_password = conf_prod.db.get('password', 'www-data'), \
            use_unicode = True, charset = 'utf8')
    cron_loop()
