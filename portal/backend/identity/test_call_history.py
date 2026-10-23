from uuid import uuid4
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from packages.access.phone_calls import issue, verify
from .models import Membership, PhoneExtension, PhoneCallAttempt


@override_settings(
    DEBUG=True,
    NEWT_CALLS_ENABLED=True,
    NEWT_USERNAME='synthetic-user',
    NEWT_PASSWORD='synthetic-secret',
)
class CallHistoryTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.setter = users.create_user('history-setter')
        self.other = users.create_user('history-other')
        self.admin = users.create_user('history-admin')
        self.advisor = users.create_user('history-advisor')
        for user, role in (
            (self.setter, 'setter'),
            (self.other, 'setter'),
            (self.admin, 'administrator'),
            (self.advisor, 'advisor'),
        ):
            Membership.objects.create(user=user, workspace='assurance', role=role)
        PhoneExtension.objects.create(user=self.setter, extension='501')
        self.client = APIClient()
        self.url = '/api/portal/assurance/call-history/'
        for check in (
            patch('portal.backend.identity.phone_calls.eligible', return_value=True),
            patch('portal.backend.identity.phone_calls.place', return_value='accepted'),
        ):
            check.start()
            self.addCleanup(check.stop)

    def call(self, label):
        self.client.force_login(self.setter)
        proof = issue(self.setter.pk, 42, 3, uuid4(), '15145550101', uuid4(), label=label)
        return self.client.post('/api/portal/assurance/calls/', {'proof': proof}, format='json')

    def test_label_is_signed_and_bounded(self):
        proof = issue(self.setter.pk, 42, 3, uuid4(), '15145550101', uuid4(), label='Dossier')
        self.assertEqual(verify(proof, self.setter.pk)['label'], 'Dossier')
        long = issue(self.setter.pk, 42, 3, uuid4(), '15145550101', uuid4(), label='x' * 300)
        self.assertEqual(len(verify(long, self.setter.pk)['label']), 120)
        with self.assertRaises(signing.BadSignature):
            verify(proof + 'x', self.setter.pk)

    def test_setter_sees_own_calls_and_administrator_the_team(self):
        self.assertEqual(self.call('Dossier Alpha').status_code, 200)
        PhoneCallAttempt.objects.create(
            request_id=uuid4(),
            user=self.other,
            workspace='assurance',
            contact_id=7,
            contact_label='Dossier Beta',
            extension='502',
            fingerprint='x',
            state='rejected',
        )
        PhoneCallAttempt.objects.create(
            request_id=uuid4(),
            user=self.other,
            workspace='isolation',
            contact_id=8,
            extension='502',
            fingerprint='y',
        )
        mine = self.client.get(self.url)
        self.assertEqual(mine['Cache-Control'], 'no-store')
        self.assertEqual(mine.data['count'], 1)
        row = mine.data['results'][0]
        self.assertEqual(row['contact_label'], 'Dossier Alpha')
        self.assertEqual(row['state'], 'accepted')
        self.assertNotIn('caller', row)
        self.assertNotIn('extension', row)
        self.assertEqual(self.client.get(self.url, {'user_id': self.other.pk}).status_code, 403)
        self.client.force_login(self.admin)
        team = self.client.get(self.url).data
        self.assertEqual(team['count'], 2)
        self.assertEqual(
            {row['caller']['username'] for row in team['results']},
            {'history-setter', 'history-other'},
        )
        self.assertEqual(self.client.get(self.url, {'user_id': self.other.pk}).data['count'], 1)
        self.assertEqual(self.client.get(self.url, {'state': 'rejected'}).data['count'], 1)
        self.assertEqual(self.client.get(self.url, {'state': 'bad'}).status_code, 400)
        self.client.force_login(self.advisor)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.get('/api/portal/unknown/call-history/').status_code, 403)
