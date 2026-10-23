from datetime import timedelta
from uuid import uuid4
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import (
    Contact,
    ContactNote,
    ContactDocument,
    AdvisorAssignment,
    Appointment,
    AppointmentReport,
    AppointmentIncident,
    BusinessAudit,
)


@override_settings(DEBUG=True)
class InteractionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.contact = Contact.objects.create(name='Contact', phone='raw', created_by_id=21)
        self.url = f'/api/assurance/contacts/{self.contact.pk}/interactions/'
        self.auth(99, 'administrator')
        self.appointments = []
        for setter, advisor in ((21, 31), (22, 32)):
            assignment = AdvisorAssignment.objects.create(
                setter_id=setter,
                setter_name='SECRET SETTER',
                advisor_id=advisor,
                advisor_name='Advisor',
            )
            appointment = Appointment.objects.create(
                request_id=uuid4(),
                fingerprint='secret fingerprint',
                contact=self.contact,
                assignment=assignment,
                setter_id=setter,
                setter_name='SECRET SETTER',
                advisor_id=advisor,
                advisor_name='Advisor',
                booked_by_id=99,
                starts_at=timezone.now() - timedelta(hours=2),
                ends_at=timezone.now() - timedelta(hours=1),
                timezone='UTC',
            )
            self.appointments.append(appointment)
            AppointmentReport.objects.create(
                appointment=appointment, performed=True, note=f'report-{advisor}', author_id=advisor
            )
            AppointmentIncident.objects.create(
                appointment=appointment,
                request_id=uuid4(),
                note=f'incident-{advisor}',
                author_id=advisor,
            )
        for author, channel, body in (
            (21, 'internal', 'INTERNAL SECRET'),
            (31, 'advisor', 'own advisor note'),
            (32, 'advisor', 'other advisor note'),
        ):
            ContactNote.objects.create(
                contact=self.contact,
                request_id=uuid4(),
                author_id=author,
                channel=channel,
                body=body,
            )
            ContactDocument.objects.create(
                contact=self.contact,
                request_id=uuid4(),
                author_id=author,
                channel=channel,
                filename=body + '.pdf',
                content_type='application/pdf',
                size=4,
                sha256='secret hash',
                content=b'secret bytes',
            )

    def auth(self, pk, role, workspace='assurance'):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, workspace, role))

    def test_administrator_combines_five_sources_without_private_metadata(self):
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['count'], 12)
        self.assertEqual(result['Cache-Control'], 'no-store')
        self.assertEqual(
            {r['event_type'] for r in result.data['results']},
            {'note', 'document', 'appointment', 'report', 'incident'},
        )
        for row in result.data['results']:
            self.assertEqual(
                set(row),
                {
                    'event_type',
                    'event_id',
                    'occurred_at',
                    'detail',
                    'state',
                    'reference_id',
                    'actor_id',
                },
            )
        self.assertEqual({row['actor_id'] for row in result.data['results']}, {21, 31, 32, 99})
        for value in (
            'SECRET SETTER',
            'author_id',
            'setter_id',
            'secret bytes',
            'secret hash',
            'secret fingerprint',
        ):
            self.assertNotIn(value, str(result.data))

    def test_advisor_only_own_appointments_and_personal_notes_documents(self):
        self.auth(31, 'advisor')
        result = self.client.get(self.url)
        self.assertEqual(result.data['count'], 5)
        self.assertTrue(all('actor_id' not in row for row in result.data['results']))
        text = str(result.data)
        self.assertIn('own advisor note', text)
        for value in (
            'INTERNAL SECRET',
            'other advisor note',
            'report-32',
            'incident-32',
            'SECRET SETTER',
        ):
            self.assertNotIn(value, text)
        refs = [
            r['reference_id']
            for r in result.data['results']
            if r['event_type'] in ('appointment', 'report', 'incident')
        ]
        self.assertEqual(set(refs), {self.appointments[0].pk})

    def test_setter_has_internal_content_and_own_appointments_only(self):
        self.auth(21, 'setter')
        result = self.client.get(self.url)
        self.assertEqual(result.data['count'], 5)
        self.assertTrue(all('actor_id' not in row for row in result.data['results']))
        text = str(result.data)
        self.assertIn('INTERNAL SECRET', text)
        for value in ('own advisor note', 'other advisor note', 'report-32', 'incident-32'):
            self.assertNotIn(value, text)

    def test_scope_direct_access_and_other_workspace_are_enforced(self):
        self.auth(33, 'advisor')
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.auth(31, 'advisor', 'isolation')
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_type_and_date_filters_inclusive_and_strict(self):
        note = ContactNote.objects.first()
        instant = note.created_at.isoformat()
        ContactNote.objects.exclude(pk=note.pk).update(
            created_at=note.created_at + timedelta(seconds=1)
        )
        result = self.client.get(self.url, {'type': 'note', 'after': instant, 'before': instant})
        self.assertEqual(result.data['count'], 1)
        self.assertEqual(result.data['results'][0]['event_id'], note.pk)
        self.assertEqual(self.client.get(self.url, {'type': 'appointment'}).data['count'], 2)
        for query in (
            {'type': 'audit'},
            {'after': 'bad'},
            {'before': '2026-10-01T00:00:00'},
            {'after': '2026-12-01T00:00:00Z', 'before': '2026-10-01T00:00:00Z'},
        ):
            self.assertEqual(self.client.get(self.url, query).status_code, 400, query)

    def test_pagination_stable_when_timestamps_match_and_read_only(self):
        at = timezone.now()
        for n in range(30):
            ContactNote.objects.create(
                contact=self.contact,
                request_id=uuid4(),
                author_id=21,
                channel='internal',
                body=f'note {n}',
            )
        ContactNote.objects.update(created_at=at)
        first = self.client.get(self.url, {'type': 'note'}).data
        second = self.client.get(self.url, {'type': 'note', 'page': 2}).data
        ids = [r['event_id'] for r in first['results'] + second['results']]
        self.assertEqual(ids, sorted(ids, reverse=True))
        self.assertEqual(len(set(ids)), 33)
        self.assertEqual(len(first['results']), 25)
        self.assertEqual(
            self.client.get(self.url, {'type': 'note'}).data['results'], first['results']
        )
        count = BusinessAudit.objects.count()
        self.assertEqual(self.client.post(self.url, {}, format='json').status_code, 405)
        self.assertEqual(BusinessAudit.objects.count(), count)

    def test_cancelled_appointment_and_foreign_contact_do_not_disappear_or_leak(self):
        Appointment.objects.filter(pk=self.appointments[0].pk).update(status='cancelled')
        other = Contact.objects.create(name='Foreign', phone='other', created_by_id=99)
        ContactNote.objects.create(
            contact=other,
            request_id=uuid4(),
            author_id=21,
            channel='internal',
            body='FOREIGN CONTACT SECRET',
        )
        self.auth(31, 'advisor')
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200)
        row = next(r for r in result.data['results'] if r['event_type'] == 'appointment')
        self.assertEqual(row['state'], 'cancelled')
        self.assertNotIn('FOREIGN CONTACT SECRET', str(result.data))
