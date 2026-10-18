from django.contrib.auth import get_user_model
from django.test import TestCase,override_settings
from rest_framework.test import APIClient
from django.core import signing
from django.conf import settings
from unittest import skipUnless
if 'portal.backend.identity' in settings.INSTALLED_APPS:
    from .models import Membership
from packages.access.tickets import issue,verify

@override_settings(DEBUG=True,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
@skipUnless(settings.ROOT_URLCONF=='portal.backend.urls','Service portail indépendant')
class PortalTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('test',password='long-test-password')
        self.client=APIClient();self.client.force_authenticate(self.user)
    def test_single_workspace_landing_and_denied_other(self):
        Membership.objects.create(user=self.user,workspace='isolation',role='setter')
        self.assertEqual(self.client.get('/api/portal/session/').data['landing'],'isolation')
        self.assertEqual(self.client.post('/api/portal/access/assurance/').status_code,403)
    def test_multi_workspace_requires_choice(self):
        for space in ('assurance','isolation'):Membership.objects.create(user=self.user,workspace=space,role='administrator')
        self.assertIsNone(self.client.get('/api/portal/session/').data['landing'])
    def test_revoked_membership_does_not_issue_ticket(self):
        Membership.objects.create(user=self.user,workspace='assurance',role='advisor',active=False)
        self.assertEqual(self.client.post('/api/portal/access/assurance/').status_code,403)
    def test_audience_and_signature_are_checked(self):
        token=issue(self.user.pk,'isolation','administrator')
        with self.assertRaises(signing.BadSignature):verify(token,'assurance')
        with self.assertRaises(signing.BadSignature):verify(token+'x','isolation')
    def test_no_membership_even_for_central_superuser(self):
        self.user.is_superuser=True;self.user.save()
        self.assertEqual(self.client.post('/api/portal/access/assurance/').status_code,403)
    def test_login_requires_csrf(self):
        client=APIClient(enforce_csrf_checks=True)
        self.assertEqual(client.post('/api/portal/login/',{'username':'test','password':'long-test-password'},format='json').status_code,403)
    def test_expired_ticket_is_rejected(self):
        from unittest.mock import patch
        with patch('django.core.signing.time.time',return_value=1000):
            token=issue(self.user.pk,'assurance','advisor')
        with self.assertRaises(signing.SignatureExpired):verify(token,'assurance')
