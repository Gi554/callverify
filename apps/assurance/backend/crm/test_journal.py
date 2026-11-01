from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from packages.quebec_period import ZONE
from .models import BusinessAudit


@override_settings(DEBUG=True)
class JournalTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + issue(90, 'assurance', 'administrator')
        )
        day = timezone.now().astimezone(ZONE).date()
        self.url = f'/api/assurance/admin-journal/?from={day}&to={day}'
        self.row = BusinessAudit.objects.create(
            actor_id=21,
            action='appointment.changed',
            object_id=12,
            metadata={
                'before': {'status': 'scheduled'},
                'after': {'status': 'cancelled'},
                'client_secret': 'private',
            },
        )
        BusinessAudit.objects.create(actor_id=22, action='other', object_id=13)

    def test_filters_details_redaction_and_read_only(self):
        data = self.client.get(
            self.url + '&actor_id=21&object_id=12&action=appointment.changed'
        ).data
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['metadata']['client_secret'], '[masqué]')
        self.assertEqual(data['results'][0]['metadata']['after']['status'], 'cancelled')
        self.assertEqual(self.client.post('/api/assurance/admin-journal/', {}).status_code, 405)
        self.assertEqual(self.client.get(self.url + '&object_id=bad').status_code, 400)

    def test_non_admin_cannot_read_journal(self):
        for role in ('setter', 'advisor'):
            self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(21, 'assurance', role))
            self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + issue(90, 'isolation', 'administrator')
        )
        self.assertIn(self.client.get(self.url).status_code, (401, 403))
