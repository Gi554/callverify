from django.test import TestCase, override_settings
from .payable_fixtures import AppointmentFixture as Fixtures
from .models import SetterAlertReview, BusinessAudit


@override_settings(DEBUG=True)
class AdminAlertsTests(TestCase):
    setUp = Fixtures.setUp
    auth = Fixtures.auth

    def test_summary_and_ack_are_admin_only_without_business_changes(self):
        response = self.client.get('/api/assurance/admin-alerts/')
        self.assertEqual(response.status_code, 200, response.data)
        alert = response.data['results'][0]
        body = {k: alert[k] for k in ['kind', 'id', 'signature']}
        body['note'] = 'Suivi en cours'
        before = self.appointment.revision
        response = self.client.post('/api/assurance/admin-alerts/', body, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(SetterAlertReview.objects.count(), 1)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.revision, before)
        self.assertTrue(BusinessAudit.objects.filter(action='payroll.alert_reviewed').exists())
        for role in ('setter', 'advisor'):
            self.auth(role, 21)
            self.assertEqual(self.client.get('/api/assurance/admin-alerts/').status_code, 403)

    def test_unknown_alert_kinds_and_removed_payment_kinds_are_refused(self):
        for kind in ('bad', 'payment_rejected', 'payroll_issues'):
            self.assertEqual(
                self.client.get(f'/api/assurance/admin-alerts/?kind={kind}').status_code, 400
            )
