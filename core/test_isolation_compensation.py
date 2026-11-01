import csv
import io
import json
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo
from django.test import TestCase, TransactionTestCase, override_settings
from openpyxl import load_workbook
from packages.access.isolation_events import issue
from . import test_isolation_client as fixtures
from .models import IsolationSetterRate, IsolationVisit, IsolationVisitResult, AuditEvent
from .isolation_compensation import capture


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class CompensationTests(TestCase):
    auth = fixtures.IsolationClientTests.auth
    report = fixtures.IsolationClientTests.report
    payload = fixtures.IsolationClientTests.payload

    def setUp(self):
        fixtures.IsolationClientTests.setUp(self)
        self.day = self.visit.starts_at.astimezone(ZoneInfo('America/Toronto')).date()
        self.query = f'from={self.day}&to={self.day}'
        source = patch(
            'core.isolation_compensation_calls.load',
            side_effect=lambda actor, start, end: {
                'from': str(start),
                'to': str(end),
                'client': {'id': 72, 'name': 'Client'},
                'results': [
                    {
                        'user_id': 21,
                        'user__username': 'Setter',
                        'calls': 5,
                        'attempts': 6,
                        'uncertain': 1,
                    }
                ],
                'totals': {'calls': 5, 'attempts': 6, 'uncertain': 1},
            },
        )
        self.source = source.start()
        self.addCleanup(source.stop)

    def token(self, actor=90):
        return issue(
            'compensation_rate',
            actor=actor,
            setter={'id': 21, 'name': 'Setter'},
            client={'id': 72, 'name': 'Client'},
        )

    def rate(self, attendance='12.50', sale='40.00', revision=0):
        self.auth(90, 'administrator')
        return self.client.post(
            '/api/isolation-compensation/rates/',
            {
                'proof': self.token(),
                'attendance_cad': attendance,
                'sale_bonus_cad': sale,
                'revision': revision,
                'reason': 'Tarif de recette',
            },
            format='json',
        )

    def totals(self, query=None):
        self.auth(90, 'administrator')
        response = self.client.get('/api/isolation-compensation/?' + (query or self.query))
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['totals']

    def value(self, revision=1):
        self.auth(90, 'administrator')
        return self.client.post(
            '/api/isolation-compensation/value/',
            {
                'proof': self.token(),
                'rate_revision': revision,
                'starts_on': str(self.day),
                'ends_on': str(self.day),
                'reason': 'Valoriser les résultats sans prix',
            },
            format='json',
        )

    def another(self, **changes):
        data = {
            key: getattr(self.visit, key)
            for key in (
                'prospect_id',
                'client_id',
                'client_name',
                'setter_id',
                'setter_name',
                'booked_by_id',
                'starts_at',
                'ends_at',
                'timezone',
                'process_id',
            )
        }
        return IsolationVisit.objects.create(
            **(data | {'request_id': uuid4(), 'fingerprint': 'new'} | changes)
        )

    def test_prices_are_frozen_and_financial_fields_are_not_in_client_result_output(self):
        self.assertEqual(self.rate().status_code, 200)
        self.auth(72, 'client')
        response = self.report(closed=True)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn('attendance_unit_cad', response.data)
        report = IsolationVisitResult.objects.get()
        self.assertEqual(
            (report.attendance_unit_cad, report.sale_unit_cad), (Decimal('12.50'), Decimal('40'))
        )
        self.assertEqual(self.rate('100', '200', 1).status_code, 200)
        self.auth(72, 'client')
        self.assertEqual(
            self.report(
                closed=True, revision=1, note='Observation corrigée', reason='Précision'
            ).status_code,
            201,
        )
        totals = self.totals()
        self.assertEqual(
            (totals['attendance_amount'], totals['sale_amount'], totals['amount_cad']),
            ('12.50', '40.00', '52.50'),
        )
        self.assertEqual(
            (totals['attendance_credits'], totals['sale_credits'], totals['calls']), (1, 1, 5)
        )
        report.refresh_from_db()
        self.assertEqual(report.attendance_rate_revision, 1)

    def test_missing_prices_are_explicit_and_admin_backfill_is_versioned_and_idempotent(self):
        self.assertEqual(self.report(closed=True).status_code, 201)
        totals = self.totals()
        self.assertFalse(totals['complete'])
        self.assertEqual(totals['attendance_unpriced'], 1)
        self.assertEqual(self.rate('0', '25.35').status_code, 200)
        self.assertEqual(self.totals()['attendance_unpriced'], 1)
        self.assertEqual(self.value().data, {'valued': 1, 'remaining': 0})
        self.assertEqual(self.value().data, {'valued': 0, 'remaining': 0})
        self.assertEqual(self.totals()['amount_cad'], '25.35')
        self.assertTrue(self.totals()['complete'])
        self.assertEqual(self.rate('30', '60', 1).status_code, 200)
        self.assertEqual(self.value().status_code, 409)
        self.assertEqual(self.totals()['amount_cad'], '25.35')

    def test_later_sale_captures_its_own_tariff_without_repricing_attendance(self):
        self.rate()
        self.auth(72, 'client')
        self.assertEqual(self.report(closed=False).status_code, 201)
        report = IsolationVisitResult.objects.get()
        self.assertIsNone(report.sale_unit_cad)
        self.assertEqual(self.rate(None, '80', 1).status_code, 200)
        self.auth(72, 'client')
        self.assertEqual(
            self.report(closed=True, revision=1, reason='Vente confirmée').status_code, 201
        )
        report.refresh_from_db()
        self.assertEqual(
            (report.attendance_unit_cad, report.sale_unit_cad), (Decimal('12.50'), Decimal('80'))
        )
        self.assertEqual((report.attendance_rate_revision, report.sale_rate_revision), (1, 2))
        self.assertEqual(self.totals()['amount_cad'], '92.50')

    def test_same_process_has_only_one_credit_per_component_and_correction_recomputes_eligibility(
        self,
    ):
        self.rate()
        self.auth(72, 'client')
        self.report(closed=True)
        second = self.another(
            starts_at=self.visit.starts_at + timedelta(minutes=20),
            ends_at=self.visit.ends_at + timedelta(minutes=20),
        )
        report = IsolationVisitResult.objects.create(
            visit=second, performed=True, closed=True, outcome='closed', note=''
        )
        capture(second, report, 72)
        totals = self.totals()
        self.assertEqual((totals['attended'], totals['sales']), (2, 2))
        self.assertEqual(
            (totals['attendance_credits'], totals['sale_credits'], totals['amount_cad']),
            (1, 1, '52.50'),
        )
        self.auth(72, 'client')
        self.assertEqual(
            self.report(
                revision=1,
                performed=False,
                closed=False,
                outcome='not_performed',
                reason='Correction de présence',
            ).status_code,
            201,
        )
        self.assertEqual(self.totals()['amount_cad'], '52.50')
        self.assertEqual(
            IsolationVisitResult.objects.get(visit=self.visit).attendance_unit_cad, Decimal('12.50')
        )

    def test_first_credit_before_the_period_prevents_double_pay_in_a_later_week(self):
        self.rate()
        self.auth(72, 'client')
        self.report(closed=True)
        first_start = self.visit.starts_at - timedelta(days=10)
        IsolationVisit.objects.filter(pk=self.visit.pk).update(
            starts_at=first_start, ends_at=first_start + timedelta(hours=1)
        )
        second = self.another()
        report = IsolationVisitResult.objects.create(
            visit=second, performed=True, closed=True, outcome='closed', note=''
        )
        capture(second, report, 72)
        totals = self.totals()
        self.assertEqual(totals['attended'], 1)
        self.assertEqual(
            (totals['attendance_credits'], totals['sale_credits'], totals['amount_cad']),
            (0, 0, '0.00'),
        )

    def test_absence_and_pending_results_are_not_payable_and_source_failure_is_not_zero_calls(self):
        self.rate()
        self.auth(72, 'client')
        self.report(performed=False, closed=False, outcome='not_performed')
        self.assertEqual(self.totals()['amount_cad'], '0.00')
        self.assertEqual(self.totals()['attendance_credits'], 0)
        self.another()
        self.source.side_effect = ValueError('source offline')
        totals = self.totals()
        self.assertIsNone(totals['calls'])
        self.assertEqual(totals['pending_results'], 1)
        self.assertFalse(totals['complete'])

    def test_week_period_uses_quebec_boundaries_and_rejects_conflicting_dates(self):
        self.auth(90, 'administrator')
        response = self.client.get('/api/isolation-compensation/?week_of=' + str(self.day))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            str(response.data['from']), str(self.day - timedelta(days=self.day.weekday()))
        )
        self.assertEqual(response.data['timezone'], 'America/Toronto')
        self.assertEqual(response.data['totals']['programmed'], 1)
        self.assertEqual(
            self.client.get('/api/isolation-compensation/?week_of=invalid').status_code, 400
        )
        self.assertEqual(
            self.client.get(
                '/api/isolation-compensation/?week_of=' + str(self.day) + '&from=' + str(self.day)
            ).status_code,
            400,
        )

    def test_admin_scope_proof_validation_and_exports_preserve_privacy(self):
        self.assertEqual(self.client.get('/api/isolation-compensation/').status_code, 403)
        self.auth(21, 'setter')
        self.assertEqual(self.client.get('/api/isolation-compensation/rates/').status_code, 403)
        self.rate()
        self.auth(72, 'client')
        self.report(closed=True)
        self.auth(90, 'administrator')
        invalid = {
            'proof': self.token(91),
            'attendance_cad': '5',
            'sale_bonus_cad': '8',
            'revision': 1,
            'reason': 'Modifier',
        }
        self.assertEqual(
            self.client.post(
                '/api/isolation-compensation/rates/', invalid, format='json'
            ).status_code,
            400,
        )
        invalid.update(proof=self.token(), attendance_cad='-1')
        self.assertEqual(
            self.client.post(
                '/api/isolation-compensation/rates/', invalid, format='json'
            ).status_code,
            400,
        )
        IsolationVisit.objects.update(setter_name='=UNTRUSTED')
        csv_response = self.client.get('/api/isolation-compensation/?' + self.query + '&export=csv')
        self.assertEqual(csv_response.status_code, 200)
        text = csv_response.content.decode('utf-8-sig')
        self.assertIn("'=UNTRUSTED", text)
        self.assertNotIn(self.prospect.raw_phone, text)
        rows = list(csv.reader(io.StringIO(text), delimiter=';'))
        self.assertEqual(len(rows), 3)
        workbook = self.client.get('/api/isolation-compensation/?' + self.query + '&export=xlsx')
        self.assertEqual(load_workbook(io.BytesIO(workbook.content)).active.max_row, 3)
        self.assertTrue(
            AuditEvent.objects.filter(action='isolation.compensation.exported').exists()
        )

    def test_backfill_is_bounded_to_200_results_per_request(self):
        self.rate('1', None)
        visits = [self.another(process_id=uuid4()) for _ in range(201)]
        IsolationVisitResult.objects.bulk_create(
            [
                IsolationVisitResult(
                    visit=v, performed=True, closed=False, outcome='completed', note=''
                )
                for v in visits
            ]
        )
        self.assertEqual(self.value().data, {'valued': 200, 'remaining': 1})
        self.assertEqual(self.value().data, {'valued': 1, 'remaining': 0})


