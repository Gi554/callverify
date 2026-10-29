from uuid import uuid4
from unittest.mock import patch, Mock
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.phone_calls import issue
from packages.newt.calls import place
from .phone_calls import eligible
from .models import Membership, PhoneExtension, PhoneCallAttempt, AccessAudit, CallRules
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import connection, close_old_connections
from django.test import TransactionTestCase


@override_settings(
    DEBUG=True,
    NEWT_CALLS_ENABLED=True,
    NEWT_USERNAME='synthetic-user',
    NEWT_PASSWORD='synthetic-secret',
)
class PhoneCallsTests(TestCase):
    def setUp(self):
        CallRules.objects.update_or_create(pk=1, defaults={'enforce_hours': False})
        self.user = get_user_model().objects.create_user('synthetic-setter')
        self.client = APIClient()
        self.client.force_login(self.user)
        self.membership = Membership.objects.create(
            user=self.user, workspace='assurance', role='setter'
        )
        PhoneExtension.objects.create(user=self.user, extension='501')
        self.key = uuid4()
        self.lease = uuid4()
        self.url = '/api/portal/assurance/calls/'
        self.proof = issue(self.user.pk, 42, 3, self.key, '15145550101', self.lease)
        self.check = patch('portal.backend.identity.phone_calls.eligible', return_value=True)
        self.eligible = self.check.start()
        self.addCleanup(self.check.stop)
        provider = patch('portal.backend.identity.phone_calls.place', return_value='accepted')
        self.provider = provider.start()
        self.addCleanup(provider.stop)

    def post(self, proof=None):
        return self.client.post(self.url, {'proof': proof or self.proof}, format='json')

    def test_one_dispatch_replay_status_and_private_output(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['state'], 'accepted')
        self.provider.assert_called_once_with(
            'synthetic-user', 'synthetic-secret', '501', '15145550101', auto_answer=False
        )
        self.assertEqual(self.post().data['state'], 'accepted')
        self.assertEqual(self.provider.call_count, 1)
        self.assertEqual(self.client.get(self.url + str(self.key) + '/').data['contact_id'], 42)
        self.assertEqual(response['Cache-Control'], 'no-store')
        # No extension or phone field, and no such digits in text values. The random request
        # UUID and the timestamps (microseconds) may contain them by chance, so they are skipped.
        self.assertEqual(
            set(response.data),
            {
                'request_id',
                'contact_id',
                'workspace',
                'state',
                'created_at',
                'updated_at',
                'definition',
            },
        )
        for key, value in response.data.items():
            if key != 'request_id' and isinstance(value, str):
                self.assertNotIn('501', value)
                self.assertNotIn('1514', value)
        self.assertEqual(AccessAudit.objects.filter(action='phone.call_reserved').count(), 1)

    def test_administrator_calls_with_own_extension_and_same_one_shot_guards(self):
        self.membership.role = 'administrator'
        self.membership.save()
        self.assertEqual(
            self.client.get(self.url + 'options/').data,
            {
                'enabled': True,
                'post_associated': True,
                'call_window': {'allowed': True, 'message': ''},
            },
        )
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.post().status_code, 200)
        self.provider.assert_called_once_with(
            'synthetic-user', 'synthetic-secret', '501', '15145550101', auto_answer=False
        )
        self.assertEqual(PhoneCallAttempt.objects.get().user, self.user)
        self.membership.active = False
        self.membership.save()
        self.assertEqual(self.client.get(self.url + str(self.key) + '/').status_code, 403)
        self.assertEqual(self.post().status_code, 403)

    def test_administrator_without_extension_cannot_borrow_another_post(self):
        self.membership.role = 'administrator'
        self.membership.save()
        PhoneExtension.objects.filter(user=self.user).delete()
        self.assertEqual(self.post().status_code, 400)
        self.assertEqual(self.client.get(self.url + 'options/').data['post_associated'], False)
        self.provider.assert_not_called()

    def test_timeout_or_crash_is_not_retried(self):
        self.provider.side_effect = RuntimeError('private provider error')
        self.assertEqual(self.post().data['state'], 'unknown')
        self.assertEqual(self.post().data['state'], 'unknown')
        self.assertEqual(self.provider.call_count, 1)
        self.assertNotIn('private', str(self.post().data))

    def test_reservation_is_committed_before_provider_and_inflight_replay(self):
        def provider(*args, **kwargs):
            self.assertEqual(PhoneCallAttempt.objects.get().state, 'dispatching')
            self.assertEqual(self.post().data['state'], 'dispatching')
            return 'accepted'

        self.provider.side_effect = provider
        self.assertEqual(self.post().data['state'], 'accepted')
        self.assertEqual(self.provider.call_count, 1)

    def test_recheck_blocking_changed_source_never_calls_provider(self):
        self.eligible.return_value = False
        self.assertEqual(self.post().data['state'], 'blocked')
        self.assertEqual(self.post().data['state'], 'blocked')
        self.provider.assert_not_called()

    def test_disabled_missing_post_and_nonsetter_refused(self):
        with override_settings(NEWT_CALLS_ENABLED=False):
            self.assertEqual(self.post().status_code, 503)
        PhoneExtension.objects.all().delete()
        self.assertEqual(self.post().status_code, 400)
        for role in ('advisor',):
            Membership.objects.filter(pk=self.membership.pk).update(role=role)
            self.assertEqual(self.post().status_code, 403)
        self.assertFalse(PhoneCallAttempt.objects.exists())
        self.provider.assert_not_called()

    def test_csrf_strict_inputs_and_proof_expiration(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(
            client.post(self.url, {'proof': self.proof}, format='json').status_code, 403
        )
        self.assertEqual(
            self.client.post(
                self.url, {'proof': self.proof, 'extension': '999'}, format='json'
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                self.url + '?_f=245', {'proof': self.proof}, format='json'
            ).status_code,
            400,
        )
        with patch('django.core.signing.time.time', return_value=timezone.now().timestamp() + 61):
            self.assertEqual(self.post().status_code, 400)
        self.provider.assert_not_called()

    def test_uuid_content_and_rate_guards(self):
        self.post()
        altered = issue(self.user.pk, 43, 3, self.key, '15145550101', self.lease)
        self.assertEqual(self.post(altered).status_code, 409)
        new = issue(self.user.pk, 42, 3, uuid4(), '15145550101', self.lease)
        self.assertEqual(self.post(new).status_code, 409)
        self.assertEqual(self.provider.call_count, 1)

    def test_other_user_and_advisor_cannot_read_attempt(self):
        self.post()
        other = get_user_model().objects.create_user('other')
        Membership.objects.create(user=other, workspace='assurance', role='setter')
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.url + str(self.key) + '/').status_code, 404)
        self.assertEqual(self.post().status_code, 400)

    def test_preflight_is_fixed_authenticated_bounded_and_fails_closed(self):
        from packages.access.phone_calls import verify

        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.status_code = 200
        response.raw.read.return_value = b'{"eligible":true}'
        with patch(
            'portal.backend.identity.phone_calls.requests.post', return_value=response
        ) as post:
            self.assertTrue(eligible(self.user, verify(self.proof, self.user.pk), self.proof))
            self.assertTrue(post.call_args.args[0].endswith('/contacts/42/call-intent-check/'))
            self.assertFalse(post.call_args.kwargs['allow_redirects'])
            self.assertTrue(post.call_args.kwargs['headers']['Authorization'].startswith('Bearer '))
        self.membership.role = 'administrator'
        self.membership.save()
        with patch(
            'portal.backend.identity.phone_calls.requests.post', return_value=response
        ) as post:
            self.assertTrue(eligible(self.user, verify(self.proof, self.user.pk), self.proof))
            from packages.access.tickets import verify as verify_access

            bearer = post.call_args.kwargs['headers']['Authorization'].split()[1]
            self.assertEqual(verify_access(bearer, 'assurance')['role'], 'administrator')
        response.raw.read.return_value = b'bad'
        with patch('portal.backend.identity.phone_calls.requests.post', return_value=response):
            self.assertFalse(eligible(self.user, verify(self.proof, self.user.pk), self.proof))


