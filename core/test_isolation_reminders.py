from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.isolation_events import issue
from . import test_isolation_client as fixtures
from .models import IsolationReminderPolicy, IsolationNotice, IsolationVisit, IsolationVisitResult
from .isolation_reminders import generate, candidates


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class IsolationReminderTests(TestCase):
    setUp = fixtures.IsolationClientTests.setUp
    auth = fixtures.IsolationClientTests.auth
    report = fixtures.IsolationClientTests.report
    payload = fixtures.IsolationClientTests.payload

    def active(self):
        IsolationReminderPolicy.objects.update_or_create(
            pk=1,
            defaults={
                'active_from': timezone.now() - timedelta(days=30),
                'enabled': True,
                'delay_hours': 24,
            },
        )

    def test_one_nudge_at_24_hours_and_no_attendance_is_inferred(self):
        self.active()
        due = self.visit.ends_at + timedelta(hours=24)
        with patch('django.utils.timezone.now', return_value=due - timedelta(seconds=1)):
            self.assertEqual(generate()['created'], 0)
        with patch('django.utils.timezone.now', return_value=due):
            self.assertEqual(generate()['created'], 1)
            self.assertEqual(generate()['created'], 0)
            self.assertEqual(candidates().count(), 1)
            self.assertEqual(
                self.client.get('/api/isolation-notices/?unread=true').data['count'], 1
            )
        self.assertFalse(IsolationVisitResult.objects.exists())
        self.assertEqual(IsolationNotice.objects.get().recipient_id, 72)

    def test_report_cancel_reschedule_and_policy_pause_invalidate_unsent_mail(self):
        self.active()
        with patch(
            'django.utils.timezone.now', return_value=self.visit.ends_at + timedelta(hours=25)
        ):
            generate()
            self.assertEqual(candidates().count(), 1)
            IsolationReminderPolicy.objects.update(enabled=False)
            self.assertEqual(candidates().count(), 0)
            IsolationReminderPolicy.objects.update(enabled=True, delay_hours=48)
            self.assertEqual(candidates().count(), 0)
            IsolationReminderPolicy.objects.update(delay_hours=24)
            IsolationVisit.objects.update(status='cancelled')
            self.assertEqual(candidates().count(), 0)
            IsolationVisit.objects.update(
                status='scheduled', starts_at=self.visit.starts_at + timedelta(minutes=1)
            )
            self.assertEqual(candidates().count(), 0)
            IsolationVisit.objects.update(starts_at=self.visit.starts_at)
            self.report(closed=False)
            self.assertEqual(candidates().count(), 0)

    def test_new_google_booked_notice_is_unique_and_feed_requires_a_server_proof(self):
        self.active()
        IsolationVisit.objects.update(
            publication='google',
            publication_status='confirmed',
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=1),
        )
        generate()
        generate()
        self.assertEqual(IsolationNotice.objects.filter(kind='booked').count(), 1)
        client = APIClient()
        url = '/api/internal/isolation/mail-events/?after=0'
        self.assertEqual(client.get(url).status_code, 403)
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue('mail_events', after=0))
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        row = response.data['events'][0]
        self.assertEqual(
            set(row),
            {'id', 'recipient_id', 'visit_id', 'kind', 'created_at', 'prospect_name', 'starts_at'},
        )
        client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + issue('mail_eligible', event=row['id'], user=72)
        )
        self.assertTrue(
            client.get(f'/api/internal/isolation/mail-events/{row["id"]}/72/').data['eligible']
        )
        IsolationVisit.objects.update(status='cancelled')
        self.assertFalse(
            client.get(f'/api/internal/isolation/mail-events/{row["id"]}/72/').data['eligible']
        )

    def test_no_historic_backlog_and_admin_policy_is_versioned(self):
        IsolationReminderPolicy.objects.update_or_create(
            pk=1, defaults={'active_from': timezone.now()}
        )
        with patch('django.utils.timezone.now', return_value=timezone.now() + timedelta(days=2)):
            self.assertEqual(generate()['created'], 0)
        self.auth(90, 'administrator')
        url = '/api/isolation-reminder-policy/'
        data = self.client.get(url).data
        self.assertEqual(data['delay_hours'], 24)
        first = self.client.post(
            url, {**data, 'delay_hours': 48, 'reason': 'Deux jours'}, format='json'
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(
            self.client.post(
                url, {**data, 'reason': 'Ancienne version'}, format='json'
            ).status_code,
            409,
        )
        self.auth(72, 'client')
        self.assertEqual(self.client.get(url).status_code, 403)
