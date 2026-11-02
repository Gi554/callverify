from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo
from django.test import TestCase, override_settings
from . import test_compensation as fixtures
from .models import AppointmentReport, PayableEntry, PayableHistory

ZONE = ZoneInfo('America/Toronto')


def at(day, hour=12):
    """The moment attendance is confirmed, in November 2026 (Monday 2 is the first day)."""
    return patch(
        'packages.payable_ledger.current_time',
        return_value=datetime(2026, 11, day, hour, tzinfo=ZONE),
    )


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class PayableAppointmentsTests(TestCase):
    setUp = fixtures.CompensationTests.setUp
    auth = fixtures.CompensationTests.auth

    def get(self, first=2, last=8, **params):
        query = {'from': f'2026-11-{first:02d}', 'to': f'2026-11-{last:02d}', **params}
        return self.client.get('/api/assurance/payable-appointments/', query)

    def report(self, performed=True, day=4):
        with at(day):
            return AppointmentReport.objects.update_or_create(
                appointment=self.appointment,
                defaults={
                    'author_id': 31,
                    'performed': performed,
                    'outcome': 'completed' if performed else 'absent',
                },
            )[0]

    def test_counted_in_the_week_attendance_is_confirmed_not_the_planned_week(self):
        # The fixture appointment was planned on 26 October, a week earlier.
        self.assertEqual(self.get().data['totals'], {'presented': 0, 'payable': 0})
        self.report(day=4)
        data = self.get().data
        self.assertEqual(data['totals'], {'presented': 1, 'payable': 1})
        self.assertFalse(data['split_sales'])
        self.assertEqual(data['rows'][0]['agent_id'], 21)
        october = self.client.get(
            '/api/assurance/payable-appointments/', {'from': '2026-10-26', 'to': '2026-11-01'}
        )
        self.assertEqual(october.data['totals']['payable'], 0)
        entry = PayableEntry.objects.get()
        self.assertEqual(str(entry.week_start), '2026-11-02')

    def test_absent_or_unconfirmed_is_not_payable(self):
        self.report(performed=False)
        self.assertEqual(self.get().data['totals']['payable'], 0)
        self.assertEqual(PayableEntry.objects.count(), 0)

    def test_confirmation_after_the_paid_week_counts_in_the_current_week(self):
        # Week of 2 November was paid; the advisor confirms on Wednesday 11 November.
        self.report(day=11)
        self.assertEqual(self.get().data['totals']['payable'], 0)
        self.assertEqual(self.get(first=9, last=15).data['totals']['payable'], 1)

    def test_a_closed_week_never_changes_and_the_history_keeps_the_correction(self):
        self.report(day=4)
        self.report(performed=False, day=11)
        self.assertEqual(self.get().data['totals']['payable'], 1)
        self.assertEqual(self.get(first=9, last=15).data['totals']['payable'], 0)
        self.assertEqual(
            list(PayableHistory.objects.order_by('pk').values_list('kind', flat=True)),
            ['counted', 'withdrawn_after_week'],
        )

    def test_withdrawal_in_the_same_week_removes_it_and_a_later_confirmation_recounts_once(self):
        self.report(day=4)
        self.report(performed=False, day=5)
        self.assertEqual(self.get().data['totals']['payable'], 0)
        self.report(day=11)
        self.assertEqual(self.get().data['totals']['payable'], 0)
        self.assertEqual(self.get(first=9, last=15).data['totals']['payable'], 1)
        self.assertEqual(PayableEntry.objects.count(), 1)

    def test_saving_the_same_result_again_never_counts_twice(self):
        for day in (4, 5, 6):
            self.report(day=day)
        self.assertEqual(self.get().data['totals']['payable'], 1)
        self.assertEqual(PayableHistory.objects.count(), 1)

    def test_administrator_sees_history_setter_chooses_setter_sees_only_self(self):
        self.report()
        data = self.get().data
        self.assertEqual(data['agents'][0]['id'], 21)
        self.assertEqual(data['changes'][0]['label'], 'Comptabilisé')
        self.assertEqual(self.get(agent=22).data['totals']['payable'], 0)
        self.auth('setter', 21)
        own = self.get().data
        self.assertEqual(own['totals']['payable'], 1)
        self.assertEqual((own['agents'], own['changes']), ([], []))
        self.assertEqual(self.get(agent=22).status_code, 403)
        self.auth('setter', 22)
        self.assertEqual(self.get().data['totals']['payable'], 0)
        self.auth('advisor', 31)
        self.assertEqual(self.get().status_code, 403)

    def test_bad_period_and_agent_are_refused(self):
        self.assertEqual(self.get(**{'from': 'x'}).status_code, 400)
        self.assertEqual(self.get(agent='abc').status_code, 400)
