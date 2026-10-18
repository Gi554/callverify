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

@override_settings(DEBUG=True,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
@skipUnless(settings.ROOT_URLCONF=='portal.backend.urls','Service portail indépendant')
class AccessManagementTests(TestCase):
    def setUp(self):
        self.actor=get_user_model().objects.create_user('manager',password='strong-password-42')
        self.own=Membership.objects.create(user=self.actor,workspace='assurance',role='administrator')
        self.other=get_user_model().objects.create_user('target',password='unchanged-password')
        self.target=Membership.objects.create(user=self.other,workspace='assurance',role='setter')
        self.isolation=Membership.objects.create(user=self.other,workspace='isolation',role='client')
        self.client=APIClient();self.client.force_authenticate(self.actor)
        self.url='/api/portal/workspaces/assurance/users/'
    def test_scope_and_no_implicit_superuser(self):
        self.assertEqual(self.client.get('/api/portal/workspaces/isolation/users/').status_code,403)
        self.actor.is_superuser=True;self.actor.save()
        self.own.delete()
        self.assertEqual(self.client.get(self.url).status_code,403)
    def test_list_excludes_other_workspace_and_secrets(self):
        data=self.client.get(self.url).data
        self.assertEqual(data['count'],2)
        self.assertNotIn('password',str(data));self.assertNotIn('client',str(data))
        self.assertEqual(self.client.get(self.url+'?search=target').data['count'],1)
    def test_create_hashes_password_and_audits_without_secret(self):
        from .models import AccessAudit
        secret='Unique-strong-pass-936!'
        response=self.client.post(self.url,{'username':'newperson','role':'advisor','password':secret},format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertTrue(get_user_model().objects.get(username='newperson').check_password(secret))
        self.assertNotIn(secret,str(response.data));self.assertNotIn(secret,str(AccessAudit.objects.last().metadata))
    def test_weak_password_and_incompatible_role_do_not_create_user(self):
        for values in ({'role':'advisor','password':'short'},{'role':'client','password':'Unique-strong-pass-936!'}):
            response=self.client.post(self.url,{'username':'rejected',**values},format='json')
            self.assertEqual(response.status_code,400)
        self.assertFalse(get_user_model().objects.filter(username='rejected').exists())
    def test_existing_link_keeps_account_and_other_access(self):
        self.target.delete();original=self.other.password
        response=self.client.post(self.url,{'username':'target','role':'advisor','existing':True},format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.other.refresh_from_db();self.isolation.refresh_from_db()
        self.assertEqual(self.other.password,original);self.assertEqual(self.isolation.role,'client')
    def test_self_change_and_cross_workspace_are_blocked(self):
        self.assertEqual(self.client.patch(self.url+str(self.own.pk)+'/',{'active':False},format='json').status_code,400)
        self.assertEqual(self.client.patch(self.url+str(self.isolation.pk)+'/',{'active':False},format='json').status_code,404)
    def test_suspend_only_selected_workspace_and_records_history(self):
        from .models import AccessAudit
        response=self.client.patch(self.url+str(self.target.pk)+'/',{'active':False,'role':'advisor'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.isolation.refresh_from_db();self.other.refresh_from_db()
        self.assertTrue(self.isolation.active);self.assertTrue(self.other.is_active)
        self.assertEqual(AccessAudit.objects.last().metadata['before']['role'],'setter')
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post('/api/portal/access/assurance/').status_code,403)
        self.assertEqual(self.client.post('/api/portal/access/isolation/').status_code,200)
    def test_session_mutation_requires_csrf(self):
        client=APIClient(enforce_csrf_checks=True);client.force_login(self.actor)
        self.assertEqual(client.patch(self.url+str(self.target.pk)+'/',{'active':False},format='json').status_code,403)
