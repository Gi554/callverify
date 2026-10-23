from uuid import uuid4
from django.test import TestCase, override_settings
from . import tests as fixtures
from .models import Appointment, AppointmentReport, Contact


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

    def test_only_attendance_consumes_and_advisor_sees_own_usage(self):
        attended = self.clone()
        AppointmentReport.objects.create(appointment=attended, performed=True, author_id=31)
        cancelled = self.clone(status='cancelled')
        AppointmentReport.objects.create(appointment=cancelled, performed=True, author_id=31)
        absent = self.clone()
        AppointmentReport.objects.create(
            appointment=absent, performed=False, outcome='absent', author_id=31
        )
        self.clone(advisor_id=self.row.advisor_id + 1)
        response = self.client.get('/api/assurance/advisor-usage/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(
            response.data['results'],
            [
                {'advisor_id': self.row.advisor_id, 'booked': 3, 'attended': 1, 'absent': 1},
            ],
        )
        self.client.credentials()
        self.assertIn(self.client.get('/api/assurance/advisor-usage/').status_code, (401, 403))

    def test_countdown_follows_report_corrections_without_double_counting(self):
        url = f'/api/assurance/appointments/{self.row.pk}/advisor-result/'
        payload = {
            'revision': 0,
            'performed': False,
            'sale_concluded': False,
            'outcome': 'absent',
            'note': 'Client absent',
        }
        self.assertEqual(self.client.post(url, payload, format='json').status_code, 200)
        self.assertEqual(
            self.client.get('/api/assurance/advisor-usage/').data['results'][0]['attended'], 0
        )
        payload.update(revision=1, performed=True, outcome='performed', reason='Présence corrigée')
        self.assertEqual(self.client.post(url, payload, format='json').status_code, 200)
        self.assertEqual(self.client.post(url, payload, format='json').status_code, 200)
        self.assertEqual(
            self.client.get('/api/assurance/advisor-usage/').data['results'][0]['attended'], 1
        )
        payload.update(revision=2, performed=False, outcome='absent', reason='Erreur de saisie')
        self.assertEqual(self.client.post(url, payload, format='json').status_code, 200)
        self.assertEqual(
            self.client.get('/api/assurance/advisor-usage/').data['results'][0]['attended'], 0
        )

    def test_prospects_are_unique_scoped_searchable_and_paginated(self):
        self.clone()
        Contact.objects.create(
            name='Hidden', phone='private', created_by_id=1, assigned_advisor_id=32
        )
        for n in range(26):
            Contact.objects.create(
                name=f'Assigned {n}', phone='raw', created_by_id=1, assigned_advisor_id=31
            )
        response = self.client.get('/api/assurance/advisor-prospects/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 27)
        self.assertEqual(response.data['totals']['assigned'], 27)
        self.assertEqual(len(response.data['results']), 25)
        self.assertIsNotNone(response.data['next'])
        self.assertNotIn('Hidden', str(response.data))
        self.assertNotIn('created_by_id', str(response.data))
        row = self.client.get('/api/assurance/advisor-prospects/?search=Prospect').data
        self.assertEqual(row['count'], 1)
        self.assertEqual(row['totals']['assigned'], 27)
        self.assertIsNotNone(row['results'][0]['appointment_id'])
        Contact.objects.filter(pk=self.row.contact_id).update(assigned_advisor_id=32)
        self.assertEqual(
            self.client.get('/api/assurance/advisor-prospects/?search=Prospect').data['count'], 0
        )
        self.fixture.auth(21, 'setter')
        self.assertEqual(self.client.get('/api/assurance/advisor-prospects/').status_code, 403)
