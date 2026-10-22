from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import FollowUpTask, BusinessAudit, AppointmentReport


def closed_task_fixture():
    from .tests import ReportTests

    fixture = ReportTests(
        methodName='test_negative_report_creates_one_task_for_original_setter_and_retry_is_idempotent'
    )
    fixture.setUp()
    fixture.report()
    task = FollowUpTask.objects.get()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(21, 'assurance', 'setter'))
    url = f'/api/assurance/follow-ups/{task.pk}/'
    response = client.post(
        url + 'close/', {'revision': 0, 'resolution': 'Premier traitement terminé'}, format='json'
    )
    assert response.status_code == 200, response.data
    task.refresh_from_db()
    return client, task, url


@override_settings(DEBUG=True)
class TaskReopeningTests(TestCase):
    def setUp(self):
        self.client, self.task, self.url = closed_task_fixture()
        self.auth(99, 'administrator')

    def auth(self, pk, role):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, 'assurance', role))

    def payload(self, **changes):
        return {
            'revision': 1,
            'priority': 'high',
            'due_at': (timezone.now() + timedelta(days=2)).isoformat(),
            'reason': 'Suivi à reprendre après contrôle',
            **changes,
        }

    def reopen(self, **changes):
        return self.client.post(
            self.url + 'reopen/?state=all', self.payload(**changes), format='json'
        )

    def test_reopen_preserves_closure_in_audit_and_restores_setter_alert(self):
        closed_at = self.task.closed_at
        response = self.reopen()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['revision'], 2)
        self.assertIsNone(response.data['closed_at'])
        self.assertEqual(response.data['resolution'], '')
        self.assertEqual(response.data['priority'], 'high')
        self.task.refresh_from_db()
        self.assertIsNone(self.task.closed_by_id)
        self.assertEqual(self.task.setter_id, 21)
        self.assertEqual(FollowUpTask.objects.count(), 1)
        self.assertFalse(AppointmentReport.objects.get().performed)
        rows = self.client.get(self.url + 'history/?state=all').data['results']
        entry = next(row for row in rows if row['action'] == 'appointment.follow_up_reopened')
        self.assertEqual(entry['actor_id'], 99)
        self.assertEqual(entry['metadata']['before']['resolution'], 'Premier traitement terminé')
        self.assertEqual(entry['metadata']['before']['closed_by_id'], 21)
        self.assertEqual(entry['metadata']['before']['closed_at'], closed_at.isoformat())
        self.auth(21, 'setter')
        self.assertEqual(self.client.get('/api/assurance/dashboard/').data['open_follow_ups'], 1)
        self.assertEqual(self.client.get('/api/assurance/follow-ups/?state=open').data['count'], 1)
        self.assertEqual(
            self.client.get('/api/assurance/follow-ups/?state=closed').data['count'], 0
        )
        self.client.get(self.url)
        self.assertEqual(self.client.get('/api/assurance/dashboard/').data['open_follow_ups'], 1)

    def test_admin_only_and_private_history(self):
        for pk, role in ((21, 'setter'), (22, 'setter'), (31, 'advisor')):
            self.auth(pk, role)
            self.assertEqual(self.reopen().status_code, 403)
            self.assertEqual(self.client.get(self.url + 'history/?state=all').status_code, 403)
        self.client.credentials()
        self.assertEqual(self.reopen().status_code, 401)
        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.closed_at)

    def test_invalid_reason_deadline_priority_and_extra_fields(self):
        for changes in (
            {'reason': ' '},
            {'due_at': '2020-01-01T00:00:00Z'},
            {'due_at': '2030-01-01T00:00:00'},
            {'priority': 'invalid'},
            {'setter_id': 22},
        ):
            self.assertEqual(self.reopen(**changes).status_code, 400, changes)
        self.task.refresh_from_db()
        self.assertEqual(self.task.revision, 1)
        self.assertIsNotNone(self.task.closed_at)

    def test_stale_repeated_and_open_task_requests_do_not_overwrite(self):
        self.assertEqual(self.reopen(revision=0).status_code, 409)
        self.assertEqual(self.reopen().status_code, 200)
        self.assertEqual(self.reopen().status_code, 409)
        self.assertEqual(self.reopen(revision=2).status_code, 409)
        self.assertEqual(
            BusinessAudit.objects.filter(action='appointment.follow_up_reopened').count(), 1
        )

    def test_stale_close_cannot_erase_reopened_task_and_new_close_is_audited(self):
        self.reopen()
        self.auth(21, 'setter')
        self.assertEqual(
            self.client.post(
                self.url + 'close/',
                {'revision': 1, 'resolution': 'Ancien formulaire'},
                format='json',
            ).status_code,
            409,
        )
        response = self.client.post(
            self.url + 'close/',
            {'revision': 2, 'resolution': 'Second traitement terminé'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['revision'], 3)
        self.assertEqual(
            BusinessAudit.objects.filter(action='appointment.follow_up_closed').count(), 2
        )

    def test_failed_audit_rolls_back_reopening(self):
        with patch(
            'apps.assurance.backend.crm.reports.BusinessAudit.objects.create',
            side_effect=RuntimeError('audit'),
        ):
            with self.assertRaises(RuntimeError):
                self.reopen()
        self.task.refresh_from_db()
        self.assertEqual(self.task.revision, 1)
        self.assertEqual(self.task.resolution, 'Premier traitement terminé')
        self.assertIsNotNone(self.task.closed_at)


@override_settings(DEBUG=True)
class ConcurrentTaskReopeningTests(TransactionTestCase):
    def test_two_admins_reopen_only_once(self):
        from django.db import connection, connections
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        if connection.vendor != 'postgresql':
            self.skipTest('Concurrence vérifiée dans la CI PostgreSQL')
        _, task, url = closed_task_fixture()
        barrier = Barrier(2)
        payload = {
            'revision': 1,
            'priority': 'high',
            'due_at': (timezone.now() + timedelta(days=1)).isoformat(),
            'reason': 'Reprise administrative',
        }

        def reopen(actor):
            try:
                client = APIClient()
                client.credentials(
                    HTTP_AUTHORIZATION='Bearer ' + issue(actor, 'assurance', 'administrator')
                )
                barrier.wait(timeout=10)
                return client.post(url + 'reopen/?state=all', payload, format='json').status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reopen, [98, 99]))
        self.assertEqual(sorted(results), [200, 409])
        task.refresh_from_db()
        self.assertEqual(task.revision, 2)
        self.assertEqual(
            BusinessAudit.objects.filter(action='appointment.follow_up_reopened').count(), 1
        )
