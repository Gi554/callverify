from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import timedelta
from uuid import uuid4
from packages.quebec_period import ZONE
from .models import AppointmentReport
from .models import Appointment, ContactCallOutcome
from .payable_fixtures import AppointmentFixture


@override_settings(DEBUG=True)
class PerformanceTests(TestCase):
    setUp = AppointmentFixture.setUp
    auth = AppointmentFixture.auth

    def test_booking_counts_creation_day_and_outcomes_stay_scoped(self):
        now = timezone.now()
        Appointment.objects.filter(pk=self.appointment.pk).update(
            created_at=now,
            starts_at=now + timedelta(days=40),
            ends_at=now + timedelta(days=40, hours=1),
        )
        for agent, result in ((21, 'callback'), (21, 'not_interested'), (22, 'voicemail')):
            ContactCallOutcome.objects.create(
                contact=self.appointment.contact,
                setter_id=agent,
                result=result,
                request_id=uuid4(),
                fingerprint='test',
            )
        self.auth('setter', 21)
        day = now.astimezone(ZONE).date()
        response = self.client.get(f'/api/assurance/setter-performance/?from={day}&to={day}')
        self.assertEqual(response.data['totals']['booked'], 1)
        self.assertEqual(response.data['totals']['scheduled'], 0)
        outcomes = {row['key']: row['count'] for row in response.data['outcomes']}
        self.assertEqual(outcomes['callback'], 1)
        self.assertEqual(outcomes['not_interested'], 1)
        self.assertEqual(outcomes['voicemail'], 0)

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
