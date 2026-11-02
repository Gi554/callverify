from datetime import timedelta
from django.test import TestCase, override_settings
from django.utils import timezone
from . import test_compensation as fixtures
from .models import Appointment, AppointmentReport


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class PayableAppointmentsTests(TestCase):
    setUp = fixtures.CompensationTests.setUp
    auth = fixtures.CompensationTests.auth

    def get(self, **params):
        query = {'from': '2026-10-26', 'to': '2026-11-01', **params}
        return self.client.get('/api/assurance/payable-appointments/', query)

    def report(self, performed=True, appointment=None):
        return AppointmentReport.objects.create(
            appointment=appointment or self.appointment,
            author_id=31,
            performed=performed,
            outcome='completed' if performed else 'absent',
        )

    def test_attended_and_validated_is_payable_with_or_without_a_sale(self):
        self.assertEqual(self.get().data['totals'], {'presented': 0, 'payable': 0})
        self.report()
        data = self.get().data
        self.assertEqual(data['totals'], {'presented': 1, 'payable': 1})
        self.assertFalse(data['split_sales'])
        self.assertEqual(data['rows'][0]['agent_id'], 21)

    def test_absent_unreported_cancelled_and_other_periods_are_not_payable(self):
        self.report(performed=False)
        self.assertEqual(self.get().data['totals']['payable'], 0)
        AppointmentReport.objects.all().delete()
        self.assertEqual(self.get().data['totals']['payable'], 0)
        self.report()
        Appointment.objects.update(status='cancelled')
        self.assertEqual(self.get().data['totals']['payable'], 0)
        Appointment.objects.update(status='scheduled')
        self.assertEqual(self.get().data['totals']['payable'], 1)
        later = self.client.get(
            '/api/assurance/payable-appointments/', {'from': '2026-11-02', 'to': '2026-11-08'}
        )
        self.assertEqual(later.data['totals']['payable'], 0)

    def test_a_future_appointment_is_not_payable_yet(self):
        self.report()
        Appointment.objects.update(
            starts_at=timezone.now() + timedelta(days=1), ends_at=timezone.now() + timedelta(days=2)
        )
        far = {
            'from': str(timezone.now().date()),
            'to': str(timezone.now().date() + timedelta(days=5)),
        }
        self.assertEqual(
            self.client.get('/api/assurance/payable-appointments/', far).data['totals']['payable'],
            0,
        )

    def test_a_rescheduled_appointment_counts_once(self):
        self.report()
        Appointment.objects.update(reschedule_count=2)
        self.assertEqual(self.get().data['totals']['payable'], 1)

    def test_administrator_chooses_setter_setter_sees_only_self_advisor_refused(self):
        self.report()
        self.assertEqual(self.get().data['agents'][0]['id'], 21)
        self.assertEqual(self.get(agent=22).data['totals']['payable'], 0)
        self.auth('setter', 21)
        self.assertEqual(self.get().data['totals']['payable'], 1)
        self.assertEqual(self.get().data['agents'], [])
        self.assertEqual(self.get(agent=22).status_code, 403)
        self.auth('setter', 22)
        self.assertEqual(self.get().data['totals']['payable'], 0)
        self.auth('advisor', 31)
        self.assertEqual(self.get().status_code, 403)

    def test_bad_period_and_agent_are_refused(self):
        self.assertEqual(self.get(**{'from': 'x'}).status_code, 400)
        self.assertEqual(self.get(agent='abc').status_code, 400)
