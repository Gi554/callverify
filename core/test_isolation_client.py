from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import Prospect, IsolationVisit, IsolationVisitResult, AuditEvent, AdminUser
from .test_isolation_activity import assigned_fixture


def client_fixture():
    prospect = assigned_fixture()
    visit = IsolationVisit.objects.create(
        prospect=prospect,
        request_id=uuid4(),
        fingerprint='test',
        client_id=72,
        client_name='Client',
        setter_id=21,
        setter_name='Setter Isolation',
        booked_by_id=91,
        starts_at=timezone.now() - timedelta(hours=2),
        ends_at=timezone.now() - timedelta(hours=1),
        timezone='UTC',
    )
    return prospect, visit


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class IsolationClientTests(TestCase):
    def setUp(self):
        self.prospect, self.visit = client_fixture()
        self.client = APIClient()
        self.auth(72, 'client')
        self.url = f'/api/visits/{self.visit.pk}/'

    def auth(self, pk, role, workspace='isolation'):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, workspace, role))

    def payload(self, **changes):
        return {
            'revision': 0,
            'performed': True,
            'outcome': 'interested',
            'note': 'Visite effectuÃƒÆ’Ã‚Â©e, prospect intÃƒÆ’Ã‚Â©ressÃƒÆ’Ã‚Â©',
            **changes,
        }

    def report(self, **changes):
        return self.client.post(self.url + 'result/', self.payload(**changes), format='json')

    def test_client_visits_and_prospect_allowlist_are_scoped(self):
        other = Prospect.objects.create(
            campaign=self.prospect.campaign,
            raw_phone='secret',
            name='Hors pÃƒÆ’Ã‚Â©rimÃƒÆ’Ã‚Â¨tre',
            assigned_setter_id=22,
        )
        foreign = IsolationVisit.objects.create(
            prospect=other,
            request_id=uuid4(),
            fingerprint='other',
            client_id=73,
            client_name='Autre client',
            setter_id=22,
            setter_name='Autre setter',
            booked_by_id=22,
            starts_at=self.visit.starts_at,
            ends_at=self.visit.ends_at,
            timezone='UTC',
        )
        data = self.client.get('/api/visits/').data
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['original_setter']['name'], 'Setter Isolation')
        self.assertEqual(self.client.get(f'/api/visits/{foreign.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/visits/{foreign.pk}/result/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/client-prospects/{other.pk}/').status_code, 404)
        row = self.client.get(f'/api/client-prospects/{self.prospect.pk}/').data
        self.assertEqual(set(row), {'id', 'name', 'reference', 'raw_phone'})
        self.assertEqual(self.client.get('/api/client-prospects/?search=Hors').data['count'], 0)
        self.assertEqual(AdminUser.objects.count(), 1)

    def test_upcoming_calendar_filter_is_bounded_and_owner_scoped(self):
        self.assertEqual(self.client.get('/api/visits/?period=upcoming').data['count'], 0)
        IsolationVisit.objects.filter(pk=self.visit.pk).update(
            starts_at=timezone.now() + timedelta(hours=1),
            ends_at=timezone.now() + timedelta(hours=2),
        )
        self.assertEqual(self.client.get('/api/visits/?period=upcoming').data['count'], 1)
        self.auth(73, 'client')
        self.assertEqual(self.client.get('/api/visits/?period=upcoming').data['count'], 0)
        self.assertEqual(self.client.get('/api/visits/?period=all').status_code, 400)

    def test_results_due_persist_after_read_and_clear_only_on_report(self):
        self.assertEqual(self.client.get('/api/client-dashboard/').data['results_due'], 1)
        self.assertIsNone(self.client.get(self.url + 'result/').data)
        self.assertEqual(self.client.get('/api/visits/?result_due=true').data['count'], 1)
        self.assertEqual(self.client.get('/api/client-dashboard/').data['results_due'], 1)
        self.assertEqual(self.report().status_code, 201)
        # Legacy attendance-only reports still need the separate sales answer.
        self.assertEqual(self.client.get('/api/client-dashboard/').data['results_due'], 1)
        self.visit.refresh_from_db()
        self.assertEqual(
            self.report(
                closed=False,
                revision=self.visit.revision,
                reason='ComplÃƒÂ©ter le rÃƒÂ©sultat commercial',
            ).status_code,
            201,
        )
        result = self.client.get('/api/client-dashboard/').data
        self.assertEqual(result['results_due'], 0)
        self.assertEqual(result['reported'], 1)
        self.assertEqual(self.client.get('/api/visits/?result_due=true').data['count'], 0)

    def test_immutable_report_retry_and_audit(self):
        self.assertEqual(self.report().status_code, 201)
        self.assertEqual(self.report().status_code, 200)
        self.assertEqual(self.report(note='Remplacer').status_code, 409)
        self.assertEqual(IsolationVisitResult.objects.count(), 1)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.revision, 1)
        record = IsolationVisitResult.objects.get()
        self.assertEqual(record.author_client_id, 72)
        audit = AuditEvent.objects.get(action='isolation.visit.result_recorded')
        self.assertEqual(audit.metadata['actor_portal_id'], 72)
        self.assertEqual(
            self.client.patch(self.url + 'result/', self.payload(), format='json').status_code, 405
        )

    def test_only_own_client_reports_staff_supervise_and_assurance_is_denied(self):
        self.auth(73, 'client')
        self.assertEqual(self.report().status_code, 404)
        self.auth(21, 'setter')
        self.assertEqual(self.report().status_code, 403)
        self.auth(91, 'administrator')
        self.assertEqual(self.report().status_code, 403)
        self.auth(72, 'client')
        self.report()
        for pk, role in ((21, 'setter'), (91, 'administrator')):
            self.auth(pk, role)
            self.assertEqual(self.client.get(self.url + 'result/').data['outcome'], 'interested')
        self.auth(21, 'advisor', 'assurance')
        self.assertEqual(self.client.get(self.url + 'result/').status_code, 401)

    def test_client_cannot_access_work_queue_or_modify_visits(self):
        for url in ['/api/work-queue/', '/api/workspace-dashboard/', self.url + 'history/']:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        for suffix in ('reschedule/', 'cancel/'):
            self.assertEqual(
                self.client.post(self.url + suffix, {}, format='json').status_code, 403
            )
        self.assertEqual(self.client.post('/api/visits/', {}, format='json').status_code, 403)
        for url in ('/api/campaigns/', '/api/lookups/', '/api/exports/', '/api/audit/'):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_future_cancelled_stale_and_inconsistent_reports_are_refused(self):
        for changes in (
            {'performed': False},
            {'outcome': 'not_performed'},
            {'outcome': 'sale'},
            {'author_client_id': 73},
        ):
            self.assertEqual(self.report(**changes).status_code, 400, changes)
        self.assertEqual(self.report(revision=9).status_code, 409)
        IsolationVisit.objects.filter(pk=self.visit.pk).update(
            ends_at=timezone.now() + timedelta(hours=1)
        )
        self.assertEqual(self.report().status_code, 409)
        IsolationVisit.objects.filter(pk=self.visit.pk).update(
            ends_at=timezone.now() - timedelta(hours=1), status='cancelled'
        )
        self.assertEqual(self.report(performed=False, outcome='not_performed').status_code, 409)
        self.assertEqual(IsolationVisitResult.objects.count(), 0)

    def test_negative_result_is_explicit_not_a_technical_line_change(self):
        self.assertEqual(
            self.report(performed=False, outcome='not_performed', note='Client absent').status_code,
            201,
        )
        self.prospect.refresh_from_db()
        self.assertEqual(self.prospect.phone.line_status, 'unknown')
        self.assertEqual(self.prospect.commercial_status, 'to_contact')
        self.assertFalse(IsolationVisitResult.objects.get().performed)

    def test_audit_failure_rolls_back_result_and_revision(self):
        with patch(
            'core.isolation_client.AuditEvent.objects.create', side_effect=RuntimeError('audit')
        ):
            with self.assertRaises(RuntimeError):
                self.report()
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.revision, 0)
        self.assertEqual(IsolationVisitResult.objects.count(), 0)

    def test_prospect_transfer_preserves_client_result_access(self):
        self.report()
        Prospect.objects.filter(pk=self.prospect.pk).update(
            assigned_setter_id=22, assigned_setter_name='Autre'
        )
        self.assertEqual(self.client.get(self.url + 'result/').status_code, 200)
        self.auth(21, 'setter')
        self.assertEqual(self.client.get(self.url + 'result/').status_code, 404)
        self.auth(22, 'setter')
        self.assertEqual(self.client.get(self.url + 'result/').status_code, 200)

    def test_reported_visit_cannot_be_rescheduled_even_if_dates_are_changed(self):
        self.report()
        IsolationVisit.objects.filter(pk=self.visit.pk).update(
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=1),
        )
        self.auth(91, 'administrator')
        self.assertEqual(
            self.client.post(
                self.url + 'cancel/',
                {'revision': 1, 'reason': 'Effacer le rÃƒÆ’Ã‚Â©sultat'},
                format='json',
            ).status_code,
            409,
        )


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class IsolationClientConcurrencyTests(TransactionTestCase):
    def setUp(self):
        from django.db import connection

        if connection.vendor != 'postgresql':
            self.skipTest('Concurrence dans CI PostgreSQL')
        self.prospect, self.visit = client_fixture()

    def race(self, payloads):
        from django.db import connections
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        barrier = Barrier(2)

        def submit(payload):
            try:
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(72, 'isolation', 'client'))
                barrier.wait(timeout=10)
                return client.post(
                    f'/api/visits/{self.visit.pk}/result/', payload, format='json'
                ).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(submit, payloads))

    def test_identical_concurrent_results_are_idempotent(self):
        payload = {
            'revision': 0,
            'performed': True,
            'outcome': 'completed',
            'note': 'EffectuÃƒÆ’Ã‚Â©e',
        }
        self.assertEqual(sorted(self.race([payload, payload])), [200, 201])
        self.assertEqual(IsolationVisitResult.objects.count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(action='isolation.visit.result_recorded').count(), 1
        )

    def test_different_concurrent_results_cannot_overwrite(self):
        first = {
            'revision': 0,
            'performed': True,
            'outcome': 'interested',
            'note': 'IntÃƒÆ’Ã‚Â©ressÃƒÆ’Ã‚Â©',
        }
        second = {'revision': 0, 'performed': False, 'outcome': 'not_performed', 'note': 'Absent'}
        self.assertEqual(sorted(self.race([first, second])), [201, 409])
        self.assertEqual(IsolationVisitResult.objects.count(), 1)
