import time
from django.core.management.base import BaseCommand
from core.reminders import send_due_reminders


class Command(BaseCommand):
    help = 'Send lecture reminders (5h/1h/10min for students, 2h/10min for lecturers). Use --loop to keep running.'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true', help='run every 60 seconds')

    def handle(self, *args, **opts):
        while True:
            n = send_due_reminders()
            self.stdout.write('Reminders sent: %d' % n)
            if not opts['loop']:
                break
            time.sleep(60)
