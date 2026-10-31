from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .models import Membership, PhoneCallAttempt


@override_settings(DEBUG=True)
class CallStatisticsTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('metrics-admin')
        self.setter = get_user_model().objects.create_user('metrics-setter')
        Membership.objects.create(user=self.admin, workspace='assurance', role='administrator')
        Membership.objects.create(user=self.setter, workspace='assurance', role='setter')
        self.client = APIClient()
        self.client.force_login(self.admin)
        self.url = '/api/portal/assurance/call-statistics/?from=2026-10-26&to=2026-11-01'

    def row(self, state, workspace='assurance', when=None):
        row = PhoneCallAttempt.objects.create(
            request_id=uuid4(),
            user=self.setter,
            contact_id=42,
            extension='501',
            fingerprint='synthetic',
            state=state,
            workspace=workspace,
        )
        stamp = when or datetime(2026, 11, 1, 23, 59, tzinfo=ZoneInfo('America/Toronto'))
        PhoneCallAttempt.objects.filter(pk=row.pk).update(created_at=stamp)

    def test_actual_accepted_commands_only_and_quebec_day_bounds(self):
        for state in ('accepted', 'accepted', 'rejected', 'blocked', 'unknown', 'dispatching'):
            self.row(state)
        self.row('accepted', workspace='isolation')
        self.row('accepted', when=datetime(2026, 11, 2, 0, 0, tzinfo=ZoneInfo('America/Toronto')))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['totals'], {'calls': 2, 'attempts': 4, 'uncertain': 1})
        self.assertEqual(response.data['results'][0]['user_id'], self.setter.pk)
        self.assertNotIn('extension', str(response.data))
        self.assertNotIn('contact_id', str(response.data))

    def test_admin_membership_required_and_dates_validated(self):
        self.assertEqual(
            self.client.get('/api/portal/assurance/call-statistics/?from=no').status_code, 400
        )
        self.client.force_login(self.setter)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        Membership.objects.filter(user=self.admin).update(active=False)
        Membership.objects.create(user=self.admin, workspace='isolation', role='administrator')
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 403)
