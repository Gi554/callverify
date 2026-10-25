from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from unittest import skipUnless
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection, close_old_connections
from django.test import TestCase, TransactionTestCase, SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from packages.calendar_connectors import calendly as provider
from packages.calendar_connectors.providers import ProviderError
from .calendars import seal, unseal
from .models import (
    Membership,
    CalendlyConnection,
    CalendlyAuthorization,
    CalendarConnection,
    AccessAudit,
)

OPTIONS = {
    'CALENDLY_WEBHOOK_SIGNING_KEY': 'synthetic-calendly-webhook-key-for-tests',
    'DEBUG': True,
    'CALENDLY_CLIENT_ID': 'test-client',
    'CALENDLY_CLIENT_SECRET': 'test-private-secret',
    'PORTAL_CALENDAR_KEY': '',
    'PORTAL_PUBLIC_URL': 'http://localhost:5174',
    'PASSWORD_HASHERS': ['django.contrib.auth.hashers.MD5PasswordHasher'],
}
OWNER = 'https://api.calendly.com/users/owner-1'
TOKENS = {'access': 'private-access', 'refresh': 'private-refresh', 'owner': OWNER}
PROFILE = {'uri': OWNER, 'name': 'Conseiller Test', 'scheduling_url': 'https://calendly.com/test'}
EVENT = {
    'uri': 'https://api.calendly.com/event_types/type-1',
    'name': 'Entretien',
    'duration': 30,
    'scheduling_url': 'https://calendly.com/test/entretien',
}
BASE = '/api/portal/calendly/'


