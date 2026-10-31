from unittest.mock import Mock, patch
from django.db import connection
from django.test import TestCase, override_settings
from packages.access.isolation_events import issue, verify
from packages.calendar_connectors import events, providers
from . import calendar_sync as sync
from . import test_calendar_sync as fixtures
from .test_calendars import OPTIONS
from .models import Membership, CalendarSync


@override_settings(**OPTIONS)
@override_settings(ISOLATION_INTERNAL_URL='http://isolation:8000')
class IsolationPublicationTests(TestCase):
    setUp = fixtures.SyncTests.setUp
    remote = fixtures.SyncTests.remote

    def prepare(self):
        Membership.objects.create(user=self.user, workspace='isolation', role='client')
        self.row.workspace = 'isolation'
        self.row.save()
        self.source['isolation_publication'] = True

    def test_publication_callback_runs_after_provider_transaction_and_preserves_key_on_recovery(
        self,
    ):
        self.prepare()
        initial = len(connection.savepoint_ids)
        calls = []

        def post(url, **kwargs):
            self.assertEqual(len(connection.savepoint_ids), initial)
            calls.append(verify(kwargs['json']['proof'], 'publication_status'))
            return Mock(status_code=200)

        with (
            patch.object(sync, 'source', return_value=self.source),
            patch.object(events, 'find', return_value=None),
            patch.object(events, 'publish', side_effect=providers.ProviderError()),
            patch('portal.backend.identity.isolation_publication.requests.post', side_effect=post),
        ):
            self.assertEqual(sync.sync_one(self.row, 41), 'error')
        ledger = CalendarSync.objects.get()
        key = ledger.key
        self.assertEqual(calls[-1]['state'], 'error')
        self.assertEqual(calls[-1]['revision'], 0)
        with (
            patch.object(sync, 'source', return_value=self.source),
            patch.object(events, 'find', return_value=self.remote()),
            patch.object(events, 'publish', return_value='remote') as publish,
            patch('portal.backend.identity.isolation_publication.requests.post', side_effect=post),
        ):
            self.assertEqual(sync.sync_one(self.row, 41), 'synced')
            self.assertIsNotNone(
                publish.call_args.args[-1]
            )  # existing event: update, never another create
        ledger.refresh_from_db()
        self.assertEqual(ledger.key, key)
        self.assertEqual(calls[-1]['state'], 'confirmed')
        self.assertEqual(calls[-1]['owner'], self.user.pk)

    def test_publication_proof_is_required_and_google_optin_must_be_active(self):
        self.prepare()
        path = '/api/portal/internal/isolation/publish-visit/'
        self.assertEqual(self.client.post(path, {'proof': 'bad'}, format='json').status_code, 403)
        proof = issue(
            'publish_visit', actor=self.user.pk, role='client', owner=self.user.pk, visit=41
        )
        self.row.auto_sync = False
        self.row.save()
        self.assertEqual(self.client.post(path, {'proof': proof}, format='json').status_code, 503)
        self.row.auto_sync = True
        self.row.save()
        with patch.object(sync, 'sync_one', return_value='synced') as publish:
            response = self.client.post(path, {'proof': proof}, format='json')
            self.assertEqual(response.data, {'state': 'synced'})
            self.assertEqual(publish.call_args.args[1], 41)
        Membership.objects.filter(workspace='isolation').update(active=False)
        self.assertEqual(self.client.post(path, {'proof': proof}, format='json').status_code, 403)
