from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .models import Membership, PhoneExtension, AccessAudit


@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PhoneExtensionTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('admin')
        self.setter = get_user_model().objects.create_user('setter')
        Membership.objects.create(user=self.admin, workspace='assurance', role='administrator')
        self.grant = Membership.objects.create(
            user=self.setter, workspace='assurance', role='setter'
        )
        self.client = APIClient()
        self.client.force_login(self.admin)
        self.url = '/api/portal/workspaces/assurance/phone-extensions/'

    def body(self, **changes):
        return {
            'membership_id': self.grant.pk,
            'extension': '505',
            'reason': 'Association manuelle vérifiée',
            **changes,
        }

    def post(self, **changes):
        return self.client.post(self.url, self.body(**changes), format='json')

    def test_create_list_update_remove_preserves_revision_and_never_networks(self):
        with patch(
            'requests.sessions.Session.request', side_effect=AssertionError('No network permitted')
        ):
            self.assertEqual(self.post().status_code, 204)
            result = self.client.get(self.url)
            self.assertEqual(result['Cache-Control'], 'no-store')
            self.assertEqual(
                next(row for row in result.data['results'] if row['username'] == 'setter')[
                    'extension'
                ],
                '505',
            )
            self.assertEqual(self.post(revision=0, extension='506').status_code, 204)
            self.assertEqual(self.post(revision=1, remove=True).status_code, 204)
        row = PhoneExtension.objects.get()
        self.assertIsNone(row.extension)
        self.assertEqual(row.revision, 2)
        self.assertEqual(self.post(revision=0).status_code, 400)
        self.assertEqual(AccessAudit.objects.filter(action='phone.extension_assigned').count(), 3)

    def test_unique_post_and_stale_version_rejected(self):
        self.post()
        other = get_user_model().objects.create_user('other')
        grant = Membership.objects.create(user=other, workspace='assurance', role='setter')
        self.assertEqual(self.post(membership_id=grant.pk).status_code, 400)
        self.assertEqual(self.post(extension='507').status_code, 400)
        self.assertEqual(PhoneExtension.objects.get().extension, '505')

    def test_setter_advisor_and_other_workspace_admin_cannot_read_or_mutate(self):
        for role in ('setter', 'advisor'):
            Membership.objects.filter(user=self.admin, workspace='assurance').update(role=role)
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self.post().status_code, 403)
        self.assertEqual(
            self.client.get('/api/portal/workspaces/isolation/phone-extensions/').status_code, 403
        )

    def test_both_workspace_admin_required_for_multi_workspace_setter(self):
        Membership.objects.create(user=self.setter, workspace='isolation', role='setter')
        self.assertEqual(self.post().status_code, 403)
        Membership.objects.create(user=self.admin, workspace='isolation', role='administrator')
        self.assertEqual(self.post().status_code, 204)
        self.assertEqual(
            next(
                row
                for row in self.client.get(
                    '/api/portal/workspaces/isolation/phone-extensions/'
                ).data['results']
                if row['username'] == 'setter'
            )['extension'],
            '505',
        )

    def test_suspended_setter_can_only_be_unassigned_and_foreign_member_rejected(self):
        self.post()
        Membership.objects.filter(pk=self.grant.pk).update(active=False)
        self.assertEqual(self.post(revision=0).status_code, 400)
        self.assertEqual(self.post(revision=0, remove=True).status_code, 204)
        self.assertEqual(self.post(membership_id=9999).status_code, 400)

    def test_strict_validation_and_audit_rollback(self):
        for changes in (
            {'extension': '505&function=245'},
            {'extension': 'abc'},
            {'reason': ' '},
            {'call': True},
        ):
            self.assertEqual(self.post(**changes).status_code, 400)
        with patch(
            'portal.backend.identity.phone_extensions.AccessAudit.objects.create',
            side_effect=RuntimeError('audit'),
        ):
            with self.assertRaises(RuntimeError):
                self.post()
        self.assertFalse(PhoneExtension.objects.exists())

    def test_csrf_required_and_global_superuser_has_no_implicit_permission(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(self.url, self.body(), format='json').status_code, 403)
        Membership.objects.filter(user=self.admin).delete()
        self.admin.is_superuser = True
        self.admin.save()
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_admin_can_associate_own_post_and_multi_workspace_role_requires_both_admin_rights(self):
        grant = Membership.objects.get(user=self.admin, workspace='assurance')
        self.assertEqual(self.post(membership_id=grant.pk, extension='501').status_code, 204)
        self.assertEqual(PhoneExtension.objects.get(user=self.admin).extension, '501')
        Membership.objects.create(user=self.admin, workspace='isolation', role='setter')
        self.assertEqual(
            self.post(membership_id=grant.pk, extension='502', revision=0).status_code, 403
        )
        Membership.objects.filter(user=self.admin, workspace='isolation').update(
            role='administrator'
        )
        self.assertEqual(
            self.post(membership_id=grant.pk, extension='502', revision=0).status_code, 204
        )
