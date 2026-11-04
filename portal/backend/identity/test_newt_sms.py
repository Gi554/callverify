from unittest.mock import patch
from uuid import uuid4
from urllib.parse import parse_qs, unquote

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from packages.newt.sms import send
from .models import Membership, SmsAttempt


@override_settings(
    NEWT_SMS_ENABLED=True,
    NEWT_SMS_CALLER_ID='5145550100',
    NEWT_USERNAME='test',
    NEWT_PASSWORD='test',
)
class SmsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('sms-admin')
        self.membership = Membership.objects.create(
            user=self.user, workspace='isolation', role='administrator'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.path = '/api/portal/isolation/sms/'
        self.body = {
            'request_id': str(uuid4()),
            'destination': '5145550101',
            'message': 'Démo & Québec',
        }

    @patch('packages.newt.sms.requests.post')
    def test_correlated_acceptance_and_replay(self, post):
        response = post.return_value.__enter__.return_value
        response.status_code = 200

        def reply(size):
            data = parse_qs(post.call_args.kwargs['data'])
            self.assertEqual(data['_txt'], [self.body['message']])
            self.assertEqual(data['_f'], ['261'])
            return [f"Success,5145550101,5145550100,{data['_t'][0]},,,".encode()]

        response.iter_content.side_effect = reply
        first = self.client.post(self.path, self.body, format='json')
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.data['state'], 'accepted')
        self.assertEqual(self.client.post(self.path, self.body, format='json').status_code, 200)
        changed = {**self.body, 'message': 'Autre'}
        self.assertEqual(self.client.post(self.path, changed, format='json').status_code, 409)
        post.assert_called_once()
        self.assertNotIn('message', self.client.get(self.path).data['results'][0])

    @patch('packages.newt.sms.requests.post')
    def test_wire_format_uses_percent_spaces_and_preserves_special_characters(self, post):
        message = 'Orvia - Québec + 2 & 50% = confirmé\nDeuxième ligne : déjà.'
        response = post.return_value.__enter__.return_value
        response.status_code = 200
        response.iter_content.return_value = [b'Success,5145550101,5145550100,expected,,,']
        self.assertEqual(
            send('user', 'password', '5145550101', '5145550100', message, 'expected'), 'accepted'
        )
        prepared = requests.Request(
            'POST',
            'https://example.invalid',
            **{key: post.call_args.kwargs[key] for key in ('data', 'headers')},
        ).prepare()
        self.assertNotIn('+', prepared.body)
        self.assertIn('%20', prepared.body)
        self.assertIn('%2B', prepared.body)
        self.assertIn('%0A', prepared.body)
        # Match the provider's percent-only decoding, rather than forgiving '+' decoding.
        fields = dict(item.split('=', 1) for item in prepared.body.split('&'))
        self.assertEqual(unquote(fields['_txt'], encoding='utf-8'), message)
        self.assertEqual(
            prepared.headers['Content-Type'], 'application/x-www-form-urlencoded; charset=utf-8'
        )

    @patch('packages.newt.sms.requests.post', side_effect=requests.Timeout)
    def test_timeout_is_durable_and_does_not_resend(self, post):
        for status in (201, 200):
            result = self.client.post(self.path, self.body, format='json')
            self.assertEqual(result.status_code, status)
            self.assertEqual(result.data['state'], 'unknown')
        post.assert_called_once()
        self.assertEqual(SmsAttempt.objects.count(), 1)

    @patch('packages.newt.sms.requests.post')
    def test_failure_requires_matching_request_id(self, post):
        response = post.return_value.__enter__.return_value
        response.status_code = 200
        response.iter_content.return_value = [b'Failure,5145550101,5145550100,other,,,']
        args = ('user', 'password', '5145550101', '5145550100', 'Test', 'expected')
        self.assertEqual(send(*args), 'unknown')
        response.iter_content.return_value = [b'Failure,5145550101,5145550100,expected,,,']
        self.assertEqual(send(*args), 'rejected')

    @patch('packages.newt.sms.requests.post')
    def test_observed_reversed_fields_require_both_exact_numbers_and_request(self, post):
        response = post.return_value.__enter__.return_value
        response.status_code = 200
        args = ('user', 'password', '4387388944', '4387388939', 'Test', 'expected')
        response.iter_content.return_value = [b'Success,4387388939,4387388944,expected,,,']
        self.assertEqual(send(*args), 'accepted')
        response.iter_content.return_value = [b'Success,4387388939,4387388999,expected,,,']
        self.assertEqual(send(*args), 'unknown')

    @patch('packages.newt.sms.send')
    def test_disabled_and_unauthorized_never_submit(self, dispatch):
        with self.settings(NEWT_SMS_ENABLED=False):
            self.assertEqual(self.client.post(self.path, self.body, format='json').status_code, 503)
        self.membership.role = 'setter'
        self.membership.save()
        self.assertEqual(self.client.get(self.path).status_code, 403)
        self.assertEqual(self.client.post(self.path, self.body, format='json').status_code, 403)
        dispatch.assert_not_called()
