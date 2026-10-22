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
from .models import (
    FollowUpTask,
    Appointment,
    AppointmentReport,
    ReminderEvent,
    ReminderPolicy,
    BusinessAudit,
)
from .reminders import generate, active


@override_settings(DEBUG=True)
class ReminderTests(TestCase):
    def setUp(self):
        self.source = fixture()
        self.appointment = self.source.appointment
        self.client = APIClient()
        self.auth(99, 'administrator')

    def auth(self, pk, role):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, 'assurance', role))

    def overdue(self):
        self.source.report()
        task = FollowUpTask.objects.get()
        FollowUpTask.objects.filter(pk=task.pk).update(due_at=timezone.now() - timedelta(hours=2))
        return task

    def missing(self):
        Appointment.objects.filter(pk=self.appointment.pk).update(
            starts_at=timezone.now() - timedelta(days=3), ends_at=timezone.now() - timedelta(days=2)
        )

    def test_task_generation_is_idempotent_and_never_closes_the_task(self):
        task = self.overdue()
        self.assertEqual(generate()['created'], 1)
        self.assertEqual(generate()['existing'], 1)
        from django.core.management import call_command
        from io import StringIO

        output = StringIO()
        call_command('generate_assurance_reminders', stdout=output)
        self.assertIn("'existing': 1", output.getvalue())
        task.refresh_from_db()
        self.assertIsNone(task.closed_at)
        self.assertEqual(task.revision, 0)
        event = ReminderEvent.objects.get()
        self.assertEqual(event.recipient_id, 21)
        self.assertEqual(event.kind, 'task_overdue')
        self.assertEqual(active().count(), 1)

    def test_only_current_period_is_generated_after_long_outage(self):
        self.overdue()
        generate()
        now = timezone.now() + timedelta(days=20)
        with patch('django.utils.timezone.now', return_value=now):
            self.assertEqual(generate()['created'], 1)
            self.assertEqual(generate()['existing'], 1)
            self.assertEqual(active().count(), 1)
        self.assertEqual(ReminderEvent.objects.count(), 2)

    def test_report_grace_and_missing_is_not_negative(self):
        self.assertEqual(generate()['created'], 0)
        self.missing()
        self.assertEqual(generate()['created'], 1)
        self.assertEqual(ReminderEvent.objects.get().recipient_role, 'advisor')
        self.assertFalse(AppointmentReport.objects.exists())
        self.assertFalse(FollowUpTask.objects.exists())
        self.auth(31, 'advisor')
        response = self.client.get('/api/assurance/reminders/')
        self.assertEqual(response.data['count'], 1)
        self.assertNotIn('SECRET', str(response.data))
        self.assertNotIn('setter', str(response.data))
        self.auth(21, 'setter')
        self.assertEqual(self.client.get('/api/assurance/reminders/').data['count'], 0)

    def test_report_or_cancellation_removes_pending_reminders(self):
        self.missing()
        generate()
        self.assertEqual(active().count(), 1)
        self.assertEqual(self.source.report(performed=True, note='').status_code, 201)
        self.assertEqual(active().count(), 0)
        self.assertEqual(generate()['created'], 0)
        self.assertTrue(AppointmentReport.objects.get().performed)

    def test_task_replanning_closure_and_transfer_revalidate_active_events(self):
        task = self.overdue()
        generate()
        FollowUpTask.objects.filter(pk=task.pk).update(setter_id=22)
        self.assertEqual(active().count(), 0)
        self.assertEqual(generate()['created'], 1)
        self.auth(21, 'setter')
        self.assertEqual(self.client.get('/api/assurance/reminders/').data['count'], 0)
        self.auth(22, 'setter')
        self.assertEqual(self.client.get('/api/assurance/reminders/').data['count'], 1)
        FollowUpTask.objects.filter(pk=task.pk).update(due_at=timezone.now() + timedelta(days=1))
        self.assertEqual(active().count(), 0)
        self.assertEqual(generate()['created'], 0)
        FollowUpTask.objects.filter(pk=task.pk).update(
            closed_at=timezone.now(), due_at=timezone.now() - timedelta(hours=1)
        )
        self.assertEqual(generate()['created'], 0)

    def test_rescheduled_or_cancelled_appointments_are_not_reminded(self):
        self.missing()
        generate()
        Appointment.objects.filter(pk=self.appointment.pk).update(
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=1),
        )
        self.assertEqual(active().count(), 0)
        self.assertEqual(generate()['created'], 0)
        self.missing()
        Appointment.objects.update(status='cancelled')
        self.assertEqual(active().count(), 0)
        self.assertEqual(generate()['created'], 0)

    def test_configuration_is_admin_only_versioned_and_stops_existing_reminders(self):
        self.overdue()
        generate()
        url = '/api/assurance/reminder-policy/'
        data = self.client.get(url).data
        self.assertEqual(data['task_interval_hours'], 24)
        response = self.client.post(
            url, {**data, 'tasks_enabled': False, 'reason': 'Pause'}, format='json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(active().count(), 0)
        self.assertEqual(
            self.client.post(url, {**data, 'reason': 'Stale'}, format='json').status_code, 409
        )
        self.assertEqual(
            BusinessAudit.objects.get(action='policy.reminders_changed').metadata['reason'], 'Pause'
        )
        self.auth(21, 'setter')
        self.assertEqual(self.client.get(url).status_code, 403)
        self.auth(31, 'advisor')
        self.assertEqual(self.client.post(url, data, format='json').status_code, 403)

    def test_configuration_validation_and_audit_rollback(self):
        url = '/api/assurance/reminder-policy/'
        data = self.client.get(url).data
        for changes in (
            {'task_interval_hours': 0},
            {'report_interval_hours': 721},
            {'report_grace_hours': -1},
            {'unknown': True},
            {'reason': ' '},
        ):
            self.assertEqual(
                self.client.post(
                    url, {**data, 'reason': 'Test', **changes}, format='json'
                ).status_code,
                400,
            )
        with patch(
            'apps.assurance.backend.crm.reminders.BusinessAudit.objects.create',
            side_effect=RuntimeError('audit'),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(url, {**data, 'reason': 'Test'}, format='json')
        self.assertFalse(ReminderPolicy.objects.exists())

    def test_signed_reminder_feed_is_separate_and_expires_with_state(self):
        self.missing()
        generate()
        event = ReminderEvent.objects.get()
        url = '/api/assurance/internal/reminder-mail-events/'
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + bridge_ticket('events', after=0))
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + bridge_ticket('reminder_events', after=0)
        )
        data = self.client.get(url).data['events'][0]
        self.assertEqual(set(data), {'id', 'created_at', 'recipient_id', 'role'})
        self.assertEqual(data['role'], 'advisor')
        self.assertNotIn('SECRET', str(data))
        self.client.credentials(
            HTTP_AUTHORIZATION='Bearer '
            + bridge_ticket('reminder_eligible', event=event.pk, user=31)
        )
        path = url + f'{event.pk}/31/'
        self.assertTrue(self.client.get(path).data['eligible'])
        Appointment.objects.update(status='cancelled')
        self.assertFalse(self.client.get(path).data['eligible'])

    def test_generation_failure_rolls_back_event(self):
        self.overdue()
        with patch(
            'apps.assurance.backend.crm.reminders.ReminderEvent.objects.get_or_create',
            side_effect=RuntimeError('storage'),
        ):
            with self.assertRaises(RuntimeError):
                generate()
        self.assertFalse(ReminderEvent.objects.exists())


@skipUnless(connection.vendor == 'postgresql', 'Concurrent scheduling requires PostgreSQL')
@override_settings(DEBUG=True)
class ReminderConcurrencyTests(TransactionTestCase):
    def test_two_workers_create_one_current_period_reminder(self):
        source = fixture()
        source.report()
        FollowUpTask.objects.update(due_at=timezone.now() - timedelta(hours=1))

        def attempt(_):
            close_old_connections()
            try:
                return generate()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(sum(row['created'] for row in results), 1)
        self.assertEqual(ReminderEvent.objects.count(), 1)
