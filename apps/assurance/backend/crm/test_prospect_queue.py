from datetime import timedelta
from uuid import uuid4
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import (
    Contact,
    ContactCallOutcome,
    Appointment,
    AppointmentReport,
    AdvisorAssignment,
    FollowUpTask,
)


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

    def test_call_session_progress_survives_reload_and_is_scoped_to_account(self):
        self.open.assigned_setter_id = 21
        self.open.save()
        second = Contact.objects.create(
            name='Second active synthetic',
            phone='5145550104',
            created_by_id=21,
            assigned_setter_id=21,
        )
        started = self.client.post(
            '/api/assurance/call-session/', {'action': 'start'}, format='json'
        )
        self.assertEqual(started.status_code, 200, started.data)
        began = self.client.post(
            '/api/assurance/call-session/',
            {'action': 'begin', 'contact_id': self.open.pk},
            format='json',
        )
        self.assertEqual(began.status_code, 200, began.data)
        self.assertEqual(
            self.client.get('/api/assurance/call-session/').data['current_id'], self.open.pk
        )
        conflict = self.client.post(
            '/api/assurance/call-session/',
            {'action': 'begin', 'contact_id': second.pk},
            format='json',
        )
        self.assertEqual(conflict.status_code, 409)
        completed = self.client.post(
            '/api/assurance/call-session/',
            {'action': 'complete', 'contact_id': self.open.pk},
            format='json',
        )
        self.assertEqual(completed.status_code, 200, completed.data)
        self.assertEqual(completed.data['visited_ids'], [self.open.pk])
        self.assertIsNone(completed.data['current_id'])
        duplicate = self.client.post(
            '/api/assurance/call-session/',
            {'action': 'begin', 'contact_id': self.open.pk},
            format='json',
        )
        self.assertEqual(duplicate.status_code, 409)
        self.declined.assigned_setter_id = 21
        self.declined.save()
        blocked = self.client.post(
            '/api/assurance/call-session/',
            {'action': 'begin', 'contact_id': self.declined.pk},
            format='json',
        )
        self.assertEqual(blocked.status_code, 400)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(22, 'assurance', 'setter'))
        other_account = self.client.get('/api/assurance/call-session/')
        self.assertEqual(other_account.status_code, 200)
        self.assertEqual(other_account.data['visited_ids'], [])

    def test_new_callback_result_stays_out_until_its_follow_up_is_due(self):
        task = FollowUpTask.objects.create(
            contact=self.declined,
            setter_id=21,
            reason='Rappel demandé',
            due_at=timezone.now() + timedelta(hours=1),
        )
        ContactCallOutcome.objects.create(
            contact=self.declined,
            setter_id=21,
            request_id=uuid4(),
            fingerprint='new',
            result='callback',
            task=task,
        )
        self.appointment.status = 'cancelled'
        self.appointment.save()
        self.assertEqual(
            self.client.get('/api/assurance/contacts/', {'queue': 'active'}).data['count'], 2
        )
        self.assertEqual(
            self.client.get('/api/assurance/contacts/', {'queue': 'callbacks'}).data['count'], 0
        )
        self.assertEqual(
            self.client.get('/api/assurance/contacts/', {'queue': 'bad'}).status_code, 400
        )

    def test_a_later_result_does_not_reopen_a_contact_declined_earlier(self):
        ContactCallOutcome.objects.create(
            contact=self.declined,
            setter_id=21,
            request_id=uuid4(),
            fingerprint='later',
            result='voicemail',
            note='Résultat plus récent, refus antérieur conservé',
        )
        active = self.client.get('/api/assurance/contacts/', {'queue': 'active'}).data['results']
        self.assertNotIn(self.declined.pk, [row['id'] for row in active])
        all_rows = self.client.get('/api/assurance/contacts/', {'queue': 'all'}).data['results']
        self.assertEqual(
            next(row for row in all_rows if row['id'] == self.declined.pk)['queue_reason'],
            'not_interested',
        )

    def test_attended_contact_remains_excluded_even_if_appointment_is_cancelled(self):
        appointment = self.appointment
        AppointmentReport.objects.create(
            appointment=appointment, performed=True, author_id=31, outcome='performed'
        )
        appointment.status = 'cancelled'
        appointment.save()
        active = self.client.get('/api/assurance/contacts/', {'queue': 'active'}).data['results']
        self.assertNotIn(self.booked.pk, [row['id'] for row in active])
        all_rows = self.client.get('/api/assurance/contacts/', {'queue': 'all'}).data['results']
        self.assertEqual(
            next(row for row in all_rows if row['id'] == self.booked.pk)['queue_reason'],
            'appointment_attended',
        )

    def test_advisor_scope_is_not_expanded_by_all_queue(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(31, 'assurance', 'advisor'))
        self.assertEqual(self.client.get('/api/assurance/contacts/').data['count'], 1)
        self.assertEqual(
            self.client.get('/api/assurance/contacts/', {'queue': 'all'}).status_code, 403
        )
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(32, 'assurance', 'advisor'))
        self.assertEqual(self.client.get('/api/assurance/contacts/').data['count'], 0)
