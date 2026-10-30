from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from django.db import connection, close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import AdvisorAssignment, AdvisorSchedule, BusinessAudit


@override_settings(DEBUG=True)
class BookingLinkTests(TestCase):
    def setUp(self):
        self.assignment = AdvisorAssignment.objects.create(
            setter_id=21, setter_name='Setter', advisor_id=31, advisor_name='Conseiller'
        )
        self.client = APIClient()

    def auth(self, pk=31, role='advisor'):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, 'assurance', role))

    def test_self_link_shared_with_assigned_setter_and_admin_can_update_it(self):
        self.auth()
        url = '/api/assurance/advisor-booking-link/'
        self.assertEqual(self.client.get(url).data, {'url': '', 'revision': 0})
        link = 'https://bookings.cloud.microsoft/book/Conseiller@example.com/?ismsaljsauthenabled'
        self.assertEqual(self.client.post(url, {'url': link, 'revision': 0}).status_code, 200)
        self.auth(21, 'setter')
        rows = self.client.get('/api/assurance/assignments/').data['results']
        self.assertEqual(rows[0]['booking_url'], link)
        path = f'/api/assurance/assignments/{self.assignment.pk}/booking-link/'
        self.assertEqual(self.client.get(path).data['url'], link)
        self.assertEqual(self.client.post(path, {'url': '', 'revision': 1}).status_code, 403)
        self.auth(99, 'administrator')
        self.assertEqual(self.client.post(path, {'url': '', 'revision': 1}).status_code, 200)
        self.assertEqual(AdvisorSchedule.objects.get().booking_url, '')
        self.assertEqual(
            BusinessAudit.objects.filter(action='advisor.booking_link_changed').count(), 2
        )
        self.assertNotIn(link, str(list(BusinessAudit.objects.values('metadata'))))

    def test_link_is_scoped_and_suspended_assignments_are_hidden(self):
        self.auth()
        self.client.post(
            '/api/assurance/advisor-booking-link/',
            {'url': 'https://calendly.com/demo', 'revision': 0},
        )
        self.auth(32)
        self.assertEqual(self.client.get('/api/assurance/advisor-booking-link/').data['url'], '')
        self.auth(22, 'setter')
        path = f'/api/assurance/assignments/{self.assignment.pk}/booking-link/'
        self.assertEqual(self.client.get(path).status_code, 404)
        self.auth(21, 'setter')
        self.assertEqual(self.client.get('/api/assurance/advisor-booking-link/').status_code, 403)
        AdvisorAssignment.objects.update(active=False)
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_invalid_link_stale_revision_and_foreign_fields_are_rejected(self):
        self.auth()
        path = '/api/assurance/advisor-booking-link/'
        for link in (
            'javascript:alert(1)',
            'http://calendly.com/demo',
            'https://user:password@example.com/a',
            '/relative',
        ):
            self.assertEqual(self.client.post(path, {'url': link, 'revision': 0}).status_code, 400)
        self.assertEqual(
            self.client.post(path, {'url': '', 'revision': 0, 'advisor_id': 32}).status_code, 400
        )
        data = {'url': 'https://calendly.com/demo', 'revision': 0}
        self.assertEqual(self.client.post(path, data).status_code, 200)
        self.assertEqual(self.client.post(path, data).status_code, 409)
        self.assertEqual(AdvisorSchedule.objects.get().booking_revision, 1)


@skipUnless(connection.vendor == 'postgresql', 'Concurrent link updates require PostgreSQL')
@override_settings(DEBUG=True)
class BookingLinkConcurrencyTests(TransactionTestCase):
    def test_stale_editor_cannot_overwrite_a_concurrent_update(self):
        AdvisorSchedule.objects.create(pk=31)

        def update(value):
            close_old_connections()
            try:
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(31, 'assurance', 'advisor'))
                return client.post(
                    '/api/assurance/advisor-booking-link/',
                    {'url': f'https://calendly.com/{value}', 'revision': 0},
                ).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(update, ('a', 'b'))), [200, 409])
