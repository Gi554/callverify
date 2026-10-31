from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase, override_settings
from packages.access.isolation_visits import issue_booking
from packages.calendar_connectors.booking import Unavailable
from . import test_isolation_unqualified as fixtures
from .models import IsolationUnqualified, IsolationVisit, Prospect, ProspectActivity, AuditEvent


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class RequalificationTests(TestCase):
    auth = fixtures.UnqualifiedTests.auth
    proof = fixtures.UnqualifiedTests.proof
    payload = fixtures.UnqualifiedTests.payload
    book = fixtures.UnqualifiedTests.book
    register = fixtures.UnqualifiedTests.register

    def setUp(self):
        fixtures.UnqualifiedTests.setUp(self)
        self.entry = self.register().data
        self.auth(72, 'client')
        self.token = issue_booking(
            72, self.prospect.pk, 21, 'Setter', 72, 'Client', reactivation=self.entry['id']
        )
        self.base = f'/api/isolation-unqualified/{self.entry["id"]}/'

    def program(self, **changes):
        return self.book(
            publication='google',
            proof=self.token,
            revision=1,
            unqualified_id=self.entry['id'],
            **changes,
        )

    def test_client_requalifies_and_programs_the_same_prospect_with_its_original_history(self):
        current = self.client.get(self.base + 'prospect/').data
        self.assertEqual(current['assigned_setter']['id'], 21)
        self.assertEqual(set(current), {'id', 'name', 'raw_phone', 'revision', 'assigned_setter'})
        draft = self.client.get(self.base + 'qualification/').data
        draft['c2']['address'] = '20 rue Exemple'
        response = self.client.post(
            self.base + 'qualification/',
            {key: draft[key] for key in ('revision', 'c2')},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['revision'], 2)
        response = self.book(
            publication='google', proof=self.token, revision=2, unqualified_id=self.entry['id']
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['original_setter']['id'], 21)
        self.assertEqual(response.data['c2_snapshot']['fields']['address'], '20 rue Exemple')
        self.assertEqual(response.data['publication_status'], 'pending')
        self.assertIn('publication_proof', response.data)
        self.assertEqual(Prospect.objects.count(), 1)
        self.assertFalse(IsolationUnqualified.objects.get().active)
        self.assertEqual(ProspectActivity.objects.filter(kind='unqualified_programmed').count(), 1)
        self.assertEqual(ProspectActivity.objects.filter(kind='call_result').count(), 0)
        self.assertEqual(
            self.book(
                publication='google', proof=self.token, revision=2, unqualified_id=self.entry['id']
            ).status_code,
            200,
        )
        self.assertEqual(IsolationVisit.objects.count(), 1)
        self.assertEqual(self.client.get('/api/isolation-unqualified/').data['count'], 0)
        self.assertEqual(self.client.get(self.base + 'history/').data['count'], 2)
        self.assertTrue(
            AuditEvent.objects.filter(action='isolation.unqualified.qualification_saved').exists()
        )

    def test_failed_availability_leaves_entry_active_and_does_not_consume_revision(self):
        self.external_check.side_effect = Unavailable()
        self.assertEqual(self.program().status_code, 503)
        self.assertTrue(IsolationUnqualified.objects.get().active)
        self.assertFalse(IsolationVisit.objects.exists())
        self.prospect.refresh_from_db()
        self.assertEqual(self.prospect.assignment_revision, 1)

    def test_proof_is_bound_to_the_exact_entry_and_client_cannot_book_arbitrary_prospects(self):
        invalid = issue_booking(
            72, self.prospect.pk, 21, 'Setter', 72, 'Client', reactivation=self.entry['id'] + 1
        )
        self.assertEqual(
            self.book(
                publication='google', proof=invalid, revision=1, unqualified_id=self.entry['id']
            ).status_code,
            403,
        )
        self.assertEqual(
            self.book(publication='google', proof=self.token, revision=1).status_code, 403
        )
        self.assertEqual(
            self.book(proof=self.token, revision=1, unqualified_id=self.entry['id']).status_code,
            403,
        )
        self.auth(73, 'client')
        self.assertEqual(self.program().status_code, 404)
        for suffix in ('prospect/', 'qualification/'):
            self.assertEqual(self.client.get(self.base + suffix).status_code, 404)
        self.assertFalse(IsolationVisit.objects.exists())

    def test_active_client_busy_lookup_and_post_programming_edits_are_guarded(self):
        query = {
            'prospect_id': str(self.prospect.pk),
            'proof': self.token,
            'unqualified_id': self.entry['id'],
            'start': self.start.isoformat(),
            'end': self.end.isoformat(),
        }
        with patch(
            'packages.calendar_connectors.booking.check', return_value={'busy': []}
        ) as check:
            response = self.client.post('/api/visits/availability/', query, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(check.call_args.args[0].role, 'client')
            self.assertEqual(check.call_args.args[1], 72)
        self.assertEqual(self.program().status_code, 201)
        self.request_id = uuid4()
        self.assertEqual(self.program().status_code, 409)
        for suffix in ('prospect/', 'qualification/'):
            self.assertEqual(self.client.get(self.base + suffix).status_code, 409)
        self.assertEqual(
            self.client.post('/api/visits/availability/', query, format='json').status_code, 409
        )
        self.assertEqual(IsolationVisit.objects.count(), 1)
