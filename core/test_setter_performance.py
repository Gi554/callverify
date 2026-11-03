from django.test import TestCase, override_settings
from packages.quebec_period import ZONE
from .models import Prospect
from .visit_fixtures import VisitFixture


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class PerformanceTests(TestCase):
    setUp = VisitFixture.setUp
    auth = VisitFixture.auth
    report = VisitFixture.report
    payload = VisitFixture.payload

    def test_original_setter_credits_and_series_survive_current_reassignment(self):
        self.auth(72, 'client')
        self.assertEqual(self.report(closed=True).status_code, 201)
        Prospect.objects.filter(pk=self.visit.prospect_id).update(assigned_setter_id=22)
        self.auth(21, 'setter')
        day = self.visit.starts_at.astimezone(ZONE).date()
        response = self.client.get(f'/api/setter-performance/?from={day}&to={day}')
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data
        self.assertEqual(data['agent_id'], 21)
        self.assertEqual(data['totals']['held'], 1)
        self.assertEqual(data['totals']['closed'], 1)
        self.assertEqual(len(data['daily']), 1)
        self.assertNotIn('generated_cad', data['totals'])
        self.assertEqual(self.client.get('/api/setter-performance/22/').status_code, 403)
        self.auth(72, 'client')
        self.assertEqual(self.client.get('/api/setter-performance/').status_code, 403)

    def test_admin_roster_and_invalid_period(self):
        self.auth(90, 'administrator')
        self.assertIn(
            21, [r['id'] for r in self.client.get('/api/setter-performance/').data['agents']]
        )
        self.assertEqual(self.client.get('/api/setter-performance/21/?from=bad').status_code, 400)
