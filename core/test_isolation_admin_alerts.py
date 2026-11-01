from copy import copy
from uuid import uuid4
from django.test import TestCase, override_settings
from .test_isolation_payroll import PayrollTests as Fixtures
from .models import IsolationVisit, IsolationAlertReview, AuditEvent


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class AdminAlertsTests(TestCase):
    setUp = Fixtures.setUp
    auth = Fixtures.auth

    def get(self, kind='missing_results'):
        self.auth(90, 'administrator')
        return self.client.get('/api/admin-alerts/?kind=' + kind)

    def test_acknowledgement_never_changes_visit_and_new_revision_reopens(self):
        result = self.get()
        self.assertEqual(result.status_code, 200, result.data)
        alert = result.data['results'][0]
        before = IsolationVisit.objects.get(pk=self.visit.pk)
        body = {k: alert[k] for k in ['kind', 'id', 'signature']}
        body['note'] = 'Le responsable est prévenu.'
        first = self.client.post('/api/admin-alerts/', body, format='json')
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(
            self.client.post('/api/admin-alerts/', body, format='json').status_code, 200
        )
        self.assertEqual(IsolationAlertReview.objects.count(), 1)
        current = IsolationVisit.objects.get(pk=self.visit.pk)
        self.assertEqual((current.status, current.revision), (before.status, before.revision))
        self.assertIsNotNone(self.get().data['results'][0]['review'])
        IsolationVisit.objects.filter(pk=self.visit.pk).update(revision=before.revision + 1)
        self.assertEqual(
            self.client.post('/api/admin-alerts/', body, format='json').status_code, 400
        )
        self.assertIsNone(self.get().data['results'][0]['review'])

    def test_duplicate_candidates_and_role_permissions(self):
        other = copy(self.visit)
        other.pk = None
        other.request_id = uuid4()
        other.save()
        response = self.get('duplicate_meetings')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['details']['Nombre'], 2)
        prospect = copy(self.visit.prospect)
        prospect.pk = None
        prospect.phone = None
        prospect.save()
        response = self.get('duplicate_prospects')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertGreater(response.data['count'], 0)
        for role in ('setter', 'client', 'closer'):
            self.auth(21, role)
            self.assertEqual(self.client.get('/api/admin-alerts/').status_code, 403)

    def test_invalid_filters_and_rejected_payment_alert(self):
        self.assertEqual(self.get('other').status_code, 400)
        self.auth(90, 'administrator')
        self.assertEqual(self.client.get('/api/admin-alerts/?page=0').status_code, 400)
        AuditEvent.objects.create(
            action='isolation.payroll.payment_rejected',
            object_id='21',
            metadata={'reason': 'Référence déjà enregistrée', 'actor_portal_id': 90},
        )
        self.assertEqual(self.get('payment_rejected').data['count'], 1)
        bad = self.client.post(
            '/api/admin-alerts/',
            {'kind': 'duplicate_meetings', 'id': 'bad', 'signature': 'a' * 64, 'note': 'Note'},
            format='json',
        )
        self.assertEqual(bad.status_code, 400)
