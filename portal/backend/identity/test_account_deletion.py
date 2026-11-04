from unittest.mock import patch
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .models import (
    Membership,
    AccessAudit,
    PhoneCallAttempt,
    PhoneExtension,
    CalendarConnection,
    SessionGeneration,
)


@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AccountDeletionTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user('admin', password='strong-password-42')
        self.own = Membership.objects.create(
            user=self.actor, workspace='assurance', role='administrator'
        )
        self.subject = get_user_model().objects.create_user(
            'setter-delete', password='strong-password-42'
        )
        self.grant = Membership.objects.create(
            user=self.subject, workspace='assurance', role='setter'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.actor)
        self.url = f'/api/portal/workspaces/assurance/users/{self.grant.pk}/'
        self.body = {'confirm_username': self.subject.username, 'reason': 'Départ de l’équipe'}

    def delete(self, **changes):
        return self.client.delete(self.url, {**self.body, **changes}, format='json')

    def test_last_access_removed_but_calls_identity_and_audit_are_preserved(self):
        attempt = PhoneCallAttempt.objects.create(
            request_id=uuid4(),
            user=self.subject,
            contact_id=1,
            extension='501',
            fingerprint='test',
            state='accepted',
        )
        PhoneExtension.objects.create(user=self.subject, extension='501')
        CalendarConnection.objects.create(
            user=self.subject,
            workspace='assurance',
            connected=True,
            auto_sync=True,
            payload='private-token',
        )
        response = self.delete()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(Membership.objects.filter(pk=self.grant.pk).exists())
        self.subject.refresh_from_db()
        self.assertFalse(self.subject.is_active)
        self.assertTrue(PhoneCallAttempt.objects.filter(pk=attempt.pk, user=self.subject).exists())
        extension = PhoneExtension.objects.get(user=self.subject)
        self.assertIsNone(extension.extension)
        calendar = CalendarConnection.objects.get(user=self.subject)
        self.assertFalse(calendar.connected)
        self.assertFalse(calendar.auto_sync)
        self.assertEqual(calendar.payload, '')
        self.assertEqual(SessionGeneration.objects.get(user=self.subject).generation, 1)
        event = AccessAudit.objects.get(action='membership.deleted')
        self.assertEqual(event.user_id, self.actor.pk)
        self.assertEqual(event.metadata['subject'], self.subject.pk)
        self.assertTrue(event.metadata['after']['deleted'])
        self.assertNotIn('private-token', str(event.metadata))
        self.assertEqual(self.delete().status_code, 404)
        self.assertFalse(
            self.client.get('/api/portal/workspaces/assurance/users/').data['results'][0][
                'can_delete'
            ]
        )
        history = self.client.get('/api/portal/workspaces/assurance/access-history/').data[
            'results'
        ][0]
        self.assertEqual(history['action'], 'membership.deleted')
        self.assertEqual(history['details']['subject_username'], self.body['confirm_username'])

    def create_replacement(self, username=None):
        return self.client.post(
            '/api/portal/workspaces/assurance/users/',
            {
                'username': username or self.body['confirm_username'],
                'email': 'replacement@example.com',
                'password': 'new-distinct-password-42',
                'role': 'setter',
            },
            format='json',
        )

    def test_deleted_login_can_be_recreated_without_inheriting_history_or_credentials(self):
        self.subject.email = 'replacement@example.com'
        self.subject.save(update_fields=['email'])
        previous_id = self.subject.pk
        self.assertEqual(self.delete().status_code, 200)
        self.subject.refresh_from_db()
        self.assertFalse(self.subject.has_usable_password())
        self.assertEqual(self.subject.email, '')
        self.assertNotEqual(self.subject.username, self.body['confirm_username'])
        response = self.create_replacement()
        self.assertEqual(response.status_code, 201, response.data)
        replacement = get_user_model().objects.get(username=self.body['confirm_username'])
        self.assertNotEqual(replacement.pk, previous_id)
        self.assertTrue(replacement.check_password('new-distinct-password-42'))
        self.assertFalse(CalendarConnection.objects.filter(user=replacement).exists())
        self.assertFalse(PhoneExtension.objects.filter(user=replacement).exists())
        self.assertEqual(
            AccessAudit.objects.get(action='membership.deleted').metadata['subject'], previous_id
        )

    def test_previously_deleted_login_is_released_but_suspended_login_is_not(self):
        self.subject.is_active = False
        self.subject.save(update_fields=['is_active'])
        self.assertEqual(self.create_replacement().status_code, 400)
        self.grant.delete()
        # An inactive account without an audited deletion must never be reclaimed.
        self.assertEqual(self.create_replacement().status_code, 400)
        AccessAudit.objects.create(
            user=self.actor,
            action='membership.deleted',
            workspace='assurance',
            metadata={'subject': self.subject.pk, 'account_disabled': True},
        )
        response = self.create_replacement()
        self.assertEqual(response.status_code, 201, response.data)
        self.subject.refresh_from_db()
        self.assertFalse(self.subject.has_usable_password())
        self.assertNotEqual(self.subject.username, self.body['confirm_username'])

    def test_isolation_client_can_be_recreated_after_deletion(self):
        self.own.workspace = 'isolation'
        self.own.save(update_fields=['workspace'])
        self.grant.workspace = 'isolation'
        self.grant.role = 'client'
        self.grant.save(update_fields=['workspace', 'role'])
        self.url = self.url.replace('/assurance/', '/isolation/')
        self.assertEqual(self.delete().status_code, 200)
        response = self.client.post(
            '/api/portal/workspaces/isolation/users/',
            {
                'username': self.body['confirm_username'],
                'email': 'replacement@example.com',
                'password': 'new-distinct-password-42',
                'role': 'client',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        client = Membership.objects.get(workspace='isolation', role='client')
        self.assertNotEqual(client.user_id, self.subject.pk)

    def test_accepted_invitation_does_not_block_reinviting_deleted_account(self):
        from django.utils import timezone
        from .models import Invitation

        previous = Invitation.objects.create(
            username=self.subject.username,
            email='replacement@example.com',
            workspace='assurance',
            role='setter',
            issuer=self.actor,
            token_hash='old-token',
            expires_at=timezone.now(),
            accepted_at=timezone.now(),
        )
        self.assertEqual(self.delete().status_code, 200)
        response = self.client.post(
            '/api/portal/workspaces/assurance/invitations/',
            {
                'username': self.body['confirm_username'],
                'email': 'replacement@example.com',
                'role': 'setter',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        previous.refresh_from_db()
        self.assertIsNotNone(previous.revoked_at)
        self.assertNotEqual(previous.username, self.body['confirm_username'])

    def test_account_in_another_space_keeps_its_other_access_calendar_and_phone(self):
        other = Membership.objects.create(user=self.subject, workspace='isolation', role='setter')
        CalendarConnection.objects.create(
            user=self.subject,
            workspace='isolation',
            connected=True,
            auto_sync=True,
            payload='other-space',
        )
        extension = PhoneExtension.objects.create(user=self.subject, extension='502')
        response = self.delete()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data['account_disabled'])
        self.subject.refresh_from_db()
        self.assertTrue(self.subject.is_active)
        self.assertEqual(self.subject.username, self.body['confirm_username'])
        self.assertEqual(self.create_replacement().status_code, 400)
        self.assertTrue(Membership.objects.filter(pk=other.pk).exists())
        self.assertTrue(CalendarConnection.objects.get(user=self.subject).connected)
        extension.refresh_from_db()
        self.assertEqual(extension.extension, '502')

    def test_admins_are_protected_including_suspended_and_other_workspace_admins(self):
        self.grant.role = 'administrator'
        self.grant.active = False
        self.grant.save()
        self.assertEqual(self.delete().status_code, 403)
        self.grant.role = 'setter'
        self.grant.save()
        Membership.objects.create(
            user=self.subject, workspace='isolation', role='administrator', active=False
        )
        self.assertEqual(self.delete().status_code, 403)
        data = self.client.get('/api/portal/workspaces/assurance/users/').data
        self.assertTrue(all(not r['can_delete'] for r in data['results']))
        self.assertTrue(Membership.objects.filter(pk=self.grant.pk).exists())

    def test_confirmation_scope_nonadmin_and_atomic_audit(self):
        self.assertEqual(self.delete(confirm_username='wrong').status_code, 400)
        self.assertEqual(self.delete(extra='forbidden').status_code, 400)
        self.assertEqual(
            self.client.delete(
                self.url.replace('/assurance/', '/isolation/'), self.body, format='json'
            ).status_code,
            403,
        )
        self.client.force_authenticate(self.subject)
        self.assertEqual(self.delete().status_code, 403)
        self.client.force_authenticate(self.actor)
        with patch(
            'portal.backend.identity.management_api.AccessAudit.objects.create',
            side_effect=RuntimeError('audit unavailable'),
        ):
            with self.assertRaises(RuntimeError):
                self.delete()
        self.assertTrue(Membership.objects.filter(pk=self.grant.pk).exists())
        self.subject.refresh_from_db()
        self.assertTrue(self.subject.is_active)

    def test_real_session_is_revoked_after_last_access_removed_and_csrf_is_required(self):
        session = APIClient(enforce_csrf_checks=True)
        session.force_login(self.actor)
        self.assertEqual(session.delete(self.url, self.body, format='json').status_code, 403)
        former = APIClient()
        former.force_login(self.subject)
        self.assertEqual(self.delete().status_code, 200)
        self.assertIn(former.get('/api/portal/session/').status_code, (401, 403))

    def test_promotion_after_list_loading_and_staff_accounts_are_protected(self):
        listed = self.client.get('/api/portal/workspaces/assurance/users/').data['results']
        self.assertTrue(next(row for row in listed if row['id'] == self.grant.pk)['can_delete'])
        Membership.objects.filter(pk=self.grant.pk).update(role='administrator')
        self.assertEqual(self.delete().status_code, 403)
        Membership.objects.filter(pk=self.grant.pk).update(role='setter')
        self.subject.is_staff = True
        self.subject.save(update_fields=['is_staff'])
        self.assertEqual(self.delete().status_code, 403)
        self.subject.is_staff = False
        self.subject.is_superuser = True
        self.subject.save(update_fields=['is_staff', 'is_superuser'])
        self.assertEqual(self.delete().status_code, 403)
