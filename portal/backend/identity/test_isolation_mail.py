from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone
from .models import Membership, PortalMail, IsolationMailRelay, ReminderPhone, SmsAttempt
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
        self.user = get_user_model().objects.create_user(
            'client', email='client@example.test', first_name='Charles'
        )
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
        self.assertIn('Date : 01/11/2026', mail.outbox[0].body)
        self.assertIn('Heure : 10:30', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_missing_result_notice_rechecks_source_before_smtp(self):
        self.data['events'][0]['kind'] = 'result_due'
        self.sync()
        with patch('portal.backend.identity.isolation_mail.eligible', return_value=False):
            self.assertEqual(dispatch()['expired'], 1)
        self.assertEqual(mail.outbox, [])

    @override_settings(
        NEWT_SMS_ENABLED=True,
        NEWT_SMS_CALLER_ID='4387388939',
        NEWT_USERNAME='test',
        NEWT_PASSWORD='test',
        NEWT_SMS_AUTOMATIC_FROM='2026-01-01T00:00:00Z',
        ISOLATION_PROSPECT_SMS_ENABLED=False,
    )
    @patch('portal.backend.identity.isolation_sms.sms.send', return_value='accepted')
    @patch('portal.backend.identity.isolation_sms.eligible', return_value=True)
    def test_new_booking_sends_one_sms_to_the_client_mobile(self, eligible, send):
        ReminderPhone.objects.create(user=self.user, mobile='4387388944')
        self.prospect_event()
        self.assertEqual(self.sync()['queued'], 1)
        self.assertEqual(self.sync()['existing'], 1)
        eligible.assert_called_once_with(1, self.user.pk)
        send.assert_called_once()
        self.assertEqual(send.call_args.args[2], '4387388944')
        message = send.call_args.args[4]
        self.assertIn('01/11/2026 à 10:30', message)
        self.assertIn('workspace=isolation&visit=42', message)
        self.assertNotIn('Léa', message)
        self.assertEqual(SmsAttempt.objects.get().kind, 'client_booking')
        self.assertEqual(PortalMail.objects.count(), 1)

    def test_missing_result_triggers_the_client_sms_and_a_failure_never_blocks_the_queue(self):
        target = 'portal.backend.identity.isolation_sms.remind_client'
        with patch(target, side_effect=RuntimeError('network')) as remind:
            self.data['events'][0]['kind'] = 'result_due'
            self.assertEqual(self.sync()['queued'], 1)
        remind.assert_called_once()
        self.assertEqual(remind.call_args.args[:2], (self.user, 1))
        self.data['events'][0].update(id=2, kind='booked', visit_id=43)
        with patch(target) as remind:
            self.assertEqual(self.sync()['queued'], 1)
        remind.assert_not_called()

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
            setter_name='Setter test',
            reference='ISO-123',
            campaign_name='Campagne test',
            qualification={
                'full_name': 'Léa Tremblay',
                'phone': '5145550100',
                'address': '12 rue Exemple',
                'city': 'Montréal',
                'postal_code': 'H2X 1Y4',
                'email': 'prospect@example.test',
                'attic_accessible': False,
                'monthly_electricity': '0.00',
                'construction_year': 1990,
                'age': 50,
            },
        )

    def test_booking_notifies_only_client_with_complete_qualification_and_signature(self):
        self.prospect_event()
        self.assertEqual(self.sync()['queued'], 1)
        self.assertEqual(self.sync()['existing'], 1)
        relay = IsolationMailRelay.objects.get()
        self.assertIsNone(relay.prospect_mail_id)
        with patch('portal.backend.identity.isolation_mail.eligible', return_value=True):
            self.assertEqual(dispatch()['sent'], 1)
            self.assertEqual(dispatch()['sent'], 0)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.user.email])
        self.assertEqual(message.subject, 'Une nouvelle visite vient d’être programmée')
        for value in (
            'Bonjour Charles',
            'Léa Tremblay',
            '5145550100',
            '12 rue Exemple',
            'Montréal',
            'H2X 1Y4',
            '01/11/2026',
            '10:30',
            '11:30',
            'Grenier accessible : Non',
            '0.00',
            '1990',
            '50',
            'Setter test',
            'ISO-123',
            'Campagne test',
            'Martinien',
            'workspace=isolation&visit=42',
        ):
            self.assertIn(value, message.body)
        self.assertIn('Informations de qualification', message.alternatives[0].content)

    def test_invalid_client_email_never_falls_back_to_the_prospect(self):
        self.prospect_event()
        self.user.email = 'client@example.invalid'
        self.user.save()
        self.assertEqual(self.sync()['queued'], 0)
        self.assertFalse(PortalMail.objects.exists())

    def test_empty_prospect_email_and_unknown_private_fields_do_not_block_client_notification(self):
        self.prospect_event()
        row = self.data['events'][0]
        row['prospect_email'] = ''
        row['qualification'].update(email='', private_note='Do not disclose')
        row['qualification']['address'] = '<script>address</script>'
        self.assertEqual(self.sync()['queued'], 1)
        with patch('portal.backend.identity.isolation_mail.eligible', return_value=True):
            self.assertEqual(dispatch()['sent'], 1)
        html = mail.outbox[0].alternatives[0].content
        self.assertNotIn('<script>address</script>', html)
        self.assertIn('&lt;script&gt;address&lt;/script&gt;', html)
        self.assertNotIn('Do not disclose', html)

    def test_inactive_client_and_cancelled_visits_do_not_dispatch(self):
        self.prospect_event()
        self.sync()
        self.membership.active = False
        self.membership.save()
        self.assertEqual(dispatch()['expired'], 1)
        self.assertEqual(mail.outbox, [])

    def test_previously_queued_prospect_confirmation_is_expired(self):
        from datetime import timedelta
        from .mail_queue import enqueue

        enqueue(
            user=self.user,
            workspace='isolation',
            subject='Old confirmation',
            body='old',
            recipient='prospect@example.test',
            guard={'kind': 'isolation_prospect_notice', 'event': 1, 'user': self.user.pk},
            expires_at=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(dispatch()['expired'], 1)
        self.assertEqual(mail.outbox, [])

    def test_smtp_retry_does_not_duplicate_client_notification(self):
        self.prospect_event()
        self.sync()
        with (
            patch('portal.backend.identity.isolation_mail.eligible', return_value=True),
            patch('portal.backend.identity.mail_queue.send_mail', side_effect=RuntimeError('smtp')),
        ):
            self.assertEqual(dispatch()['retry'], 1)
        self.assertEqual(self.sync()['queued'], 0)
        PortalMail.objects.filter(status='pending').update(next_attempt_at=timezone.now())
        with (
            patch('portal.backend.identity.isolation_mail.eligible', return_value=True),
            patch('portal.backend.identity.mail_queue.send_mail', return_value=1) as smtp,
        ):
            self.assertEqual(dispatch()['sent'], 1)
        self.assertEqual(smtp.call_args.args[3], [self.user.email])

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
