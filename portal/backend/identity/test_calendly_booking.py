from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase, override_settings
from django.db import connection, close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient
from packages.calendar_connectors import calendly as provider
from packages.calendar_connectors.providers import ProviderError
from packages.calendar_connectors.calendly_bridge import proof
from .models import Membership, CalendlyConnection, CalendlyReservation, CalendlyWebhook
from .calendars import seal
from .test_calendly import OPTIONS, TOKENS, PROFILE, EVENT


@override_settings(**OPTIONS)
class CalendlyDispatchTests(TestCase):
    def setUp(self):
        cache.clear()
        self.actor = get_user_model().objects.create_user('setter')
        self.owner = get_user_model().objects.create_user('advisor')
        Membership.objects.create(user=self.actor, workspace='assurance', role='setter')
        Membership.objects.create(user=self.owner, workspace='assurance', role='advisor')
        self.row = CalendlyConnection.objects.create(
            user=self.owner,
            connected=True,
            expires_at=timezone.now() + timedelta(hours=2),
            payload=seal(
                {
                    'tokens': {**TOKENS, 'scopes': list(provider.BOOKING_SCOPES)},
                    'profile': PROFILE,
                    'event_types': [EVENT],
                    'selected': EVENT['uri'],
                }
            ),
        )
        self.start = (timezone.now() + timedelta(days=4)).replace(microsecond=0)
        CalendlyWebhook.objects.create(
            connection=self.row,
            owner_uri=TOKENS['owner'],
            organization='https://api.calendly.com/organizations/org-1',
            state='active',
        )
        self.data = {
            'actor': self.actor.pk,
            'role': 'setter',
            'owner': self.owner.pk,
            'request_id': str(uuid4()),
            'event_type': EVENT['uri'],
            'starts_at': self.start.isoformat(),
            'ends_at': (self.start + timedelta(minutes=30)).isoformat(),
            'name': 'Prospect',
            'email': 'prospect@example.invalid',
        }
        self.client = APIClient()
        self.url = '/api/portal/internal/calendly/'
        self.uri = 'https://api.calendly.com/scheduled_events/event/invitees/invitee'

    def call(self, action='reserve', **changes):
        return self.client.post(
            self.url, {'proof': proof(action, {**self.data, **changes})}, format='json'
        )

    def test_unsigned_or_wrong_role_never_reaches_provider(self):
        with patch.object(provider, 'create_invitee') as create:
            self.assertEqual(self.client.post(self.url, self.data, format='json').status_code, 400)
            self.assertEqual(self.call(role='administrator').status_code, 403)
            create.assert_not_called()

    def test_timeout_is_not_dispatched_twice_and_keeps_durable_intent(self):
        with (
            patch.object(provider, 'times', return_value=[self.start.isoformat()]),
            patch.object(
                provider, 'create_invitee', side_effect=ProviderError(code='uncertain')
            ) as create,
        ):
            self.assertEqual(self.call().data['state'], 'uncertain')
            self.assertEqual(self.call().data['state'], 'uncertain')
            create.assert_called_once()
        self.assertEqual(CalendlyReservation.objects.count(), 1)
        self.assertNotIn(self.data['email'], str(CalendlyReservation.objects.get().__dict__))

    def test_success_busy_and_forbidden_are_distinct_and_idempotent(self):
        remote = {
            'invitee': self.uri,
            'starts_at': self.data['starts_at'],
            'ends_at': self.data['ends_at'],
            'status': 'scheduled',
        }
        with (
            patch.object(provider, 'times', return_value=[self.start.isoformat()]),
            patch.object(provider, 'create_invitee', return_value=self.uri) as create,
            patch.object(provider, 'appointment', return_value=remote),
        ):
            self.assertEqual(self.call().data['state'], 'confirmed')
            self.row.connected = False
            self.row.save()
            self.assertEqual(self.call().data['state'], 'confirmed')
            create.assert_called_once()
        self.row.connected = True
        self.row.save()
        with (
            patch.object(provider, 'times', return_value=[]),
            patch.object(provider, 'create_invitee') as create,
        ):
            self.assertEqual(self.call(request_id=str(uuid4())).data['state'], 'rejected')
            create.assert_not_called()
        with (
            patch.object(provider, 'times', return_value=[self.start.isoformat()]),
            patch.object(provider, 'create_invitee', side_effect=ProviderError(code='rejected')),
        ):
            self.assertEqual(self.call(request_id=str(uuid4())).data['state'], 'rejected')


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL concurrency')
@override_settings(**OPTIONS)
class CalendlyDispatchConcurrencyTests(TransactionTestCase):
    setUp = CalendlyDispatchTests.setUp

    def test_parallel_same_request_dispatches_only_once(self):
        remote = {
            'invitee': self.uri,
            'starts_at': self.data['starts_at'],
            'ends_at': self.data['ends_at'],
            'status': 'scheduled',
        }

        def send(_):
            close_old_connections()
            try:
                return (
                    APIClient()
                    .post(self.url, {'proof': proof('reserve', self.data)}, format='json')
                    .status_code
                )
            finally:
                close_old_connections()

        with (
            patch.object(provider, 'times', return_value=[self.start.isoformat()]),
            patch.object(provider, 'create_invitee', return_value=self.uri) as create,
            patch.object(provider, 'appointment', return_value=remote),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            self.assertEqual(list(pool.map(send, range(2))), [200, 200])
            create.assert_called_once()
