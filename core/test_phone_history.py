from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from packages.access.tickets import issue
from packages.access.phone_history import verify
from .test_isolation_activity import assigned_fixture
from .models import Prospect, AuditEvent


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class IsolationHistoryProofTests(TestCase):
    def setUp(self):
        self.row = assigned_fixture()
        self.client = APIClient()
        self.auth(21, 'setter')
        self.base = f'/api/work-queue/{self.row.pk}/'

    def auth(self, pk, role):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, 'isolation', role))

    def test_read_only_proof_has_distinct_purpose_and_detects_change_or_transfer(self):
        response = self.client.post(self.base + 'phone-history-proof/', {}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        claims = verify(response.data['proof'], 21, 'isolation')
        self.assertEqual(claims['destination'], '14165550123')
        body = {'proof': response.data['proof']}
        self.assertTrue(
            self.client.post(self.base + 'phone-history-check/', body, format='json').data[
                'eligible'
            ]
        )
        Prospect.objects.filter(pk=self.row.pk).update(assignment_revision=1)
        self.assertFalse(
            self.client.post(self.base + 'phone-history-check/', body, format='json').data[
                'eligible'
            ]
        )
        Prospect.objects.filter(pk=self.row.pk).update(assigned_setter_id=22)
        self.assertEqual(
            self.client.post(self.base + 'phone-history-check/', body, format='json').status_code,
            404,
        )
        self.assertFalse(AuditEvent.objects.filter(action__contains='call_intent').exists())

    def test_proof_does_not_require_permission_to_place_a_call(self):
        self.row.compliance = 'review'
        self.row.validity = 'invalid'
        self.row.save()
        self.assertEqual(
            self.client.post(self.base + 'phone-history-proof/', {}, format='json').status_code, 200
        )
        self.auth(91, 'administrator')
        self.assertEqual(
            self.client.post(self.base + 'phone-history-proof/', {}, format='json').status_code, 403
        )
        self.auth(22, 'setter')
        self.assertEqual(
            self.client.post(self.base + 'phone-history-proof/', {}, format='json').status_code, 404
        )
