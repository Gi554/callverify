from uuid import uuid4
from datetime import timedelta
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .test_isolation_client import client_fixture
from .models import IsolationVisit, IsolationVisitResult, ProspectActivity, IsolationFollowUp


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class IsolationFolderTests(TestCase):
    def setUp(self):
        self.prospect, self.visit = client_fixture()
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + issue(99, 'isolation', 'administrator')
        )
        self.url = '/api/client-folders/72/'

    def test_statuses_calls_tasks_and_foreign_client_separation(self):
        IsolationVisitResult.objects.create(
            visit=self.visit,
            performed=True,
            closed=True,
            outcome='completed',
            note='Synthetic sale',
        )
        values = {
            f.attname: getattr(self.visit, f.attname)
            for f in IsolationVisit._meta.fields
            if not f.primary_key and f.name not in ('created_at', 'request_id')
        }
        cancelled = IsolationVisit.objects.create(
            **{**values, 'request_id': uuid4(), 'status': 'cancelled'}
        )
        IsolationVisitResult.objects.create(
            visit=cancelled, performed=True, closed=True, outcome='completed'
        )
        IsolationVisit.objects.create(**{**values, 'request_id': uuid4(), 'client_id': 73})
        ProspectActivity.objects.create(
            prospect=self.prospect,
            request_id=uuid4(),
            fingerprint='x',
            author_portal_id=21,
            author_role='setter',
            kind='call_result',
            body='Synthetic note',
            changes={'result': 'callback'},
        )
        IsolationFollowUp.objects.create(
            prospect=self.prospect,
            request_id=uuid4(),
            fingerprint='x',
            created_by_id=21,
            note='Synthetic task',
            due_at=timezone.now() - timedelta(hours=1),
        )
        data = self.client.get(self.url).data
        self.assertEqual(data['summary']['statuses'], {'performed': 1, 'cancelled': 1})
        self.assertEqual(data['summary']['sales'], 1)
        self.assertEqual(data['summary']['prospects'], 1)
        self.assertEqual(data['summary']['call_results'], 1)
        self.assertEqual(data['summary']['overdue_tasks'], 1)
        self.assertEqual(self.client.get(self.url, {'section': 'appointments'}).data['count'], 2)
        calls = self.client.get(self.url, {'section': 'calls'}).data['results']
        self.assertEqual((calls[0]['actor_id'], calls[0]['status']), (21, 'callback'))
        self.assertEqual(
            self.client.get(self.url, {'section': 'tasks'}).data['results'][0]['note'],
            'Synthetic task',
        )
        empty = self.client.get('/api/client-folders/74/').data
        self.assertEqual(empty['count'], 0)
        self.assertEqual(empty['summary']['sales'], 0)
        self.assertEqual(self.client.get('/api/client-folders/', {'ids': '72,73'}).status_code, 200)

    def test_admin_permission_is_not_implicitly_granted_by_another_workspace(self):
        for workspace, role in [
            ('isolation', 'setter'),
            ('isolation', 'client'),
            ('isolation', 'closer'),
            ('assurance', 'administrator'),
        ]:
            self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(99, workspace, role))
            self.assertIn(self.client.get(self.url).status_code, (401, 403))
        self.client.credentials()
        self.assertIn(self.client.get(self.url).status_code, (401, 403))
