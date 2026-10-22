from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from packages.access.isolation_visits import verify_closer
from packages.access.tickets import verify
from .models import Membership


@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CloserProofTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/portal/isolation/closers/'
        self.users = {}
        for role in ('administrator', 'client', 'setter', 'closer'):
            user = get_user_model().objects.create_user(role)
            Membership.objects.create(user=user, workspace='isolation', role=role)
            self.users[role] = user
        self.client.force_authenticate(self.users['client'])

    def post(self, **changes):
        return self.client.post(
            self.url,
            {'visit_id': 12, 'closer_id': self.users['closer'].pk, **changes},
            format='json',
        )

    def test_client_and_admin_choose_active_closer_and_closer_can_enter(self):
        response = self.post()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            verify_closer(response.data['proof'], self.users['client'].pk, 12)['closer'],
            self.users['closer'].pk,
        )
        self.assertEqual(self.client.get(self.url).data['count'], 1)
        self.client.force_authenticate(self.users['administrator'])
        self.assertEqual(self.post().status_code, 200)
        self.client.force_authenticate(self.users['closer'])
        token = self.client.post('/api/portal/access/isolation/', {}, format='json')
        self.assertEqual(token.status_code, 200, token.data)
        self.assertEqual(verify(token.data['token'], 'isolation')['role'], 'closer')

    def test_other_roles_and_disabled_or_wrong_role_targets_rejected(self):
        self.assertEqual(self.post(closer_id=self.users['setter'].pk).status_code, 400)
        member = Membership.objects.get(user=self.users['closer'])
        member.active = False
        member.save()
        self.assertEqual(self.post().status_code, 400)
        self.assertEqual(self.client.get(self.url).data['count'], 0)
        for role in ('setter', 'closer'):
            self.client.force_authenticate(self.users[role])
            self.assertEqual(self.post().status_code, 403)

    def test_active_user_and_strict_fields_required(self):
        self.assertEqual(self.post(client_id=self.users['client'].pk).status_code, 400)
        user = self.users['closer']
        user.is_active = False
        user.save()
        self.assertEqual(self.post().status_code, 400)
