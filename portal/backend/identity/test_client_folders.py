from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .models import Membership, PhoneCallAttempt
from uuid import uuid4


@override_settings(DEBUG=True)
class ClientCatalogTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('admin-folders')
        self.member = get_user_model().objects.create_user(
            'client-folders', first_name='Synthetic', last_name='Client'
        )
        Membership.objects.create(user=self.admin, workspace='assurance', role='administrator')
        Membership.objects.create(
            user=self.member, workspace='assurance', role='advisor', active=False, prospect_quota=20
        )
        Membership.objects.create(user=self.member, workspace='isolation', role='client')
        self.client = APIClient()
        self.client.force_login(self.admin)
        self.url = '/api/portal/assurance/client-folders/'

    def test_catalog_keeps_historical_clients_and_searches_without_cross_space_access(self):
        data = self.client.get(self.url, {'search': 'Synthetic'})
        self.assertEqual(data.status_code, 200)
        self.assertEqual(data.data['count'], 1)
        self.assertEqual(
            data.data['results'],
            [{'id': self.member.pk, 'name': 'Synthetic Client', 'active': False, 'quota': 20}],
        )
        self.assertEqual(data['Cache-Control'], 'no-store')
        self.assertEqual(self.client.get('/api/portal/isolation/client-folders/').status_code, 403)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_contact_call_history_filters_workspace_and_never_dispatches_calls(self):
        for space, contact in [('assurance', 42), ('assurance', 43), ('isolation', 42)]:
            PhoneCallAttempt.objects.create(
                request_id=uuid4(),
                user=self.admin,
                workspace=space,
                contact_id=contact,
                extension='501',
                fingerprint='x',
                state='accepted',
            )
        url = '/api/portal/assurance/call-history/'
        data = self.client.get(url, {'contact_id': '42'})
        self.assertEqual(data.data['count'], 1)
        self.assertEqual(data.data['results'][0]['caller']['id'], self.admin.pk)
        self.assertEqual(self.client.get(url, {'contact_id': '-1'}).status_code, 400)
        Membership.objects.filter(user=self.admin).update(role='setter')
        self.assertEqual(self.client.get(url, {'contact_id': '42'}).status_code, 403)
