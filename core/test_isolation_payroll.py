from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.db import connection, close_old_connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from packages.access.tickets import issue
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from django.test import TestCase, override_settings
from django.utils import timezone
from packages.quebec_period import ZONE
from . import test_isolation_compensation as fixtures
from .models import (
    IsolationPayrollTerms,
    IsolationPayrollPayment,
    IsolationPayrollAdjustment,
    IsolationVisitResult,
    IsolationSetterRate,
)
from .isolation_compensation import capture
from .payroll import reconcile


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class PayrollTests(TestCase):
    setUp = fixtures.CompensationTests.setUp
    auth = fixtures.CompensationTests.auth
    token = fixtures.CompensationTests.token
    report = fixtures.CompensationTests.report
    payload = fixtures.CompensationTests.payload

    def terms(self, **changes):
        today = timezone.now().astimezone(ZONE).date()
        body = {
            'starts_on': str(today),
            'ends_on': str(today + timedelta(days=27)),
            'cadence': 'week',
            'target': 10,
            'attendance_cad': '25.00',
            'bonus_cad': '50.00',
            'conditions': 'Visites validées',
            'reason': 'Accord individuel',
            'revision': 0,
            'proof': self.token(),
            **changes,
        }
        self.auth(90, 'administrator')
        return self.client.post('/api/payroll/21/terms/', body, format='json')

    def statement(self):
        self.auth(90, 'administrator')
        return self.client.get('/api/payroll/21/').data

    def payment(self, **changes):
        state = self.statement()
        body = {
            'request_id': str(uuid4()),
            'amount_cad': '25.00',
            'paid_on': str(timezone.now().astimezone(ZONE).date()),
            'reference': 'VIR-1',
            'note': 'Paiement effectué ailleurs',
            'revision': state['revision'],
            **changes,
        }
        return self.client.post('/api/payroll/21/payments/', body, format='json')

    def test_dated_rates_are_captured_once_and_sale_components_remain_separate(self):
        response = self.terms()
        self.assertEqual(response.status_code, 200, response.data)
        self.auth(72, 'client')
        response = self.report(closed=True)
        self.assertEqual(response.status_code, 201, response.data)
        result = IsolationVisitResult.objects.get(visit=self.visit)
        self.assertEqual(result.attendance_unit_cad, Decimal('25'))
        self.assertEqual(result.sale_unit_cad, Decimal('50'))
        self.assertEqual(result.attendance_term_id, IsolationPayrollTerms.objects.get().pk)
        state = self.statement()
        self.assertEqual(state['generated_cad'], '75.00')
        self.assertEqual(state['attendance_amount_cad'], '25.00')
        self.assertEqual(state['sale_bonus_cad'], '50.00')
        IsolationSetterRate.objects.update(attendance_cad='999', sale_bonus_cad='999')
        self.assertEqual(self.statement()['generated_cad'], '75.00')
        self.assertEqual(self.terms().status_code, 400)
        term = IsolationPayrollTerms.objects.get()
        payload = {
            'starts_on': str(term.starts_on),
            'ends_on': str(term.ends_on),
            'cadence': 'week',
            'target': 20,
            'attendance_cad': '999',
            'bonus_cad': '999',
            'conditions': '',
            'reason': 'modifier',
            'revision': 0,
            'proof': self.token(),
        }
        self.assertEqual(
            self.client.post(
                f'/api/payroll/21/terms/{term.pk}/', payload, format='json'
            ).status_code,
            400,
        )

    def test_payment_is_replayable_and_reference_revision_balance_checks_prevent_duplicate_payment(
        self,
    ):
        self.terms()
        self.auth(72, 'client')
        self.report(closed=True)
        state = self.statement()
        request = str(uuid4())
        body = {
            'request_id': request,
            'amount_cad': '25.00',
            'paid_on': str(timezone.now().astimezone(ZONE).date()),
            'reference': 'VIR-1',
            'revision': state['revision'],
        }
        response = self.client.post('/api/payroll/21/payments/', body, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(
            self.client.post('/api/payroll/21/payments/', body, format='json').data['replayed']
        )
        self.assertEqual(IsolationPayrollPayment.objects.count(), 1)
        self.assertEqual(self.payment(reference='vir-1').status_code, 400)
        self.assertEqual(self.payment(reference='VIR-2', amount_cad='51').status_code, 400)
        self.assertEqual(self.payment(reference='VIR-2', revision=0).status_code, 400)
        state = self.statement()
        self.assertEqual(state['paid_cad'], '25.00')
        self.assertEqual(state['to_pay_cad'], '50.00')

    def test_correction_retains_payment_and_creates_an_audited_adjustment(self):
        self.terms()
        self.auth(72, 'client')
        self.report(closed=True)
        self.assertEqual(self.payment(amount_cad='75').status_code, 200)
        report = IsolationVisitResult.objects.get(visit=self.visit)
        report.performed = False
        report.closed = False
        report.outcome = 'not_performed'
        report.save()
        capture(self.visit, report, 72)
        state = self.statement()
        self.assertEqual(state['paid_cad'], '75.00')
        self.assertEqual(state['generated_cad'], '0.00')
        self.assertEqual(state['to_regularize_cad'], '75.00')
        adjustment = IsolationPayrollAdjustment.objects.get()
        self.assertEqual(adjustment.delta_cad, Decimal('-75'))
        self.assertEqual(adjustment.actor_id, 72)
        reconcile(21, 72)
        self.assertEqual(IsolationPayrollAdjustment.objects.count(), 1)
        self.assertEqual(IsolationPayrollPayment.objects.count(), 1)

    def test_setter_only_reads_own_statement_and_never_changes_conditions_or_payments(self):
        self.terms()
        self.auth(21, 'setter')
        result = self.client.get('/api/payroll/')
        self.assertEqual(result.status_code, 200)
        self.assertEqual([r['agent_id'] for r in result.data['results']], [21])
        self.assertEqual(self.client.get('/api/payroll/22/').status_code, 403)
        self.assertEqual(
            self.client.post('/api/payroll/21/payments/', {}, format='json').status_code, 403
        )
        self.assertEqual(
            self.client.post('/api/payroll/21/terms/', {}, format='json').status_code, 403
        )
        self.auth(72, 'client')
        self.assertEqual(self.client.get('/api/payroll/').status_code, 403)
        self.auth(91, 'closer')
        self.assertEqual(self.client.get('/api/payroll/').status_code, 401)

    def test_missing_tariff_and_no_show_never_generate_fake_amounts(self):
        self.auth(72, 'client')
        self.report(closed=False)
        state = self.statement()
        self.assertEqual(state['generated_cad'], '0.00')
        self.assertEqual(state['unpriced'], 1)
        self.assertEqual(self.payment().status_code, 400)

    def test_future_weekly_conditions_can_be_modified_with_a_revision_without_changing_current_rates(
        self,
    ):
        today = timezone.now().astimezone(ZONE).date()
        future = today + timedelta(days=7)
        response = self.terms(starts_on=str(future), ends_on=str(future + timedelta(days=6)))
        self.assertEqual(response.status_code, 200, response.data)
        pk = response.data['id']
        body = {
            'starts_on': str(future),
            'ends_on': str(future + timedelta(days=6)),
            'cadence': 'week',
            'target': 15,
            'attendance_cad': '30',
            'bonus_cad': '60',
            'conditions': 'Futur',
            'reason': 'Nouvel accord',
            'revision': 0,
            'proof': self.token(),
        }
        response = self.client.post(f'/api/payroll/21/terms/{pk}/', body, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['revision'], 1)
        self.assertEqual(
            self.client.post(f'/api/payroll/21/terms/{pk}/', body, format='json').status_code, 400
        )
        self.assertIsNone(self.statement()['goal'])

    def test_adjustment_is_reversed_when_a_corrected_presence_is_restored(self):
        self.terms()
        self.auth(72, 'client')
        self.report(closed=True)
        report = IsolationVisitResult.objects.get(visit=self.visit)
        report.performed = False
        report.closed = False
        report.outcome = 'not_performed'
        report.save()
        capture(self.visit, report, 72)
        report.performed = True
        report.closed = True
        report.outcome = 'closed'
        report.save()
        capture(self.visit, report, 72)
        self.assertEqual(
            list(
                IsolationPayrollAdjustment.objects.order_by('pk').values_list(
                    'delta_cad', flat=True
                )
            ),
            [Decimal('-75'), Decimal('75')],
        )
        self.assertEqual(self.statement()['generated_cad'], '75.00')

    def test_payment_audit_failure_rolls_back_receipt_and_balance(self):
        from unittest.mock import patch
        from .payroll import Store

        self.terms()
        self.auth(72, 'client')
        self.report(closed=True)
        with patch.object(Store, 'audit', side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):
                self.payment()
        self.assertFalse(IsolationPayrollPayment.objects.exists())
        self.assertEqual(self.statement()['paid_cad'], '0.00')

    def test_history_is_paged_and_invalid_page_is_rejected(self):
        self.terms()
        day = timezone.now().astimezone(ZONE).date()
        for i in range(26):
            IsolationPayrollPayment.objects.create(
                agent_id=21,
                request_id=uuid4(),
                fingerprint='test',
                amount_cad='1',
                paid_on=day,
                reference=f'TEST-{i}',
                reference_key=str(i),
                actor_id=90,
            )
        data = self.statement()
        self.assertEqual(data['payments_count'], 26)
        self.assertEqual(len(data['payments']), 25)
        result = self.client.get('/api/payroll/21/?payments_page=2')
        self.assertEqual(len(result.data['payments']), 1)
        self.assertEqual(self.client.get('/api/payroll/21/?payments_page=bad').status_code, 400)


@skipUnless(connection.vendor == 'postgresql', 'Verrouillage réel PostgreSQL requis')
@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class PayrollConcurrencyTests(TransactionTestCase):
    setUp = PayrollTests.setUp
    auth = PayrollTests.auth
    token = PayrollTests.token
    report = PayrollTests.report
    payload = PayrollTests.payload
    terms = PayrollTests.terms
    statement = PayrollTests.statement

    def exercise(self, same_request):
        self.terms()
        self.auth(72, 'client')
        self.report(closed=True)
        state = self.statement()
        gate = Barrier(2)
        request_id = str(uuid4())
        day = str(timezone.now().astimezone(ZONE).date())

        def submit(index):
            close_old_connections()
            try:
                client = APIClient()
                client.credentials(
                    HTTP_AUTHORIZATION='Bearer ' + issue(90, 'isolation', 'administrator')
                )
                body = {
                    'request_id': request_id if same_request else str(uuid4()),
                    'amount_cad': '60',
                    'paid_on': day,
                    'reference': f'PAY-{0 if same_request else index}',
                    'revision': state['revision'],
                }
                gate.wait(timeout=15)
                response = client.post('/api/payroll/21/payments/', body, format='json')
                return response.status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(submit, [1, 2]))
        self.assertEqual(sorted(statuses), [200, 200] if same_request else [200, 400])
        self.assertEqual(IsolationPayrollPayment.objects.count(), 1)
        self.assertEqual(self.statement()['paid_cad'], '60.00')

    def test_simultaneous_payments_cannot_spend_the_same_balance_twice(self):
        self.exercise(False)

    def test_simultaneous_replay_creates_exactly_one_receipt(self):
        self.exercise(True)
