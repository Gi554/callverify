from unittest.mock import patch, Mock
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from packages.newt import directory
from .models import Membership, AccessAudit, PhoneExtension
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, Barrier
from time import sleep
from django.db import connection, close_old_connections
from django.test import TransactionTestCase


@override_settings(
    DEBUG=True, NEWT_DIRECTORY_ENABLED=True, NEWT_USERNAME='test-user', NEWT_PASSWORD='test-secret'
)
class DirectoryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user('admin')
        self.client = APIClient()
        self.client.force_login(self.user)
        self.url = '/api/portal/phone-directory/'
        for space in ('assurance', 'isolation'):
            Membership.objects.create(user=self.user, workspace=space, role='administrator')

    def test_explicit_read_has_minimal_results_no_ip_secret_or_assignment(self):
        with patch(
            'portal.backend.identity.phone_directory.fetch',
            return_value=[{'extension': '501', 'name': 'Test'}],
        ) as fetch:
            result = self.client.post(self.url, {}, format='json')
            self.assertEqual(result.status_code, 200)
            fetch.assert_called_once_with('test-user', 'test-secret')
        self.assertEqual(result['Cache-Control'], 'no-store')
        self.assertEqual(result.data['source'], 'NEWT 343')
        self.assertFalse(PhoneExtension.objects.exists())
        self.assertEqual(AccessAudit.objects.get().metadata, {'count': 1})
        self.assertNotIn('test-secret', str(result.data) + str(list(AccessAudit.objects.values())))

    def test_one_space_admin_setter_advisor_and_revoked_roles_cannot_fetch(self):
        for role in ('setter', 'advisor'):
            Membership.objects.filter(workspace='assurance').update(role=role)
            with patch('portal.backend.identity.phone_directory.fetch') as fetch:
                self.assertEqual(self.client.post(self.url, {}, format='json').status_code, 403)
                fetch.assert_not_called()
        Membership.objects.filter(workspace='assurance').delete()
        with patch('portal.backend.identity.phone_directory.fetch') as fetch:
            self.assertEqual(self.client.post(self.url, {}, format='json').status_code, 403)
            fetch.assert_not_called()

    def test_disabled_missing_config_get_and_arbitrary_functions_refused(self):
        with patch('portal.backend.identity.phone_directory.fetch') as fetch:
            with override_settings(NEWT_DIRECTORY_ENABLED=False):
                self.assertEqual(self.client.post(self.url, {}, format='json').status_code, 503)
            with override_settings(NEWT_PASSWORD=''):
                self.assertEqual(self.client.post(self.url, {}, format='json').status_code, 503)
            self.assertEqual(self.client.get(self.url).status_code, 405)
            self.assertEqual(
                self.client.post(self.url, {'_f': '245'}, format='json').status_code, 400
            )
            self.assertEqual(
                self.client.post(self.url + '?_f=245', {}, format='json').status_code, 400
            )
            fetch.assert_not_called()

    def test_failure_never_means_empty_success_or_mutates_associations(self):
        PhoneExtension.objects.create(user=self.user, extension='501')
        with patch(
            'portal.backend.identity.phone_directory.fetch',
            side_effect=directory.DirectoryUnavailable('private provider body'),
        ):
            result = self.client.post(self.url, {}, format='json')
        self.assertEqual(result.status_code, 503)
        self.assertNotIn('private provider body', str(result.data))
        self.assertEqual(PhoneExtension.objects.get().extension, '501')
        self.assertFalse(AccessAudit.objects.exists())

    def test_csrf_and_rate_limit(self):
        csrf = APIClient(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.url, {}, format='json').status_code, 403)
        with patch(
            'portal.backend.identity.phone_directory.fetch',
            return_value=[{'extension': '501', 'name': 'Test'}],
        ):
            for _ in range(5):
                self.assertEqual(self.client.post(self.url, {}, format='json').status_code, 200)
            self.assertEqual(self.client.post(self.url, {}, format='json').status_code, 429)


