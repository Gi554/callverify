from datetime import timedelta
from uuid import uuid4
from django.test import TestCase, override_settings
from django.utils import timezone
from . import test_isolation_statistics as fixtures
from .models import IsolationVisit, IsolationVisitResult, IsolationFollowUp


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class AdminActivityTests(TestCase):
    setUp = fixtures.IsolationStatisticsTests.setUp
    auth = fixtures.IsolationStatisticsTests.auth
    visit = fixtures.IsolationStatisticsTests.visit

    def test_combined_filters_scope_totals_groups_previous_daily_and_callbacks(self):
        row = self.visit(performed=True)
        IsolationVisitResult.objects.filter(visit=row).update(closed=True)
        IsolationVisit.objects.filter(pk=row.pk).update(closer_id=41, closer_name='Représentant')
        self.visit(setter=22, client=73)
        IsolationFollowUp.objects.create(
            prospect=self.prospect,
            request_id=uuid4(),
            fingerprint='test',
            due_at=self.day,
            note='PRIVATE',
        )
        args = {
            'setter_id': '21',
            'client_id': '72',
            'closer_id': '41',
            'campaign_id': str(self.prospect.campaign_id),
        }
        data = self.client.get(self.url, args).data
        self.assertEqual(data['totals']['visits'], 1)
        self.assertEqual(data['totals']['closed'], 1)
        self.assertEqual(data['pending_callbacks'], 1)
        self.assertEqual(sum(x['visits'] for x in data['daily']), 1)
        self.assertEqual(data['setters']['count'], 1)
        self.assertNotIn('PRIVATE', str(data))
        self.assertEqual(data['applied_filters']['setter_id'], 21)
        self.assertEqual(
            self.client.get(self.url, {**args, 'client_id': '999'}).data['totals']['visits'], 0
        )
        self.assertEqual(
            self.client.get(self.url, {**args, 'client_id': '999'}).data['pending_callbacks'], 0
        )

    def test_result_due_includes_explicit_presence_with_unknown_sale_but_never_future_or_cancelled(
        self,
    ):
        self.visit(performed=True)
        self.visit(performed=True, status='cancelled')
        future = self.visit(performed=True)
        IsolationVisit.objects.filter(pk=future.pk).update(
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=1),
        )
        data = self.client.get(
            self.url, {'to': str((timezone.now() + timedelta(days=2)).date())}
        ).data
        self.assertEqual(data['totals']['updates_due'], 1)
        self.assertEqual(data['totals']['not_closed'], 0)
        self.assertEqual(data['totals']['not_performed'], 0)

    def test_filter_validation_and_non_admin_never_expose_team_options(self):
        self.visit()
        for invalid in ('-1', 'x', '0', '9223372036854775808'):
            self.assertEqual(self.client.get(self.url, {'setter_id': invalid}).status_code, 400)
        for role, pk in [('setter', 21), ('client', 72), ('closer', 41)]:
            self.auth(pk, role)
            self.assertNotIn('filter_options', self.client.get(self.url).data)
            self.assertEqual(
                self.client.get(self.url, {'setter_id': '21'}).status_code,
                401 if role == 'closer' else 403,
            )
