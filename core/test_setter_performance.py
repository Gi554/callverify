from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import timedelta
from uuid import uuid4
from packages.quebec_period import ZONE
from .models import Prospect, ProspectActivity, IsolationVisit
from .visit_fixtures import VisitFixture


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class PerformanceTests(TestCase):
    setUp = VisitFixture.setUp
    auth = VisitFixture.auth
    report = VisitFixture.report
    payload = VisitFixture.payload

    def test_upcoming_and_declarations_are_distinct_from_missing_results(self):
        now = timezone.now()
        IsolationVisit.objects.filter(pk=self.visit.pk).update(
            created_at=now, starts_at=now + timedelta(hours=1), ends_at=now + timedelta(hours=2)
        )
        for agent, result in ((21, 'callback'), (21, 'voicemail'), (22, 'not_interested')):
            ProspectActivity.objects.create(
                prospect=self.visit.prospect,
                author_portal_id=agent,
                author_role='setter',
                kind='call_result',
                request_id=uuid4(),
                fingerprint='test',
                body='',
                changes={'result': result},
            )
        self.auth(21, 'setter')
        today = now.astimezone(ZONE).date()
        tomorrow = today + timedelta(days=1)
        data = self.client.get(f'/api/setter-performance/?from={today}&to={tomorrow}').data
        self.assertEqual(data['totals']['booked'], 1)
        self.assertEqual(data['totals']['upcoming'], 1)
        self.assertEqual(data['totals']['awaiting_result'], 0)
        outcomes = {row['key']: row['count'] for row in data['outcomes']}
        self.assertEqual(outcomes['callback'], 1)
        self.assertEqual(outcomes['voicemail'], 1)
        self.assertEqual(outcomes['not_interested'], 0)

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
