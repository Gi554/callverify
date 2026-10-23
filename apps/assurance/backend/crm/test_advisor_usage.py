from uuid import uuid4
from django.test import TestCase, override_settings
from . import tests as fixtures
from .models import Appointment


@override_settings(DEBUG=True)
class AdvisorUsageTests(TestCase):
    def setUp(self):
        self.fixture = fixtures.ReportTests()
        self.fixture.setUp()
        self.client = self.fixture.client
        self.row = self.fixture.appointment

    def clone(self, **changes):
        values = {
            field.attname: getattr(self.row, field.attname)
            for field in Appointment._meta.fields
            if not field.primary_key and field.name not in ('created_at', 'request_id')
        }
        return Appointment.objects.create(**{**values, 'request_id': uuid4(), **changes})

    def test_booked_appointments_consume_and_cancellations_give_back(self):
        self.clone()
        self.clone(status='cancelled')
        self.clone(advisor_id=self.row.advisor_id + 1)
        response = self.client.get('/api/assurance/advisor-usage/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(
            response.data['results'],
            [
                {'advisor_id': self.row.advisor_id, 'booked': 2},
                {'advisor_id': self.row.advisor_id + 1, 'booked': 1},
            ],
        )
        self.client.credentials()
        self.assertIn(self.client.get('/api/assurance/advisor-usage/').status_code, (401, 403))
