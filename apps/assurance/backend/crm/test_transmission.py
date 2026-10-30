from copy import deepcopy
from datetime import timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase, override_settings
from django.db import connection, close_old_connections
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from rest_framework.test import APIClient
from packages.access.tickets import issue
from . import tests as fixtures
from .models import (
    AdvisorSchedule,
    Appointment,
    AppointmentNotification,
    ContactCallOutcome,
    Contact,
)


@override_settings(DEBUG=True)
class TransmissionTests(TestCase):
    def setUp(self):
        self.source = fixtures.AppointmentTests(
            methodName='test_booking_is_idempotent_and_keeps_one_responsible_setter'
        )
        self.source.setUp()
        self.addCleanup(self.source.doCleanups)
        self.client = self.source.client
        self.contact = self.source.contact
        AdvisorSchedule.objects.create(
            pk=31, booking_url='https://bookings.cloud.microsoft/book/demo@example.com/'
        )
        self.url = '/api/assurance/appointments/transmit/'

    def payload(self):
        return self.source.payload(
            starts_at=self.source.start.astimezone(ZoneInfo('America/Toronto')).isoformat(),
            ends_at=self.source.end.astimezone(ZoneInfo('America/Toronto')).isoformat(),
            timezone='America/Toronto',
            contact_revision=0,
            meeting_type='video',
            external_confirmed=True,
            qualification={
                'age': 42,
                'profession': 'full_time',
                'has_children': True,
                'advisor_notes': 'Préparer la rencontre',
            },
        )

    def test_atomic_transmission_does_not_reserve_or_check_external_calendar(self):
        data = self.payload()
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.post(self.url, data, format='json').status_code, 200)
        self.source.external_check.assert_not_called()
        self.assertEqual(Appointment.objects.count(), 1)
        self.assertEqual(ContactCallOutcome.objects.get().result, 'appointment_booked')
        self.assertEqual(AppointmentNotification.objects.get().recipient_id, 31)
        self.contact.refresh_from_db()
        row = Appointment.objects.get()
        self.assertEqual(row.calendar, 'external_link')
        self.assertEqual(row.meeting_type, 'video')
        self.assertEqual(row.qualification_snapshot['qualification']['age'], 42)
        self.assertEqual(row.qualification_snapshot['contact_revision'], self.contact.revision)
        self.assertEqual(response.data['contact_revision'], self.contact.revision)
        self.assertTrue(response.data['call_outcome_recorded'])

    def test_failed_notification_rolls_back_qualification_appointment_and_outcome(self):
        with patch(
            'apps.assurance.backend.crm.appointments.AppointmentNotification.objects.create',
            side_effect=RuntimeError('storage'),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, self.payload(), format='json')
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.assurance_qualification, {})
        self.assertFalse(Appointment.objects.exists())
        self.assertFalse(ContactCallOutcome.objects.exists())

    def test_revision_link_confirmation_type_and_timezone_are_checked(self):
        data = self.payload()
        for changes, status in (
            ({'contact_revision': 9}, 409),
            ({'external_confirmed': False}, 400),
            ({'meeting_type': 'office'}, 400),
            ({'timezone': 'UTC'}, 400),
            ({'qualification': {'age': 999}}, 400),
        ):
            response = self.client.post(self.url, {**deepcopy(data), **changes}, format='json')
            self.assertEqual(response.status_code, status, response.data)
        AdvisorSchedule.objects.update(booking_url='')
        self.assertEqual(self.client.post(self.url, data, format='json').status_code, 400)
        self.assertFalse(Appointment.objects.exists())

    def test_assignment_permissions_overlap_and_notification_privacy(self):
        data = self.payload()
        self.assertEqual(self.client.post(self.url, data, format='json').status_code, 201)
        duplicate = self.payload()
        duplicate['contact_revision'] = 1
        self.assertEqual(self.client.post(self.url, duplicate, format='json').status_code, 409)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(32, 'assurance', 'advisor'))
        self.assertEqual(
            self.client.get('/api/assurance/appointment-notifications/').data['count'], 0
        )
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(31, 'assurance', 'advisor'))
        feed = self.client.get('/api/assurance/appointment-notifications/').data
        self.assertEqual(feed['count'], 1)
        row = feed['results'][0]
        path = f"/api/assurance/appointment-notifications/{row['id']}/read/"
        self.assertEqual(self.client.post(path).status_code, 200)
        self.assertEqual(self.client.post(self.url, data, format='json').status_code, 403)
        self.assertNotIn('SECRET SETTER', str(feed))

    def test_rebooking_retains_previous_occurrence_and_historical_notes(self):
        Contact.objects.filter(pk=self.contact.pk).update(
            assurance_qualification={'additional_notes': 'Ancienne note conservée'}
        )
        first = self.client.post(self.url, self.payload(), format='json')
        self.assertEqual(first.status_code, 201, first.data)
        data = self.payload()
        data['contact_revision'] = first.data['contact_revision']
        from django.utils.dateparse import parse_datetime

        for field in ('starts_at', 'ends_at'):
            data[field] = (parse_datetime(data[field]) + timedelta(days=1)).isoformat()
        second = self.client.post(self.url, data, format='json')
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(Appointment.objects.count(), 2)
        self.assertEqual(AppointmentNotification.objects.count(), 2)
        self.contact.refresh_from_db()
        self.assertEqual(
            self.contact.assurance_qualification['additional_notes'], 'Ancienne note conservée'
        )


@skipUnless(connection.vendor == 'postgresql', 'Concurrent transmission requires PostgreSQL')
@override_settings(DEBUG=True)
class TransmissionConcurrencyTests(TransactionTestCase):
    setUp = TransmissionTests.setUp
    payload = TransmissionTests.payload

    def test_two_identical_transmissions_record_one_qualification_and_notification(self):
        data = self.payload()

        def send(_):
            close_old_connections()
            try:
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(21, 'assurance', 'setter'))
                return client.post(self.url, data, format='json').status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(send, (1, 2))), [200, 201])
        self.assertEqual(Appointment.objects.count(), 1)
        self.assertEqual(AppointmentNotification.objects.count(), 1)
        self.assertEqual(ContactCallOutcome.objects.count(), 1)
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.revision, 1)
