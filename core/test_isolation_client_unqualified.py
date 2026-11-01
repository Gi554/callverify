from django.test import TestCase, override_settings
from . import test_isolation_client as fixtures
from .models import (
    IsolationVisitResult,
    IsolationFollowUp,
    IsolationClientFollowUp,
    IsolationNotice,
)


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class ClientUnqualifiedTests(TestCase):
    setUp = fixtures.IsolationClientTests.setUp
    auth = fixtures.IsolationClientTests.auth
    report = fixtures.IsolationClientTests.report
    payload = fixtures.IsolationClientTests.payload

    def unqualified(self, **changes):
        return self.report(
            performed=False,
            closed=False,
            outcome='unqualified',
            absence_reason='Ville non desservie',
            **changes,
        )

    def test_nonqualified_is_explicit_not_an_absence_or_payable_visit(self):
        response = self.unqualified(note='À revoir si le secteur ouvre')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['outcome'], 'unqualified')
        self.assertEqual(self.unqualified(note='À revoir si le secteur ouvre').status_code, 200)
        self.assertFalse(IsolationFollowUp.objects.exists())
        self.assertFalse(IsolationClientFollowUp.objects.exists())
        self.assertIsNone(IsolationVisitResult.objects.get().attendance_unit_cad)
        self.assertEqual(self.client.get('/api/client-dashboard/').data['results_due'], 0)
        self.auth(21, 'setter')
        self.assertEqual(
            self.client.get('/api/isolation-notices/').data['results'][0]['kind'], 'unqualified'
        )
        self.assertEqual(self.client.get(self.url).data['result']['outcome'], 'unqualified')
        self.assertEqual(self.client.get('/api/work-queue/?queue=active').data['count'], 1)
        stats = self.client.get('/api/workspace-statistics/').data['totals']
        self.assertEqual(stats['unqualified'], 1)
        self.assertEqual(stats['not_performed'], 0)
        self.assertEqual(stats['performed'], 0)
        self.assertIsNone(stats['performed_rate'])
        self.auth(22, 'setter')
        self.assertEqual(self.client.get('/api/isolation-notices/').data['count'], 0)
        self.assertEqual(IsolationNotice.objects.filter(kind='unqualified').count(), 1)

    def test_reason_required_and_foreign_client_cannot_invalidate_a_visit(self):
        self.assertEqual(
            self.report(performed=False, closed=False, outcome='unqualified').status_code, 400
        )
        self.assertEqual(
            self.report(
                performed=True, closed=False, outcome='unqualified', absence_reason='Hors zone'
            ).status_code,
            400,
        )
        self.auth(73, 'client')
        self.assertEqual(self.unqualified().status_code, 404)
        self.assertFalse(IsolationVisitResult.objects.exists())

    def test_reasoned_correction_closes_old_callback_without_inventing_absence(self):
        self.assertEqual(
            self.report(performed=False, closed=False, outcome='not_performed').status_code, 201
        )
        self.assertEqual(
            self.unqualified(revision=1, reason='Critères non remplis').status_code, 201
        )
        self.assertIsNotNone(IsolationFollowUp.objects.get().closed_at)
        self.assertEqual(IsolationFollowUp.objects.count(), 1)
        self.assertEqual(IsolationVisitResult.objects.get().outcome, 'unqualified')
