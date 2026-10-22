from uuid import uuid4
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from packages.access.tickets import issue as ticket
from packages.access.phone_calls import verify, issue
from .models import Prospect, Suppression, AuditEvent
from .test_isolation_activity import assigned_fixture


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class IsolationCallIntentTests(TestCase):
    def setUp(self):
        self.row = assigned_fixture()
        self.row.compliance = 'allowed'
        self.row.save()
        self.client = APIClient()
        self.auth(21, 'setter')
        self.base = f'/api/work-queue/{self.row.pk}/'
        self.body = {'revision': 0, 'request_id': str(uuid4())}

    def auth(self, pk, role, space='isolation'):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + ticket(pk, space, role))

    def post(self, **changes):
        return self.client.post(self.base + 'call-intent/', {**self.body, **changes}, format='json')

    def test_proof_binds_assigned_actor_prospect_revision_and_normalized_destination(self):
        result = self.post()
        self.assertEqual(result.status_code, 200, result.data)
        claims = verify(result.data['proof'], 21, 'isolation')
        self.assertEqual(claims['contact'], self.row.pk)
        self.assertEqual(claims['destination'], '14165550123')
        self.assertNotIn('lease', claims)
        self.assertTrue(
            self.client.post(
                self.base + 'call-intent-check/', {'proof': result.data['proof']}, format='json'
            ).data['eligible']
        )
        self.row.refresh_from_db()
        self.assertEqual(self.row.assignment_revision, 0)
        self.assertEqual(self.row.phone.line_status, 'unknown')
        audit = AuditEvent.objects.get(action='isolation.prospect.call_intent')
        self.assertEqual(audit.metadata['actor_portal_id'], 21)
        self.assertEqual(audit.metadata['setter_name'], 'Setter')

    def test_other_setter_client_admin_and_other_space_cannot_authorize(self):
        self.auth(22, 'setter')
        self.assertEqual(self.post().status_code, 404)
        for role in ('administrator', 'client'):
            self.auth(21, role)
            self.assertEqual(self.post().status_code, 403)
        self.auth(21, 'setter', 'assurance')
        self.assertEqual(self.post().status_code, 401)

    def test_no_arbitrary_number_or_extension_and_stale_revision(self):
        for values, status in (
            ({'destination': '15145550101'}, 400),
            ({'extension': '501'}, 400),
            ({'revision': 1}, 409),
        ):
            self.assertEqual(self.post(**values).status_code, status)
        self.assertEqual(self.client.get(self.base + 'call-intent/').status_code, 405)

    def test_compliance_suppression_and_missing_phone_fail_closed(self):
        self.row.compliance = 'review'
        self.row.save()
        self.assertEqual(self.post().status_code, 400)
        self.row.compliance = 'allowed'
        self.row.save()
        Suppression.objects.create(e164=self.row.phone.e164, reason='test exclusion')
        self.assertEqual(self.post().status_code, 400)
        Suppression.objects.all().delete()
        self.row.phone = None
        self.row.save()
        self.assertEqual(self.post().status_code, 400)

    def test_final_check_revalidates_transfer_number_and_exclusion(self):
        proof = self.post().data['proof']
        payload = {'proof': proof}
        Suppression.objects.create(e164=self.row.phone.e164, reason='late exclusion')
        self.assertFalse(
            self.client.post(self.base + 'call-intent-check/', payload, format='json').data[
                'eligible'
            ]
        )
        Suppression.objects.all().delete()
        self.row.phone.e164 = '+15145550101'
        self.row.phone.save()
        self.assertFalse(
            self.client.post(self.base + 'call-intent-check/', payload, format='json').data[
                'eligible'
            ]
        )
        Prospect.objects.filter(pk=self.row.pk).update(assigned_setter_id=22)
        self.assertEqual(
            self.client.post(self.base + 'call-intent-check/', payload, format='json').status_code,
            404,
        )

    def test_assurance_proof_and_expired_proof_refused(self):
        from unittest.mock import patch
        from django.utils import timezone

        assurance = issue(21, self.row.pk, 0, uuid4(), '14165550123', uuid4())
        self.assertEqual(
            self.client.post(
                self.base + 'call-intent-check/', {'proof': assurance}, format='json'
            ).status_code,
            400,
        )
        proof = self.post().data['proof']
        with patch('django.core.signing.time.time', return_value=timezone.now().timestamp() + 61):
            self.assertEqual(
                self.client.post(
                    self.base + 'call-intent-check/', {'proof': proof}, format='json'
                ).status_code,
                400,
            )
