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

    def test_public_history_keeps_reasons_and_notes_without_admin_or_financial_metadata(self):
        self.assertEqual(self.report(closed=False, note='Premier retour').status_code, 201)
        self.assertEqual(
            self.unqualified(
                revision=1, reason='Critères revérifiés', note='Retour non qualifié'
            ).status_code,
            201,
        )
        url = self.url + 'result-history/'
        data = self.client.get(url).data
        self.assertEqual(data['count'], 2)
        first = data['results'][0]
        self.assertEqual(first['before']['note'], 'Premier retour')
        self.assertEqual(first['after']['note'], 'Retour non qualifié')
        self.assertEqual(first['after']['absence_reason'], 'Ville non desservie')
        self.assertEqual(first['reason'], 'Critères revérifiés')
        self.assertNotIn('metadata', first)
        self.assertNotIn('attendance_unit_cad', first['after'])
        self.assertNotIn('actor_portal_id', str(data))
        self.auth(73, 'client')
        self.assertEqual(self.client.get(url).status_code, 404)
        self.auth(22, 'setter')
        self.assertEqual(self.client.get(url).status_code, 404)
        self.auth(91, 'administrator')
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_notification_is_withdrawn_when_prospect_leaves_setter_scope(self):
        self.assertEqual(self.unqualified().status_code, 201)
        self.auth(21, 'setter')
        feed = self.client.get('/api/isolation-notices/').data
        self.assertEqual(feed['count'], 1)
        notice_id = feed['results'][0]['id']
        self.prospect.assigned_setter_id = 22
        self.prospect.save(update_fields=['assigned_setter_id'])
        self.assertEqual(self.client.get('/api/isolation-notices/').data['count'], 0)
        self.assertEqual(
            self.client.post(
                f'/api/isolation-notices/{notice_id}/read/', {}, format='json'
            ).status_code,
            404,
        )
