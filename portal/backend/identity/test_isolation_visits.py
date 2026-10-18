from django.contrib.auth import get_user_model
from django.test import TestCase,override_settings
from rest_framework.test import APIClient
from .models import Membership
from packages.access.isolation_visits import verify_booking

@override_settings(DEBUG=True,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IsolationVisitProofTests(TestCase):
    def setUp(self):
        self.setter=get_user_model().objects.create_user('setter');self.client_user=get_user_model().objects.create_user('client')
        self.admin=get_user_model().objects.create_user('admin')
        self.setter_access=Membership.objects.create(user=self.setter,workspace='isolation',role='setter')
        self.client_access=Membership.objects.create(user=self.client_user,workspace='isolation',role='client')
        Membership.objects.create(user=self.admin,workspace='isolation',role='administrator')
        self.client=APIClient();self.client.force_authenticate(self.setter);self.url='/api/portal/isolation/visit-proof/'
    def post(self,**changes):return self.client.post(self.url,{'prospect_id':12,'setter_id':self.setter.pk,**changes},format='json')
    def test_setter_and_admin_attest_active_pair(self):
        result=self.post();self.assertEqual(result.status_code,200)
        self.assertEqual(verify_booking(result.data['proof'],self.setter.pk,12)['client']['id'],self.client_user.pk)
        self.client.force_authenticate(self.admin);self.assertEqual(self.post().status_code,200)
    def test_no_client_or_multiple_active_clients_require_configuration(self):
        self.client_access.active=False;self.client_access.save();self.assertEqual(self.post().status_code,400)
        self.client_access.active=True;self.client_access.save()
        extra=get_user_model().objects.create_user('other-client');Membership.objects.create(user=extra,workspace='isolation',role='client')
        self.assertEqual(self.post().status_code,400)
    def test_scope_revocation_and_other_setter_are_denied(self):
        self.assertEqual(self.post(setter_id=self.admin.pk).status_code,403)
        self.setter_access.active=False;self.setter_access.save();self.assertEqual(self.post().status_code,403)
        self.client.force_authenticate(self.admin);self.assertEqual(self.post().status_code,400)
        self.client.force_authenticate(self.client_user);self.assertEqual(self.post().status_code,403)
    def test_inactive_client_user_and_extra_payload_are_rejected(self):
        self.assertEqual(self.post(client_id=self.client_user.pk).status_code,400)
        self.client_user.is_active=False;self.client_user.save();self.assertEqual(self.post().status_code,400)
