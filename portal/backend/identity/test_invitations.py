import re
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from .models import Invitation, Membership, AccessAudit, PortalMail
from .mail_queue import dispatch


@override_settings(
    DEBUG=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PORTAL_PUBLIC_URL='http://localhost:5173',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class InvitationTests(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.admin = get_user_model().objects.create_user('boss', password='Initial-Password!6241')
        Membership.objects.create(user=self.admin, workspace='assurance', role='administrator')
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.admin)
        self.csrf = self.client.get('/api/portal/csrf/').data['csrfToken']
        self.public = APIClient(enforce_csrf_checks=True)
        self.public_csrf = self.public.get('/api/portal/csrf/').data['csrfToken']
        self.base = '/api/portal/workspaces/assurance/invitations/'
        self.accept_url = '/api/portal/invitations/accept/'

    def create(self, **changes):
        response = self.client.post(
            self.base,
            {'username': 'newperson', 'email': 'new@example.test', 'role': 'advisor', **changes},
            format='json',
            HTTP_X_CSRFTOKEN=self.csrf,
        )
        dispatch()
        return response

    def payload(self):
        match = re.search(r'#invite=([a-f0-9-]+):([A-Za-z0-9_-]+)', mail.outbox[-1].body)
        return {
            'id': match[1],
            'token': match[2],
            'password': 'Invitation-Password!4628',
            'confirmation': 'Invitation-Password!4628',
        }

    def accept(self, body):
        return self.public.post(
            self.accept_url, body, format='json', HTTP_X_CSRFTOKEN=self.public_csrf
        )

    def action(self, action):
        response = self.client.post(
            self.base + str(Invitation.objects.get().pk) + '/',
            {'action': action},
            format='json',
            HTTP_X_CSRFTOKEN=self.csrf,
        )
        dispatch()
        return response

    def test_accept_creates_only_the_invited_membership_and_is_single_use(self):
        response = self.create()
        self.assertEqual(response.status_code, 201)
        body = self.payload()
        self.assertFalse(get_user_model().objects.filter(username='newperson').exists())
        self.assertNotIn(body['token'], str(response.data))
        self.assertNotIn(body['token'], str(list(AccessAudit.objects.values())))
        self.assertNotEqual(Invitation.objects.get().token_hash, body['token'])
        self.assertEqual(self.accept(body).status_code, 204)

        user = get_user_model().objects.get(username='newperson')
        self.assertTrue(user.check_password(body['password']))
        self.assertEqual(
            list(Membership.objects.filter(user=user).values_list('workspace', 'role')),
            [('assurance', 'advisor')],
        )
        self.assertNotIn('_auth_user_id', self.public.session)
        self.assertEqual(self.accept(body).status_code, 400)

    def test_permissions_scoping_and_roles(self):
        self.assertEqual(
            self.client.post(
                self.base.replace('assurance', 'isolation'),
                {},
                format='json',
                HTTP_X_CSRFTOKEN=self.csrf,
            ).status_code,
            403,
        )
        self.assertEqual(self.create(role='client').status_code, 400)
        self.assertEqual(self.public.get(self.base).status_code, 403)
        self.create()
        self.assertEqual(self.client.get(self.base).data['count'], 1)
        Membership.objects.filter(user=self.admin).update(role='setter')
        self.assertEqual(self.client.get(self.base).status_code, 403)
        self.assertEqual(self.accept(self.payload()).status_code, 403)
        self.assertFalse(get_user_model().objects.filter(username='newperson').exists())

    def test_expiry_revocation_and_resend_invalidate_old_token(self):
        self.create()
        old = self.payload()
        Invitation.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.accept(old).status_code, 400)
        self.assertEqual(self.action('resend').status_code, 200)
        new = self.payload()
        self.assertNotEqual(old['token'], new['token'])
        self.assertEqual(self.accept(old).status_code, 400)
        self.assertEqual(self.action('revoke').status_code, 200)
        self.assertEqual(self.accept(new).status_code, 400)
        self.assertEqual(self.action('resend').status_code, 409)

    def test_existing_account_and_duplicate_addresses_are_not_replaced(self):
        self.assertEqual(self.create(username='BOSS').status_code, 400)
        self.create()
        self.assertEqual(self.create(username='other').status_code, 400)
        self.assertEqual(
            self.create(username='NEWPERSON', email='another@example.test').status_code, 400
        )
        body = self.payload()
        get_user_model().objects.create_user(
            'elsewhere', email='NEW@example.test', password='Different-Password!6578'
        )
        self.assertEqual(self.accept(body).status_code, 400)
        self.assertFalse(get_user_model().objects.filter(username='newperson').exists())

    def test_validation_csrf_and_throttle(self):
        self.assertEqual(self.client.post(self.base, {}, format='json').status_code, 403)
        self.create()
        body = self.payload()
        self.assertEqual(self.public.post(self.accept_url, body, format='json').status_code, 403)
        self.assertEqual(self.accept({**body, 'role': 'administrator'}).status_code, 400)
        self.assertEqual(
            self.accept({**body, 'password': 'short', 'confirmation': 'short'}).status_code, 400
        )
        self.assertEqual(self.accept({**body, 'confirmation': 'different'}).status_code, 400)
        self.assertEqual(self.accept({**body, 'token': 'invalid'}).status_code, 400)
        cache.clear()
        for _ in range(10):
            self.assertEqual(self.accept({**body, 'token': 'invalid'}).status_code, 400)
        self.assertEqual(self.accept(body).status_code, 429)

    def test_mail_failure_is_reported_without_secrets_and_can_be_retried(self):
        with patch(
            'portal.backend.identity.mail_queue.send_mail', side_effect=RuntimeError('secret')
        ):
            response = self.create()
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['mail_queued'])
        self.assertNotIn('secret', str(response.data))
        self.assertTrue(AccessAudit.objects.filter(action='mail.retry').exists())
        self.assertEqual(self.action('resend').status_code, 200)
        self.assertEqual(self.accept(self.payload()).status_code, 204)

    def test_accept_audit_failure_rolls_back_account_and_access(self):
        self.create()
        body = self.payload()
        with patch(
            'portal.backend.identity.invitations.AccessAudit.objects.create',
            side_effect=RuntimeError('audit unavailable'),
        ):
            with self.assertRaises(RuntimeError):
                self.accept(body)
        self.assertFalse(get_user_model().objects.filter(username='newperson').exists())
        self.assertIsNone(Invitation.objects.get().accepted_at)
        self.assertEqual(self.accept(body).status_code, 204)


