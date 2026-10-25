import time
from django.core.management.base import BaseCommand, CommandError
from portal.backend.identity.calendly_sync import sweep
from portal.backend.identity.calendly_sync import reconcile
from portal.backend.identity.models import CalendlyReservation
from packages.calendar_connectors.calendly import invitee_uri
from packages.calendar_connectors.providers import ProviderError
from rest_framework.exceptions import APIException
from uuid import UUID


class Command(BaseCommand):
    help = 'Process signed Calendly notifications and reconcile linked CRM appointments.'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true')
        parser.add_argument('--interval', type=int, default=30)
        parser.add_argument('--limit', type=int, default=20)
        parser.add_argument('--recover-request')
        parser.add_argument('--invitee')

    def handle(self, *args, **options):
        if not 5 <= options['interval'] <= 60 or not 1 <= options['limit'] <= 100:
            raise CommandError('Interval 5..60 seconds and limit 1..100 required.')
        if options['recover_request'] or options['invitee']:
            try:
                if options['loop'] or not options['recover_request'] or not options['invitee']:
                    raise ValueError()
                row = (
                    CalendlyReservation.objects.select_related('connection')
                    .filter(state__in=['uncertain', 'dispatching'])
                    .get(pk=UUID(options['recover_request']))
                )
                reconcile(row, {'invitee': invitee_uri(options['invitee'])})
                row.refresh_from_db()
                if row.state != 'confirmed' or row.delivered_revision != row.revision:
                    raise ValueError()
            except (
                ValueError,
                TypeError,
                ProviderError,
                APIException,
                CalendlyReservation.DoesNotExist,
            ):
                raise CommandError(
                    'Rapprochement non confirmé. Vérifiez le compte d’origine, le destinataire et le créneau ; aucune réservation n’a été créée par cette commande.'
                ) from None
            self.stdout.write('Rapprochement confirmé ; aucune nouvelle réservation externe créée.')
            return
        try:
            while True:
                self.stdout.write(str(sweep(options['limit'])))
                if not options['loop']:
                    break
                time.sleep(options['interval'])
        except KeyboardInterrupt:
            pass
