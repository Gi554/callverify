from datetime import timedelta
from uuid import uuid4
from django.test import TestCase, override_settings
from django.utils import timezone
from . import tests as fixtures
from .models import Appointment, AppointmentReport, Contact, ContactCallOutcome, FollowUpTask


@override_settings(DEBUG=True)
class ClientFolderTests(TestCase):
    def setUp(self):
        self.fixture = fixtures.ReportTests()
        self.fixture.setUp()
        self.fixture.auth(99, 'administrator')
        self.client = self.fixture.client
        self.row = self.fixture.appointment
        self.url = '/api/assurance/client-folders/31/'

    def clone(self, **changes):
        values = {
            f.attname: getattr(self.row, f.attname)
            for f in Appointment._meta.fields
            if not f.primary_key and f.name not in ('created_at', 'request_id')
        }
        return Appointment.objects.create(**{**values, 'request_id': uuid4(), **changes})

    def test_totals_are_disjoint_and_only_confirmed_attendance_counts(self):
        done = self.clone()
        AppointmentReport.objects.create(
            appointment=done, performed=True, sale_concluded=True, author_id=31
        )
        cancelled = self.clone(status='cancelled')
        AppointmentReport.objects.create(
            appointment=cancelled, performed=True, sale_concluded=True, author_id=31
        )
        absent = self.clone()
        AppointmentReport.objects.create(
            appointment=absent, performed=False, outcome='absent', author_id=31
        )
        other = self.clone()
        AppointmentReport.objects.create(
            appointment=other, performed=False, outcome='not_performed', author_id=31
        )
        future = timezone.now() + timedelta(days=3)
        self.clone(starts_at=future, ends_at=future + timedelta(hours=1), reschedule_count=1)
        self.clone(advisor_id=32)
        Contact.objects.create(
            name='Foreign secret', phone='private', created_by_id=21, assigned_advisor_id=32
        )
        data = self.client.get(self.url).data
        summary = data['summary']
        self.assertEqual(summary['prospects'], 1)
        self.assertEqual(summary['appointments'], 6)
        self.assertEqual(summary['sales'], 1)
        self.assertEqual(
            summary['statuses'],
            {
                'report_due': 1,
                'performed': 1,
                'cancelled': 1,
                'absent': 1,
                'not_performed': 1,
                'rescheduled': 1,
            },
        )
        self.assertNotIn('Foreign secret', str(data))
        page = self.client.get(self.url, {'section': 'appointments', 'status': 'absent'})
        self.assertEqual(page.data['count'], 1)
        self.assertEqual(page.data['results'][0]['setter_id'], 21)
        self.assertEqual(page.data['results'][0]['booked_by_id'], 99)
        self.assertEqual(page['Cache-Control'], 'no-store')

    def test_pagination_work_and_search_do_not_change_totals(self):
        for n in range(26):
            Contact.objects.create(
                name=f'Synthetic {n}', phone='raw', created_by_id=21, assigned_advisor_id=31
            )
        call = ContactCallOutcome.objects.create(
            contact=self.row.contact,
            setter_id=21,
            request_id=uuid4(),
            fingerprint='x',
            result='callback',
            note='Synthetic callback',
        )
        task = FollowUpTask.objects.create(
            appointment=self.row,
            setter_id=21,
            reason='Synthetic task',
            due_at=timezone.now() - timedelta(hours=1),
        )
        first = self.client.get(self.url).data
        self.assertEqual((first['count'], len(first['results'])), (27, 25))
        filtered = self.client.get(self.url, {'search': 'Synthetic 25'}).data
        self.assertEqual(filtered['count'], 1)
        self.assertEqual(filtered['summary']['prospects'], 27)
        self.assertEqual(filtered['summary']['open_tasks'], 1)
        self.assertEqual(filtered['summary']['overdue_tasks'], 1)
        calls = self.client.get(self.url, {'section': 'calls'}).data
        self.assertEqual(calls['results'][0]['actor_id'], call.setter_id)
        self.assertEqual(calls['results'][0]['note'], 'Synthetic callback')
        tasks = self.client.get(self.url, {'section': 'tasks'}).data
        self.assertEqual(tasks['results'][0]['contact_id'], self.row.contact_id)
        self.assertEqual(tasks['results'][0]['id'], task.pk)
        self.assertEqual(tasks['results'][0]['status'], 'overdue')
        self.assertEqual(
            self.client.get('/api/assurance/client-folders/', {'ids': '31,32'}).status_code, 200
        )

    def test_all_endpoints_are_admin_only_and_validate_inputs(self):
        for role in ('advisor', 'setter'):
            self.fixture.auth(31, role)
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(
                self.client.get('/api/assurance/client-folders/', {'ids': '31'}).status_code, 403
            )
        self.fixture.auth(99, 'administrator')
        for ids in ('', '-1', 'abc', '²', ','.join(['1'] * 26)):
            self.assertEqual(
                self.client.get('/api/assurance/client-folders/', {'ids': ids}).status_code, 400
            )
        self.assertEqual(self.client.get(self.url, {'section': 'secret'}).status_code, 400)
        self.client.credentials()
        self.assertIn(self.client.get(self.url).status_code, (401, 403))
