from unittest.mock import patch, Mock
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from packages.newt import status
from packages.newt.directory import DirectoryUnavailable, URL
from .models import Membership, PhoneExtension, AccessAudit


@override_settings(
    DEBUG=True, NEWT_STATUS_ENABLED=True, NEWT_USERNAME='test-user', NEWT_PASSWORD='test-secret'
)
class StatusTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user('admin')
        self.setter = get_user_model().objects.create_user('setter')
        self.client = APIClient()
        self.client.force_login(self.user)
        for space in ('assurance', 'isolation'):
            Membership.objects.create(user=self.user, workspace=space, role='administrator')
        self.grant = Membership.objects.create(
            user=self.setter, workspace='assurance', role='setter'
        )
        self.link = PhoneExtension.objects.create(user=self.setter, extension='505')
        self.url = f'/api/portal/workspaces/assurance/phone-extensions/{self.grant.pk}/status/'

    def test_administrator_post_can_be_observed_without_calling(self):
        member = Membership.objects.get(user=self.user, workspace='assurance')
        PhoneExtension.objects.create(user=self.user, extension='501')
        url = f'/api/portal/workspaces/assurance/phone-extensions/{member.pk}/status/'
        with patch(
            'portal.backend.identity.phone_status.fetch_status',
            return_value={'codes': [], 'observations': 0, 'conclusion': 'indeterminate'},
        ) as fetch:
            response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, 200)
        fetch.assert_called_once_with('test-user', 'test-secret', '501')

    def test_only_assigned_post_and_sanitized_observation_are_used(self):
        with patch(
            'portal.backend.identity.phone_status.fetch_status',
            return_value={'codes': ['C'], 'observations': 1, 'conclusion': 'indeterminate'},
        ) as fetch:
            response = self.client.post(self.url, {}, format='json')
            self.assertEqual(response.status_code, 200)
            fetch.assert_called_once_with('test-user', 'test-secret', '505')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response.data['conclusion'], 'indeterminate')
        self.assertEqual(
            AccessAudit.objects.get().metadata, {'target_id': self.setter.pk, 'observations': 1}
        )
        self.link.refresh_from_db()
        self.assertEqual(self.link.extension, '505')

    def test_arbitrary_post_function_query_and_get_cannot_trigger_provider(self):
        with patch('portal.backend.identity.phone_status.fetch_status') as fetch:
            self.assertEqual(self.client.get(self.url).status_code, 405)
            self.assertEqual(
                self.client.post(
                    self.url, {'extension': '513', '_f': '245'}, format='json'
                ).status_code,
                400,
            )
            self.assertEqual(
                self.client.post(self.url + '?_f=245', {}, format='json').status_code, 400
            )
            fetch.assert_not_called()

    def test_disabled_missing_secret_and_foreign_suspended_or_unassigned_refused(self):
        with patch('portal.backend.identity.phone_status.fetch_status') as fetch:
            with override_settings(NEWT_STATUS_ENABLED=False):
                self.assertEqual(self.client.post(self.url, {}, format='json').status_code, 503)
            with override_settings(NEWT_PASSWORD=''):
                self.assertEqual(self.client.post(self.url, {}, format='json').status_code, 503)
            self.assertEqual(
                self.client.post(
                    self.url.replace('/assurance/', '/isolation/'), {}, format='json'
                ).status_code,
                400,
            )
            Membership.objects.filter(pk=self.grant.pk).update(active=False)
            self.assertEqual(self.client.post(self.url, {}, format='json').status_code, 400)
            Membership.objects.filter(pk=self.grant.pk).update(active=True)
            PhoneExtension.objects.update(extension=None)
            self.assertEqual(self.client.post(self.url, {}, format='json').status_code, 400)
            fetch.assert_not_called()

    def test_permissions_csrf_and_failure_are_not_call_outcomes(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url, {}, format='json').status_code, 403)
        with patch(
            'portal.backend.identity.phone_status.fetch_status',
            side_effect=DirectoryUnavailable('private body'),
        ):
            response = self.client.post(self.url, {}, format='json')
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('private body', str(response.data))
        Membership.objects.filter(user=self.user, workspace='isolation').update(role='setter')
        with patch('portal.backend.identity.phone_status.fetch_status') as fetch:
            self.assertEqual(self.client.post(self.url, {}, format='json').status_code, 403)
            fetch.assert_not_called()


class StatusAdapterTests(TestCase):
    def row(self, **changes):
        data = {
            'extension': '505',
            'number': '15140000000',
            'code': 'C',
            'id': 'private-id',
            't': '0123456789',
            'direction': 'Outbound',
            'name': 'private name',
            'recording': 'private-recording',
            **changes,
        }
        return ','.join(data.values()).encode()

    def test_raw_destinations_ids_names_and_recordings_never_leave_parser(self):
        result = status.parse(self.row(), '505', '0123456789')
        self.assertEqual(result, {'codes': ['C'], 'observations': 1, 'conclusion': 'indeterminate'})
        self.assertEqual(
            status.parse(b'', '505', '0123456789'),
            {'codes': [], 'observations': 0, 'conclusion': 'indeterminate'},
        )
        self.assertEqual(status.parse(self.row() + b',', '505', '0123456789'), result)

    def test_mixed_post_correlation_unknown_code_partial_or_oversized_rows_fail(self):
        for raw in (
            self.row(extension='513'),
            self.row(t='wrong'),
            self.row(code='unknown'),
            b'Error',
            self.row() + b'\ninvalid',
            b'\xff',
        ):
            with self.assertRaises(DirectoryUnavailable):
                status.parse(raw, '505', '0123456789')
        with self.assertRaises(DirectoryUnavailable):
            status.parse(b'\n'.join([self.row()] * 101), '505', '0123456789')

    def test_only_fixed_244_no_destination_and_bounded_https_transport(self):
        response = Mock(status_code=200)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.iter_content.return_value = [self.row()]
        with (
            patch.object(status.secrets, 'token_hex', return_value='0123456789'),
            patch.object(status.requests, 'get', return_value=response) as http,
        ):
            status.fetch_status('test-user', 'test-secret', '505')
        self.assertEqual(http.call_args.args, (URL,))
        args = http.call_args.kwargs
        self.assertEqual(args['params'], {'_f': '244', '_v': 'C', '_x': '505', '_t': '0123456789'})
        self.assertFalse(args['allow_redirects'])
        self.assertTrue(args['stream'])
        response.iter_content.return_value = [b'x' * (status.MAX_BYTES + 1)]
        with patch.object(status.requests, 'get', return_value=response):
            with self.assertRaises(DirectoryUnavailable):
                status.fetch_status('u', 'p', '505')
        with patch.object(status.requests, 'get') as http:
            with self.assertRaises(DirectoryUnavailable):
                status.fetch_status('u', 'p', '505&_f=245')
            http.assert_not_called()
