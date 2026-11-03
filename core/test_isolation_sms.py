from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from packages.access.isolation_events import issue
from .test_isolation_client import client_fixture


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class SmsVisitFeedTests(TestCase):
    def test_feed_requires_signature_and_excludes_pending_cancelled_and_old_visits(self):
        _, visit = client_fixture()
        now = timezone.now()
        visit.starts_at = now + timedelta(days=1)
        visit.ends_at = visit.starts_at + timedelta(hours=1)
        visit.c2_snapshot = {'fields': {'phone': '4387388944', 'email': 'private@example.test'}}
        visit.save()
        since = (now - timedelta(hours=1)).isoformat().replace('+00:00', 'Z')
        path = '/api/internal/isolation/sms-visits/'
        client = APIClient()
        self.assertEqual(client.get(path, {'since': since}).status_code, 403)
        client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + issue('sms_visits', since=since, after=0, visit=0)
        )
        result = client.get(path, {'since': since})
        self.assertEqual(result.status_code, 200)
        row = result.data['visits'][0]
        self.assertEqual(row['phone'], '4387388944')
        self.assertEqual(set(row), {'id', 'phone', 'starts_at', 'created_at'})
        visit.publication = 'google'
        visit.publication_status = 'pending'
        visit.save()
        self.assertEqual(client.get(path, {'since': since}).data['visits'], [])
        visit.publication_status = 'confirmed'
        visit.status = 'cancelled'
        visit.save()
        self.assertEqual(client.get(path, {'since': since}).data['visits'], [])
        visit.status = 'scheduled'
        visit.created_at = now - timedelta(days=1)
        visit.save()
        self.assertEqual(client.get(path, {'since': since}).data['visits'], [])
