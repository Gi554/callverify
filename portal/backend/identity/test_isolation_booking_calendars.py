from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.calendar_checks import issue
from packages.calendar_connectors import providers
from .models import Membership, CalendarConnection, CalendarSync
from .calendars import seal
from .test_calendars import OPTIONS, TOKENS


@override_settings(**OPTIONS)
class IsolationBookingCalendarTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.actor = get_user_model().objects.create_user('isolation-setter')
        self.owner = get_user_model().objects.create_user('sole-client')
        Membership.objects.create(user=self.actor, workspace='isolation', role='setter')
        self.membership = Membership.objects.create(
            user=self.owner, workspace='isolation', role='client'
        )
        self.start = timezone.now() + timedelta(days=2)
        self.end = self.start + timedelta(minutes=30)
        self.url = '/api/portal/internal/isolation/calendar-check/'

    def proof(self, workspace='isolation', source_id=None):
        return issue(
            self.actor.pk, 'setter', self.owner.pk, self.start, self.end, source_id, workspace
        )

    def post(self, proof=None):
        return self.client.post(self.url, {'proof': proof or self.proof()}, format='json')

    def test_client_calendar_is_distinct_from_assurance_and_free_busy_explicit(self):
        self.assertEqual(self.post().data['result'], 'internal_only')
        row = CalendarConnection.objects.get()
        row.provider = 'microsoft'
        row.connected = True
        row.payload = seal(TOKENS)
        row.expires_at = timezone.now() + timedelta(hours=1)
        row.save()
        for periods, expected in (
            ([], 'free'),
            ([{'start': self.start.isoformat(), 'end': self.end.isoformat()}], 'busy'),
        ):
            with patch.object(providers, 'busy', return_value=periods):
                self.assertEqual(self.post().data['result'], expected)
        self.assertEqual(CalendarConnection.objects.count(), 1)
        self.assertEqual(row.workspace, 'isolation')

    def test_wrong_space_proof_or_inactive_client_never_queries_provider(self):
        with patch.object(providers, 'busy') as busy:
            self.assertEqual(self.post(self.proof('assurance')).status_code, 403)
            self.membership.active = False
            self.membership.save()
            self.assertEqual(self.post().status_code, 403)
            busy.assert_not_called()

    def test_provider_failure_and_reschedule_marker_control(self):
        row = CalendarConnection.objects.create(
            user=self.owner,
            workspace='isolation',
            provider='google',
            connected=True,
            payload=seal(TOKENS),
            expires_at=timezone.now() + timedelta(hours=1),
        )
        with patch.object(providers, 'busy', side_effect=providers.ProviderError()):
            self.assertEqual(self.post().status_code, 503)
        CalendarSync.objects.create(
            connection=row,
            source_id=7,
            provider='google',
            status='synced',
            remote_id='event',
            expected_start=self.start,
            expected_end=self.end,
        )
        with (
            patch(
                'portal.backend.identity.booking_calendars.events.find',
                return_value={'id': 'event'},
            ),
            patch(
                'portal.backend.identity.booking_calendars.events.interval',
                return_value=(self.start, self.end),
            ),
            patch.object(providers, 'busy', return_value=[]) as busy,
        ):
            self.assertEqual(self.post(self.proof(source_id=7)).status_code, 200)
            self.assertEqual(busy.call_args.kwargs['exclude_id'], 'event')
