import re
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework.test import APIClient
from .models import AccessAudit
from .mail_queue import dispatch


@override_settings(
    DEBUG=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PORTAL_PUBLIC_URL='http://localhost:5173',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class RecoveryTests(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.user = get_user_model().objects.create_user(
            'alice', email='alice@example.test', password='Ancien-Mdp!6842-local'
        )
        self.client = APIClient(enforce_csrf_checks=True)
        self.csrf = self.client.get('/api/portal/csrf/').data['csrfToken']
        self.request_url = '/api/portal/password/reset/request/'
        self.confirm_url = '/api/portal/password/reset/confirm/'
        self.password = 'Nouveau-Mdp!9751-local'

    def request(self, email='alice@example.test'):
        response = self.client.post(
            self.request_url, {'email': email}, format='json', HTTP_X_CSRFTOKEN=self.csrf
        )
        dispatch()
        return response

    def payload(self, **changes):
        return {
            'uid': urlsafe_base64_encode(force_bytes(self.user.pk)),
            'token': default_token_generator.make_token(self.user),
            'password': self.password,
            'confirmation': self.password,
            **changes,
        }

    def confirm(self, body=None):
        return self.client.post(
            self.confirm_url, body or self.payload(), format='json', HTTP_X_CSRFTOKEN=self.csrf
        )

    def test_generic_response_and_email_link_uses_fixed_origin_and_fragment(self):
        known = self.request()
        unknown = self.request('absent@example.test')
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['alice@example.test'])
        self.assertIn('http://localhost:5173/crm#reset=', mail.outbox[0].body)
        html, mime = mail.outbox[0].alternatives[0]
        self.assertEqual(mime, 'text/html')
        self.assertIn('Choisir mon mot de passe', html)
        self.assertIn('http://localhost:5173/crm#reset=', html)
        self.assertIn('30 minutes', html)
        self.assertIn('Orvia CRM', mail.outbox[0].subject)
        self.assertNotIn('token', str(known.data))
        self.assertEqual(known['Cache-Control'], 'no-store')
        self.assertEqual(AccessAudit.objects.get(action='account.recovery_requested').metadata, {})

    def test_inactive_unusable_and_ambiguous_email_do_not_send(self):
        self.user.is_active = False
        self.user.save()
        self.request()
        self.assertEqual(len(mail.outbox), 0)
        self.user.is_active = True
        self.user.set_unusable_password()
        self.user.save()
        self.request()
        self.assertEqual(len(mail.outbox), 0)
        self.user.set_password('Ancien-Mdp!6842-local')
        self.user.save()
        get_user_model().objects.create_user(
            'other', email=self.user.email, password='Long-Password!123'
        )
        self.request()
        self.assertEqual(len(mail.outbox), 0)

    def test_email_token_resets_once_and_invalidates_old_sessions(self):
        session = APIClient()
        session.force_login(self.user)
        self.request()
        uid, token = re.search(r'#reset=([^:]+):([A-Za-z0-9_-]+)', mail.outbox[0].body).groups()
        data = self.payload(uid=uid, token=token)
        self.assertEqual(self.confirm(data).status_code, 204)
        self.assertEqual(self.confirm(data).status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))
        self.assertEqual(session.get('/api/portal/session/').status_code, 403)
        self.assertEqual(self.client.get('/api/portal/session/').status_code, 403)
        self.assertTrue(AccessAudit.objects.filter(action='account.password_reset').exists())

    def test_expired_invalid_uid_changed_email_and_revoked_account_are_denied(self):
        payload = self.payload()
        for uid in ('bad', '-1', urlsafe_base64_encode(b'9999999999999999999999999')):
            self.assertEqual(self.confirm({**payload, 'uid': uid}).status_code, 400)
        with patch.object(
            default_token_generator,
            '_now',
            return_value=default_token_generator._now() + timedelta(seconds=1801),
        ):
            self.assertEqual(self.confirm(payload).status_code, 400)
        self.user.email = 'changed@example.test'
        self.user.save()
        self.assertEqual(self.confirm(payload).status_code, 400)
        payload = self.payload()
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.confirm(payload).status_code, 400)

    def test_password_validation_csrf_and_throttle(self):
        self.assertEqual(
            self.client.post(
                self.request_url, {'email': self.user.email}, format='json'
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(self.confirm_url, self.payload(), format='json').status_code, 403
        )
        for changes in (
            {'confirmation': 'different'},
            {'password': 'short', 'confirmation': 'short'},
            {'user_id': 999},
        ):
            self.assertEqual(self.confirm(self.payload(**changes)).status_code, 400)
        cache.clear()
        for _ in range(5):
            self.assertEqual(self.request('absent@example.test').status_code, 200)
        self.assertEqual(self.request().status_code, 429)

    def test_mail_failure_is_generic_and_audited_without_secrets(self):
        with patch(
            'portal.backend.identity.mail_queue.send_mail',
            side_effect=RuntimeError('private SMTP data'),
        ):
            response = self.request()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('SMTP', str(response.data))
        self.assertTrue(AccessAudit.objects.filter(action='mail.retry').exists())

    def test_audit_failure_rolls_back_password(self):
        with patch(
            'portal.backend.identity.recovery.AccessAudit.objects.create',
            side_effect=RuntimeError('audit'),
        ):
            with self.assertRaises(RuntimeError):
                self.confirm()
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password(self.password))
