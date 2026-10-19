import time
from django.core.management.base import BaseCommand,CommandError
from ...reminders import generate

class Command(BaseCommand):
    help='Generate current-period Assurance reminders; no SMTP send.'
    def add_arguments(self,parser):
        parser.add_argument('--loop',action='store_true')
        parser.add_argument('--interval',type=int,default=60)
    def handle(self,*args,**options):
        if not 10<=options['interval']<=300:raise CommandError('interval 10..300')
        try:
            while True:
                try:self.stdout.write(str(generate()))
                except Exception:
                    if not options['loop']:raise CommandError('Reminder generation failed') from None
                    self.stderr.write('Reminder generation failed; retry scheduled')
                if not options['loop']:break
                time.sleep(options['interval'])
        except KeyboardInterrupt:pass
