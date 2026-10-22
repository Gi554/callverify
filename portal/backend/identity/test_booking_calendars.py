from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.calendar_checks import issue
from packages.access.tickets import issue as ticket
from packages.calendar_connectors import providers
from .models import Membership, CalendarConnection, CalendarSync, AccessAudit
from .calendars import seal
from .test_calendars import OPTIONS, TOKENS


@override_settings(**OPTIONS)
class BookingCalendarTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.actor = get_user_model().objects.create_user('setter')
        self.owner = get_user_model().objects.create_user('advisor')
        Membership.objects.create(user=self.actor, workspace='assurance', role='setter')
        self.membership = Membership.objects.create(
            user=self.owner, workspace='assurance', role='advisor'
        )
        self.start = timezone.now() + timedelta(days=2)
        self.end = self.start + timedelta(minutes=30)
        self.url = '/api/portal/internal/assurance/calendar-check/'

    def proof(self, **kwargs):
        return issue(self.actor.pk, 'setter', self.owner.pk, self.start, self.end, **kwargs)

    def post(self, proof=None):
        return self.client.post(self.url, {'proof': proof or self.proof()}, format='json')

    def connection(self, provider='google'):
        return CalendarConnection.objects.create(
            user=self.owner,
            workspace='assurance',
            provider=provider,
            connected=True,
            payload=seal(TOKENS),
            expires_at=timezone.now() + timedelta(hours=1),
        )

    def test_unconnected_is_explicit_internal_only_and_never_exposes_events(self):
        with patch.object(providers, 'busy') as busy:
            result = self.post()
            self.assertEqual(result.status_code, 200, result.data)
            self.assertEqual(result.data['result'], 'internal_only')
            busy.assert_not_called()
        self.assertEqual(result['Cache-Control'], 'no-store')
        self.assertEqual(set(result.data), {'result', 'checked_at'})

    def test_both_providers_busy_or_free_and_disconnected_fail_closed(self):
        connection = self.connection()
        for provider in ('google', 'microsoft'):
            connection.provider = provider
            connection.save()
            for periods, expected in (
                ([], 'free'),
                ([{'start': self.start.isoformat(), 'end': self.end.isoformat()}], 'busy'),
            ):
                with patch.object(providers, 'busy', return_value=periods) as busy:
                    response = self.post()
                    self.assertEqual(response.status_code, 200, response.data)
                    self.assertEqual(response.data['result'], expected)
                    self.assertEqual(busy.call_args.args[0], provider)
        connection.connected = False
        connection.save()
        self.assertEqual(self.post().status_code, 503)

    def test_provider_failure_and_reauthorization_never_become_free(self):
        connection = self.connection()
        with patch.object(providers, 'busy', side_effect=providers.ProviderError(True)):
            self.assertEqual(self.post().status_code, 503)
        connection.refresh_from_db()
        self.assertFalse(connection.connected)
        self.assertEqual(connection.payload, '')
        self.assertEqual(
            AccessAudit.objects.get(action='calendar.booking_checked').metadata['result'],
            'unavailable',
        )

    def test_only_service_assertion_active_actor_and_owner_allowed(self):
        with patch.object(providers, 'busy') as busy:
            self.assertEqual(
                self.post(ticket(self.actor.pk, 'assurance', 'setter')).status_code, 403
            )
            self.assertEqual(
                self.client.post(self.url, {'owner': self.owner.pk}, format='json').status_code, 400
            )
            proof = self.proof()
            with patch(
                'django.core.signing.time.time', return_value=timezone.now().timestamp() + 121
            ):
                self.assertEqual(self.post(proof).status_code, 403)
            self.membership.active = False
            self.membership.save()
            self.assertEqual(self.post().status_code, 403)
            self.membership.active = True
            self.membership.save()
            self.actor.is_active = False
            self.actor.save()
            self.assertEqual(self.post().status_code, 403)
            busy.assert_not_called()

    def test_reschedule_excludes_only_verified_owned_amx_event(self):
        connection = self.connection()
        ledger = CalendarSync.objects.create(
            connection=connection,
            source_id=7,
            provider='google',
            remote_id='owned-event',
            status='synced',
            expected_start=self.start,
            expected_end=self.end,
        )
        remote = {'id': 'owned-event'}
        with (
            patch('portal.backend.identity.booking_calendars.events.find', return_value=remote),
            patch(
                'portal.backend.identity.booking_calendars.events.interval',
                return_value=(self.start, self.end),
            ),
            patch.object(providers, 'busy', return_value=[]) as busy,
        ):
            self.assertEqual(self.post(self.proof(source_id=7)).status_code, 200)
            self.assertEqual(busy.call_args.kwargs['exclude_id'], 'owned-event')
            ledger.status = 'error'
            ledger.save()
            busy.reset_mock()
            self.assertEqual(self.post(self.proof(source_id=7)).status_code, 503)
            busy.assert_not_called()
