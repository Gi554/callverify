from uuid import uuid4
from zoneinfo import ZoneInfo
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.isolation_events import issue, verify
from .models import Membership, PhoneCallAttempt


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class CompensationIdentityTests(TestCase):
    def setUp(self):
        self.users = {}
        for role in ('administrator', 'setter', 'client', 'closer'):
            user = get_user_model().objects.create_user(role)
            Membership.objects.create(user=user, workspace='isolation', role=role)
            self.users[role] = user
        self.client = APIClient()
        self.day = timezone.now().astimezone(ZoneInfo('America/Toronto')).date().isoformat()

    def test_only_admin_can_attest_active_setter_and_unique_client(self):
        url = '/api/portal/isolation/compensation-proof/'
        self.client.force_authenticate(self.users['setter'])
        self.assertEqual(
            self.client.post(
                url, {'setter_id': self.users['setter'].pk}, format='json'
            ).status_code,
            403,
        )
        self.client.force_authenticate(self.users['administrator'])
        response = self.client.post(url, {'setter_id': self.users['setter'].pk}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        data = verify(response.data['proof'], 'compensation_rate')
        self.assertEqual(data['actor'], self.users['administrator'].pk)
        self.assertEqual(data['client']['id'], self.users['client'].pk)
        self.assertEqual(data['setter']['id'], self.users['setter'].pk)
        self.assertEqual(
            self.client.post(
                url, {'setter_id': self.users['closer'].pk}, format='json'
            ).status_code,
            400,
        )
        Membership.objects.filter(user=self.users['client']).update(active=False)
        self.assertEqual(
            self.client.post(
                url, {'setter_id': self.users['setter'].pk}, format='json'
            ).status_code,
            400,
        )

    def test_call_aggregate_is_service_only_workspace_scoped_and_never_contains_numbers(self):
        for workspace, state in [
            ('isolation', 'accepted'),
            ('isolation', 'rejected'),
            ('isolation', 'unknown'),
            ('isolation', 'blocked'),
            ('assurance', 'accepted'),
        ]:
            PhoneCallAttempt.objects.create(
                request_id=uuid4(),
                user=self.users['setter'],
                workspace=workspace,
                contact_id=123,
                extension='501',
                fingerprint='test',
                state=state,
            )
        url = f'/api/portal/internal/isolation/call-statistics/?from={self.day}&to={self.day}'
        self.assertEqual(self.client.get(url).status_code, 403)
        token = issue(
            'compensation_calls',
            actor=self.users['administrator'].pk,
            **{'from': self.day, 'to': self.day},
        )
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['totals'], {'calls': 1, 'attempts': 3, 'uncertain': 1})
        self.assertEqual(response.data['client']['id'], self.users['client'].pk)
        self.assertEqual(
            set(response.data['results'][0]),
            {'user_id', 'user__username', 'calls', 'attempts', 'uncertain'},
        )
        self.assertEqual(self.client.get(url + '&setter_id=1').status_code, 403)
        Membership.objects.filter(user=self.users['administrator']).update(active=False)
        self.assertEqual(self.client.get(url).status_code, 403)
