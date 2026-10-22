from datetime import timedelta
from unittest.mock import patch
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from django.db import connection, close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from packages.access.mail_bridge import issue as bridge_ticket
from .test_notifications import fixture
from .models import FollowUpTask, Appointment, AppointmentReport, ReminderEvent, ReminderPolicy
from .reminders import generate, active, ESCALATIONS


@override_settings(DEBUG=True)
class EscalationTests(TestCase):
    def setUp(self):
        self.source = fixture()
        self.client = APIClient()
        self.auth(99, 'administrator')

    def auth(self, pk, role):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, 'assurance', role))

    def rules(self):
        return ReminderPolicy.objects.create(
            escalations_enabled=True, task_escalation_hours=3, report_escalation_hours=3
        )

    def overdue(self):
        self.source.report()
        FollowUpTask.objects.update(due_at=timezone.now() - timedelta(hours=4))
        return FollowUpTask.objects.get()

    def test_opt_in_configuration_and_admin_only_visibility(self):
        self.overdue()
        generate()
        self.assertFalse(ReminderEvent.objects.filter(kind__in=ESCALATIONS).exists())
        url = '/api/assurance/reminder-policy/'
        data = self.client.get(url).data
        self.assertFalse(data['escalations_enabled'])
        response = self.client.post(
            url,
            {
                **data,
                'escalations_enabled': True,
                'task_escalation_hours': 3,
                'reason': 'Seuil validé',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        generate()
        path = '/api/assurance/reminders/?category=escalations'
        self.assertEqual(self.client.get(path).data['count'], 1)
        self.auth(21, 'setter')
        self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.get('/api/assurance/reminders/').data['count'], 1)
        self.auth(31, 'advisor')
        self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.get('/api/assurance/reminders/').data['count'], 0)

    def test_task_threshold_current_period_and_no_automatic_action(self):
        self.rules()
        task = self.overdue()
        generate()
        self.assertEqual(generate()['created'], 0)
        self.assertEqual(active().filter(kind='task_escalation').count(), 1)
        task.refresh_from_db()
        self.assertEqual(task.setter_id, 21)
        self.assertEqual(task.revision, 0)
        self.assertIsNone(task.closed_at)
        future = timezone.now() + timedelta(days=20)
        with patch('django.utils.timezone.now', return_value=future):
            self.assertEqual(generate()['created'], 2)
            self.assertEqual(active().filter(kind='task_escalation').count(), 1)
        self.assertEqual(ReminderEvent.objects.filter(kind='task_escalation').count(), 2)

    def test_report_escalation_waits_for_grace_and_extra_delay(self):
        self.rules()
        now = timezone.now()
        Appointment.objects.update(
            starts_at=now - timedelta(hours=27), ends_at=now - timedelta(hours=26)
        )
        generate()
        self.assertEqual(active().filter(kind='report_escalation').count(), 0)
        with patch('django.utils.timezone.now', return_value=now + timedelta(hours=2)):
            generate()
            self.assertEqual(active().filter(kind='report_escalation').count(), 1)
        self.assertFalse(AppointmentReport.objects.exists())
        self.assertFalse(FollowUpTask.objects.exists())

    def test_closure_replanning_disable_and_type_pause_remove_escalation(self):
        self.rules()
        task = self.overdue()
        generate()
        ReminderPolicy.objects.update(tasks_enabled=False)
        self.assertEqual(active().filter(kind__in=ESCALATIONS).count(), 0)
        ReminderPolicy.objects.update(tasks_enabled=True, escalations_enabled=False)
        self.assertEqual(active().filter(kind__in=ESCALATIONS).count(), 0)
        ReminderPolicy.objects.update(escalations_enabled=True)
        FollowUpTask.objects.filter(pk=task.pk).update(due_at=timezone.now() + timedelta(days=1))
        self.assertEqual(active().filter(kind__in=ESCALATIONS).count(), 0)
        FollowUpTask.objects.filter(pk=task.pk).update(due_at=task.due_at, closed_at=timezone.now())
        self.assertEqual(active().filter(kind__in=ESCALATIONS).count(), 0)

    def test_reassignment_does_not_duplicate_administrative_supervision(self):
        self.rules()
        self.overdue()
        generate()
        FollowUpTask.objects.update(setter_id=22)
        self.assertEqual(active().filter(kind='task_escalation').count(), 1)
        generate()
        self.assertEqual(ReminderEvent.objects.filter(kind='task_escalation').count(), 1)

    def test_report_response_and_cancellation_stop_escalation(self):
        self.rules()
        now = timezone.now()
        Appointment.objects.update(
            starts_at=now - timedelta(days=3), ends_at=now - timedelta(days=2)
        )
        generate()
        self.assertEqual(active().filter(kind='report_escalation').count(), 1)
        self.assertEqual(self.source.report(performed=True, note='').status_code, 201)
        self.assertEqual(active().filter(kind='report_escalation').count(), 0)

    def test_service_feed_is_separate_and_administrator_broadcast_is_minimal(self):
        self.rules()
        self.overdue()
        generate()
        event = ReminderEvent.objects.get(kind='task_escalation')
        url = '/api/assurance/internal/escalation-mail-events/'
        self.client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + bridge_ticket('reminder_events', after=0)
        )
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + bridge_ticket('escalation_events', after=0)
        )
        rows = self.client.get(url).data['events']
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0]), {'id', 'created_at', 'recipient_id', 'role'})
        self.assertEqual(rows[0]['recipient_id'], 0)
        self.assertEqual(rows[0]['role'], 'administrator')
        self.client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + bridge_ticket('reminder_events', after=0)
        )
        self.assertTrue(
            all(
                row['role'] != 'administrator'
                for row in self.client.get('/api/assurance/internal/reminder-mail-events/').data[
                    'events'
                ]
            )
        )
        self.client.credentials(
            HTTP_AUTHORIZATION='Bearer '
            + bridge_ticket('escalation_eligible', event=event.pk, user=99)
        )
        path = url + f'{event.pk}/99/'
        self.assertTrue(self.client.get(path).data['eligible'])
        FollowUpTask.objects.update(closed_at=timezone.now())
        self.assertFalse(self.client.get(path).data['eligible'])

    def test_threshold_validation(self):
        url = '/api/assurance/reminder-policy/'
        data = self.client.get(url).data
        for changes in (
            {'task_escalation_hours': 0},
            {'report_escalation_hours': 2161},
            {'escalation_interval_hours': 0},
        ):
            self.assertEqual(
                self.client.post(
                    url, {**data, 'reason': 'Test', **changes}, format='json'
                ).status_code,
                400,
            )


@skipUnless(
    connection.vendor == 'postgresql', 'Concurrent escalation generation requires PostgreSQL'
)
@override_settings(DEBUG=True)
class EscalationConcurrencyTests(TransactionTestCase):
    def test_two_generators_create_one_escalation_in_the_period(self):
        source = fixture()
        source.report()
        FollowUpTask.objects.update(due_at=timezone.now() - timedelta(hours=4))
        ReminderPolicy.objects.create(escalations_enabled=True, task_escalation_hours=3)

        def attempt(_):
            close_old_connections()
            try:
                return generate()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(sum(row['created'] for row in results), 2)
        self.assertEqual(ReminderEvent.objects.filter(kind='task_escalation').count(), 1)
