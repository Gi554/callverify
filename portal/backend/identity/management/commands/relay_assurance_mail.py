import time
from django.core.management.base import BaseCommand,CommandError
from ...assurance_mail import sync

class Command(BaseCommand):
    help='Pull minimal Assurance notifications into the portal outbox (no SMTP send).'
    def add_arguments(self,parser):
        parser.add_argument('--loop',action='store_true')
        parser.add_argument('--interval',type=int,default=30)
        parser.add_argument('--stream',choices=['all','incidents','reminders','escalations'],default='all')
    def handle(self,*args,**options):
        if not 5<=options['interval']<=60:raise CommandError('interval 5..60')
        try:
            while True:
                try:
                    for stream in (['incidents','reminders','escalations'] if options['stream']=='all' else [options['stream']]):self.stdout.write(str({'stream':stream,**sync(stream)}))
                except Exception:
                    # No exception text: network errors may contain signed credentials.
                    if not options['loop']:raise CommandError('Mail relay failed; verify service, key and configuration') from None
                    self.stderr.write('Mail relay unavailable; retry scheduled')
                if not options['loop']:break
                time.sleep(options['interval'])
        except KeyboardInterrupt:pass
