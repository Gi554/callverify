import time
from django.core.management.base import BaseCommand
from portal.backend.identity.models import CalendarConnection
from portal.backend.identity.calendar_sync import sync_connection
from rest_framework.exceptions import APIException


class Command(BaseCommand):
    help = 'Synchronize opted-in Google/Microsoft calendars. No provider secrets in command output.'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true')
        parser.add_argument('--interval', type=int, default=60)

    def handle(self, *args, **options):
        while True:
            done = failed = 0
            for connection in (
                CalendarConnection.objects.filter(
                    connected=True, auto_sync=True, user__is_active=True
                )
                .select_related('user')
                .order_by('pk')
                .iterator(chunk_size=100)
            ):
                try:
                    sync_connection(connection)
                    done += 1
                except APIException:
                    failed += 1
            self.stdout.write(f'Checked: {done}; unavailable: {failed}')
            if not options['loop']:
                break
            time.sleep(max(10, min(options['interval'], 3600)))
