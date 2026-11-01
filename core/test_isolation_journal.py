from datetime import timedelta
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from packages.quebec_period import ZONE
from .models import AuditEvent


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class JournalTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + issue(90, 'isolation', 'administrator')
        )
        day = timezone.now().astimezone(ZONE).date()
        self.url = f'/api/admin-journal/?from={day}&to={day}'
        self.row = AuditEvent.objects.create(
            action='isolation.visit.result_recorded',
            object_id='12',
            metadata={
                'actor_portal_id': 21,
                'before': {'performed': False},
                'after': {'performed': True},
                'proof': 'private',
                'nested': {'access_token': 'private'},
            },
        )
        AuditEvent.objects.create(action='platform.secret.changed', object_id='12', metadata={})

    def test_scope_filters_and_redacted_before_after(self):
        result = self.client.get(self.url + '&actor_id=21&object_id=12')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['count'], 1)
        row = result.data['results'][0]
        self.assertEqual(row['actor_id'], 21)
        self.assertEqual(row['metadata']['proof'], '[masqué]')
        self.assertEqual(row['metadata']['nested']['access_token'], '[masqué]')
        self.assertEqual(row['metadata']['before'], {'performed': False})
        self.assertEqual(row['metadata']['after'], {'performed': True})
        self.assertEqual(result['Cache-Control'], 'no-store')
        self.assertEqual(self.client.get(self.url + '&action=other').data['count'], 0)

    def test_read_only_and_permissions(self):
        self.assertEqual(self.client.post('/api/admin-journal/', {}).status_code, 405)
        for role in ('setter', 'client', 'closer'):
            self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(21, 'isolation', role))
            self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + issue(90, 'assurance', 'administrator')
        )
        self.assertIn(self.client.get(self.url).status_code, (401, 403))

    def test_pagination_validation_and_period_scope(self):
        for _ in range(26):
            AuditEvent.objects.create(action='isolation.test', metadata={})
        old = AuditEvent.objects.create(action='isolation.old', metadata={})
        AuditEvent.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=4))
        result = self.client.get(self.url)
        self.assertEqual(result.data['count'], 27)
        self.assertEqual(len(result.data['results']), 25)
        self.assertEqual(len(self.client.get(self.url + '&page=2').data['results']), 2)
        for suffix in ('&page=0', '&page=bad', '&actor_id=no', '&from=bad'):
            self.assertEqual(self.client.get(self.url + suffix).status_code, 400)
        self.assertEqual(
            self.client.get(
                f'/api/admin-journal/{old.pk}/' + self.url[self.url.index('?') :]
            ).status_code,
            404,
        )
