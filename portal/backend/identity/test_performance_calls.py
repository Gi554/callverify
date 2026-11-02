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
