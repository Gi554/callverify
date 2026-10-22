from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .models import Membership, AccessAudit
from packages.access.followups import verify_owner


@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TaskOwnerProofTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('admin', password='password-test')
        self.setter = get_user_model().objects.create_user('setter')
        self.membership = Membership.objects.create(
            user=self.admin, workspace='assurance', role='administrator'
        )
        self.target = Membership.objects.create(
            user=self.setter, workspace='assurance', role='setter'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.url = '/api/portal/assurance/task-owner-proof/'

    def attest(self, **changes):
        return self.client.post(
            self.url, {'task_id': 12, 'setter_id': self.setter.pk, **changes}, format='json'
        )

    def test_active_setter_attestation_bound_to_actor_and_task(self):
        result = self.attest()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            verify_owner(result.data['proof'], self.admin.pk, 12),
            {'id': self.setter.pk, 'name': 'setter'},
        )
        self.assertEqual(result.data['expires_in'], 120)
        self.assertTrue(
            AccessAudit.objects.filter(
                action='follow_up.owner_attested', workspace='assurance'
            ).exists()
        )

    def test_revoked_or_wrong_target_role_is_denied(self):
        for changes in (
            {'active': False},
            {'active': True, 'role': 'advisor'},
            {'role': 'administrator'},
            {'role': 'setter', 'workspace': 'isolation'},
        ):
            for key, value in changes.items():
                setattr(self.target, key, value)
            self.target.save()
            self.assertEqual(self.attest().status_code, 400)
        self.target.workspace = 'assurance'
        self.target.save()
        self.setter.is_active = False
        self.setter.save()
        self.assertEqual(self.attest().status_code, 400)

    def test_only_explicit_active_assurance_admin_can_attest(self):
        self.client.force_authenticate(self.setter)
        self.assertEqual(self.attest().status_code, 403)
        self.client.force_authenticate(self.admin)
        self.membership.active = False
        self.membership.save()
        self.assertEqual(self.attest().status_code, 403)
        self.admin.is_superuser = True
        self.admin.save()
        self.assertEqual(self.attest().status_code, 403)
        self.client.force_authenticate(None)
        self.assertIn(self.attest().status_code, (401, 403))

    def test_reject_invalid_payload_and_require_session_csrf(self):
        self.assertEqual(self.attest(task_id=0).status_code, 400)
        self.assertEqual(self.attest(extra=True).status_code, 400)
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(
            client.post(
                self.url, {'task_id': 12, 'setter_id': self.setter.pk}, format='json'
            ).status_code,
            403,
        )
