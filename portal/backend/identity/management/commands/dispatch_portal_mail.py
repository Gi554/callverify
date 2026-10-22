import time
from django.core.management.base import BaseCommand, CommandError
from ...mail_queue import dispatch, cipher
from ...models import PortalMail
from django.db.models import Count


class Command(BaseCommand):
    help = 'Deliver pending portal mail (encrypted outbox), without logging addresses or links.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)
        parser.add_argument('--loop', action='store_true')
        parser.add_argument('--interval', type=int, default=10)
        parser.add_argument(
            '--status', action='store_true', help='Show counts only; do not send mail.'
        )

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 1000 or not 1 <= options['interval'] <= 60:
            raise CommandError('limit 1..1000; interval 1..60')
        if options['status']:
            self.stdout.write(
                str(dict(PortalMail.objects.values_list('status').annotate(total=Count('pk'))))
            )
            return
        cipher()
        try:
            while True:
                self.stdout.write(str(dispatch(options['limit'])))
                if not options['loop']:
                    break
                time.sleep(options['interval'])
        except KeyboardInterrupt:
            pass
