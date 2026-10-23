import time
from django.core.management.base import BaseCommand, CommandError
from packages.newt.directory import DirectoryUnavailable
from portal.backend.identity.call_journal import run, configured


class Command(BaseCommand):
    help = 'Record NEWT 511 durations on recent CRM calls. No provider line or number is printed.'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true')
        parser.add_argument('--interval', type=int, default=900)

    def handle(self, *args, **options):
        if not configured():
            raise CommandError('Journal NEWT non configuré (NEWT_CDR_HISTORY_ENABLED et accès).')
        while True:
            for workspace in ('assurance', 'isolation'):
                try:
                    summary = run(workspace)
                    self.stdout.write(f'{workspace}: {summary}')
                except DirectoryUnavailable:
                    self.stderr.write(f'{workspace}: journal NEWT indisponible')
            if not options['loop']:
                return
            time.sleep(max(options['interval'], 300))
