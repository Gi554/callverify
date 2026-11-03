from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, override_settings
from django.db import connection, close_old_connections
from openpyxl import load_workbook
from rest_framework.test import APIClient
from .models import Membership, ReportPlan, GeneratedReport, AccessAudit
from .generated_reports import schedule, claim, generate


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class ReportTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('reports-admin')
        self.setter = get_user_model().objects.create_user('reports-setter')
        Membership.objects.create(user=self.admin, workspace='assurance', role='administrator')
        Membership.objects.create(user=self.setter, workspace='assurance', role='setter')
        self.client = APIClient()
        self.client.force_login(self.admin)
        self.url = '/api/portal/assurance/reports/'
        self.body = {
            'request_id': str(uuid4()),
            'kind': 'performance',
            'starts_on': '2026-10-26',
            'ends_on': '2026-11-01',
        }

    def request_job(self):
        response = self.client.post(self.url, self.body, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return GeneratedReport.objects.get(pk=response.data['id'])

    def sample(self, job):
        return {
            'workspace': job.workspace,
            'kind': job.kind,
            'from': str(job.starts_on),
            'to': str(job.ends_on),
            'headers': ['Setter', 'Tenus'],
            'rows': [['=Texte fourni', '3']],
            'definition': 'Données fictives. Heure du Québec.',
        }

    def test_plan_revision_and_workspace_permissions(self):
        url = '/api/portal/assurance/report-plan/'
        self.assertFalse(self.client.get(url).data['enabled'])
        first = self.client.post(url, {'enabled': True, 'hour': 19, 'revision': 0}, format='json')
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(
            self.client.post(
                url, {'enabled': False, 'hour': 19, 'revision': 0}, format='json'
            ).status_code,
            400,
        )
        self.client.force_login(self.setter)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/api/portal/isolation/reports/').status_code, 403)

    def test_schedule_is_idempotent_and_handles_previous_week_across_dst(self):
        ReportPlan.objects.create(
            workspace='assurance', enabled=True, hour=19, actor_id=self.admin.pk
        )
        now = datetime(2026, 11, 2, 19, 0, tzinfo=ZoneInfo('America/Toronto'))
        self.assertEqual(schedule(now), 4)
        self.assertEqual(schedule(now), 0)
        week = GeneratedReport.objects.get(cadence='weekly', kind='performance')
        self.assertEqual(str(week.starts_on), '2026-10-26')
        self.assertEqual(str(week.ends_on), '2026-11-01')
        self.assertEqual(AccessAudit.objects.filter(action='report.requested').count(), 4)
        self.assertEqual(
            schedule(datetime(2026, 12, 1, 18, 0, tzinfo=ZoneInfo('America/Toronto'))), 0
        )
        self.assertEqual(
            schedule(datetime(2026, 12, 1, 19, 0, tzinfo=ZoneInfo('America/Toronto'))), 4
        )

    def test_manual_idempotency_frozen_files_and_download_scope(self):
        job = self.request_job()
        self.assertEqual(self.client.post(self.url, self.body, format='json').status_code, 200)
        self.assertEqual(GeneratedReport.objects.count(), 1)
        claimed = claim()
        with patch(
            'portal.backend.identity.generated_reports.snapshot', side_effect=self.sample
        ) as capture:
            self.assertTrue(generate(claimed))
            self.assertFalse(generate(claimed))
            self.assertEqual(capture.call_count, 1)
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded')
        self.assertTrue(bytes(job.pdf_data).startswith(b'%PDF-'))
        book = load_workbook(BytesIO(bytes(job.xlsx_data)))
        self.assertEqual(book.active['A7'].data_type, 's')
        self.assertEqual(book.active['B7'].value, '3')
        path = f'{self.url}{job.pk}/download/pdf/'
        self.assertEqual(self.client.get(path).status_code, 200)
        excel = self.client.get(f'{self.url}{job.pk}/download/xlsx/')
        self.assertEqual(
            excel['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertEqual(
            self.client.get(f'/api/portal/isolation/reports/{job.pk}/download/pdf/').status_code,
            403,
        )
        events = self.client.get(f'{self.url}{job.pk}/history/').data['results']
        self.assertEqual(len(events), 5)
        self.client.force_login(self.setter)
        self.assertEqual(self.client.get(path).status_code, 403)

    def test_failed_generation_preserves_snapshot_and_retries_do_not_recapture(self):
        self.request_job()
        job = claim()
        with (
            patch('portal.backend.identity.generated_reports.snapshot', side_effect=self.sample),
            patch(
                'portal.backend.identity.generated_reports.document',
                side_effect=ValueError('secret must not escape'),
            ),
        ):
            self.assertFalse(generate(job))
        job.refresh_from_db()
        self.assertEqual(job.error_code, 'generation_failed')
        self.assertTrue(job.snapshot)
        GeneratedReport.objects.filter(pk=job.pk).update(
            retry_at=datetime(2020, 1, 1, tzinfo=ZoneInfo('UTC'))
        )
        retry = claim()
        with patch(
            'portal.backend.identity.generated_reports.snapshot',
            side_effect=AssertionError('frozen snapshot expected'),
        ):
            self.assertTrue(generate(retry))

    def test_expired_last_lease_fails_visibly_and_revocation_stops_generation(self):
        job = self.request_job()
        GeneratedReport.objects.filter(pk=job.pk).update(
            state='running', attempts=3, lease_until=datetime(2020, 1, 1, tzinfo=ZoneInfo('UTC'))
        )
        self.assertIsNone(claim())
        job.refresh_from_db()
        self.assertEqual(job.error_code, 'attempts_exhausted')
        GeneratedReport.objects.filter(pk=job.pk).update(state='queued', attempts=0)
        job = claim()
        Membership.objects.filter(user=self.admin).update(active=False)
        with patch('portal.backend.identity.generated_reports.snapshot') as source:
            self.assertFalse(generate(job))
            source.assert_not_called()

    def test_snapshot_uses_period_gains_and_real_call_states_without_claiming_reached(self):
        from .report_sources import snapshot
        from .models import PhoneCallAttempt

        self.body['kind'] = 'performance'
        job = self.request_job()
        call = PhoneCallAttempt.objects.create(
            request_id=uuid4(),
            user=self.setter,
            workspace='assurance',
            contact_id=42,
            extension='501',
            fingerprint='test',
            state='accepted',
        )
        PhoneCallAttempt.objects.filter(pk=call.pk).update(
            created_at=datetime(2026, 11, 1, 23, 59, tzinfo=ZoneInfo('America/Toronto'))
        )
        totals = {
            'appointments': 20,
            'performed': 15,
            'closed': 5,
            'not_closed': 10,
            'not_performed': 5,
            'updates_due': 0,
        }
        stats = {
            'from': '2026-10-26',
            'to': '2026-11-01',
            'timezone': 'America/Toronto',
            'totals': totals,
            'setters': {
                'count': 1,
                'results': [{'setter_id': self.setter.pk, 'setter_name': 'Setter', **totals}],
            },
        }

        def source(workspace, actor, path, params):
            self.assertEqual(workspace, 'assurance')
            self.assertEqual(actor, self.admin.pk)
            self.assertNotEqual(path, 'payroll/')
            return stats

        with patch('portal.backend.identity.report_sources.business', side_effect=source):
            data = snapshot(job)
            row = dict(zip(data['headers'], data['rows'][0]))
            self.assertEqual(row['Acceptés par le poste'], 1)
            self.assertEqual(row['Prospects joints'], 'Non disponible')
            self.assertFalse([name for name in data['headers'] if 'CAD' in name or 'Gains' in name])

    def test_campaign_report_filters_each_campaign_and_retains_the_whole_space_total(self):
        from .report_sources import snapshot

        self.body['kind'] = 'campaigns'
        job = self.request_job()
        counts = {
            'appointments': 20,
            'performed': 15,
            'closed': 5,
            'not_closed': 10,
            'not_performed': 5,
            'updates_due': 0,
        }
        result = {
            'from': '2026-10-26',
            'to': '2026-11-01',
            'timezone': 'America/Toronto',
            'totals': counts,
            'filter_options': {'campaign_id': [{'id': 8, 'name': 'Lot test'}]},
        }
        with patch(
            'portal.backend.identity.report_sources.business', return_value=result
        ) as source:
            data = snapshot(job)
            self.assertEqual(len(data['rows']), 2)
            self.assertIn('sans campagne', data['rows'][0][1])
            self.assertEqual(source.call_args_list[1].args[3]['campaign_id'], 8)


@skipUnless(connection.vendor == 'postgresql', 'Verrouillage PostgreSQL requis')
@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class ReportConcurrencyTests(TransactionTestCase):
    setUp = ReportTests.setUp
    request_job = ReportTests.request_job

    def test_two_workers_cannot_claim_the_same_report(self):
        self.request_job()
        gate = Barrier(2)

        def run(_):
            close_old_connections()
            try:
                gate.wait(timeout=15)
                job = claim()
                return job.pk if job else None
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, [1, 2]))
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(GeneratedReport.objects.get().attempts, 1)
