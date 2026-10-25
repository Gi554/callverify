from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .models import Membership
from packages.access.isolation import verify_owner


@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IsolationSetterDirectoryTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('admin')
        self.setter = get_user_model().objects.create_user('setter')
        self.membership = Membership.objects.create(
            user=self.admin, workspace='isolation', role='administrator'
        )
        self.target = Membership.objects.create(
            user=self.setter, workspace='isolation', role='setter'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.url = '/api/portal/isolation/setters/'

    def post(self, **changes):
        return self.client.post(
            self.url, {'setter_id': self.setter.pk, 'prospect_id': 12, **changes}, format='json'
        )

    def test_active_directory_and_bound_proof(self):
        self.assertEqual(
            self.client.get(self.url).data['results'], [{'id': self.setter.pk, 'name': 'setter'}]
        )
        result = self.post()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            verify_owner(result.data['proof'], self.admin.pk, 12)['setter'], self.setter.pk
        )

    def test_only_isolation_setters_active_accounts_are_allowed(self):
        for changes in (
            {'active': False},
            {'active': True, 'role': 'client'},
            {'role': 'setter', 'workspace': 'assurance'},
        ):
            for key, value in changes.items():
                setattr(self.target, key, value)
            self.target.save()
            self.assertEqual(self.post().status_code, 400)
            self.assertEqual(self.client.get(self.url).data['count'], 0)
        self.target.workspace = 'isolation'
        self.target.save()
        self.setter.is_active = False
        self.setter.save()
        self.assertEqual(self.post().status_code, 400)

    def test_explicit_admin_only_and_csrf(self):
        self.client.force_authenticate(self.setter)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.post().status_code, 403)
        self.client.force_authenticate(self.admin)
        self.membership.active = False
        self.membership.save()
        self.assertEqual(self.post().status_code, 403)
        self.membership.active = True
        self.membership.save()
        csrf = APIClient(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(
            csrf.post(
                self.url, {'setter_id': self.setter.pk, 'prospect_id': 12}, format='json'
            ).status_code,
            403,
        )

    def test_invalid_payload(self):
        self.assertEqual(self.post(prospect_id=0).status_code, 400)
        self.assertEqual(self.post(extra=True).status_code, 400)


@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IsolationLotProofTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('admin')
        self.setter = get_user_model().objects.create_user('setter')
        Membership.objects.create(user=self.admin, workspace='isolation', role='administrator')
        self.target = Membership.objects.create(
            user=self.setter, workspace='isolation', role='setter'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.url = '/api/portal/isolation/lot-proof/'

    def test_proof_names_the_active_setter_and_the_actor(self):
        from packages.access.isolation import verify_lot

        result = self.client.post(self.url, {'setter_id': self.setter.pk}, format='json')
        self.assertEqual(result.status_code, 200)
        claims = verify_lot(result.data['proof'], self.admin.pk)
        self.assertEqual((claims['setter'], claims['name']), (self.setter.pk, 'setter'))

    def test_inactive_setter_other_role_and_non_admin_are_refused(self):
        self.target.active = False
        self.target.save()
        self.assertEqual(
            self.client.post(self.url, {'setter_id': self.setter.pk}, format='json').status_code,
            400,
        )
        self.client.force_authenticate(self.setter)
        self.assertEqual(
            self.client.post(self.url, {'setter_id': self.setter.pk}, format='json').status_code,
            403,
        )

    def test_administrator_can_take_a_lot_and_is_listed_only_on_request(self):
        from packages.access.isolation import verify_lot

        result = self.client.post(self.url, {'setter_id': self.admin.pk}, format='json')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(verify_lot(result.data['proof'], self.admin.pk)['setter'], self.admin.pk)
        listing = '/api/portal/isolation/setters/'
        self.assertEqual(
            [row['id'] for row in self.client.get(listing).data['results']], [self.setter.pk]
        )
        both = self.client.get(listing, {'with_admins': '1'}).data['results']
        self.assertEqual({row['id'] for row in both}, {self.admin.pk, self.setter.pk})
