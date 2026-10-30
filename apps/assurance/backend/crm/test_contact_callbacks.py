from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import (
    Contact,
    ContactCallOutcome,
    FollowUpTask,
    TaskNotification,
    ReminderEvent,
)


@override_settings(DEBUG=True)
class ContactCallbackTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.auth(21)
        self.contact = Contact.objects.create(
            name='Prospect rappel', phone='5145550123', created_by_id=21
        )
        self.base = f'/api/assurance/contacts/{self.contact.pk}/'
        self.token = self.client.post(self.base + 'lease/', {}, format='json').data['token']
        self.due = (timezone.now() + timedelta(days=1)).isoformat()

    def auth(self, pk, role='setter'):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, 'assurance', role))

    def payload(self, **changes):
        return {'token': self.token, 'contact_revision': 0, 'request_id': str(uuid4()), **changes}

    def callback(self, **changes):
        return self.client.post(
            self.base + 'call-outcomes/',
            self.payload(result='callback', note='Après 17 h', due_at=self.due, **changes),
            format='json',
        )

    def test_callback_creates_exactly_one_task_and_internal_notification_on_retry(self):
        body = self.payload(result='callback', note='Après 17 h', due_at=self.due)
        first = self.client.post(self.base + 'call-outcomes/', body, format='json')
        self.assertEqual(first.status_code, 201, first.data)
        retry = self.client.post(self.base + 'call-outcomes/', body, format='json')
        self.assertEqual(retry.status_code, 200, retry.data)
        self.assertEqual(FollowUpTask.objects.count(), 1)
        self.assertEqual(ContactCallOutcome.objects.count(), 1)
        self.assertEqual(TaskNotification.objects.count(), 1)
        task = FollowUpTask.objects.get()
        self.assertEqual(task.contact_id, self.contact.pk)
        self.assertIsNone(task.appointment_id)
        self.assertEqual(task.setter_id, 21)
        body['note'] = 'Autre'
        self.assertEqual(
            self.client.post(self.base + 'call-outcomes/', body, format='json').status_code, 409
        )
        self.assertEqual(
            self.client.get('/api/assurance/follow-ups/summary/?state=all').data['open'], 1
        )

    def test_all_non_booking_results_are_declared_without_changing_technical_or_commercial_state(
        self,
    ):
        for result in [
            'voicemail',
            'invalid_number',
            'disconnected',
            'not_interested',
            'unreachable',
            'other',
        ]:
            response = self.client.post(
                self.base + 'call-outcomes/',
                self.payload(result=result, note='Observation'),
                format='json',
            )
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data['source'], 'setter_declared')
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.status, 'to_contact')
        self.assertEqual(FollowUpTask.objects.count(), 0)

    def test_manual_callback_note_is_optional(self):
        response = self.client.post(
            self.base + 'follow-ups/', self.payload(due_at=self.due), format='json'
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(FollowUpTask.objects.get().reason, '')

    def test_manual_task_can_be_edited_closed_and_seen_in_contact_history(self):
        body = self.payload(reason='Rappeler le contact', due_at=self.due, priority='high')
        first = self.client.post(self.base + 'follow-ups/', body, format='json')
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(
            self.client.post(self.base + 'follow-ups/', body, format='json').status_code, 200
        )
        url = f"/api/assurance/follow-ups/{first.data['id']}/"
        edited = self.client.post(
            url + 'edit/?state=all',
            {'revision': 0, 'reason': 'Demain matin', 'due_at': self.due, 'priority': 'urgent'},
            format='json',
        )
        self.assertEqual(edited.status_code, 200, edited.data)
        self.assertEqual(edited.data['revision'], 1)
        self.assertEqual(
            self.client.post(
                url + 'edit/?state=all',
                {'revision': 0, 'reason': 'Périmé', 'due_at': self.due},
                format='json',
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.post(
                url + 'close/?state=all',
                {'revision': 1, 'resolution': 'Prospect joint'},
                format='json',
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(self.base + 'follow-ups/').data['results'][0]['resolution'],
            'Prospect joint',
        )
        self.assertEqual(self.client.get(self.base + 'interactions/?type=task').data['count'], 1)
        self.assertEqual(self.client.get('/api/assurance/dashboard/').data['open_follow_ups'], 0)
        self.auth(22)
        self.assertEqual(
            self.client.post(
                url + 'edit/?state=all',
                {'revision': 2, 'reason': 'Intrusion', 'due_at': self.due},
                format='json',
            ).status_code,
            404,
        )
        self.assertEqual(self.client.get(self.base + 'follow-ups/').data['count'], 0)

    def test_invalid_dates_lease_and_appointment_claims_are_rejected(self):
        for changes in (
            {'due_at': self.due[:19]},
            {'due_at': (timezone.now() - timedelta(days=1)).isoformat()},
            {'result': 'invented'},
            {'token': str(uuid4())},
            {'contact_revision': 99},
        ):
            body = self.payload(result='callback', due_at=self.due)
            body.update(changes)
            self.assertIn(
                self.client.post(self.base + 'call-outcomes/', body, format='json').status_code,
                (400, 409),
            )
        for body in (
            self.payload(result='appointment_booked'),
            self.payload(result='appointment_booked', appointment_id=999),
            self.payload(result='voicemail', due_at=self.due),
        ):
            self.assertEqual(
                self.client.post(self.base + 'call-outcomes/', body, format='json').status_code, 400
            )
        self.assertFalse(FollowUpTask.objects.exists())

    def test_failed_audit_rolls_back_callback_and_result(self):
        with patch(
            'apps.assurance.backend.crm.contact_followups.BusinessAudit.objects.create',
            side_effect=RuntimeError('audit'),
        ):
            with self.assertRaises(RuntimeError):
                self.callback()
        self.assertFalse(FollowUpTask.objects.exists())
        self.assertFalse(ContactCallOutcome.objects.exists())
        self.assertFalse(TaskNotification.objects.exists())

    def test_other_setter_and_advisor_cannot_read_internal_outcomes_or_mutate_tasks(self):
        self.callback()
        self.auth(22)
        self.assertEqual(self.client.get(self.base + 'call-outcomes/').data['count'], 0)
        self.assertEqual(
            self.client.get(self.base + 'interactions/?type=call_result').data['count'], 0
        )
        self.assertEqual(self.callback().status_code, 409)
        self.auth(31, 'advisor')
        self.assertIn(self.client.get(self.base + 'call-outcomes/').status_code, (403, 404))

    def test_overdue_reminder_generation_accepts_contact_task_without_appointment(self):
        self.callback()
        FollowUpTask.objects.update(due_at=timezone.now() - timedelta(hours=1))
        from .reminders import generate

        generate()
        self.assertTrue(
            ReminderEvent.objects.filter(
                task__contact=self.contact, appointment__isnull=True
            ).exists()
        )
        reminder = self.client.get('/api/assurance/reminders/')
        self.assertEqual(reminder.status_code, 200)

    def test_booked_result_requires_the_setters_existing_appointment(self):
        from .models import Appointment, AdvisorAssignment

        assignment = AdvisorAssignment.objects.create(
            setter_id=21, setter_name='Setter', advisor_id=31, advisor_name='Conseiller'
        )
        appointment = Appointment.objects.create(
            contact=self.contact,
            assignment=assignment,
            request_id=uuid4(),
            fingerprint='test',
            setter_id=21,
            setter_name='Setter',
            advisor_id=31,
            advisor_name='Conseiller',
            booked_by_id=21,
            starts_at=timezone.now() + timedelta(days=2),
            ends_at=timezone.now() + timedelta(days=2, hours=1),
            timezone='UTC',
        )
        body = self.payload(result='appointment_booked', appointment_id=appointment.pk)
        response = self.client.post(self.base + 'call-outcomes/', body, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['appointment_id'], appointment.pk)
        self.assertFalse(FollowUpTask.objects.exists())
        appointment.status = 'cancelled'
        appointment.save()
        self.assertEqual(
            self.client.post(
                self.base + 'call-outcomes/',
                self.payload(result='appointment_booked', appointment_id=appointment.pk),
                format='json',
            ).status_code,
            400,
        )

    def test_manual_notification_read_and_admin_reassignment_keep_source(self):
        task = self.callback().data['task_id']
        notification = TaskNotification.objects.get()
        self.assertEqual(
            self.client.post(
                f'/api/assurance/notifications/{notification.pk}/read/', {}, format='json'
            ).status_code,
            200,
        )
        self.auth(99, 'administrator')
        from packages.access.followups import issue_owner

        response = self.client.post(
            f'/api/assurance/follow-ups/{task}/reassign/?state=all',
            {
                'revision': 0,
                'proof': issue_owner(99, task, 22, 'Nouveau setter'),
                'reason': 'Attribution',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data['appointment_id'])
        self.assertIsNone(response.data['original_setter_id'])
        history = self.client.get(f'/api/assurance/follow-ups/{task}/history/?state=all')
        self.assertEqual(history.status_code, 200)
        self.assertTrue(history.data['count'] >= 2)
        self.auth(21)
        self.assertEqual(self.client.get(self.base + 'follow-ups/').data['count'], 0)
        self.auth(22)
        self.assertEqual(self.client.get(self.base + 'follow-ups/').data['count'], 1)
