from datetime import timedelta
from uuid import uuid4
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import Contact, ContactCallOutcome, Appointment, AdvisorAssignment


@override_settings(DEBUG=True)
class ProspectQueueTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(21, 'assurance', 'setter'))
        self.open = Contact.objects.create(
            name='Active synthetic', phone='5145550101', created_by_id=21
        )
        self.declined = Contact.objects.create(
            name='Declined synthetic', phone='5145550102', created_by_id=21
        )
        self.booked = Contact.objects.create(
            name='Booked synthetic', phone='5145550103', created_by_id=21
        )
        ContactCallOutcome.objects.create(
            contact=self.declined,
            setter_id=21,
            request_id=uuid4(),
            fingerprint='test',
            result='not_interested',
            note='Synthetic note',
        )
        assignment = AdvisorAssignment.objects.create(
            setter_id=21, setter_name='Setter', advisor_id=31, advisor_name='Advisor'
        )
        self.appointment = Appointment.objects.create(
            contact=self.booked,
            assignment=assignment,
            request_id=uuid4(),
            fingerprint='test',
            setter_id=21,
            setter_name='Setter',
            advisor_id=31,
            advisor_name='Advisor',
            booked_by_id=21,
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=1),
            timezone='UTC',
        )

    def test_active_queue_excludes_bookings_and_latest_decline_without_deleting(self):
        response = self.client.get(
            '/api/assurance/contacts/', {'queue': 'active', 'status': 'to_contact'}
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([row['id'] for row in response.data['results']], [self.open.pk])
        all_rows = self.client.get('/api/assurance/contacts/', {'queue': 'all'}).data['results']
        self.assertEqual(
            {row['id']: row['queue_reason'] for row in all_rows},
            {
                self.open.pk: '',
                self.declined.pk: 'not_interested',
                self.booked.pk: 'appointment_booked',
            },
        )
        self.assertEqual(Contact.objects.count(), 3)
        self.assertEqual(
            self.client.get(f'/api/assurance/contacts/{self.declined.pk}/').status_code, 200
        )
        self.assertEqual(ContactCallOutcome.objects.get(contact=self.declined).setter_id, 21)
        self.client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + issue(10, 'assurance', 'administrator')
        )
        events = self.client.get(f'/api/assurance/contacts/{self.declined.pk}/interactions/').data[
            'results'
        ]
        self.assertEqual(events[0]['actor_id'], 21)
        self.assertEqual(events[0]['detail'], 'Synthetic note')
        export = self.client.get(
            '/api/assurance/contacts/export/', {'queue': 'active', 'file': 'csv'}
        )
        self.assertEqual(export.status_code, 200)
        self.assertNotIn('Declined synthetic', export.content.decode('utf-8-sig'))
        self.assertNotIn('Booked synthetic', export.content.decode('utf-8-sig'))

    def test_new_explicit_result_reopens_decline_and_cancelled_booking_is_not_hidden(self):
        ContactCallOutcome.objects.create(
            contact=self.declined,
            setter_id=21,
            request_id=uuid4(),
            fingerprint='new',
            result='callback',
        )
        self.appointment.status = 'cancelled'
        self.appointment.save()
        self.assertEqual(
            self.client.get('/api/assurance/contacts/', {'queue': 'active'}).data['count'], 3
        )
        self.assertEqual(
            self.client.get('/api/assurance/contacts/', {'queue': 'bad'}).status_code, 400
        )

    def test_advisor_scope_is_not_expanded_by_all_queue(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(31, 'assurance', 'advisor'))
        self.assertEqual(self.client.get('/api/assurance/contacts/').data['count'], 1)
        self.assertEqual(
            self.client.get('/api/assurance/contacts/', {'queue': 'all'}).status_code, 403
        )
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(32, 'assurance', 'advisor'))
        self.assertEqual(self.client.get('/api/assurance/contacts/').data['count'], 0)
