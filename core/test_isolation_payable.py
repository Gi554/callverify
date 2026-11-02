from datetime import timedelta
from django.test import TestCase, override_settings
from packages.quebec_period import ZONE
from . import test_isolation_statistics as fixtures
from .models import IsolationVisitResult


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class IsolationPayableTests(TestCase):
    setUp = fixtures.IsolationStatisticsTests.setUp
    auth = fixtures.IsolationStatisticsTests.auth
    visit = fixtures.IsolationStatisticsTests.visit

    def closed(self, **kwargs):
        closed = kwargs.pop('closed')
        row = self.visit(performed=True, **kwargs)
        IsolationVisitResult.objects.filter(visit=row).update(closed=closed)
        return row

    def get(self, **params):
        day = self.day.astimezone(ZONE).date()
        query = {'from': str(day - timedelta(days=1)), 'to': str(day + timedelta(days=1))}
        return self.client.get('/api/payable-appointments/', {**query, **params})

    def test_closed_and_not_closed_are_counted_apart_and_summed(self):
        self.closed(closed=True)
        self.closed(closed=True)
        self.closed(closed=False)
        data = self.get().data
        self.assertEqual(
            data['totals'], {'presented': 3, 'payable': 3, 'closed': 2, 'not_closed': 1}
        )
        self.assertEqual(len(data['rows']), 1)
        self.assertTrue(data['split_sales'])

    def test_only_closed_shows_zero_not_closed_and_reverse(self):
        self.closed(closed=True)
        self.assertEqual(self.get().data['totals']['not_closed'], 0)
        IsolationVisitResult.objects.all().delete()
        self.visit(performed=True)
        data = self.get().data['totals']
        self.assertEqual((data['closed'], data['not_closed'], data['payable']), (0, 1, 1))

    def test_absent_unreported_cancelled_and_outside_period_are_not_payable(self):
        self.visit(performed=False)
        self.visit()
        self.visit(performed=True, status='cancelled')
        self.assertEqual(self.get().data['totals']['payable'], 0)
        self.closed(closed=True)
        far = (self.day + timedelta(days=30)).astimezone(ZONE).date()
        empty = self.client.get('/api/payable-appointments/', {'from': str(far), 'to': str(far)})
        self.assertEqual(empty.data['totals']['payable'], 0)

    def test_administrator_filters_by_setter_and_setter_sees_only_self(self):
        self.closed(closed=True, setter=21)
        self.closed(closed=False, setter=22)
        everyone = self.get().data
        self.assertEqual(everyone['totals']['payable'], 2)
        self.assertEqual({row['agent_id'] for row in everyone['rows']}, {21, 22})
        self.assertEqual({row['id'] for row in everyone['agents']}, {21, 22})
        only = self.get(agent=22).data
        self.assertEqual((only['totals']['closed'], only['totals']['not_closed']), (0, 1))
        self.auth(21, 'setter')
        own = self.get().data
        self.assertEqual([row['agent_id'] for row in own['rows']], [21])
        self.assertEqual(own['agents'], [])
        self.assertEqual(self.get(agent=22).status_code, 403)
        self.auth(72, 'client')
        self.assertEqual(self.get().status_code, 403)
