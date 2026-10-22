from datetime import datetime, timezone
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .models import Membership, AccessAudit


@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AccessHistoryTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user('admin', password='strong-password-42')
        self.grant = Membership.objects.create(
            user=self.actor, workspace='assurance', role='administrator'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.actor)
        self.url = '/api/portal/workspaces/assurance/access-history/'

    def event(self, action='membership.granted', workspace='assurance', **changes):
        return AccessAudit.objects.create(
            user=self.actor,
            workspace=workspace,
            action=action,
            metadata=changes.get('metadata', {'subject': 55, 'role': 'setter', 'existing': True}),
        )

    def test_workspace_scope_and_global_or_unknown_actions_excluded(self):
        event = self.event()
        self.event(workspace='isolation')
        self.event(action='session.login', workspace='')
        self.event(action='workspace.access')
        self.event(action='mail.queued')
        self.event(action='future.secret_action')
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result['Cache-Control'], 'no-store')
        self.assertEqual(result.data['count'], 1)
        self.assertEqual(result.data['results'][0]['id'], event.pk)
        self.assertEqual(
            self.client.get('/api/portal/workspaces/isolation/access-history/').status_code, 403
        )
        Membership.objects.create(user=self.actor, workspace='isolation', role='administrator')
        self.assertEqual(
            self.client.get('/api/portal/workspaces/isolation/access-history/').data['count'], 1
        )

    def test_explicit_admin_required_and_revocation_is_immediate(self):
        self.event()
        self.assertEqual(self.client.get(self.url).status_code, 200)
        for role in ('setter', 'advisor'):
            Membership.objects.filter(pk=self.grant.pk).update(role=role)
            self.assertEqual(self.client.get(self.url).status_code, 403)
        Membership.objects.filter(pk=self.grant.pk).update(role='administrator', active=False)
        self.actor.is_superuser = True
        self.actor.save()
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(
            self.client.get('/api/portal/workspaces/other/access-history/').status_code, 403
        )
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_allowlist_excludes_nested_secrets_and_invitation_addresses(self):
        secret = 'never-return-this-secret'
        self.event(
            metadata={
                'subject': 55,
                'role': 'setter',
                'existing': True,
                'password': secret,
                'email': secret,
            }
        )
        self.event(
            action='membership.updated',
            metadata={
                'subject': 55,
                'before': {'role': 'setter', 'active': True, 'token': secret},
                'after': {'role': 'advisor', 'active': False, 'private': secret},
            },
        )
        invitation = str(uuid4())
        self.event(
            action='invitation.created',
            metadata={
                'invitation': invitation,
                'role': 'advisor',
                'email': secret,
                'token': secret,
                'issuer': 777,
            },
        )
        result = self.client.get(self.url).data
        self.assertNotIn(secret, str(result))
        rows = {row['action']: row for row in result['results']}
        self.assertEqual(
            rows['membership.updated']['details']['before'], {'role': 'setter', 'active': True}
        )
        self.assertEqual(
            rows['invitation.created']['details'], {'invitation_id': invitation, 'role': 'advisor'}
        )
        self.assertEqual(
            set(rows['membership.granted']),
            {'id', 'action', 'label', 'created_at', 'actor', 'details'},
        )
        self.assertEqual(
            rows['membership.granted']['actor'], {'id': self.actor.pk, 'username': 'admin'}
        )

    def test_filters_dates_utc_boundaries_and_pagination_order(self):
        first = self.event()
        second = self.event(action='invitation.revoke', metadata={'invitation': str(uuid4())})
        AccessAudit.objects.filter(pk=first.pk).update(
            created_at=datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
        )
        AccessAudit.objects.filter(pk=second.pk).update(
            created_at=datetime(2026, 10, 1, 23, 59, 59, tzinfo=timezone.utc)
        )
        result = self.client.get(
            self.url + f'?start_date=2026-10-01&end_date=2026-10-01&actor_id={self.actor.pk}'
        )
        self.assertEqual([row['id'] for row in result.data['results']], [second.pk, first.pk])
        self.assertEqual(self.client.get(self.url + '?action=invitation.revoke').data['count'], 1)
        self.assertEqual(self.client.get(self.url + '?actor_id=999999').data['count'], 0)
        for _ in range(26):
            self.event()
        result = self.client.get(self.url)
        self.assertEqual(result.data['count'], 28)
        self.assertEqual(len(result.data['results']), 25)
        self.assertEqual(len(self.client.get(self.url + '?page=2').data['results']), 3)

    def test_invalid_filters_and_mutations_are_refused_without_writes(self):
        self.event()
        before = AccessAudit.objects.count()
        for query in (
            'action=session.login',
            'actor_id=0',
            'actor_id=abc',
            'actor_id=999999999999999999999',
            'start_date=bad',
            'end_date=2026-02-30',
            'start_date=2026-10-02&end_date=2026-10-01',
            'workspace=isolation',
        ):
            self.assertEqual(self.client.get(self.url + '?' + query).status_code, 400, query)
        self.assertEqual(self.client.post(self.url, {}, format='json').status_code, 405)
        self.assertEqual(self.client.patch(self.url, {}, format='json').status_code, 405)
        self.assertEqual(self.client.delete(self.url).status_code, 405)
        self.assertEqual(AccessAudit.objects.count(), before)

    def test_real_access_changes_are_visible_with_before_and_after(self):
        subject = get_user_model().objects.create_user('target', password='strong-password-43')
        base = '/api/portal/workspaces/assurance/users/'
        result = self.client.post(
            base, {'username': subject.username, 'existing': True, 'role': 'setter'}, format='json'
        )
        self.assertEqual(result.status_code, 201)
        self.assertEqual(
            self.client.patch(
                base + str(result.data['id']) + '/',
                {'active': False, 'role': 'advisor'},
                format='json',
            ).status_code,
            200,
        )
        rows = self.client.get(self.url).data['results']
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            rows[0]['details'],
            {
                'subject_id': subject.pk,
                'before': {'role': 'setter', 'active': True},
                'after': {'role': 'advisor', 'active': False},
            },
        )
        self.assertEqual(rows[1]['details']['existing_account'], True)

    def test_deleted_actor_and_malformed_metadata_do_not_expose_or_break_history(self):
        deleted = get_user_model().objects.create_user('removed')
        row = self.event()
        row.user = deleted
        row.save()
        deleted.delete()
        self.event(metadata={'subject': True, 'role': [], 'existing': 'secret'})
        self.event(
            action='membership.updated',
            metadata={'before': {'role': {}, 'active': 'secret'}, 'after': 'secret'},
        )
        self.event(
            action='invitation.accepted',
            metadata={'invitation': 'not-a-uuid', 'role': [], 'issuer': 'secret'},
        )
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200)
        self.assertNotIn('secret', str(result.data))
        self.assertIsNone(
            next(item for item in result.data['results'] if item['id'] == row.pk)['actor']
        )
