import hashlib
import hmac
import json
import time
from io import StringIO
from datetime import timedelta
from unittest.mock import patch
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from django.conf import settings
from django.core.management import call_command
from django.utils import timezone
from django.test import TestCase, TransactionTestCase, override_settings
from django.db import connection, close_old_connections
from packages.calendar_connectors import calendly as provider
from packages.calendar_connectors.providers import ProviderError
from .calendars import seal, unseal
from .calendly_booking import email_digest
from .calendly_sync import process_receipt, reconcile
from .models import CalendlyReservation, CalendlyInvitee, CalendlyWebhook, CalendlyWebhookReceipt
from .test_calendly import OPTIONS, TOKENS, EVENT
from .test_calendly_booking import CalendlyDispatchTests


@override_settings(**OPTIONS)
class CalendlyWebhookTests(TestCase):
    setUp = CalendlyDispatchTests.setUp

    def event(self, **changes):
        return {
            'event': 'invitee.created',
            'payload': {
                'uri': self.uri,
                'tracking': {'utm_content': self.data['request_id']},
                'email': 'private@example.invalid',
                'questions_and_answers': [{'answer': 'private qualification'}],
                **changes,
            },
        }

    def send(self, body=None, timestamp=None, signature=None, hook=None):
        hook = hook or CalendlyWebhook.objects.get()
        raw = json.dumps(body or self.event(), separators=(',', ':')).encode()
        timestamp = str(timestamp if timestamp is not None else int(time.time()))
        digest = hmac.new(
            settings.CALENDLY_WEBHOOK_SIGNING_KEY.encode(),
            timestamp.encode() + b'.' + raw,
            hashlib.sha256,
        ).hexdigest()
        header = signature if signature is not None else f't={timestamp},v1={digest}'
        return self.client.post(
            f'/api/portal/calendly/webhook/{hook.pk}/',
            raw,
            content_type='application/json',
            HTTP_CALENDLY_WEBHOOK_SIGNATURE=header,
        )

    def ledger(self, known=False):
        row = CalendlyReservation.objects.create(
            request_id=self.data['request_id'],
            connection=self.row,
            actor_id=self.actor.pk,
            fingerprint='test',
            owner_uri=TOKENS['owner'],
            event_type=EVENT['uri'],
            state='uncertain',
            expected_start=self.start,
            expected_end=self.start + timedelta(minutes=30),
            email_digest=email_digest(self.data['request_id'], self.data['email']),
            payload=seal({'invitee': self.uri}) if known else '',
        )
        if known:
            CalendlyInvitee.objects.create(uri=self.uri, reservation=row)
        return row

    def canonical(self, **changes):
        return {
            'invitee': self.uri,
            'starts_at': self.data['starts_at'],
            'ends_at': self.data['ends_at'],
            'status': 'scheduled',
            'new_invitee': None,
            'old_invitee': None,
            'rescheduled': False,
            'email': self.data['email'],
            'request_id': self.data['request_id'],
            'cancel_url': 'https://calendly.com/cancellations/token',
            'reschedule_url': 'https://calendly.com/reschedulings/token',
            **changes,
        }

    def test_signature_rejects_tampered_stale_future_and_empty_bodies(self):
        with patch.object(provider, 'appointment') as fetch:
            for header in [
                '',
                't=1,v1=bad',
                't=1,t=2,v1=' + 'a' * 64,
                't=²,v1=' + 'a' * 64,
                f't={int(time.time())},v1=' + 'é' * 64,
            ]:
                self.assertEqual(self.send(signature=header).status_code, 403)
            self.assertEqual(self.send(timestamp=int(time.time()) - 181).status_code, 403)
            self.assertEqual(self.send(timestamp=int(time.time()) + 181).status_code, 403)
            self.assertEqual(
                self.client.post(
                    f'/api/portal/calendly/webhook/{CalendlyWebhook.objects.get().pk}/',
                    b'',
                    content_type='application/json',
                ).status_code,
                403,
            )
            fetch.assert_not_called()
        self.assertFalse(CalendlyWebhookReceipt.objects.exists())

    def test_receipt_is_deduplicated_and_strips_personal_data(self):
        self.assertEqual(self.send().status_code, 202)
        self.assertEqual(self.send().status_code, 202)
        self.assertEqual(CalendlyWebhookReceipt.objects.count(), 1)
        row = CalendlyWebhookReceipt.objects.get()
        clean = unseal(row.payload)
        self.assertEqual(
            set(clean), {'event', 'invitee', 'old_invitee', 'new_invitee', 'request_id'}
        )
        self.assertNotIn('private', row.payload)
        self.assertNotIn('email', str(clean))
        hook = CalendlyWebhook.objects.get()
        hook.state = 'inactive'
        hook.save()
        self.assertEqual(self.send(self.event(uri=self.uri + '-different')).status_code, 204)
        self.assertEqual(CalendlyWebhookReceipt.objects.count(), 1)

    def test_lost_response_recovers_and_delivers_only_once(self):
        row = self.ledger()
        self.send()
        item = CalendlyWebhookReceipt.objects.get()
        with (
            patch.object(provider, 'appointment', return_value=self.canonical()),
            patch(
                'portal.backend.identity.calendly_sync.rpc',
                side_effect=lambda *args: {'result': 'applied', 'revision': args[3]['revision']},
            ) as deliver,
        ):
            self.assertEqual(process_receipt(item.pk), 'done')
            self.assertEqual(process_receipt(item.pk), 'skipped')
            deliver.assert_called_once()
            self.assertNotIn('email', str(deliver.call_args.args[3]))
            self.assertEqual(deliver.call_args.args[3]['owner'], self.owner.pk)
        row.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(row.state, 'confirmed')
        self.assertEqual(row.delivered_revision, row.revision)
        self.assertEqual(item.payload, '')
        self.assertEqual(CalendlyInvitee.objects.get().reservation_id, row.pk)

    def test_unrelated_or_mismatched_bookings_never_attach_to_a_prospect(self):
        self.send(self.event(tracking={'utm_content': str(uuid4())}))
        item = CalendlyWebhookReceipt.objects.get()
        with (
            patch.object(provider, 'appointment') as fetch,
            patch('portal.backend.identity.calendly_sync.rpc') as deliver,
        ):
            self.assertEqual(process_receipt(item.pk), 'ignored')
            fetch.assert_not_called()
            deliver.assert_not_called()
        row = self.ledger()
        self.send()
        item = CalendlyWebhookReceipt.objects.order_by('-pk').first()
        with (
            patch.object(
                provider, 'appointment', return_value=self.canonical(email='other@example.invalid')
            ),
            patch('portal.backend.identity.calendly_sync.rpc') as deliver,
        ):
            self.assertEqual(process_receipt(item.pk), 'retry')
            deliver.assert_not_called()
        row.refresh_from_db()
        self.assertEqual(row.state, 'uncertain')

    def test_reschedule_chain_and_late_cancellation_preserve_the_new_meeting(self):
        row = self.ledger(known=True)
        new_uri = 'https://api.calendly.com/scheduled_events/new-event/invitees/new-invitee'
        new_time = self.start + timedelta(days=1)
        old = self.canonical(status='cancelled', rescheduled=True, new_invitee=new_uri)
        new = self.canonical(
            invitee=new_uri,
            starts_at=new_time.isoformat(),
            ends_at=(new_time + timedelta(minutes=30)).isoformat(),
            old_invitee=self.uri,
        )

        def fetch(access, uri, owner, event_type):
            self.assertEqual(owner, TOKENS['owner'])
            return old if uri == self.uri else new

        with (
            patch.object(provider, 'appointment', side_effect=fetch),
            patch(
                'portal.backend.identity.calendly_sync.rpc',
                side_effect=lambda *args: {'result': 'applied', 'revision': args[3]['revision']},
            ) as deliver,
        ):
            reconcile(row, {'invitee': new_uri})
            row.refresh_from_db()
            first_revision = row.revision
            reconcile(row, {'invitee': self.uri})
            row.refresh_from_db()
            self.assertEqual(unseal(row.payload)['invitee'], new_uri)
            self.assertEqual(unseal(row.payload)['status'], 'scheduled')
            self.assertEqual(row.revision, first_revision)
            self.assertEqual(deliver.call_count, 1)
        self.assertEqual(CalendlyInvitee.objects.filter(reservation=row).count(), 2)

    def test_delivery_failure_keeps_the_same_version_for_retry(self):
        row = self.ledger(known=True)
        with (
            patch.object(provider, 'appointment', return_value=self.canonical()),
            patch('portal.backend.identity.calendly_sync.rpc', side_effect=ProviderError()),
        ):
            with self.assertRaises(ProviderError):
                reconcile(row)
        row.refresh_from_db()
        revision = row.revision
        self.assertEqual(row.delivered_revision, 0)
        with (
            patch.object(provider, 'appointment', return_value=self.canonical()),
            patch(
                'portal.backend.identity.calendly_sync.rpc',
                side_effect=lambda *args: {'result': 'applied', 'revision': args[3]['revision']},
            ),
        ):
            reconcile(row)
        row.refresh_from_db()
        self.assertEqual(row.revision, revision)
        self.assertEqual(row.delivered_revision, revision)

    def test_operator_recovery_verifies_state_without_creating_a_remote_booking(self):
        row = self.ledger()
        output = StringIO()
        with (
            patch.object(provider, 'appointment', return_value=self.canonical()),
            patch.object(provider, 'create_invitee') as create,
            patch(
                'portal.backend.identity.calendly_sync.rpc',
                side_effect=lambda *args: {'result': 'applied', 'revision': args[3]['revision']},
            ),
        ):
            call_command(
                'sync_calendly', recover_request=str(row.pk), invitee=self.uri, stdout=output
            )
            create.assert_not_called()
        row.refresh_from_db()
        self.assertEqual(row.state, 'confirmed')
        self.assertEqual(row.delivered_revision, row.revision)
        self.assertIn('Rapprochement confirmé', output.getvalue())

    def test_an_expired_receipt_worker_cannot_erase_a_newer_claim(self):
        self.ledger(known=True)
        self.send()
        item = CalendlyWebhookReceipt.objects.get()
        newer_lease = timezone.now() + timedelta(minutes=10)

        def replaced(*args):
            CalendlyWebhookReceipt.objects.filter(pk=item.pk).update(
                state='processing', lease_until=newer_lease
            )

        with patch('portal.backend.identity.calendly_sync.reconcile', side_effect=replaced):
            self.assertEqual(process_receipt(item.pk), 'skipped')
        item.refresh_from_db()
        self.assertEqual(item.state, 'processing')
        self.assertEqual(item.lease_until, newer_lease)
        self.assertTrue(item.payload)

    def test_register_does_not_repeat_uncertain_subscription_creation(self):
        CalendlyWebhook.objects.all().delete()
        payload = unseal(self.row.payload)
        payload['tokens']['organization'] = 'https://api.calendly.com/organizations/org-1'
        self.row.payload = seal(payload)
        self.row.save()
        self.client.force_login(self.owner)
        with (
            patch.object(provider, 'find_webhook', return_value=None),
            patch.object(provider, 'create_webhook', side_effect=ProviderError()) as create,
        ):
            first = self.client.post(
                '/api/portal/calendly/webhooks/', {'revision': self.row.revision}, format='json'
            )
            self.assertEqual(first.status_code, 503)
            self.assertEqual(
                self.client.post(
                    '/api/portal/calendly/webhooks/', {'revision': self.row.revision}, format='json'
                ).status_code,
                503,
            )
            create.assert_called_once()
        with (
            patch.object(
                provider,
                'find_webhook',
                return_value='https://api.calendly.com/webhook_subscriptions/subscription',
            ),
            patch.object(provider, 'create_webhook') as create,
        ):
            self.assertEqual(
                self.client.post(
                    '/api/portal/calendly/webhooks/', {'revision': self.row.revision}, format='json'
                ).status_code,
                200,
            )
            create.assert_not_called()
        self.assertEqual(CalendlyWebhook.objects.get().state, 'active')


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL receipt locking')
@override_settings(**OPTIONS)
class CalendlyWebhookConcurrencyTests(TransactionTestCase):
    setUp = CalendlyWebhookTests.setUp
    ledger = CalendlyWebhookTests.ledger
    canonical = CalendlyWebhookTests.canonical
    send = CalendlyWebhookTests.send
    event = CalendlyWebhookTests.event

    def test_parallel_duplicate_receipt_delivers_once(self):
        self.ledger(known=True)
        self.send()
        pk = CalendlyWebhookReceipt.objects.get().pk

        def run(_):
            close_old_connections()
            try:
                return process_receipt(pk)
            finally:
                close_old_connections()

        with (
            patch.object(provider, 'appointment', return_value=self.canonical()),
            patch(
                'portal.backend.identity.calendly_sync.rpc',
                side_effect=lambda *args: {'result': 'applied', 'revision': args[3]['revision']},
            ) as deliver,
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            self.assertEqual(sorted(pool.map(run, range(2))), ['done', 'skipped'])
            deliver.assert_called_once()
