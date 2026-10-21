from django.contrib.auth import get_user_model
from django.test import TestCase,override_settings
from rest_framework.test import APIClient
from .models import Membership

@override_settings(DEBUG=True,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ProfileLoginTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('profile-setter',password='synthetic-secret')
        Membership.objects.create(user=self.user,workspace='assurance',role='setter')
        self.client=APIClient(enforce_csrf_checks=True)
        self.csrf=self.client.get('/api/portal/csrf/').data['csrfToken']
    def post(self,workspace):return self.client.post('/api/portal/login/',{'username':self.user.username,'password':'synthetic-secret','workspace':workspace},format='json',HTTP_X_CSRFTOKEN=self.csrf)
    def test_wrong_profile_cannot_create_a_session(self):
        self.assertEqual(self.post('isolation').status_code,403)
        self.assertNotIn('_auth_user_id',self.client.session)
        self.assertEqual(self.post('other').status_code,400)
    def test_allowed_profile_uses_existing_memberships_only(self):
        response=self.post('assurance');self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['workspaces'],[{'workspace':'assurance','role':'setter'}])
        self.assertEqual(Membership.objects.count(),1)
