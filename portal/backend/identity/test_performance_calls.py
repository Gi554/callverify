from . import test_call_statistics as fixtures
from django.test import TestCase, override_settings
from .models import Membership


@override_settings(DEBUG=True)
class PerformanceCallTests(TestCase):
    setUp = fixtures.CallStatisticsTests.setUp
    row = fixtures.CallStatisticsTests.row

    def test_own_scope_and_no_claim_that_accepted_means_reached(self):
        self.row('accepted')
        self.row('unknown')
        self.row('accepted', workspace='isolation')
        self.client.force_login(self.setter)
        url = '/api/portal/assurance/performance-calls/?from=2026-10-26&to=2026-11-01'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['totals']['calls'], 1)
        self.assertIsNone(response.data['totals']['reached'])
        self.assertEqual(self.client.get(url + '&setter_id=' + str(self.admin.pk)).status_code, 403)
        self.assertEqual(
            self.client.get(url.replace('/assurance/', '/isolation/')).status_code, 403
        )
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get(url + '&setter_id=' + str(self.setter.pk)).data['totals']['calls'], 1
        )
        Membership.objects.filter(user=self.admin).update(active=False)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_admin_team_report_groups_call_metrics_without_target_membership_lookup(self):
        self.row('accepted')
        row = fixtures.PhoneCallAttempt.objects.filter(user=self.setter).first()
        fixtures.PhoneCallAttempt.objects.filter(pk=row.pk).update(
            journal_status='matched', journal_duration=75
        )
        response = self.client.get(
            '/api/portal/assurance/performance-calls/?from=2026-10-26&to=2026-11-01&team=1'
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['team'][0]['user_id'], self.setter.pk)
        self.assertEqual(response.data['team'][0]['attempts'], 1)
        self.assertEqual(response.data['team'][0]['calls_over_minute'], 1)
        self.assertEqual(response.data['team'][0]['duration_total_seconds'], 75)
