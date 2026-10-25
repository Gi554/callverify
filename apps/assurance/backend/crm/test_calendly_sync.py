from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase, override_settings
from packages.calendar_connectors.calendly_bridge import proof
from .models import Appointment, AppointmentReport, CalendlyBooking, BusinessAudit, Contact
from .test_calendly import CalendlyBookingTests


@override_settings(DEBUG=True)
class CalendlySynchronizationTests(TestCase):
    setUp = CalendlyBookingTests.setUp
    authorize = CalendlyBookingTests.authorize
    proof = CalendlyBookingTests.proof
    payload = CalendlyBookingTests.payload
    data = CalendlyBookingTests.data
    ready = CalendlyBookingTests.ready

    def prepare(self):
        with patch(
            'apps.assurance.backend.crm.calendly.bridge', return_value={'state': 'uncertain'}
        ) as bridge:
            self.ready(bridge)
            response = self.client.post('/api/assurance/calendly/book/', self.data(), format='json')
            self.assertEqual(response.status_code, 202, response.data)
        self.booking = CalendlyBooking.objects.get()

    def delivery(self, revision=1, **changes):
        body = {
            'request_id': str(self.booking.pk),
            'owner': self.assignment.advisor_id,
            'revision': revision,
            'appointment': {
                'invitee': 'https://api.calendly.com/scheduled_events/event/invitees/invitee',
                'starts_at': self.start.isoformat(),
                'ends_at': self.end.isoformat(),
                'status': 'scheduled',
                'cancel_url': 'https://calendly.com/cancellations/token',
                'reschedule_url': 'https://calendly.com/reschedulings/token',
                **changes,
            },
        }
        return self.client.post(
            '/api/assurance/internal/calendly/', {'proof': proof('deliver', body)}, format='json'
        )

    def test_creation_reschedule_cancellation_and_replays_keep_one_appointment(self):
        self.prepare()
        self.assertEqual(self.delivery().status_code, 200)
        self.assertEqual(Appointment.objects.count(), 1)
        row = Appointment.objects.get()
        qualification = row.qualification_snapshot
        when = self.start + timedelta(days=1)
        result = self.delivery(
            2, starts_at=when.isoformat(), ends_at=(when + timedelta(minutes=30)).isoformat()
        )
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(self.delivery(1, status='cancelled').data['result'], 'duplicate')
        row.refresh_from_db()
        self.assertEqual(row.starts_at, when)
        self.assertEqual(row.reschedule_count, 1)
        self.assertEqual(row.status, 'scheduled')
        self.assertEqual(
            self.delivery(
                3,
                starts_at=when.isoformat(),
                ends_at=(when + timedelta(minutes=30)).isoformat(),
                status='cancelled',
            ).status_code,
            200,
        )
        self.assertEqual(self.delivery(3).data['result'], 'duplicate')
        row.refresh_from_db()
        self.assertEqual(row.status, 'cancelled')
        self.assertEqual(row.reschedule_count, 1)
        self.assertEqual(row.qualification_snapshot, qualification)
        self.assertEqual(Appointment.objects.count(), 1)
        self.assertEqual(
            BusinessAudit.objects.filter(action='appointment.calendly_cancelled').count(), 1
        )
        self.authorize(self.assignment.advisor_id, 'advisor')
        output = self.client.get(f'/api/assurance/appointments/{row.pk}/').data
        self.assertTrue(output['calendly']['cancel_url'].startswith('https://calendly.com/'))
        self.assertEqual(output['timezone'], 'America/Toronto')

    def test_unsigned_wrong_advisor_and_unsafe_links_never_modify_the_crm(self):
        self.prepare()
        self.assertEqual(
            self.client.post(
                '/api/assurance/internal/calendly/', {'proof': 'forged'}, format='json'
            ).status_code,
            403,
        )
        self.assertEqual(
            self.delivery(cancel_url='https://attacker.invalid/token').status_code, 400
        )
        body = {
            'request_id': str(self.booking.pk),
            'owner': 999,
            'revision': 1,
            'appointment': {
                'invitee': 'https://api.calendly.com/scheduled_events/event/invitees/invitee',
                'starts_at': self.start.isoformat(),
                'ends_at': self.end.isoformat(),
                'status': 'scheduled',
                'cancel_url': '',
                'reschedule_url': '',
            },
        }
        self.assertEqual(
            self.client.post(
                '/api/assurance/internal/calendly/',
                {'proof': proof('deliver', body)},
                format='json',
            ).status_code,
            403,
        )
        self.assertFalse(Appointment.objects.exists())

    def test_external_conflict_is_visible_and_does_not_hide_the_real_meeting(self):
        self.prepare()
        self.delivery()
        when = self.start + timedelta(days=1)
        other = Contact.objects.create(name='Other', phone='raw', created_by_id=21)
        Appointment.objects.create(
            request_id=uuid4(),
            fingerprint='other',
            contact=other,
            assignment=self.assignment,
            setter_id=21,
            setter_name='Setter',
            advisor_id=31,
            advisor_name='Advisor',
            booked_by_id=21,
            starts_at=when,
            ends_at=when + timedelta(minutes=30),
            timezone='America/Toronto',
        )
        self.assertEqual(
            self.delivery(
                2, starts_at=when.isoformat(), ends_at=(when + timedelta(minutes=30)).isoformat()
            ).status_code,
            200,
        )
        self.booking.refresh_from_db()
        self.assertTrue(self.booking.snapshot['sync_conflict'])
        self.assertEqual(self.booking.appointment.starts_at, when)
        self.assertEqual(Appointment.objects.count(), 2)

    def test_a_completed_report_is_preserved_and_flagged_for_review(self):
        self.prepare()
        self.delivery()
        row = Appointment.objects.get()
        AppointmentReport.objects.create(
            appointment=row,
            performed=True,
            outcome='performed',
            sale_concluded=True,
            note='Preserve the adviser report',
            author_id=31,
        )
        result = self.delivery(2, status='cancelled')
        self.assertEqual(result.data['result'], 'review')
        row.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(row.status, 'scheduled')
        self.assertTrue(row.report.performed)
        self.assertTrue(self.booking.snapshot['sync_review'])
        self.assertEqual(self.delivery(2, status='cancelled').data['result'], 'review')
