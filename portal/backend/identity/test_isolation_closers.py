from importlib import import_module
from datetime import timedelta
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue, verify
from .models import Membership, AccessAudit, SessionGeneration, Invitation
from .invitations import digest


@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RetiredCloserTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.users = {}
        for role in ('administrator', 'client', 'setter', 'closer'):
            user = get_user_model().objects.create_user(role)
            Membership.objects.create(user=user, workspace='isolation', role=role)
            self.users[role] = user
        self.client.force_authenticate(self.users['administrator'])

    def test_no_new_closer_grants_invitations_or_role_updates(self):
        response = self.client.post(
            '/api/portal/workspaces/isolation/users/',
            {'username': 'newcloser', 'role': 'closer', 'password': 'Strong-test-password-456!'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            '/api/portal/workspaces/isolation/invitations/',
            {'username': 'newcloser', 'email': 'test@example.test', 'role': 'closer'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        member = Membership.objects.get(user=self.users['setter'])
        url = f'/api/portal/workspaces/isolation/users/{member.pk}/'
        self.assertEqual(self.client.patch(url, {'role': 'closer'}, format='json').status_code, 400)
        member.refresh_from_db()
        self.assertEqual(member.role, 'setter')
        retired = Membership.objects.get(user=self.users['closer'])
        with self.assertRaises(ValidationError):
            retired.full_clean()
        response = self.client.patch(
            f'/api/portal/workspaces/isolation/users/{retired.pk}/', {'active': True}, format='json'
        )
        self.assertEqual(response.status_code, 400)

    def test_legacy_membership_is_not_exposed_or_granted_a_ticket(self):
        listed = self.client.get('/api/portal/workspaces/isolation/users/').data
        self.assertEqual(listed['count'], 3)
        self.client.force_authenticate(self.users['closer'])
        self.assertEqual(self.client.get('/api/portal/session/').data['workspaces'], [])
        self.assertEqual(
            self.client.post('/api/portal/access/isolation/', {}, format='json').status_code, 403
        )
        with self.assertRaises(signing.BadSignature):
            verify(issue(77, 'isolation', 'closer'), 'isolation')
        self.assertEqual(verify(issue(21, 'isolation', 'setter'), 'isolation')['role'], 'setter')

    def test_retired_directory_cannot_create_proofs(self):
        for role in ('administrator', 'client', 'setter'):
            self.client.force_authenticate(self.users[role])
            self.assertEqual(self.client.get('/api/portal/isolation/closers/').data['count'], 0)
            self.assertEqual(
                self.client.post('/api/portal/isolation/closers/', {}, format='json').status_code,
                410,
            )
            self.assertFalse(AccessAudit.objects.filter(action='visit.closer_attested').exists())

    def test_migration_archives_only_closers_revokes_invites_and_preserves_other_roles(self):
        user = self.users['closer']
        Membership.objects.create(user=user, workspace='assurance', role='advisor')
        invite = Invitation.objects.create(
            username='pending-closer',
            email='pending@example.test',
            workspace='isolation',
            role='closer',
            issuer=self.users['administrator'],
            token_hash=digest('old-closer-token'),
            expires_at=timezone.now() + timedelta(days=1),
        )
        accepted = self.client.post(
            '/api/portal/invitations/accept/',
            {
                'id': str(invite.pk),
                'token': 'old-closer-token',
                'password': 'Strong-old-invite-test-456!',
                'confirmation': 'Strong-old-invite-test-456!',
            },
            format='json',
        )
        self.assertEqual(accepted.status_code, 400)
        self.assertFalse(get_user_model().objects.filter(username='pending-closer').exists())
        retire = import_module(
            'portal.backend.identity.migrations.0027_retire_isolation_closer'
        ).retire_closers
        retire(apps, None)
        member = Membership.objects.get(user=user, workspace='isolation')
        self.assertFalse(member.active)
        self.assertEqual(member.role, 'closer')
        self.assertTrue(Membership.objects.get(user=user, workspace='assurance').active)
        self.assertTrue(
            Membership.objects.get(user=self.users['setter'], workspace='isolation').active
        )
        self.assertTrue(
            Membership.objects.get(user=self.users['client'], workspace='isolation').active
        )
        self.assertEqual(SessionGeneration.objects.get(user=user).generation, 1)
        self.assertEqual(AccessAudit.objects.filter(action='membership.role_retired').count(), 1)
        invite.refresh_from_db()
        self.assertIsNotNone(invite.revoked_at)
        retire(apps, None)
        self.assertEqual(SessionGeneration.objects.get(user=user).generation, 1)
        self.assertEqual(AccessAudit.objects.filter(action='membership.role_retired').count(), 1)

        history = self.client.get(
            '/api/portal/workspaces/isolation/access-history/',
            {'action': 'membership.role_retired'},
        )
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.data['count'], 1)
        self.assertEqual(
            history.data['results'][0]['details']['before'], {'role': 'closer', 'active': True}
        )
        self.assertEqual(
            history.data['results'][0]['details']['after'], {'role': 'closer', 'active': False}
        )