@skipUnless(connection.vendor == 'postgresql', 'Call serialization requires PostgreSQL')
@override_settings(
    DEBUG=True,
    NEWT_CALLS_ENABLED=True,
    NEWT_USERNAME='synthetic-user',
    NEWT_PASSWORD='synthetic-secret',
)
class CallConcurrencyTests(TransactionTestCase):
    def test_concurrent_same_request_is_dispatched_only_once(self):
        # This tests serialization, independently of the real time in Montreal.
        CallRules.objects.update_or_create(pk=1, defaults={'enforce_hours': False})
        user = get_user_model().objects.create_user('concurrent-setter')
        Membership.objects.create(user=user, workspace='assurance', role='setter')
        PhoneExtension.objects.create(user=user, extension='501')
        proof = issue(user.pk, 42, 0, uuid4(), '15145550101', uuid4())
        barrier = Barrier(2)

        def worker(_):
            close_old_connections()
            try:
                client = APIClient()
                client.force_login(user)
                barrier.wait(timeout=10)
                result = client.post(
                    '/api/portal/assurance/calls/', {'proof': proof}, format='json'
                )
                return result.status_code, result.data['state']
            finally:
                close_old_connections()

        with (
            patch('portal.backend.identity.phone_calls.eligible', return_value=True),
            patch('portal.backend.identity.phone_calls.place', return_value='accepted') as provider,
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(worker, range(2)))
            self.assertTrue(all(code == 200 for code, state in results))
            self.assertTrue(all(state in ('accepted', 'dispatching') for code, state in results))
            self.assertEqual(provider.call_count, 1)
        self.assertEqual(PhoneCallAttempt.objects.count(), 1)


