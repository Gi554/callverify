import csv
from datetime import datetime
from io import BytesIO, StringIO
from uuid import uuid4
from openpyxl import load_workbook
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import Prospect, ProspectActivity, AuditEvent
from .isolation_followups import RESULTS
from .test_isolation_work import fixture


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class IsolationExportTests(TestCase):
    def setUp(self):
        self.row = fixture()
        self.row.assigned_setter_id = 21
        self.row.assigned_setter_name = 'setter.demo01'
        self.row.reference = 'ISO-1'
        self.row.save()
        self.other = Prospect.objects.create(
            campaign=self.row.campaign, name='-1+cmd', raw_phone='+1 (416) 555-0199'
        )
        self.client = APIClient()
        self.url = '/api/work-queue/export/'

    def auth(self, pk, role, space='isolation'):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, space, role))

    def csv_rows(self, query=None):
        response = self.client.get(self.url, {'file': 'csv', **(query or {})})
        self.assertEqual(response.status_code, 200)
        self.assertIn('prospects-isolation-', response['Content-Disposition'])
        return list(csv.reader(StringIO(response.content.decode('utf-8')[1:]), delimiter=';'))

    def test_setter_cannot_export_any_prospect_file(self):
        self.auth(21, 'setter')
        for file in ('csv', 'xlsx', 'pdf'):
            self.assertEqual(self.client.get(self.url, {'file': file}).status_code, 403)

    def test_administrator_exports_team_with_filters(self):
        self.auth(91, 'administrator')
        rows = self.csv_rows()
        self.assertEqual([row[0] for row in rows[1:]], [str(self.other.pk), str(self.row.pk)])
        self.assertEqual(rows[1][2], "'-1+cmd")
        self.assertEqual(rows[1][3], '+1 (416) 555-0199')
        self.assertEqual(rows[1][6], 'Non affecté')
        self.assertEqual(len(self.csv_rows({'owner': 'unassigned'})), 2)
        response = self.client.get(self.url, {'file': 'xlsx', 'owner': '21'})
        sheet = load_workbook(BytesIO(response.content)).worksheets[0]
        self.assertEqual(sheet.max_row, 2)
        self.assertEqual(sheet['C2'].value, 'Prospect')

    def test_invalid_requests_are_refused(self):
        self.auth(91, 'administrator')
        self.assertEqual(self.client.get(self.url).status_code, 400)
        self.assertEqual(self.client.get(self.url, {'file': 'csv', 'owner': 'x'}).status_code, 400)
        self.auth(5, 'client')
        self.assertEqual(self.client.get(self.url, {'file': 'csv'}).status_code, 403)

    def activity(self, prospect, result, kind='call_result'):
        return ProspectActivity.objects.create(
            prospect=prospect,
            request_id=uuid4(),
            fingerprint='test',
            author_portal_id=21,
            author_role='setter',
            kind=kind,
            body='Commentaire conservé',
            changes={'result': result},
        )

    def test_filter_uses_latest_call_result_not_old_results_or_notes(self):
        self.auth(91, 'administrator')
        first = self.activity(self.row, 'invalid_number')
        last = self.activity(self.row, 'voicemail')
        # Equal timestamps must be resolved by activity id.
        ProspectActivity.objects.filter(pk=last.pk).update(created_at=first.created_at)
        self.activity(self.row, 'invalid_number', kind='note')
        self.activity(self.other, 'invalid_number')
        query = {'call_result': 'invalid_number', 'queue': 'all'}
        listed = self.client.get('/api/work-queue/', query)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([r['id'] for r in listed.data['results']], [self.other.pk])
        rows = self.csv_rows(query)
        self.assertEqual([r[0] for r in rows[1:]], [str(self.other.pk)])
        self.assertEqual(rows[0][-1], 'Dernier résultat d’appel')
        self.assertEqual(rows[1][-1], 'Numéro non attribué')
        audit = AuditEvent.objects.filter(action='isolation.prospects.exported').latest('pk')
        self.assertEqual(audit.metadata['filters']['call_result'], 'invalid_number')
        self.assertEqual(len(self.csv_rows({**query, 'owner': '21'})), 1)
        excel = self.client.get(self.url, {**query, 'file': 'xlsx'})
        self.assertEqual(excel.status_code, 200)
        sheet = load_workbook(BytesIO(excel.content)).worksheets[0]
        self.assertEqual(sheet.max_row, 2)
        self.assertEqual(sheet['A2'].value, self.other.pk)
        self.assertEqual(sheet['J2'].value, 'Numéro non attribué')
        pdf = self.client.get(self.url, {**query, 'file': 'pdf'})
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b'%PDF'))
        active = self.client.get('/api/work-queue/', {**query, 'queue': 'active'})
        self.assertEqual(active.data['count'], 0)
        self.assertEqual(ProspectActivity.objects.count(), 4)

    def test_every_supported_result_and_processed_files_can_be_exported(self):
        self.auth(91, 'administrator')
        for result, label in RESULTS.items():
            with self.subTest(result=result):
                self.activity(self.row, result)
                rows = self.csv_rows({'call_result': result, 'queue': 'all'})
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[1][0], str(self.row.pk))
                self.assertEqual(rows[1][-1], label)

    def test_latest_result_labels_match_list_drawer_and_export_without_resetting_status(self):
        self.auth(91, 'administrator')
        for result in ('invalid_number', 'disconnected'):
            with self.subTest(result=result):
                self.activity(self.row, result)
                self.activity(self.row, 'unrelated', kind='note')
                query = {'call_result': result, 'queue': 'all'}
                listed = self.client.get('/api/work-queue/', query)
                row = listed.data['results'][0]
                detail = self.client.get(f'/api/work-queue/{self.row.pk}/').data
                for value in (row, detail):
                    self.assertEqual(value['last_call_result'], result)
                    self.assertEqual(value['last_call_result_label'], RESULTS[result])
                self.assertEqual(self.csv_rows(query)[1][-1], RESULTS[result])
                self.row.refresh_from_db()
                self.assertEqual(self.row.commercial_status, 'to_contact')
        untouched = self.client.get(f'/api/work-queue/{self.other.pk}/').data
        self.assertIsNone(untouched['last_call_result'])
        self.assertEqual(untouched['last_call_result_label'], '')
        self.assertEqual(untouched['commercial_label'], 'À contacter')

    def test_result_filter_preserves_scope_and_rejects_unknown_values(self):
        self.activity(self.other, 'invalid_number')
        self.auth(21, 'setter')
        response = self.client.get('/api/work-queue/', {'call_result': 'invalid_number'})
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(
            self.client.get(self.url, {'file': 'csv', 'call_result': 'invalid_number'}).status_code,
            403,
        )
        self.auth(91, 'administrator')
        for url in ('/api/work-queue/', self.url):
            self.assertEqual(
                self.client.get(url, {'file': 'csv', 'call_result': 'unknown'}).status_code, 400
            )

    def test_export_contains_all_pages_once(self):
        self.auth(91, 'administrator')
        for i in range(27):
            prospect = Prospect.objects.create(campaign=self.row.campaign, name=f'Export {i}')
            self.activity(prospect, 'invalid_number')
        query = {'call_result': 'invalid_number', 'queue': 'all'}
        listed = self.client.get('/api/work-queue/', query)
        self.assertEqual(listed.data['count'], 27)
        self.assertEqual(len(listed.data['results']), 25)
        exported = self.csv_rows(query)
        self.assertEqual(len(exported), 28)
        self.assertEqual(len({r[0] for r in exported[1:]}), 27)

    def dated_result(self, prospect, result, stamp):
        activity = self.activity(prospect, result)
        ProspectActivity.objects.filter(pk=activity.pk).update(
            created_at=datetime.fromisoformat(stamp)
        )
        return activity

    def test_period_applies_to_latest_result_for_every_outcome(self):
        self.auth(91, 'administrator')
        period = {'queue': 'all', 'call_result_from': '2026-11-01', 'call_result_to': '2026-11-23'}
        for result in RESULTS:
            with self.subTest(result=result):
                ProspectActivity.objects.all().delete()
                self.dated_result(self.row, result, '2026-11-12T17:00:00+00:00')
                query = {**period, 'call_result': result}
                self.assertEqual(len(self.csv_rows(query)), 2)
                # A later result outside the requested period invalidates the old match.
                changed = 'voicemail' if result != 'voicemail' else 'appointment_booked'
                self.dated_result(self.row, changed, '2026-11-24T17:00:00+00:00')
                self.assertEqual(len(self.csv_rows(query)), 1)
                self.assertEqual(self.client.get('/api/work-queue/', query).data['count'], 0)
                # Even the same result repeated outside the period must not match the old one.
                self.dated_result(self.row, result, '2026-11-25T17:00:00+00:00')
                self.assertEqual(len(self.csv_rows(query)), 1)

    def test_quebec_period_includes_full_day_and_dst_transition(self):
        self.auth(91, 'administrator')
        # Montreal's 1 November 2026 is 25 hours long (UTC-4 becomes UTC-5).
        cases = [
            ('2026-11-01T03:59:59+00:00', False),
            ('2026-11-01T04:00:00+00:00', True),
            ('2026-11-02T04:59:59.999999+00:00', True),
            ('2026-11-02T05:00:00+00:00', False),
        ]
        expected = set()
        for stamp, included in cases:
            row = Prospect.objects.create(campaign=self.row.campaign, name=stamp)
            self.dated_result(row, 'voicemail', stamp)
            if included:
                expected.add(row.pk)
        query = {
            'queue': 'all',
            'call_result': 'voicemail',
            'call_result_from': '2026-11-01',
            'call_result_to': '2026-11-01',
        }
        listed = self.client.get('/api/work-queue/', query)
        self.assertEqual({row['id'] for row in listed.data['results']}, expected)
        self.assertEqual({int(row[0]) for row in self.csv_rows(query)[1:]}, expected)
        audit = AuditEvent.objects.filter(action='isolation.prospects.exported').latest('pk')
        self.assertEqual(audit.metadata['filters']['call_result_from'], '2026-11-01')
        self.assertEqual(audit.metadata['filters']['call_result_to'], '2026-11-01')
        excel = self.client.get(self.url, {**query, 'file': 'xlsx'})
        sheet = load_workbook(BytesIO(excel.content)).worksheets[0]
        self.assertEqual({row[0].value for row in list(sheet.rows)[1:]}, expected)

    def test_period_can_have_one_bound_and_excludes_files_without_results(self):
        self.auth(91, 'administrator')
        self.dated_result(self.row, 'invalid_number', '2026-11-12T17:00:00+00:00')
        for bounds in (
            {'call_result_from': '2026-11-12'},
            {'call_result_to': '2026-11-12'},
        ):
            rows = self.csv_rows({'queue': 'all', **bounds})
            self.assertEqual([row[0] for row in rows[1:]], [str(self.row.pk)])

    def test_invalid_period_is_rejected_in_listing_and_export(self):
        self.auth(91, 'administrator')
        for period in (
            {'call_result_from': 'yesterday'},
            {'call_result_to': '2026-02-30'},
            {'call_result_to': '9999-12-31'},
            {'call_result_from': '20261101'},
            {'call_result_from': '2026-11-23', 'call_result_to': '2026-11-01'},
        ):
            for path in ('/api/work-queue/', self.url):
                with self.subTest(path=path, period=period):
                    response = self.client.get(path, {'file': 'csv', **period})
                    self.assertEqual(response.status_code, 400)
