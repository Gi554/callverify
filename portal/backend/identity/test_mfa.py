import base64
import hashlib
import hmac
import struct
import time
from unittest.mock import patch
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import AccessAudit, Membership, PortalMFA
from .mfa import decrypt_secret, encrypt_secret


@override_settings(
    DEBUG=True,
    MFA_ENCRYPTION_KEY=Fernet.generate_key().decode(),
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class PortalMFATests(TestCase):
    def setUp(self):
        cache.clear()
        self.password = 'Admin-Password!2026-local'
        self.user = get_user_model().objects.create_user('secure-admin', password=self.password)
        Membership.objects.create(user=self.user, workspace='assurance', role='administrator')
        self.client = APIClient(enforce_csrf_checks=True)
        self.csrf = self.client.get('/api/portal/csrf/').data['csrfToken']

    def post(self, path, data):
        self.csrf = self.client.get('/api/portal/csrf/').data['csrfToken']
        return self.client.post(path, data, format='json', HTTP_X_CSRFTOKEN=self.csrf)

    def login(self, code=''):
        return self.post(
            '/api/portal/login/',
            {'username': self.user.username, 'password': self.password, 'code': code},
        )

    @staticmethod
    def code(secret, step=None):
        if step is None:
            step = int(time.time() // 30) + 1
        key = base64.b32decode(secret)
        digest = hmac.new(key, struct.pack('>Q', step), hashlib.sha1).digest()
        offset = digest[-1] & 15
        number = (struct.unpack('>I', digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
        return f'{number:06d}'

    def enable(self):
        logged = self.login()
        self.assertEqual(logged.status_code, 200)
        self.assertTrue(logged.data['mfa_required'])
        started = self.post('/api/portal/mfa/', {'action': 'enroll'})
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started['Cache-Control'], 'no-store')
        uri = started.data['uri']
        secret = uri.split('secret=', 1)[1].split('&', 1)[0]
        confirmed = self.post(
            '/api/portal/mfa/',
            {'action': 'confirm', 'code': self.code(secret, int(time.time() // 30))},
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        self.assertEqual(confirmed['Cache-Control'], 'no-store')
        self.assertEqual(len(confirmed.data['backup_codes']), 10)
        row = PortalMFA.objects.get(user=self.user)
        self.assertTrue(row.secret.startswith('enc:'))
        self.assertEqual(decrypt_secret(row.secret), secret)
        self.assertNotIn(confirmed.data['backup_codes'][0], str(row.backup_codes))
        self.assertEqual(self.client.get('/api/portal/session/').data['mfa_required'], False)
        return secret, confirmed.data['backup_codes']

    def test_admin_must_enroll_before_using_the_portal_and_gets_one_time_recovery_codes(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['mfa_required'])
        self.assertEqual(response.data['mfa_enabled'], False)
        with override_settings(DEBUG=False):
            blocked = self.post('/api/portal/access/assurance/', {})
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(self.client.get('/api/portal/session/').status_code, 200)
        secret, backups = self.enable() if not PortalMFA.objects.exists() else ('', [])
        self.assertTrue(secret)
        self.assertEqual(len(backups), 10)
        self.assertEqual(AccessAudit.objects.filter(action='mfa.enabled').count(), 1)

    def test_login_requires_totp_rejects_replay_and_consumes_a_backup_code_once(self):
        secret, backups = self.enable()
        self.assertEqual(self.post('/api/portal/session/', {}).status_code, 204)
        without_code = self.login()
        self.assertEqual(without_code.status_code, 401)
        self.assertTrue(without_code.data['mfa_required'])

        step = int(time.time() // 30) + 1
        accepted = self.login(self.code(secret, step))
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertTrue(accepted.data['mfa_enabled'])
        self.assertEqual(self.post('/api/portal/session/', {}).status_code, 204)
        replay = self.login(self.code(secret, step))
        self.assertEqual(replay.status_code, 401)

        self.assertEqual(self.login(backups[0]).status_code, 200)
        self.assertEqual(self.post('/api/portal/session/', {}).status_code, 204)
        self.assertEqual(self.login(backups[0]).status_code, 401)
        self.assertEqual(len(PortalMFA.objects.get(user=self.user).backup_codes), 9)

    def test_non_admin_login_does_not_require_mfa(self):
        Membership.objects.filter(user=self.user).delete()
        Membership.objects.create(user=self.user, workspace='assurance', role='setter')
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['mfa_required'])
        self.assertTrue(response.data['workspaces'])

    @override_settings(DEBUG=False, MFA_ENABLED=False)
    @patch('packages.access.tickets.key_for', return_value='test-assurance-access-key')
    def test_pilot_disables_portal_mfa_without_deleting_existing_factor(self, _key_for):
        from django.utils import timezone

        factor = PortalMFA.objects.create(
            user=self.user,
            secret=encrypt_secret('JBSWY3DPEHPK3PXP'),
            enabled_at=timezone.now(),
            backup_codes=['already-hashed-code'],
        )
        response = self.login()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data['mfa_required'])
        self.assertFalse(response.data['mfa_enabled'])
        self.assertEqual(self.post('/api/portal/access/assurance/', {}).status_code, 200)
        self.assertEqual(self.post('/api/portal/mfa/', {'action': 'enroll'}).status_code, 404)
        factor.refresh_from_db()
        self.assertTrue(factor.enabled_at)
        self.assertEqual(factor.backup_codes, ['already-hashed-code'])

    def test_wrong_totp_and_extra_mfa_fields_do_not_enable_factor(self):
        self.login()
        started = self.post('/api/portal/mfa/', {'action': 'enroll'})
        self.assertEqual(started.status_code, 200)
        self.assertEqual(
            self.post(
                '/api/portal/mfa/', {'action': 'confirm', 'code': '000000', 'secret': 'x'}
            ).status_code,
            400,
        )
        self.assertFalse(
            PortalMFA.objects.filter(user=self.user, enabled_at__isnull=False).exists()
        )
