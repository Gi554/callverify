from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone
from .models import Membership, PortalMail, IsolationMailRelay
from .isolation_mail import sync
from .mail_queue import dispatch


@override_settings(
    DEBUG=True,
    ISOLATION_INTERNAL_URL='http://api:8000',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class IsolationMailTests(TestCase):
    def setUp(self):
        mail.outbox = []
        self.user = get_user_model().objects.create_user('client', email='client@example.test')
        self.membership = Membership.objects.create(
            user=self.user, workspace='isolation', role='client'
        )
        self.data = {
            'events': [
                {
                    'id': 1,
                    'recipient_id': self.user.pk,
                    'visit_id': 42,
                    'kind': 'booked',
                    'created_at': timezone.now().isoformat(),
                    'starts_at': '2026-11-01T15:30:00Z',
                    'prospect_name': 'Léa Tremblay',
                }
            ]
        }

    def sync(self):
        with patch('portal.backend.identity.isolation_mail.fetch', return_value=self.data):
            return sync()

    def test_mail_queue_is_deduplicated_encrypted_and_links_the_exact_visit(self):
        self.assertEqual(self.sync()['queued'], 1)
        self.assertEqual(self.sync()['existing'], 1)
        self.assertEqual(IsolationMailRelay.objects.count(), 1)
        self.assertNotIn('Léa', PortalMail.objects.get().payload)
        self.assertEqual(mail.outbox, [])
        with patch('portal.backend.identity.isolation_mail.eligible', return_value=True):
            self.assertEqual(dispatch()['sent'], 1)
            self.assertEqual(dispatch()['sent'], 0)
        self.assertIn('workspace=isolation&visit=42', mail.outbox[0].body)
        self.assertIn('Léa Tremblay', mail.outbox[0].body)
        self.assertIn('01/11/2026 à 10:30', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_missing_result_notice_rechecks_source_before_smtp(self):
        self.data['events'][0]['kind'] = 'result_due'
        self.sync()
        with patch('portal.backend.identity.isolation_mail.eligible', return_value=False):
            self.assertEqual(dispatch()['expired'], 1)
        self.assertEqual(mail.outbox, [])

    def test_fake_or_inactive_recipient_skipped_and_bad_contract_not_queued(self):
        for changes in (
            {'visit_id': True},
            {'prospect_name': ''},
            {'starts_at': '2026-11-01T10:00:00'},
        ):
            before = self.data['events'][0].copy()
            self.data['events'][0].update(changes)
            with self.assertRaises(ValueError):
                self.sync()
            self.data['events'][0] = before
        self.user.email = 'client@example.invalid'
        self.user.save()
        self.assertEqual(self.sync()['skipped'], 1)
        self.assertFalse(PortalMail.objects.exists())

    def prospect_event(self):
        self.data['events'][0].update(
            prospect_email='prospect@example.test',
            ends_at='2026-11-01T16:30:00Z',
            visit_address='12 rue Exemple · Montréal',
        )

    def test_booking_confirms_both_recipients_once_without_exposing_the_private_crm_to_the_prospect(
        self,
    ):
        self.prospect_event()
        self.assertEqual(self.sync()['queued'], 2)
        self.assertEqual(self.sync()['existing'], 2)
        relay = IsolationMailRelay.objects.get()
        self.assertNotEqual(relay.mail_id, relay.prospect_mail_id)
        self.assertNotIn('prospect@example.test', relay.prospect_mail.payload)
        with patch(
            'portal.backend.identity.isolation_mail.fetch',
            return_value={'eligible': True, 'prospect_email': 'prospect@example.test'},
        ):
            self.assertEqual(dispatch()['sent'], 2)
            self.assertEqual(dispatch()['sent'], 0)
        client = next(m for m in mail.outbox if m.to == [self.user.email])
        prospect = next(m for m in mail.outbox if m.to == ['prospect@example.test'])
        self.assertIn('workspace=isolation&visit=42', client.body)
        self.assertIn('01/11/2026 à 10:30', prospect.body)
        self.assertIn('11:30', prospect.body)
        self.assertIn('12 rue Exemple', prospect.body)
        self.assertNotIn('/crm', prospect.body)
        html = prospect.alternatives[0].content
        self.assertNotIn('btn-link', html.split('</style>')[-1])
        self.assertIn('modifier ou annuler', html)

    def test_prospect_confirmation_is_not_suppressed_by_an_invalid_demo_client_email(self):
        self.prospect_event()
        self.user.email = 'client@example.invalid'
        self.user.save()
        self.assertEqual(self.sync()['queued'], 1)
        relay = IsolationMailRelay.objects.get()
        self.assertIsNone(relay.mail_id)
        self.assertIsNotNone(relay.prospect_mail_id)

    def test_source_cancellation_or_email_mismatch_prevents_prospect_dispatch(self):
        self.prospect_event()
        self.sync()
        with patch(
            'portal.backend.identity.isolation_mail.fetch',
            return_value={'eligible': True, 'prospect_email': 'changed@example.test'},
        ):
            counts = dispatch()
        self.assertEqual(counts['sent'], 1)
        self.assertEqual(counts['expired'], 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_missing_result_never_sends_a_prospect_email_and_inactive_owner_blocks_both(self):
        self.prospect_event()
        self.data['events'][0]['kind'] = 'result_due'
        self.assertEqual(self.sync()['queued'], 1)
        self.membership.active = False
        self.membership.save()
        self.assertEqual(dispatch()['expired'], 1)
        self.assertEqual(mail.outbox, [])

    def test_prospect_smtp_retry_does_not_requeue_the_client_confirmation(self):
        self.prospect_event()
        self.sync()
        with (
            patch(
                'portal.backend.identity.isolation_mail.fetch',
                return_value={'eligible': True, 'prospect_email': 'prospect@example.test'},
            ),
            patch(
                'portal.backend.identity.mail_queue.send_mail',
                side_effect=[1, RuntimeError('smtp')],
            ),
        ):
            result = dispatch()
        self.assertEqual(result['sent'], 1)
        self.assertEqual(result['retry'], 1)
        self.assertEqual(self.sync()['queued'], 0)
        PortalMail.objects.filter(status='pending').update(next_attempt_at=timezone.now())
        with (
            patch(
                'portal.backend.identity.isolation_mail.fetch',
                return_value={'eligible': True, 'prospect_email': 'prospect@example.test'},
            ),
            patch('portal.backend.identity.mail_queue.send_mail', return_value=1) as smtp,
        ):
            self.assertEqual(dispatch()['sent'], 1)
        self.assertEqual(smtp.call_args.args[3], ['prospect@example.test'])

    def test_isolation_calendar_event_has_an_owner_reminder_without_inviting_the_prospect(self):
        from uuid import uuid4
        from datetime import timedelta
        from packages.calendar_connectors.events import body

        now = timezone.now()
        event = body(
            'google',
            uuid4(),
            'isolation',
            {'id': 42, 'starts_at': now, 'ends_at': now + timedelta(hours=1)},
        )
        self.assertEqual(
            event['reminders'],
            {'useDefault': False, 'overrides': [{'method': 'popup', 'minutes': 30}]},
        )
        self.assertNotIn('attendees', event)
