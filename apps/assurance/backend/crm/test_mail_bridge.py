from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.mail_bridge import issue
from packages.access.tickets import issue as user_ticket
from .test_notifications import fixture
from .models import TaskNotification, FollowUpTask


@override_settings(DEBUG=True)
class MailBridgeTests(TestCase):
    def setUp(self):
        self.source = fixture()
        self.source.report()
        self.notice = TaskNotification.objects.get()
        self.client = APIClient()
        self.url = '/api/assurance/internal/mail-events/'

    def auth(self, op, **claims):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(op, **claims))

    def test_signed_feed_minimizes_fields_and_uses_cursor(self):
        self.auth('events', after=0)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        event = response.data['events'][0]
        self.assertEqual(set(event), {'id', 'created_at', 'setter_id'})
        self.assertEqual(event['setter_id'], 21)
        self.assertNotIn('SECRET', str(response.data))
        self.assertNotIn('No show', str(response.data))
        self.auth('events', after=self.notice.pk)
        self.assertEqual(self.client.get(self.url + f'?after={self.notice.pk}').data['events'], [])

    def test_user_tickets_wrong_operation_claims_and_expiry_are_refused(self):
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + user_ticket(99, 'assurance', 'administrator')
        )
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.auth('eligible', event=self.notice.pk, user=21)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.auth('events', after=1)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        with patch('django.core.signing.time.time', return_value=1000):
            self.auth('events', after=0)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_eligibility_rechecks_closure_and_current_owner(self):
        url = self.url + f'{self.notice.pk}/21/'
        self.auth('eligible', event=self.notice.pk, user=21)
        self.assertTrue(self.client.get(url).data['eligible'])
        FollowUpTask.objects.update(setter_id=22)
        self.assertFalse(self.client.get(url).data['eligible'])
        self.auth('events', after=0)
        self.assertEqual(self.client.get(self.url).data['events'][0]['setter_id'], 22)
        FollowUpTask.objects.update(closed_at=timezone.now())
        self.assertEqual(self.client.get(self.url).data['events'], [])

    def test_historical_backfill_and_old_events_are_not_emailed(self):
        TaskNotification.objects.create(
            task=self.notice.task, event_key='existing:test', kind='existing'
        )
        TaskNotification.objects.filter(pk=self.notice.pk).update(
            created_at=timezone.now() - timedelta(days=8)
        )
        self.auth('events', after=0)
        self.assertEqual(self.client.get(self.url).data['events'], [])

    def test_feed_is_bounded(self):
        TaskNotification.objects.bulk_create(
            [
                TaskNotification(task=self.notice.task, event_key=f'event:{i}', kind='incident')
                for i in range(105)
            ]
        )
        self.auth('events', after=0)
        response = self.client.get(self.url)
        self.assertEqual(len(response.data['events']), 100)
        last = response.data['events'][-1]['id']
        self.auth('events', after=last)
        self.assertEqual(len(self.client.get(self.url + f'?after={last}').data['events']), 6)
