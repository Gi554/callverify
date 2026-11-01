from datetime import timedelta
from uuid import uuid4
from django.test import TestCase, override_settings
from . import tests as fixtures
from .models import Appointment, AppointmentReport, FollowUpTask, ContactImport


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class AdminActivityTests(TestCase):
    setUp = fixtures.StatisticsTests.setUp
    auth = fixtures.StatisticsTests.auth

    def test_combined_filters_and_callback_due_dates_are_applied(self):
        batch = ContactImport.objects.create(
            request_id=uuid4(),
            fingerprint='x',
            filename='Campagne test',
            created_by_id=99,
            total=1,
            imported=1,
            rejected=0,
        )
        self.row.contact.import_batch = batch
        self.row.contact.save()
        AppointmentReport.objects.create(
            appointment=self.row,
            performed=True,
            sale_concluded=True,
            outcome='completed',
            note='',
            author_id=31,
        )
        Appointment.objects.create(
            **{**self.base, 'setter_id': 22},
            request_id=uuid4(),
            starts_at=self.now - timedelta(hours=4),
            ends_at=self.now - timedelta(hours=3),
        )
        FollowUpTask.objects.create(
            appointment=self.row, setter_id=21, reason='PRIVATE', due_at=self.now
        )
        args = {
            'from': str((self.now - timedelta(days=1)).date()),
            'to': str((self.now + timedelta(days=1)).date()),
            'setter_id': '21',
            'advisor_id': '31',
            'campaign_id': str(batch.pk),
        }
        result = self.client.get(self.url, args)
        self.assertEqual(result.status_code, 200, result.data)
        data = result.data
        self.assertEqual(data['totals']['appointments'], 1)
        self.assertEqual(data['totals']['closed'], 1)
        self.assertEqual(data['pending_callbacks'], 1)
        self.assertEqual(sum(x['appointments'] for x in data['daily']), 1)
        self.assertNotIn('PRIVATE', str(data))
        self.assertEqual(
            data['filter_options']['campaign_id'], [{'id': batch.pk, 'name': 'Campagne test'}]
        )
        self.assertEqual(
            self.client.get(self.url, {**args, 'advisor_id': '999'}).data['pending_callbacks'], 0
        )

    def test_explicit_false_sale_and_unknown_sale_stay_distinct(self):
        report = AppointmentReport.objects.create(
            appointment=self.row,
            performed=True,
            sale_concluded=None,
            outcome='completed',
            note='',
            author_id=31,
        )
        data = self.client.get(self.url).data['totals']
        self.assertEqual(data['closure_unknown'], 1)
        self.assertEqual(data['updates_due'], 1)
        self.assertEqual(data['not_closed'], 0)
        report.sale_concluded = False
        report.save()
        data = self.client.get(self.url).data['totals']
        self.assertEqual(data['not_closed'], 1)
        self.assertEqual(data['updates_due'], 0)

    def test_setter_cannot_use_admin_filters_or_read_team_options(self):
        self.assertEqual(self.client.get(self.url, {'campaign_id': 'bad'}).status_code, 400)
        self.auth(21, 'setter')
        self.assertNotIn('filter_options', self.client.get(self.url).data)
        self.assertEqual(self.client.get(self.url, {'setter_id': '22'}).status_code, 403)
