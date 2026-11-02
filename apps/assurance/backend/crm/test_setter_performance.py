from django.test import TestCase, override_settings
from packages.quebec_period import ZONE
from . import test_payroll as fixtures


@override_settings(DEBUG=True)
class PerformanceTests(TestCase):
    setUp = fixtures.PayrollTests.setUp
    auth = fixtures.PayrollTests.auth
    terms = fixtures.PayrollTests.terms
    earn = fixtures.PayrollTests.earn

    def test_frozen_earnings_match_daily_series_and_scope(self):
        self.terms()
        self.earn()
        self.appointment.refresh_from_db()
        self.auth('setter', 21)
        day = self.appointment.starts_at.astimezone(ZONE).date()
        response = self.client.get(f'/api/assurance/setter-performance/?from={day}&to={day}')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['totals']['held'], 1)
        self.assertEqual(self.client.get('/api/assurance/setter-performance/22/').status_code, 403)
        self.auth('advisor', 31)
        self.assertEqual(self.client.get('/api/assurance/setter-performance/').status_code, 403)
