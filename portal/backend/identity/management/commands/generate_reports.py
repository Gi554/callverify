import time
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from ...generated_reports import schedule, claim, generate


class Command(BaseCommand):
    help = 'Generate queued and scheduled Orvia reports; never sends email or calls providers.'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true')
        parser.add_argument('--interval', type=int, default=60)

    def handle(self, *args, **options):
        if not 10 <= options['interval'] <= 300:
            raise CommandError('interval 10..300')
        try:
            while True:
                close_old_connections()
                try:
                    queued = schedule()
                    completed = 0
                    for _ in range(9):
                        job = claim()
                        if job is None:
                            break
                        completed += generate(job)
                    self.stdout.write(str({'queued': queued, 'completed': completed}))
                except Exception:
                    if not options['loop']:
                        raise CommandError(
                            'Report worker failed; verify services and database'
                        ) from None
                    self.stderr.write('Report worker unavailable; retry scheduled')
                if not options['loop']:
                    break
                time.sleep(options['interval'])
        except KeyboardInterrupt:
            pass