@override_settings(DEBUG=True, PORTAL_INTERNAL_URL='http://portal:8000')
class CallsContractTests(TestCase):
    def test_invalid_or_inconsistent_aggregate_is_rejected(self):
        from .isolation_compensation_calls import load

        data = {
            'from': '2026-11-01',
            'to': '2026-11-01',
            'client': {'id': 72, 'name': 'Client'},
            'results': [
                {
                    'user_id': 21,
                    'user__username': 'Setter',
                    'calls': 1,
                    'attempts': 1,
                    'uncertain': 0,
                }
            ],
            'totals': {'calls': 1, 'attempts': 1, 'uncertain': 0},
        }

        def response(value):
            mock = MagicMock()
            mock.__enter__.return_value = mock
            mock.status_code = 200
            mock.raw = MagicMock()
            mock.raw.read.return_value = json.dumps(value).encode()
            return mock

        with patch('core.isolation_compensation_calls.requests.get', return_value=response(data)):
            self.assertEqual(load(90, '2026-11-01', '2026-11-01')['totals']['calls'], 1)
        data['totals']['calls'] = 2
        with (
            patch('core.isolation_compensation_calls.requests.get', return_value=response(data)),
            self.assertRaises(ValueError),
        ):
            load(90, '2026-11-01', '2026-11-01')


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class CompensationConcurrencyTests(TransactionTestCase):
    setUp = fixtures.IsolationClientConcurrencyTests.setUp
    race = fixtures.IsolationClientConcurrencyTests.race

    def test_concurrent_identical_reports_capture_each_component_only_once(self):
        IsolationSetterRate.objects.create(
            setter_id=21,
            setter_name='Setter',
            client_id=72,
            client_name='Client',
            attendance_cad='12.50',
            sale_bonus_cad='40',
            revision=1,
        )
        payload = {
            'revision': 0,
            'performed': True,
            'closed': True,
            'outcome': 'closed',
            'note': '',
        }
        self.assertEqual(sorted(self.race([payload, payload])), [200, 201])
        report = IsolationVisitResult.objects.get()
        self.assertEqual(report.attendance_unit_cad, Decimal('12.50'))
        self.assertEqual(report.sale_unit_cad, Decimal('40'))
        self.assertEqual(
            AuditEvent.objects.filter(action='isolation.compensation.captured').count(), 1
        )
