from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase, override_settings
from . import test_isolation_visits as fixtures
from .models import IsolationUnqualified, IsolationVisit, ProspectActivity


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class UnqualifiedTests(TestCase):
    setUp = fixtures.IsolationVisitTests.setUp
    auth = fixtures.IsolationVisitTests.auth
    proof = fixtures.IsolationVisitTests.proof
    payload = fixtures.IsolationVisitTests.payload
    book = fixtures.IsolationVisitTests.book

    def register(self, **changes):
        return self.client.post(
            '/api/isolation-unqualified/',
            {
                'prospect_id': self.prospect.pk,
                'revision': 0,
                'proof': self.proof(),
                'request_id': str(self.request_id),
                'reason': 'out_of_area',
                'note': '',
                **changes,
            },
            format='json',
        )

    def test_partial_qualification_and_optional_note_create_no_visit_and_keep_original_data(self):
        self.prospect.c2 = {'city': 'Montréal', 'postal_code': 'H2X 1Y4'}
        self.prospect.save()
        original_phone = self.prospect.raw_phone
        response = self.register()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['qualification']['fields']['city'], 'Montréal')
        self.assertEqual(response.data['phone'], original_phone)
        self.assertEqual(response.data['setter']['id'], 21)
        self.assertEqual(response.data['client']['id'], 72)
        self.assertFalse(IsolationVisit.objects.exists())
        self.assertEqual(self.register().status_code, 200)
        self.assertEqual(IsolationUnqualified.objects.count(), 1)
        self.assertEqual(self.client.get('/api/work-queue/?queue=active').data['count'], 0)
        self.assertEqual(
            self.client.get('/api/work-queue/?queue=all').data['results'][0]['queue_reason'],
            'unqualified',
        )
        self.assertEqual(self.register(request_id=str(uuid4()), revision=1).status_code, 409)
        self.prospect.refresh_from_db()
        self.assertEqual(self.prospect.assignment_revision, 1)
        self.assertEqual(self.prospect.raw_phone, original_phone)

    def test_client_filters_sort_history_and_callbacks_are_strictly_scoped(self):
        row = self.register(note='À reprendre plus tard').data
        self.auth(72, 'client')
        for query, expected in [
            ('city=Montr', 1),
            ('postal_code=h2x1', 1),
            ('reason=out_of_area', 1),
            ('city=Québec', 0),
            ('reason=distance', 0),
            ('sort=setter', 1),
        ]:
            self.assertEqual(
                self.client.get('/api/isolation-unqualified/?' + query).data['count'], expected
            )
        self.assertEqual(
            self.client.get('/api/isolation-unqualified/?reason=invalid').status_code, 400
        )
        self.assertEqual(
            self.client.get('/api/isolation-unqualified/?sort=actor_id').status_code, 400
        )
        self.assertEqual(
            self.client.get(f'/api/isolation-unqualified/{row["id"]}/history/').data['count'], 1
        )
        self.assertEqual(
            self.client.get(f'/api/isolation-unqualified/{row["id"]}/callbacks/').data['count'], 0
        )
        self.assertEqual(self.register().status_code, 403)
        self.auth(73, 'client')
        self.assertEqual(self.client.get('/api/isolation-unqualified/').data['count'], 0)
        for suffix in ('', 'history/', 'callbacks/'):
            self.assertEqual(
                self.client.get(f'/api/isolation-unqualified/{row["id"]}/{suffix}').status_code, 404
            )
        self.auth(22, 'setter')
        self.assertEqual(
            self.client.get(f'/api/isolation-unqualified/{row["id"]}/').status_code, 404
        )

    def test_booked_visit_archives_unqualified_entry_without_deleting_history(self):
        record = self.register().data
        self.request_id = uuid4()
        response = self.book(revision=1)
        self.assertEqual(response.status_code, 201, response.data)
        row = IsolationUnqualified.objects.get(pk=record['id'])
        self.assertFalse(row.active)
        self.assertEqual(row.programmed_visit_id, response.data['id'])
        self.assertEqual(self.client.get('/api/isolation-unqualified/').data['count'], 0)
        self.assertTrue(
            ProspectActivity.objects.filter(kind='unqualified', prospect=self.prospect).exists()
        )
        self.assertEqual(self.client.get(f'/api/isolation-unqualified/{row.pk}/').status_code, 200)

    def test_invalid_proof_role_and_active_visit_do_not_mutate(self):
        self.assertEqual(self.register(proof='forged').status_code, 400)
        self.assertEqual(self.register(reason='not_interested').status_code, 400)
        self.assertEqual(self.register(revision=9).status_code, 409)
        self.assertFalse(IsolationUnqualified.objects.exists())
        self.assertEqual(self.book().status_code, 201)
        self.request_id = uuid4()
        self.assertEqual(self.register(revision=1).status_code, 409)
        self.assertFalse(IsolationUnqualified.objects.exists())

    def test_audit_failure_rolls_back_all_business_changes(self):
        with patch(
            'core.isolation_unqualified.AuditEvent.objects.create',
            side_effect=RuntimeError('audit'),
        ):
            with self.assertRaises(RuntimeError):
                self.register()
        self.assertFalse(IsolationUnqualified.objects.exists())
        self.assertFalse(ProspectActivity.objects.exists())
        self.prospect.refresh_from_db()
        self.assertEqual(self.prospect.assignment_revision, 0)
