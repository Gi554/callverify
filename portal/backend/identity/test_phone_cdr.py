from datetime import date, timedelta
from unittest.mock import Mock, patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.newt import cdr
from packages.newt.directory import DirectoryUnavailable, URL
from .models import Membership, AccessAudit, PhoneExtension


@override_settings(
    DEBUG=True, NEWT_CDR_SCHEMA_ENABLED=True, NEWT_USERNAME='test-user', NEWT_PASSWORD='test-secret'
)
class CdrTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user('admin')
        self.client = APIClient()
        self.client.force_login(self.user)
        self.url = '/api/portal/phone-cdr-schema/'
        for space in ('assurance', 'isolation'):
            Membership.objects.create(user=self.user, workspace=space, role='administrator')
        self.day = timezone.localdate()
        self.body = {'starts_on': str(self.day), 'ends_on': str(self.day)}

    def test_schema_only_no_records_or_assignments_and_minimal_audit(self):
        result = {
            'columns': ['Extension', 'Destination', 'Result'],
            'row_count': 12,
            'schema_fingerprint': 'a' * 64,
        }
        with patch('portal.backend.identity.phone_cdr.fetch_schema', return_value=result) as fetch:
            response = self.client.post(self.url, self.body, format='json')
            self.assertEqual(response.status_code, 200)
            fetch.assert_called_once_with('test-user', 'test-secret', self.day, self.day)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertFalse(response.data['mapping_confirmed'])
        self.assertNotIn('records', response.data)
        self.assertFalse(PhoneExtension.objects.exists())
        self.assertNotIn('test-secret', str(list(AccessAudit.objects.values())))

    def test_permissions_and_csrf(self):
        csrf = APIClient(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.url, self.body, format='json').status_code, 403)
        Membership.objects.filter(user=self.user, workspace='isolation').update(role='setter')
        with patch('portal.backend.identity.phone_cdr.fetch_schema') as fetch:
            self.assertEqual(self.client.post(self.url, self.body, format='json').status_code, 403)
            fetch.assert_not_called()

    def test_disabled_unconfigured_and_arbitrary_functions_never_request(self):
        with patch('portal.backend.identity.phone_cdr.fetch_schema') as fetch:
            with override_settings(NEWT_CDR_SCHEMA_ENABLED=False):
                self.assertEqual(
                    self.client.post(self.url, self.body, format='json').status_code, 503
                )
            with override_settings(NEWT_PASSWORD=''):
                self.assertEqual(
                    self.client.post(self.url, self.body, format='json').status_code, 503
                )
            self.assertEqual(
                self.client.post(self.url, {**self.body, '_f': '245'}, format='json').status_code,
                400,
            )
            self.assertEqual(
                self.client.post(self.url + '?_f=245', self.body, format='json').status_code, 400
            )
            fetch.assert_not_called()

    def test_invalid_dates_and_future_or_excess_window_refused(self):
        for body in (
            {'starts_on': 'bad', 'ends_on': str(self.day)},
            {'starts_on': str(self.day), 'ends_on': str(self.day + timedelta(days=1))},
            {'starts_on': str(self.day - timedelta(days=7)), 'ends_on': str(self.day)},
            {'starts_on': str(self.day), 'ends_on': str(self.day - timedelta(days=1))},
        ):
            self.assertEqual(self.client.post(self.url, body, format='json').status_code, 400)

    def test_error_body_not_exposed_and_no_success_audit(self):
        with patch(
            'portal.backend.identity.phone_cdr.fetch_schema',
            side_effect=DirectoryUnavailable('private raw CDR'),
        ):
            response = self.client.post(self.url, self.body, format='json')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private raw CDR', str(response.data))
        self.assertFalse(AccessAudit.objects.exists())


class CdrAdapterTests(TestCase):
    def test_only_headers_count_and_fingerprint_leave_parser(self):
        first = cdr.inspect(b'Extension,Destination,Result\n505,15140000000,PRIVATE RESULT\n')
        second = cdr.inspect(b'Extension,Destination,Result\n513,18190000000,OTHER SECRET\n')
        self.assertEqual(first, second)
        self.assertNotIn('PRIVATE', str(first))
        self.assertEqual(first['row_count'], 1)
        self.assertEqual(cdr.inspect(b'Extension,Destination,Result\n')['row_count'], 0)

    def test_empty_partial_duplicate_header_oversize_and_non_utf8_refused(self):
        for raw in (
            b'',
            b'Error',
            b'A,B\n1,2,3',
            b'A,a',
            b'A,',
            b'505,15140000000',
            b'A,B\n"unterminated',
            b'A,B\n\xff',
            b'A,B\n1,' + b'x' * 2049,
        ):
            with self.assertRaises(DirectoryUnavailable):
                cdr.inspect(raw)
        with self.assertRaises(DirectoryUnavailable):
            cdr.inspect(b'A,B\n' + b'1,2\n' * 10001)

    def test_only_fixed_511_bounded_dates_both_directions_and_no_call_command(self):
        response = Mock(status_code=200)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.iter_content.return_value = [b'Extension,Result\n505,Unknown']
        start = date(2026, 10, 1)
        end = date(2026, 10, 7)
        with patch.object(cdr.requests, 'get', return_value=response) as http:
            cdr.fetch_schema('u', 'p', start, end)
        self.assertEqual(http.call_args.args, (URL,))
        args = http.call_args.kwargs
        self.assertEqual(args['params']['_f'], '511')
        self.assertEqual(args['params']['_sd'], '20261001')
        self.assertEqual(args['params']['_ed'], '20261007')
        self.assertEqual(args['params']['_dir'], 'B')
        self.assertRegex(args['params']['_t'], r'^[a-f0-9]{10}$')
        self.assertFalse(args['allow_redirects'])
        response.iter_content.return_value = [b'x' * (cdr.MAX_BYTES + 1)]
        with patch.object(cdr.requests, 'get', return_value=response):
            with self.assertRaises(DirectoryUnavailable):
                cdr.fetch_schema('u', 'p', start, end)
        with patch.object(cdr.requests, 'get') as http:
            with self.assertRaises(DirectoryUnavailable):
                cdr.fetch_schema('u', 'p', '20261001&_f=245', end)
            http.assert_not_called()