class ProviderTests(TestCase):
    def response(self, body, status=200):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock()
        response.status_code = status
        response.iter_content.return_value = [body]
        return response

    def test_correlated_success_fixed_arguments_and_no_autoanswer(self):
        with (
            patch('packages.newt.calls.secrets.token_hex', return_value='0123456789'),
            patch(
                'packages.newt.calls.requests.get',
                return_value=self.response(b'Success,501,15145550101,0123456789,,,'),
            ) as get,
        ):
            self.assertEqual(place('u', 'p', '501', '15145550101'), 'accepted')
            get.assert_called_once()
            params = get.call_args.kwargs['params']
            self.assertEqual(params['_f'], '245')
            self.assertNotIn('_a', params)
            self.assertFalse(get.call_args.kwargs['allow_redirects'])

    def test_auto_answer_is_sent_only_when_explicitly_enabled(self):
        with (
            patch('packages.newt.calls.secrets.token_hex', return_value='0123456789'),
            patch(
                'packages.newt.calls.requests.get',
                return_value=self.response(b'Success,501,15145550101,0123456789,,,'),
            ) as get,
        ):
            self.assertEqual(place('u', 'p', '501', '15145550101', auto_answer=True), 'accepted')
            self.assertEqual(get.call_args.kwargs['params']['_a'], 'Y')

    def test_invalid_response_is_unknown_not_success_and_no_retry(self):
        for body in (
            b'Success,999,15145550101,0123456789',
            b'<html>error</html>',
            b'',
            b'x' * 4097,
        ):
            with (
                patch('packages.newt.calls.secrets.token_hex', return_value='0123456789'),
                patch('packages.newt.calls.requests.get', return_value=self.response(body)) as get,
            ):
                self.assertEqual(place('u', 'p', '501', '15145550101'), 'unknown')
                self.assertEqual(get.call_count, 1)

    def test_invalid_destination_cannot_select_a_function(self):
        with patch('packages.newt.calls.requests.get') as get:
            self.assertEqual(place('u', 'p', '501', '512&_f=250'), 'unknown')
            get.assert_not_called()

    def test_confirmed_provider_blank_echo_success_and_failure(self):
        for word, expected in (('Success', 'accepted'), ('Failure', 'rejected')):
            with patch(
                'packages.newt.calls.requests.get',
                return_value=self.response(f'{word},501,15145550101,,,,,'.encode()),
            ) as get:
                self.assertEqual(place('u', 'p', '501', '15145550101'), expected)
                get.assert_called_once()
                self.assertNotIn('_a', get.call_args.kwargs['params'])
        for body in (
            b'Success,501,15145550102,,,,,',
            b'Success,501,15145550101,foreign,,,,',
            b'Success,501,15145550101,,unexpected,,,',
        ):
            with patch('packages.newt.calls.requests.get', return_value=self.response(body)):
                self.assertEqual(place('u', 'p', '501', '15145550101'), 'unknown')
