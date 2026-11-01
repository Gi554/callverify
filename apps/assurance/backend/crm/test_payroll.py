from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from django.test import TestCase, override_settings
from django.utils import timezone
from packages.quebec_period import ZONE
from . import test_compensation as fixtures
from .models import AppointmentReport, SetterPayrollPayment, SetterPayrollAdjustment, SetterRate
from .compensation import capture


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class PayrollTests(TestCase):
    setUp = fixtures.CompensationTests.setUp
    auth = fixtures.CompensationTests.auth

    def terms(self, **changes):
        self.auth()
        day = timezone.now().astimezone(ZONE).date()
        body = {
            'starts_on': str(day),
            'ends_on': str(day + timedelta(days=30)),
            'cadence': 'mandate',
            'target': 10,
            'attendance_cad': '15.00',
            'reason': 'Mandat individuel',
            'revision': 0,
            **changes,
        }
        return self.client.post('/api/assurance/payroll/21/terms/', body, format='json')

    def statement(self):
        self.auth()
        return self.client.get('/api/assurance/payroll/21/').data

    def earn(self):
        report = AppointmentReport.objects.create(
            appointment=self.appointment, author_id=31, performed=True, outcome='completed'
        )
        capture(report, self.appointment, 31)
        return report

    def test_assurance_terms_pay_attendance_only_and_freeze_the_unit_price(self):
        response = self.terms()
        self.assertEqual(response.status_code, 200, response.data)
        report = self.earn()
        report.refresh_from_db()
        self.assertEqual(report.unit_rate_cad, Decimal('15'))
        self.assertEqual(report.payroll_term_id, response.data['id'])
        SetterRate.objects.update_or_create(setter_id=21, defaults={'amount': '99'})
        self.assertEqual(self.statement()['generated_cad'], '15.00')
        self.assertEqual(
            self.terms(
                starts_on=str(timezone.now().astimezone(ZONE).date() + timedelta(days=40)),
                ends_on=str(timezone.now().astimezone(ZONE).date() + timedelta(days=50)),
                bonus_cad='1',
            ).status_code,
            400,
        )

    def test_receipt_survives_a_corrected_presence_and_is_never_executed_as_a_transfer(self):
        self.terms()
        report = self.earn()
        state = self.statement()
        body = {
            'request_id': str(uuid4()),
            'amount_cad': '15',
            'paid_on': str(timezone.now().astimezone(ZONE).date()),
            'reference': 'Virement externe',
            'revision': state['revision'],
        }
        url = '/api/assurance/payroll/21/payments/'
        response = self.client.post(url, body, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(self.client.post(url, body, format='json').data['replayed'])
        self.assertEqual(SetterPayrollPayment.objects.count(), 1)
        report.performed = False
        report.save()
        capture(report, self.appointment, 31)
        state = self.statement()
        self.assertEqual(state['to_regularize_cad'], '15.00')
        self.assertEqual(state['paid_cad'], '15.00')
        self.assertEqual(SetterPayrollAdjustment.objects.get().delta_cad, Decimal('-15'))

    def test_own_finances_are_read_only_and_other_roles_cannot_access_the_registry(self):
        self.terms()
        self.auth('setter', 21)
        result = self.client.get('/api/assurance/payroll/')
        self.assertEqual(result.status_code, 200)
        self.assertEqual([r['agent_id'] for r in result.data['results']], [21])
        self.assertEqual(self.client.get('/api/assurance/payroll/22/').status_code, 403)
        self.assertEqual(
            self.client.post('/api/assurance/payroll/21/payments/', {}, format='json').status_code,
            403,
        )
        self.auth('advisor', 31)
        self.assertEqual(self.client.get('/api/assurance/payroll/').status_code, 403)
