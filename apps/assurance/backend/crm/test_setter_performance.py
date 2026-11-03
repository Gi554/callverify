from django.test import TestCase, override_settings
from packages.quebec_period import ZONE
from .models import AppointmentReport
from .payable_fixtures import AppointmentFixture


@override_settings(DEBUG=True)
class PerformanceTests(TestCase):
    setUp = AppointmentFixture.setUp
    auth = AppointmentFixture.auth

    def test_held_count_matches_the_scope_and_no_money_is_exposed(self):
        AppointmentReport.objects.create(
            appointment=self.appointment, author_id=31, performed=True, outcome='completed'
        )
        self.appointment.refresh_from_db()
        self.auth('setter', 21)
        day = self.appointment.starts_at.astimezone(ZONE).date()
        response = self.client.get(f'/api/assurance/setter-performance/?from={day}&to={day}')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['totals']['held'], 1)
        self.assertNotIn('generated_cad', response.data['totals'])
        self.assertNotIn('currency', response.data)
        self.assertEqual(self.client.get('/api/assurance/setter-performance/22/').status_code, 403)
        self.auth('advisor', 31)
        self.assertEqual(self.client.get('/api/assurance/setter-performance/').status_code, 403)
