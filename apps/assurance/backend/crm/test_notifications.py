from uuid import uuid4
from unittest.mock import patch
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.db import connection, close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from packages.access.followups import issue_owner
from .models import (
    TaskNotification,
    TaskNotificationRead,
    FollowUpTask,
    BusinessAudit,
    AppointmentReport,
    AppointmentIncident,
)
from .tests import ReportTests


def fixture():
    test = ReportTests(
        methodName='test_negative_report_creates_one_task_for_original_setter_and_retry_is_idempotent'
    )
    test.setUp()
    return test


@override_settings(DEBUG=True)
class NotificationTests(TestCase):
    def setUp(self):
        self.source = fixture()
        self.source.report()
        self.task = FollowUpTask.objects.get()
        self.notice = TaskNotification.objects.get()
        self.client = APIClient()
        self.auth(21, 'setter')
        self.url = '/api/assurance/notifications/'

    def auth(self, pk, role, workspace='assurance'):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, workspace, role))

    def read(self, **body):
        return self.client.post(f'{self.url}{self.notice.pk}/read/?state=all', body, format='json')

    def summary(self):
        return self.client.get(self.url + 'summary/').data

    def test_notification_is_atomic_idempotent_and_safe_for_advisor(self):
        self.assertEqual(self.source.report().status_code, 200)
        self.assertEqual(TaskNotification.objects.count(), 1)
        self.auth(31, 'advisor')
        for path in (self.url, self.url + 'summary/'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 403)
            self.assertNotIn('SECRET', str(response.data))
        self.assertEqual(self.read().status_code, 403)
        self.auth(21, 'setter', 'isolation')
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_read_is_persistent_idempotent_and_never_closes_task(self):
        self.assertEqual(self.summary(), {'open': 1, 'unread_open': 1})
        first = self.read()
        self.assertEqual(first.status_code, 200)
        second = self.read()
        self.assertEqual(first.data['read_at'], second.data['read_at'])
        self.assertEqual(self.summary(), {'open': 1, 'unread_open': 0})
        self.task.refresh_from_db()
        self.assertIsNone(self.task.closed_at)
        self.assertEqual(self.task.revision, 0)
        self.assertEqual(TaskNotificationRead.objects.count(), 1)
        self.assertEqual(
            BusinessAudit.objects.filter(action='appointment.notification_read').count(), 1
        )
        self.client = APIClient()
        self.auth(21, 'setter')
        self.assertEqual(self.summary()['open'], 1)
        self.assertIsNotNone(self.client.get(self.url).data['results'][0]['read_at'])
        self.assertEqual(self.read(user_id=22).status_code, 400)

    def test_read_state_is_per_user_and_moves_with_task_ownership(self):
        self.auth(99, 'administrator')
        self.read()
        self.assertEqual(self.summary()['unread_open'], 0)
        self.auth(21, 'setter')
        self.assertEqual(self.summary()['unread_open'], 1)
        self.read()
        self.auth(99, 'administrator')
        response = self.client.post(
            f'/api/assurance/follow-ups/{self.task.pk}/reassign/',
            {
                'revision': 0,
                'proof': issue_owner(99, self.task.pk, 22, 'New setter'),
                'reason': 'Répartition',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.auth(21, 'setter')
        self.assertEqual(self.summary()['open'], 0)
        self.assertEqual(self.read().status_code, 404)
        self.auth(22, 'setter')
        self.assertEqual(self.summary()['unread_open'], 1)
        row = self.client.get(self.url).data['results'][0]
        self.assertNotIn('setter', str(row))
        self.assertNotIn('SECRET', str(row))

    def test_close_and_reopen_change_alert_not_read_history(self):
        self.read()
        response = self.client.post(
            f'/api/assurance/follow-ups/{self.task.pk}/close/',
            {'revision': 0, 'resolution': 'Traitement terminé'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.summary()['open'], 0)
        self.assertEqual(self.client.get(self.url + '?state=resolved').data['count'], 1)
        self.auth(99, 'administrator')
        response = self.client.post(
            f'/api/assurance/follow-ups/{self.task.pk}/reopen/?state=all',
            {
                'revision': 1,
                'priority': 'high',
                'due_at': (timezone.now() + timedelta(days=1)).isoformat(),
                'reason': 'Nouveau suivi',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.auth(21, 'setter')
        self.assertEqual(self.summary(), {'open': 1, 'unread_open': 0})

    def test_each_new_incident_notifies_once_without_duplicate_task(self):
        self.read()
        url = f'/api/assurance/appointments/{self.task.appointment_id}/incidents/'
        body = {'request_id': str(uuid4()), 'note': 'Problème complémentaire'}
        self.assertEqual(self.source.client.post(url, body, format='json').status_code, 201)
        self.assertEqual(self.source.client.post(url, body, format='json').status_code, 200)
        self.assertEqual(TaskNotification.objects.count(), 2)
        self.assertEqual(FollowUpTask.objects.count(), 1)
        self.assertEqual(self.summary(), {'open': 2, 'unread_open': 1})
        self.assertEqual(self.client.get(self.url + '?unread=true').data['count'], 1)

    def test_pagination_validation_and_allowlist(self):
        for index in range(27):
            TaskNotification.objects.create(
                task=self.task, event_key=f'test:{index}', kind='incident'
            )
        response = self.client.get(self.url)
        self.assertEqual(response.data['count'], 28)
        self.assertEqual(len(response.data['results']), 25)
        self.assertEqual(len(self.client.get(self.url + '?page=2').data['results']), 3)
        self.assertEqual(
            set(response.data['results'][0]),
            {
                'id',
                'task_id',
                'kind',
                'label',
                'created_at',
                'read_at',
                'resolved',
                'priority',
                'due_at',
            },
        )
        self.assertEqual(response['Cache-Control'], 'no-store')
        for query in ('state=bad', 'unread=bad'):
            self.assertEqual(self.client.get(self.url + '?' + query).status_code, 400)

    def test_notification_or_read_audit_failure_roll_back(self):
        with patch(
            'apps.assurance.backend.crm.notifications.BusinessAudit.objects.create',
            side_effect=RuntimeError('audit'),
        ):
            with self.assertRaises(RuntimeError):
                self.read()
        self.assertEqual(TaskNotificationRead.objects.count(), 0)
        with patch(
            'apps.assurance.backend.crm.reports.notify', side_effect=RuntimeError('storage')
        ):
            with self.assertRaises(RuntimeError):
                self.source.client.post(
                    f'/api/assurance/appointments/{self.task.appointment_id}/incidents/',
                    {'request_id': str(uuid4()), 'note': 'Test'},
                    format='json',
                )
        self.assertEqual(AppointmentIncident.objects.count(), 0)
        self.task.refresh_from_db()
        self.assertEqual(self.task.revision, 0)
        from .models import Appointment

        other = Appointment.objects.get(pk=self.task.appointment_id)
        other.pk = None
        other.request_id = uuid4()
        other.save()
        self.source.url = f'/api/assurance/appointments/{other.pk}/report/'
        with patch(
            'apps.assurance.backend.crm.reports.notify', side_effect=RuntimeError('storage')
        ):
            with self.assertRaises(RuntimeError):
                self.source.report()
        self.assertEqual(AppointmentReport.objects.count(), 1)
        self.assertEqual(FollowUpTask.objects.count(), 1)

    def test_existing_open_tasks_are_backfilled_once(self):
        import importlib
        from types import SimpleNamespace
        from django.apps import apps

        migration = importlib.import_module(
            'apps.assurance.backend.crm.migrations.0016_existing_task_notifications'
        )
        TaskNotification.objects.all().delete()
        editor = SimpleNamespace(connection=SimpleNamespace(alias='default'))
        migration.populate(apps, editor)
        migration.populate(apps, editor)
        self.assertEqual(TaskNotification.objects.count(), 1)
        self.assertEqual(TaskNotification.objects.get().kind, 'existing')
        TaskNotification.objects.all().delete()
        FollowUpTask.objects.update(closed_at=timezone.now())
        migration.populate(apps, editor)
        self.assertEqual(TaskNotification.objects.count(), 0)


@skipUnless(connection.vendor == 'postgresql', 'Concurrent receipt writes require PostgreSQL')
@override_settings(DEBUG=True)
class NotificationConcurrencyTests(TransactionTestCase):
    def test_concurrent_reads_create_one_receipt_and_one_audit(self):
        source = fixture()
        source.report()
        notice = TaskNotification.objects.get()

        def attempt(_):
            close_old_connections()
            try:
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(21, 'assurance', 'setter'))
                return client.post(
                    f'/api/assurance/notifications/{notice.pk}/read/', {}, format='json'
                ).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(results, [200, 200])
        self.assertEqual(TaskNotificationRead.objects.count(), 1)
        self.assertEqual(
            BusinessAudit.objects.filter(action='appointment.notification_read').count(), 1
        )
