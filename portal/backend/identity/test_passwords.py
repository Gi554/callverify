from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .models import Membership, AccessAudit


@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PasswordChangeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.old = 'Ancien-Mdp!6842-local'
        self.new = 'Nouveau-Mdp!9751-local'
        self.user = get_user_model().objects.create_user('alice', password=self.old)
        Membership.objects.create(user=self.user, workspace='isolation', role='setter')
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.url = '/api/portal/password/change/'
        self.csrf = self.client.get('/api/portal/csrf/').data['csrfToken']

    def payload(self, **changes):
        return {
            'current_password': self.old,
            'new_password': self.new,
            'confirmation': self.new,
            **changes,
        }

    def change(self, **changes):
        return self.client.post(
            self.url, self.payload(**changes), format='json', HTTP_X_CSRFTOKEN=self.csrf
        )

    def test_changes_password_rotates_current_session_and_revokes_other_session(self):
        other = APIClient()
        other.force_login(self.user)
        before = self.client.cookies['amx_portal_session'].value
        self.assertEqual(other.get('/api/portal/session/').status_code, 200)
        response = self.change()
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertNotEqual(before, self.client.cookies['amx_portal_session'].value)
        self.assertEqual(self.client.get('/api/portal/session/').status_code, 200)
        self.assertEqual(other.get('/api/portal/session/').status_code, 403)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new))
        self.assertFalse(self.user.check_password(self.old))
        self.assertEqual(Membership.objects.get().role, 'setter')
        audit = AccessAudit.objects.get(action='account.password_changed')
        self.assertEqual(audit.user_id, self.user.pk)
        self.assertEqual(audit.metadata, {})
        self.assertNotIn(self.new, str(list(AccessAudit.objects.values())))

    def test_wrong_current_weak_password_mismatch_and_same_password_rejected(self):
        for changes in (
            {'current_password': 'wrong'},
            {'new_password': 'short', 'confirmation': 'short'},
            {'new_password': 'password1234', 'confirmation': 'password1234'},
            {'confirmation': 'different'},
            {'new_password': self.old, 'confirmation': self.old},
        ):
            self.assertEqual(self.change(**changes).status_code, 400, changes)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.old))
        self.assertFalse(AccessAudit.objects.filter(action='account.password_changed').exists())

    def test_csrf_anonymous_and_unsupported_methods(self):
        self.assertEqual(self.client.post(self.url, self.payload(), format='json').status_code, 403)
        self.assertEqual(APIClient().post(self.url, self.payload(), format='json').status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_cannot_target_other_user_or_send_extra_fields(self):
        other = get_user_model().objects.create_user('bob', password=self.old)
        self.assertEqual(self.change(user_id=other.pk).status_code, 400)
        other.refresh_from_db()
        self.assertTrue(other.check_password(self.old))

    def test_attempts_are_throttled(self):
        for _ in range(5):
            self.assertEqual(self.change(current_password='wrong').status_code, 400)
        self.assertEqual(self.change().status_code, 429)

    def test_audit_failure_rolls_back_password_and_preserves_session(self):
        with patch(
            'portal.backend.identity.passwords.AccessAudit.objects.create',
            side_effect=RuntimeError('audit'),
        ):
            with self.assertRaises(RuntimeError):
                self.change()
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.old))
        self.assertEqual(self.client.get('/api/portal/session/').status_code, 200)

    def test_account_without_workspace_can_manage_its_password(self):
        Membership.objects.all().delete()
        self.assertEqual(self.change().status_code, 204)
        self.assertEqual(self.client.get('/api/portal/session/').data['workspaces'], [])

    def test_new_credentials_allow_login_and_old_credentials_fail(self):
        self.change()
        fresh = APIClient(enforce_csrf_checks=True)
        csrf = fresh.get('/api/portal/csrf/').data['csrfToken']
        for password, expected in ((self.old, 400), (self.new, 200)):
            response = fresh.post(
                '/api/portal/login/',
                {'username': self.user.username, 'password': password},
                format='json',
                HTTP_X_CSRFTOKEN=csrf,
            )
            self.assertEqual(response.status_code, expected)
