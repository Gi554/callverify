from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo
from django.test import TestCase, override_settings
from . import test_isolation_statistics as fixtures
from .models import IsolationVisitResult, PayableEntry, PayableHistory

ZONE = ZoneInfo('America/Toronto')


def at(day, hour=12):
    """The moment attendance is confirmed, in November 2026 (Monday 2 is the first day)."""
    return patch(
        'packages.payable_ledger.current_time',
        return_value=datetime(2026, 11, day, hour, tzinfo=ZONE),
    )


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class IsolationPayableTests(TestCase):
    setUp = fixtures.IsolationStatisticsTests.setUp
    auth = fixtures.IsolationStatisticsTests.auth
    visit = fixtures.IsolationStatisticsTests.visit

    def confirm(self, closed, day=4, setter=21, row=None):
        """Record a result: the visit is created on first call, then corrected on later ones."""
        with at(day):
            row = row or self.visit(setter=setter)
            IsolationVisitResult.objects.update_or_create(
                visit=row,
                defaults={
                    'author_client_id': 72,
                    'performed': True,
                    'outcome': 'completed',
                    'note': 'Note',
                    'closed': closed,
                },
            )
        return row

    def get(self, first=2, last=8, **params):
        query = {'from': f'2026-11-{first:02d}', 'to': f'2026-11-{last:02d}'}
        return self.client.get('/api/payable-appointments/', {**query, **params})

    def test_closed_and_not_closed_are_counted_apart_and_summed(self):
        self.confirm(True)
        self.confirm(True)
        self.confirm(False)
        data = self.get().data
        self.assertEqual(
            data['totals'], {'presented': 3, 'payable': 3, 'closed': 2, 'not_closed': 1}
        )
        self.assertTrue(data['split_sales'])

    def test_only_closed_shows_zero_not_closed_and_unknown_sale_counts_as_not_closed(self):
        self.confirm(True)
        self.assertEqual(self.get().data['totals']['not_closed'], 0)
        self.confirm(None)
        data = self.get().data['totals']
        self.assertEqual((data['closed'], data['not_closed'], data['payable']), (1, 1, 2))

    def test_awaiting_absent_and_unqualified_results_are_not_payable(self):
        self.visit()
        with at(4):
            self.visit(performed=False)
        self.assertEqual(self.get().data['totals']['payable'], 0)
        self.assertEqual(PayableEntry.objects.count(), 0)

    def test_not_closed_turning_closed_later_is_one_payable_with_history_and_alert(self):
        row = self.confirm(False, day=4)
        self.confirm(True, day=11, row=row)
        week_two = self.get().data['totals']
        self.assertEqual((week_two['not_closed'], week_two['closed']), (1, 0))
        self.assertEqual(self.get(first=9, last=15).data['totals']['payable'], 0)
        self.assertEqual(PayableEntry.objects.count(), 1)
        change = PayableHistory.objects.get(kind='sale_status_changed')
        self.assertEqual(
            (change.old_value, change.new_value, change.late), ('not_closed', 'closed', True)
        )
        shown = self.get(first=9, last=15).data['changes']
        self.assertEqual(shown[0]['before'], 'Non closé')
        self.assertEqual(shown[0]['after'], 'Closé')
        alerts = self.client.get('/api/admin-alerts/', {'kind': 'late_closures'}).data
        self.assertEqual(alerts['count'], 1)
        self.assertIn('late_closures', [item['kind'] for item in alerts['kinds']])

    def test_closing_within_the_same_week_is_not_a_late_alert(self):
        row = self.confirm(False, day=4)
        self.confirm(True, day=6, row=row)
        self.assertEqual(
            self.client.get('/api/admin-alerts/', {'kind': 'late_closures'}).data['count'], 0
        )
        self.assertFalse(PayableHistory.objects.get(kind='sale_status_changed').late)

    def test_administrator_filters_by_setter_and_setter_sees_only_self(self):
        self.confirm(True, setter=21)
        self.confirm(False, setter=22)
        everyone = self.get().data
        self.assertEqual(everyone['totals']['payable'], 2)
        self.assertEqual({row['agent_id'] for row in everyone['rows']}, {21, 22})
        self.assertEqual({row['id'] for row in everyone['agents']}, {21, 22})
        only = self.get(agent=22).data
        self.assertEqual((only['totals']['closed'], only['totals']['not_closed']), (0, 1))
        self.auth(21, 'setter')
        own = self.get().data
        self.assertEqual([row['agent_id'] for row in own['rows']], [21])
        self.assertEqual((own['agents'], own['changes']), ([], []))
        self.assertEqual(self.get(agent=22).status_code, 403)
        self.auth(72, 'client')
        self.assertEqual(self.get().status_code, 403)
