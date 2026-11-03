from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from .isolation_sms import sync
from .models import SmsAttempt


@override_settings(
    NEWT_SMS_ENABLED=True,
    NEWT_SMS_CALLER_ID='4387388939',
    NEWT_USERNAME='test',
    NEWT_PASSWORD='test',
    NEWT_SMS_AUTOMATIC_FROM='2026-01-01T00:00:00Z',
)
class AutomaticSmsTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.visit = {
            'id': 1,
            'phone': '+1 438 738-8944',
            'created_at': (now - timedelta(days=2)).isoformat(),
            'starts_at': (now + timedelta(hours=23)).isoformat(),
        }

    @patch('portal.backend.identity.isolation_sms.sms.send', return_value='unknown')
    @patch('portal.backend.identity.isolation_sms.load')
    def test_each_kind_submits_once_and_uncertain_results_are_not_retried(self, load, send):
        load.return_value = [self.visit]
        self.assertEqual(sync(), 2)
        self.assertEqual(sync(), 0)
        self.assertEqual(send.call_count, 2)
        self.assertEqual(
            set(SmsAttempt.objects.values_list('kind', flat=True)), {'confirmation', 'reminder'}
        )
        self.assertTrue(
            all(row.actor_id is None and row.state == 'unknown' for row in SmsAttempt.objects.all())
        )

    @patch('portal.backend.identity.isolation_sms.sms.send')
    @patch('portal.backend.identity.isolation_sms.load')
    def test_cancelled_or_changed_visit_is_not_submitted(self, load, send):
        load.side_effect = [[self.visit], [], []]
        self.assertEqual(sync(), 0)
        send.assert_not_called()

    @patch('portal.backend.identity.isolation_sms.sms.send', return_value='accepted')
    @patch('portal.backend.identity.isolation_sms.load')
    def test_older_booking_still_gets_reminder_and_invalid_number_is_skipped(self, load, send):
        self.visit['created_at'] = (timezone.now() - timedelta(days=15)).isoformat()
        load.side_effect = [[self.visit, {**self.visit, 'id': 2, 'phone': 'bad'}], [self.visit]]
        self.assertEqual(sync(), 1)
        self.assertEqual(SmsAttempt.objects.get().kind, 'reminder')
        send.assert_called_once()
