from datetime import timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase, override_settings
from . import tests as fixtures
from .models import Appointment, CalendlyBooking


@override_settings(DEBUG=True)
class CalendlyBookingTests(TestCase):
    setUp = fixtures.AppointmentTests.setUp
    authorize = fixtures.AppointmentTests.authorize
    proof = fixtures.AppointmentTests.proof
    payload = fixtures.AppointmentTests.payload

    def data(self, **changes):
        type(self.contact).objects.filter(pk=self.contact.pk).update(
            email='prospect@example.invalid'
        )
        return self.payload(
            starts_at=self.start.astimezone(ZoneInfo('America/Toronto')).isoformat(),
            ends_at=self.end.astimezone(ZoneInfo('America/Toronto')).isoformat(),
            timezone='America/Toronto',
            event_type='https://api.calendly.com/event_types/personal',
            **changes,
        )

    def confirmed(self):
        return {
            'state': 'confirmed',
            'appointment': {
                'starts_at': self.start.isoformat(),
                'ends_at': self.end.isoformat(),
                'status': 'scheduled',
            },
        }

    @patch('apps.assurance.backend.crm.calendly.bridge')
    def test_confirmed_booking_is_linked_idempotent_and_has_qualification(self, bridge):
        bridge.return_value = self.confirmed()
        payload = self.data()
        first = self.client.post('/api/assurance/calendly/book/', payload, format='json')
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.data['calendar'], 'calendly')
        self.assertEqual(first.data['timezone'], 'America/Toronto')
        self.assertEqual(first.data['contact']['id'], self.contact.pk)
        self.assertIn('qualification_snapshot', first.data)
        second = self.client.post('/api/assurance/calendly/book/', payload, format='json')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Appointment.objects.count(), 1)
        bridge.assert_called_once()
        row = Appointment.objects.get()
        for action, values in [('cancel', {'revision': 0, 'reason': 'x'}), ('reschedule', {})]:
            result = self.client.post(
                f'/api/assurance/appointments/{row.pk}/{action}/', values, format='json'
            )
            self.assertEqual(result.status_code, 409)

    @patch('apps.assurance.backend.crm.calendly.bridge')
    def test_pending_is_not_counted_as_booked_and_blocks_another_request(self, bridge):
        bridge.return_value = {'state': 'uncertain', 'appointment': None}
        payload = self.data()
        first = self.client.post('/api/assurance/calendly/book/', payload, format='json')
        self.assertEqual(first.status_code, 202, first.data)
        self.assertTrue(first.data['pending'])
        self.assertFalse(Appointment.objects.exists())
        duplicate = self.client.post('/api/assurance/calendly/book/', self.data(), format='json')
        self.assertEqual(duplicate.status_code, 409)
        bridge.return_value = self.confirmed()
        recovered = self.client.post('/api/assurance/calendly/book/', payload, format='json')
        self.assertEqual(recovered.status_code, 201, recovered.data)
        self.assertEqual(Appointment.objects.count(), 1)

    @patch('apps.assurance.backend.crm.calendly.bridge')
    def test_lease_assignment_and_montral_offset_are_enforced(self, bridge):
        payload = self.data()
        payload['starts_at'] = self.start.isoformat()
        result = self.client.post('/api/assurance/calendly/book/', payload, format='json')
        self.assertEqual(result.status_code, 400)
        self.authorize(22)
        self.assertIn(
            self.client.post(
                '/api/assurance/calendly/book/', self.data(), format='json'
            ).status_code,
            (400, 403),
        )
        self.authorize(21)
        self.assignment.active = False
        self.assignment.save()
        self.assertEqual(
            self.client.post(
                '/api/assurance/calendly/book/', self.data(), format='json'
            ).status_code,
            409,
        )
        bridge.assert_not_called()
        self.assertFalse(CalendlyBooking.objects.exists())

    @patch('apps.assurance.backend.crm.calendly.bridge')
    def test_slots_hide_crm_conflicts_and_reject_other_setter(self, bridge):
        bridge.return_value = {'slots': [self.start.isoformat()], 'duration': 30}
        self.authorize(22)
        query = {
            'assignment_id': self.assignment.pk,
            'contact_id': self.contact.pk,
            'start': self.start.isoformat(),
            'end': (self.start + timedelta(days=1)).isoformat(),
        }
        self.assertEqual(self.client.get('/api/assurance/calendly/slots/', query).status_code, 403)
        bridge.assert_not_called()
        self.authorize(21)
        response = self.client.get('/api/assurance/calendly/slots/', query)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['slots'], [self.start.isoformat()])
