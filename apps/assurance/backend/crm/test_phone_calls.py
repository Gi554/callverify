from uuid import uuid4
from datetime import timedelta
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue as ticket
from packages.access.phone_calls import verify
from .models import Contact, BusinessAudit


@override_settings(DEBUG=True)
class CallIntentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.auth(21, 'setter')
        self.contact = Contact.objects.create(
            name='Synthetic', phone='+1 (514) 555-0101', created_by_id=21
        )
        self.base = f'/api/assurance/contacts/{self.contact.pk}/'
        self.token = self.client.post(self.base + 'lease/', {}, format='json').data['token']
        self.body = {'token': self.token, 'contact_revision': 0, 'request_id': str(uuid4())}

    def auth(self, pk, role, space='assurance'):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + ticket(pk, space, role))

    def test_intent_is_bound_to_actor_contact_revision_lease_and_source_phone(self):
        response = self.client.post(self.base + 'call-intent/', self.body, format='json')
        self.assertEqual(response.status_code, 200)
        proof = response.data['proof']
        claims = verify(proof, 21)
        self.assertEqual(claims['destination'], '15145550101')
        self.assertEqual(claims['lease'], self.token)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertTrue(
            self.client.post(
                self.base + 'call-intent-check/', {'proof': proof}, format='json'
            ).data['eligible']
        )
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.phone, '+1 (514) 555-0101')
        self.assertEqual(self.contact.revision, 0)
        event = BusinessAudit.objects.get(action='contact.call_intent')
        self.assertNotIn('1514', str(event.metadata))
        self.assertNotIn(self.token, str(event.metadata))

    def test_no_arbitrary_destination_or_extension_and_invalid_lease(self):
        for changes, code in (
            ({'destination': '15145550102'}, 400),
            ({'extension': '999'}, 400),
            ({'contact_revision': 9}, 409),
            ({'token': str(uuid4())}, 409),
        ):
            self.assertEqual(
                self.client.post(
                    self.base + 'call-intent/', {**self.body, **changes}, format='json'
                ).status_code,
                code,
            )
        self.assertEqual(self.client.get(self.base + 'call-intent/').status_code, 405)

    def test_role_and_space_fences(self):
        for role in ('administrator', 'advisor'):
            self.auth(21, role)
            self.assertEqual(
                self.client.post(self.base + 'call-intent/', self.body, format='json').status_code,
                403,
            )
        self.auth(21, 'setter', 'isolation')
        self.assertEqual(
            self.client.post(self.base + 'call-intent/', self.body, format='json').status_code, 401
        )

    def test_recheck_rejects_released_expired_changed_or_other_actor(self):
        proof = self.client.post(self.base + 'call-intent/', self.body, format='json').data['proof']
        Contact.objects.filter(pk=self.contact.pk).update(revision=1)
        self.assertFalse(
            self.client.post(
                self.base + 'call-intent-check/', {'proof': proof}, format='json'
            ).data['eligible']
        )
        Contact.objects.filter(pk=self.contact.pk).update(
            revision=0, lease_expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertFalse(
            self.client.post(
                self.base + 'call-intent-check/', {'proof': proof}, format='json'
            ).data['eligible']
        )
        self.auth(22, 'setter')
        self.assertEqual(
            self.client.post(
                self.base + 'call-intent-check/', {'proof': proof}, format='json'
            ).status_code,
            400,
        )

    def test_uncomposable_source_refused_without_lookup_or_mutation(self):
        for value in ('bad', '5145550101 ext 3', '+33 123456789', '15145550101&_f=245'):
            Contact.objects.filter(pk=self.contact.pk).update(phone=value)
            self.assertEqual(
                self.client.post(self.base + 'call-intent/', self.body, format='json').status_code,
                400,
            )
