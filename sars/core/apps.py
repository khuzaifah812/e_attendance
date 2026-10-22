import os
import sys
import threading
import time
import logging

from django.apps import AppConfig

log = logging.getLogger(__name__)


def _scheduler_loop():
    from django.db import close_old_connections
    from .reminders import send_due_reminders
    time.sleep(15)
    while True:
        try:
            send_due_reminders()
        except Exception as exc:  # never let the thread die
            log.exception('Reminder scheduler error: %s', exc)
        finally:
            close_old_connections()
        time.sleep(60)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from django.conf import settings
        if not settings.ENABLE_SCHEDULER:
            return
        argv = ' '.join(sys.argv)
        if any(c in argv for c in ('migrate', 'makemigrations', 'collectstatic', 'seed_demo', 'send_reminders', 'shell')):
            return
        if 'runserver' in argv and os.environ.get('RUN_MAIN') != 'true':
            return  # only the reloaded child process runs the scheduler
        threading.Thread(target=_scheduler_loop, name='sars-reminders', daemon=True).start()
