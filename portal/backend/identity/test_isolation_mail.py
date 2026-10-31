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