class DirectoryAdapterTests(TestCase):
    def response(self, raw=b'501,10.0.0.1,"Test, Name"\n', status=200):
        response = Mock(status_code=status)
        response.iter_content.return_value = [raw]
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    def test_only_343_fixed_https_and_ten_hex_correlation_no_redirect(self):
        with patch.object(directory.requests, 'get', return_value=self.response()) as http:
            result = directory.fetch('test-user', 'test-secret')
        self.assertEqual(result, [{'extension': '501', 'name': 'Test, Name'}])
        self.assertEqual(http.call_args.args, (directory.URL,))
        args = http.call_args.kwargs
        self.assertEqual(args['params']['_f'], '343')
        self.assertEqual(args['params']['_v'], 'C')
        self.assertRegex(args['params']['_t'], r'^[a-f0-9]{10}$')
        self.assertFalse(args['allow_redirects'])
        self.assertTrue(args['stream'])
        self.assertEqual(args['auth'], ('test-user', 'test-secret'))
        self.assertNotIn('10.0.0.1', str(result))

    def test_partial_malformed_duplicate_empty_and_oversize_fail_closed(self):
        for raw in (
            b'',
            b'Unauthorized',
            b'501,,A\n501,,B',
            b'501,,A\ninvalid',
            b'501,,A,extra',
            b'501,,"unterminated',
            b'501,,bad\x00name',
            b'abc,,A',
            b'501,,\xff',
        ):
            with self.assertRaises(directory.DirectoryUnavailable):
                directory.parse(raw)
        with patch.object(
            directory.requests, 'get', return_value=self.response(b'x' * (directory.MAX_BYTES + 1))
        ):
            with self.assertRaises(directory.DirectoryUnavailable):
                directory.fetch('u', 'p')
        for status in (301, 401, 500):
            with patch.object(directory.requests, 'get', return_value=self.response(status=status)):
                with self.assertRaises(directory.DirectoryUnavailable):
                    directory.fetch('u', 'p')

    def test_sorted_directory_bounds_and_missing_credentials_do_not_network(self):
        self.assertEqual(
            [r['extension'] for r in directory.parse(b'513,,B\n501,,A')], ['501', '513']
        )
        with self.assertRaises(directory.DirectoryUnavailable):
            directory.parse(('501,,' + 'x' * 151).encode())
        with patch.object(directory.requests, 'get') as http:
            with self.assertRaises(directory.DirectoryUnavailable):
                directory.fetch('', '')
            http.assert_not_called()


@skipUnless(connection.vendor == 'postgresql', 'Directory serialization requires PostgreSQL')
@override_settings(
    DEBUG=True, NEWT_DIRECTORY_ENABLED=True, NEWT_USERNAME='test-user', NEWT_PASSWORD='test-secret'
)
class DirectoryConcurrencyTests(TransactionTestCase):
    def test_provider_reads_are_serialized_between_workers(self):
        from .models import PhoneDirectoryGate

        cache.clear()
        user = get_user_model().objects.create_user('admin')
        PhoneDirectoryGate.objects.create(pk=1)
        for space in ('assurance', 'isolation'):
            Membership.objects.create(user=user, workspace=space, role='administrator')
        clients = [APIClient(), APIClient()]
        for client in clients:
            client.force_login(user)
        guard = Lock()
        barrier = Barrier(2)
        state = {'active': 0, 'peak': 0}

        def provider(*args):
            with guard:
                state['active'] += 1
                state['peak'] = max(state['peak'], state['active'])
            sleep(0.05)
            with guard:
                state['active'] -= 1
            return [{'extension': '501', 'name': 'Test'}]

        def worker(client):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return client.post('/api/portal/phone-directory/', {}, format='json').status_code
            finally:
                close_old_connections()

        with patch('portal.backend.identity.phone_directory.fetch', side_effect=provider):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(worker, clients))
        self.assertEqual(results, [200, 200])
        self.assertEqual(state['peak'], 1)
