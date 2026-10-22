from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from packages.access.tickets import issue
from packages.access.phone_history import verify
from .models import Contact


@override_settings(DEBUG=True)
class AssuranceHistoryProofTests(TestCase):
    def setUp(self):
        self.row = Contact.objects.create(created_by_id=21, name='Synthetic', phone='5145550100')
        self.client = APIClient()
        self.auth(21, 'setter')
        self.base = f'/api/assurance/contacts/{self.row.pk}/'

    def auth(self, pk, role):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, 'assurance', role))

    def test_read_only_proof_does_not_require_lease_and_rechecks_current_number(self):
        response = self.client.post(self.base + 'phone-history-proof/', {}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        claims = verify(response.data['proof'], 21, 'assurance')
        self.assertEqual(claims['destination'], '15145550100')
        body = {'proof': response.data['proof']}
        self.assertTrue(
            self.client.post(self.base + 'phone-history-check/', body, format='json').data[
                'eligible'
            ]
        )
        Contact.objects.filter(pk=self.row.pk).update(phone='5145550101')
        self.assertFalse(
            self.client.post(self.base + 'phone-history-check/', body, format='json').data[
                'eligible'
            ]
        )

    def test_shared_setter_pool_still_binds_proof_to_each_actor_and_denies_other_roles(self):
        self.auth(22, 'setter')
        response = self.client.post(self.base + 'phone-history-proof/', {}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(verify(response.data['proof'], 22, 'assurance')['actor'], 22)
        from django.core import signing

        with self.assertRaises(signing.BadSignature):
            verify(response.data['proof'], 21, 'assurance')
        self.auth(91, 'administrator')
        self.assertEqual(
            self.client.post(self.base + 'phone-history-proof/', {}, format='json').status_code, 403
        )
        self.auth(31, 'advisor')
        self.assertEqual(
            self.client.post(self.base + 'phone-history-proof/', {}, format='json').status_code, 403
        )
