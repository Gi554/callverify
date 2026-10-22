from unittest import skipUnless
from unittest.mock import patch
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection, close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient
from .models import Membership, SessionGeneration, AccessAudit


@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SessionRevocationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.password = 'Mot-de-passe!8125-local'
        self.user = get_user_model().objects.create_user('alice', password=self.password)
        Membership.objects.create(user=self.user, workspace='isolation', role='setter')
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.other = APIClient(enforce_csrf_checks=True)
        self.other.force_login(self.user)
        self.csrf = self.client.get('/api/portal/csrf/').data['csrfToken']
        self.url = '/api/portal/session/revoke-others/'

    def revoke(self, **changes):
        return self.client.post(
            self.url,
            {'current_password': self.password, **changes},
            format='json',
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def test_other_sessions_revoked_current_rotated_and_other_accounts_untouched(self):
        third = get_user_model().objects.create_user('bob', password=self.password)
        unrelated = APIClient()
        unrelated.force_login(third)
        old = self.client.cookies['amx_portal_session'].value
        self.assertEqual(self.other.get('/api/portal/session/').status_code, 200)
        response = self.revoke()
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertNotEqual(old, self.client.cookies['amx_portal_session'].value)
        self.assertEqual(self.client.get('/api/portal/session/').status_code, 200)
        self.assertEqual(self.other.get('/api/portal/session/').status_code, 403)
        self.assertEqual(unrelated.get('/api/portal/session/').status_code, 200)
        audit = AccessAudit.objects.get(action='account.other_sessions_revoked')
        self.assertEqual(audit.metadata, {})
        self.assertNotIn(self.password, str(list(AccessAudit.objects.values())))

    def test_password_csrf_anonymous_and_extra_fields_cannot_revoke(self):
        self.assertEqual(self.revoke(current_password='wrong').status_code, 400)
        self.assertEqual(self.revoke(user_id=999).status_code, 400)
        self.assertEqual(
            self.client.post(
                self.url, {'current_password': self.password}, format='json'
            ).status_code,
            403,
        )
        self.assertEqual(
            APIClient()
            .post(self.url, {'current_password': self.password}, format='json')
            .status_code,
            403,
        )
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertFalse(SessionGeneration.objects.exists())
        self.assertEqual(self.other.get('/api/portal/session/').status_code, 200)

    def test_fresh_real_login_uses_latest_generation(self):
        self.revoke()
        fresh = APIClient(enforce_csrf_checks=True)
        token = fresh.get('/api/portal/csrf/').data['csrfToken']
        response = fresh.post(
            '/api/portal/login/',
            {'username': self.user.username, 'password': self.password},
            format='json',
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(fresh.get('/api/portal/session/').status_code, 200)
        token = fresh.get('/api/portal/csrf/').data['csrfToken']
        self.assertEqual(
            fresh.post(
                self.url, {'current_password': self.password}, format='json', HTTP_X_CSRFTOKEN=token
            ).status_code,
            204,
        )
        self.assertEqual(self.client.get('/api/portal/session/').status_code, 403)
        self.assertEqual(fresh.get('/api/portal/session/').status_code, 200)

    def test_audit_error_rolls_back_generation_without_rotating_session(self):
        old = self.client.cookies['amx_portal_session'].value
        with patch(
            'portal.backend.identity.session_security.AccessAudit.objects.create',
            side_effect=RuntimeError('audit'),
        ):
            with self.assertRaises(RuntimeError):
                self.revoke()
        self.assertFalse(SessionGeneration.objects.exists())
        self.assertEqual(old, self.client.cookies['amx_portal_session'].value)
        self.assertEqual(self.other.get('/api/portal/session/').status_code, 200)

    def test_bad_password_attempts_share_account_security_throttle(self):
        for _ in range(5):
            self.assertEqual(self.revoke(current_password='wrong').status_code, 400)
        self.assertEqual(self.revoke().status_code, 429)
        self.assertFalse(SessionGeneration.objects.exists())

    def test_account_without_workspace_and_password_or_grants_unchanged(self):
        Membership.objects.all().delete()
        before = self.user.password
        self.assertEqual(self.revoke().status_code, 204)
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, before)
        self.assertEqual(self.client.get('/api/portal/session/').data['workspaces'], [])

    def test_revoked_sessions_cannot_issue_tickets_but_can_recover_csrf_and_login(self):
        token = self.other.get('/api/portal/csrf/').data['csrfToken']
        self.revoke()
        response = self.other.post(
            '/api/portal/access/isolation/', {}, format='json', HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(AccessAudit.objects.filter(action='workspace.access').exists())
        token = self.other.get('/api/portal/csrf/').data['csrfToken']
        self.assertEqual(
            self.other.post(
                '/api/portal/login/',
                {'username': 'alice', 'password': self.password},
                format='json',
                HTTP_X_CSRFTOKEN=token,
            ).status_code,
            200,
        )


@skipUnless(connection.vendor == 'postgresql', 'Concurrent session revocation requires PostgreSQL')
@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ConcurrentSessionRevocationTests(TransactionTestCase):
    def test_two_old_sessions_cannot_both_preserve_themselves(self):
        cache.clear()
        password = 'Mot-de-passe!8125-local'
        user = get_user_model().objects.create_user('alice', password=password)
        clients = [APIClient(), APIClient()]
        for client in clients:
            client.force_login(user)
        barrier = Barrier(2)

        def attempt(client):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return client.post(
                    '/api/portal/session/revoke-others/',
                    {'current_password': password},
                    format='json',
                ).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            codes = list(pool.map(attempt, clients))
        self.assertEqual(sorted(codes), [204, 403])
        self.assertEqual(SessionGeneration.objects.get(user=user).generation, 1)
        self.assertEqual(
            AccessAudit.objects.filter(action='account.other_sessions_revoked').count(), 1
        )
        self.assertEqual(clients[codes.index(204)].get('/api/portal/session/').status_code, 200)
        self.assertEqual(clients[codes.index(403)].get('/api/portal/session/').status_code, 403)