from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from django.db import connection, close_old_connections
from django.test import TransactionTestCase


@skipUnless(connection.vendor == 'postgresql', 'Row locking requires PostgreSQL')
@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ConcurrentInvitationTests(TransactionTestCase):
    def test_two_acceptances_create_one_account_and_one_grant(self):
        from .invitations import digest

        cache.clear()
        issuer = get_user_model().objects.create_user('issuer', password='Initial-Password!6241')
        Membership.objects.create(user=issuer, workspace='isolation', role='administrator')
        row = Invitation.objects.create(
            username='invited',
            email='invited@example.test',
            workspace='isolation',
            role='setter',
            issuer=issuer,
            token_hash=digest('temporary-token'),
            expires_at=timezone.now() + timedelta(hours=24),
        )

        def attempt(_):
            close_old_connections()
            try:
                client = APIClient(enforce_csrf_checks=True)
                csrf = client.get('/api/portal/csrf/').data['csrfToken']
                return client.post(
                    '/api/portal/invitations/accept/',
                    {
                        'id': str(row.pk),
                        'token': 'temporary-token',
                        'password': 'Invitation-Password!4628',
                        'confirmation': 'Invitation-Password!4628',
                    },
                    format='json',
                    HTTP_X_CSRFTOKEN=csrf,
                ).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(sorted(results), [204, 400])
        self.assertEqual(get_user_model().objects.filter(username='invited').count(), 1)
        self.assertEqual(Membership.objects.filter(user__username='invited').count(), 1)
        self.assertEqual(AccessAudit.objects.filter(action='invitation.accepted').count(), 1)
