from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from packages.access.tickets import verify
from .models import AccessAudit, Membership
from .support_sessions import KEY, STOP_PATH


@override_settings(DEBUG=True, MFA_ENABLED=False)
class SupportSessionTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.actor = users.create_user('support-admin', is_superuser=True)
        self.target = users.create_user('setter')
        Membership.objects.create(user=self.target, workspace='isolation', role='setter')
        Membership.objects.create(user=self.target, workspace='assurance', role='setter')
        self.client = APIClient()
        self.path = f'/api/portal/platform/accounts/{self.target.pk}/support/'
        self.data = {'workspace': 'isolation', 'reason': 'Vérifier le parcours du setter'}

    def test_support_uses_target_role_and_preserves_the_operator_login(self):
        self.client.force_login(self.actor)
        result = self.client.post(self.path, self.data)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['username'], self.target.username)
        self.assertFalse(result.data['superadmin'])
        self.assertEqual(result.data['workspaces'], [{'workspace': 'isolation', 'role': 'setter'}])
        self.assertEqual(self.client.get('/api/portal/session/').data['username'], 'setter')
        token = self.client.post('/api/portal/access/isolation/').data['token']
        self.assertEqual(verify(token, 'isolation')['support_actor'], self.actor.pk)
        self.assertEqual(verify(token, 'isolation')['sub'], str(self.target.pk))
        self.assertEqual(self.client.post('/api/portal/access/assurance/').status_code, 403)
        self.assertEqual(self.client.post('/api/portal/password/change/').status_code, 403)
        self.assertEqual(self.client.post('/api/portal/isolation/calls/').status_code, 400)
        action = AccessAudit.objects.get(action='platform.support_action')
        self.assertEqual(action.user_id, self.actor.pk)
        self.assertEqual(action.metadata['subject'], self.target.pk)
        self.assertEqual(self.client.post(self.path, self.data).status_code, 403)
        self.assertEqual(self.client.post(STOP_PATH).status_code, 204)
        self.assertEqual(
            self.client.get('/api/portal/session/').data['username'], self.actor.username
        )
        self.assertEqual(
            AccessAudit.objects.filter(
                user=self.actor, action__startswith='platform.support_'
            ).count(),
            3,
        )

    def test_only_superadmin_can_start_and_expiration_never_grants_access(self):
        self.client.force_login(self.target)
        self.assertEqual(self.client.post(self.path, self.data).status_code, 403)
        self.client.force_login(self.actor)
        self.assertEqual(self.client.post(self.path, self.data).status_code, 200)
        stored = self.client.session
        stored[KEY] = {**stored[KEY], 'expires': 0}
        stored.save()
        self.assertEqual(self.client.post('/api/portal/access/isolation/').status_code, 403)
        self.assertEqual(
            self.client.get('/api/portal/session/').data['username'], self.actor.username
        )