@override_settings(**OPTIONS)
class CalendlyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user('advisor')
        self.grant = Membership.objects.create(
            user=self.user, workspace='assurance', role='advisor'
        )
        self.client = APIClient()
        self.client.force_login(self.user)

    def post(self, route, data=None, client=None):
        return (client or self.client).post(BASE + route + '/', data or {}, format='json')

    def start(self):
        response = self.post('start')
        self.assertEqual(response.status_code, 200, response.data)
        return parse_qs(urlsplit(response.data['authorization_url']).query)['state'][0]

    def finish(self, state):
        return self.post('callback', {'state': state, 'code': 'private-code'})

    def connected(self, expired=False):
        return CalendlyConnection.objects.create(
            user=self.user,
            connected=True,
            revision=3,
            payload=seal(
                {
                    'tokens': TOKENS,
                    'profile': PROFILE,
                    'event_types': [EVENT],
                    'selected': EVENT['uri'],
                }
            ),
            expires_at=timezone.now() + timedelta(seconds=-1 if expired else 7200),
            checked_at=timezone.now(),
        )

    def test_disabled_and_owner_roles(self):
        with override_settings(CALENDLY_CLIENT_SECRET=''):
            response = self.client.get(BASE)
            self.assertFalse(response.data['configured'])
            self.assertEqual(self.post('start').status_code, 503)
            self.assertIn('no-store', self.post('start')['Cache-Control'])
        for role in ['administrator', 'setter']:
            self.grant.role = role
            self.grant.save()
            self.assertEqual(self.client.get(BASE).status_code, 403)
            self.assertEqual(self.post('start').status_code, 403)
        self.grant.delete()
        Membership.objects.create(user=self.user, workspace='isolation', role='client')
        self.assertEqual(self.post('start').status_code, 403)

    def test_pkce_binding_expiry_replay_and_consent_denied(self):
        state = self.start()
        attempt = CalendlyAuthorization.objects.get()
        self.assertNotEqual(attempt.state_hash, state)
        self.assertEqual(len(unseal(attempt.verifier)), 86)
        second = APIClient()
        second.force_login(self.user)
        with patch.object(provider, 'tokens') as tokens:
            self.assertEqual(
                self.post('callback', {'state': state, 'code': 'x'}, second).status_code, 400
            )
            CalendlyAuthorization.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
            self.assertEqual(self.finish(state).status_code, 400)
            state = self.start()
            self.assertEqual(
                self.post('callback', {'state': state, 'error': 'access_denied'}).status_code, 400
            )
            self.assertEqual(self.finish(state).status_code, 400)
            tokens.assert_not_called()
        self.assertFalse(
            CalendlyAuthorization.objects.filter(used=True).exclude(verifier='').exists()
        )

    def test_connection_seals_secrets_and_preserves_google(self):
        google = CalendarConnection.objects.create(
            user=self.user,
            workspace='assurance',
            provider='google',
            connected=True,
            payload=seal({'access': 'google-private'}),
        )
        state = self.start()
        with (
            patch.object(provider, 'tokens', return_value=(TOKENS, 7200)),
            patch.object(provider, 'profile', return_value=PROFILE),
            patch.object(provider, 'event_types', return_value=[EVENT]),
        ):
            response = self.finish(state)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(self.finish(state).status_code, 400)
        row = CalendlyConnection.objects.get()
        self.assertNotIn(TOKENS['access'], row.payload)
        self.assertNotIn(PROFILE['name'], row.payload)
        self.assertEqual(unseal(row.payload)['tokens'], TOKENS)
        response = self.client.get(BASE)
        self.assertNotIn('private', str(response.data))
        self.assertFalse(response.data['booking_in_crm'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(CalendarConnection.objects.get().payload, google.payload)
        self.assertFalse(AccessAudit.objects.exclude(metadata={}).exists())

    def test_new_start_disconnect_and_stale_callback(self):
        first = self.start()
        second = self.start()
        with patch.object(provider, 'tokens') as exchange:
            self.assertEqual(self.finish(first).status_code, 400)
            row = CalendlyConnection.objects.get()
            self.assertEqual(self.post('disconnect', {'revision': row.revision}).status_code, 204)
            self.assertEqual(self.finish(second).status_code, 400)
            exchange.assert_not_called()

    def test_disconnect_during_exchange_cannot_resurrect_connection(self):
        state = self.start()

        def exchange(*args, **kwargs):
            self.post('disconnect', {'revision': CalendlyConnection.objects.get().revision})
            return TOKENS, 7200

        with (
            patch.object(provider, 'tokens', side_effect=exchange),
            patch.object(provider, 'profile', return_value=PROFILE),
            patch.object(provider, 'event_types', return_value=[EVENT]),
        ):
            self.assertEqual(self.finish(state).status_code, 400)
        self.assertFalse(CalendlyConnection.objects.get().connected)

    def test_select_only_own_pages_revision_and_disconnect(self):
        row = self.connected()
        other = get_user_model().objects.create_user('other')
        other_row = CalendlyConnection.objects.create(
            user=other, connected=True, payload='unreadable'
        )
        self.assertEqual(
            self.post(
                'selection',
                {'revision': 3, 'event_type': 'https://api.calendly.com/event_types/foreign'},
            ).status_code,
            400,
        )
        self.assertEqual(self.post('selection', {'revision': 3, 'event_type': ''}).status_code, 200)
        self.assertEqual(
            self.post('selection', {'revision': 3, 'event_type': EVENT['uri']}).status_code, 400
        )
        self.assertEqual(
            self.post('disconnect', {'revision': 3, 'user': other.pk}).status_code, 400
        )
        self.grant.delete()
        self.assertEqual(self.post('disconnect', {'revision': 4}).status_code, 204)
        row.refresh_from_db()
        other_row.refresh_from_db()
        self.assertFalse(row.connected)
        self.assertEqual(row.payload, '')
        self.assertTrue(other_row.connected)

    def test_refresh_rotation_persisted_when_later_discovery_fails(self):
        row = self.connected(expired=True)
        rotated = {**TOKENS, 'refresh': 'new-private-refresh'}
        with (
            patch.object(provider, 'tokens', return_value=(rotated, 7200)) as renew,
            patch.object(provider, 'profile', side_effect=ProviderError()),
        ):
            self.assertEqual(self.post('refresh', {'revision': row.revision}).status_code, 503)
            renew.assert_called_once()
        row.refresh_from_db()
        self.assertTrue(row.connected)
        self.assertEqual(unseal(row.payload)['tokens']['refresh'], rotated['refresh'])
        with (
            patch.object(provider, 'tokens') as renew,
            patch.object(provider, 'profile', return_value=PROFILE),
            patch.object(provider, 'event_types', return_value=[]),
        ):
            response = self.post('refresh', {'revision': row.revision})
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['selected_event_type'], '')
            renew.assert_not_called()

    def test_ambiguous_refresh_failure_does_not_reuse_token(self):
        row = self.connected(expired=True)
        with patch.object(provider, 'tokens', side_effect=ProviderError()) as renew:
            self.assertEqual(self.post('refresh', {'revision': row.revision}).status_code, 503)
            row.refresh_from_db()
            self.assertFalse(row.connected)
            self.assertEqual(row.payload, '')
            self.assertEqual(self.post('refresh', {'revision': row.revision}).status_code, 400)
            renew.assert_called_once()

    def test_role_loss_during_refresh_does_not_roll_back_spent_token(self):
        row = self.connected(expired=True)

        def types(*args):
            self.grant.active = False
            self.grant.save()
            return [EVENT]

        with (
            patch.object(provider, 'tokens', return_value=({**TOKENS, 'refresh': 'new'}, 7200)),
            patch.object(provider, 'profile', return_value=PROFILE),
            patch.object(provider, 'event_types', side_effect=types),
        ):
            self.assertEqual(self.post('refresh', {'revision': row.revision}).status_code, 403)
        row.refresh_from_db()
        self.assertFalse(row.connected)
        self.assertEqual(row.payload, '')


class CalendlyAdapterTests(SimpleTestCase):
    def test_authorization_and_token_basic_auth_rotation_scopes(self):
        options = {
            'client_id': 'client',
            'client_secret': 'private-secret',
            'redirect': 'https://example.org/crm/oauth/calendly',
        }
        query = parse_qs(urlsplit(provider.authorization(options, 'state', 'verifier')).query)
        self.assertEqual(query['code_challenge_method'], ['S256'])
        self.assertNotIn('private-secret', str(query))
        self.assertEqual(set(query['scope'][0].split()), set(provider.BOOKING_SCOPES))
        token = {
            'access_token': 'access',
            'refresh_token': 'rotated',
            'expires_in': 7200,
            'token_type': 'Bearer',
            'owner': OWNER,
            'scope': 'users:read event_types:read',
        }
        with patch.object(provider, 'http', return_value=token) as http:
            result, seconds = provider.tokens(options, code='code', verifier='verifier')
            self.assertEqual(seconds, 7200)
            self.assertEqual(result['refresh'], 'rotated')
            self.assertEqual(http.call_args.kwargs['auth'], ('client', 'private-secret'))
            self.assertEqual(http.call_args.kwargs['data']['code_verifier'], 'verifier')
            with self.assertRaises(ProviderError):
                provider.tokens(options, refresh='rotated')
            token['scope'] = 'users:read'
            with self.assertRaises(ProviderError):
                provider.tokens(options, code='code', verifier='verifier')
            token.pop('refresh_token')
            with self.assertRaises(ProviderError):
                provider.tokens(options, refresh='old')

    def test_pages_are_scoped_minimal_and_pagination_never_follows_urls(self):
        event = {
            **EVENT,
            'active': True,
            'kind': 'solo',
            'profile': {'owner': OWNER},
            'internal_note': 'do-not-store',
        }
        first = {
            'collection': [
                event,
                {**event, 'kind': 'group'},
                {**event, 'profile': {'owner': OWNER + '-foreign'}},
            ],
            'pagination': {'next_page_token': 'page2', 'next_page': 'https://attacker.invalid'},
        }
        second = {'collection': [], 'pagination': {'next_page_token': None}}
        with patch.object(provider, 'http', side_effect=[first, second]) as http:
            self.assertEqual(provider.event_types('access', OWNER), [EVENT])
            for call in http.call_args_list:
                self.assertEqual(call.args[1], 'https://api.calendly.com/event_types')
                self.assertEqual(call.kwargs['params']['user'], OWNER)
            self.assertEqual(http.call_args.kwargs['params']['page_token'], 'page2')
        with patch.object(provider, 'http', return_value=first):
            with self.assertRaises(ProviderError):
                provider.event_types('access', OWNER)

    def test_untrusted_booking_links_and_profile_owner_rejected(self):
        for url in [
            'http://calendly.com/a',
            'https://calendly.com.attacker.com/a',
            'https://user@calendly.com/a',
            'https://calendly.com/a?email=secret',
            'javascript:alert(1)',
            'https://calendly.com/a\\b',
        ]:
            with self.assertRaises(ProviderError):
                provider.booking_url(url)
        with patch.object(
            provider, 'http', return_value={'resource': {**PROFILE, 'uri': OWNER + '-foreign'}}
        ):
            with self.assertRaises(ProviderError):
                provider.profile('access', OWNER)


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL row locking')
@override_settings(**OPTIONS)
class CalendlyConcurrencyTests(TransactionTestCase):
    def test_parallel_refresh_only_spends_token_once(self):
        cache.clear()
        user = get_user_model().objects.create_user('concurrent-advisor')
        Membership.objects.create(user=user, workspace='assurance', role='advisor')
        row = CalendlyConnection.objects.create(
            user=user,
            connected=True,
            revision=3,
            expires_at=timezone.now(),
            payload=seal(
                {'tokens': TOKENS, 'profile': PROFILE, 'event_types': [EVENT], 'selected': ''}
            ),
        )
        clients = [APIClient(), APIClient()]
        for client in clients:
            client.force_login(user)

        def run(client):
            close_old_connections()
            try:
                return client.post(
                    BASE + 'refresh/', {'revision': row.revision}, format='json'
                ).status_code
            finally:
                close_old_connections()

        with (
            patch.object(
                provider, 'tokens', return_value=({**TOKENS, 'refresh': 'new'}, 7200)
            ) as renew,
            patch.object(provider, 'profile', return_value=PROFILE),
            patch.object(provider, 'event_types', return_value=[EVENT]),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            self.assertEqual(sorted(pool.map(run, clients)), [200, 400])
            renew.assert_called_once()
