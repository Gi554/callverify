from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.isolation_events import issue, verify
from . import test_isolation_visits as fixtures
from .models import IsolationVisit, AuditEvent


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class PublicationTests(TestCase):
    setUp = fixtures.IsolationVisitTests.setUp
    auth = fixtures.IsolationVisitTests.auth
    proof = fixtures.IsolationVisitTests.proof
    payload = fixtures.IsolationVisitTests.payload
    book = fixtures.IsolationVisitTests.book

    def create_google(self):
        self.external_check.return_value = {
            'result': 'free',
            'checked_at': timezone.now().isoformat(),
        }
        response = self.book(publication='google')
        self.assertEqual(response.status_code, 201, response.data)
        self.row = IsolationVisit.objects.get()
        return response

    def feedback(self, **changes):
        data = {
            'visit': self.row.pk,
            'owner': 72,
            'revision': 0,
            'state': 'confirmed',
            'checked_at': timezone.now().isoformat(),
            'error': '',
            **changes,
        }
        client = APIClient()
        return client.post(
            '/api/internal/isolation/publication-status/',
            {'proof': issue('publication_status', **data)},
            format='json',
        )

    def test_committed_intent_is_pending_until_signed_feedback_and_replay_keeps_one_visit(self):
        response = self.create_google()
        self.assertEqual(response.data['publication_status'], 'pending')
        claims = verify(response.data['publication_proof'], 'publish_visit')
        self.assertEqual(claims, {'actor': 21, 'role': 'setter', 'owner': 72, 'visit': self.row.pk})
        self.assertTrue(self.external_check.call_args.kwargs['publication'])
        self.assertEqual(self.book(publication='google').status_code, 200)
        self.assertEqual(IsolationVisit.objects.count(), 1)
        stamp = timezone.now().isoformat()
        self.assertTrue(self.feedback(checked_at=stamp).data['applied'])
        self.assertFalse(self.feedback(checked_at=stamp).data['applied'])
        self.row.refresh_from_db()
        self.assertEqual(self.row.publication_status, 'confirmed')
        self.assertEqual(
            AuditEvent.objects.filter(action='isolation.visit.publication_checked').count(), 1
        )
        self.assertNotIn(
            'publication_proof', self.client.get(self.url + str(self.row.pk) + '/').data
        )

    def test_obsolete_wrong_owner_and_untrusted_status_cannot_confirm(self):
        self.create_google()
        self.assertFalse(self.feedback(owner=73).data['applied'])
        self.assertFalse(self.feedback(revision=9).data['applied'])
        self.assertEqual(
            self.feedback(checked_at=(timezone.now() - timedelta(hours=1)).isoformat()).status_code,
            403,
        )
        client = APIClient()
        self.assertEqual(
            client.post(
                '/api/internal/isolation/publication-status/', {'proof': 'fake'}, format='json'
            ).status_code,
            403,
        )
        IsolationVisit.objects.update(status='cancelled', revision=1)
        self.assertFalse(self.feedback(revision=1).data['applied'])
        self.assertTrue(self.feedback(revision=1, state='removed').data['applied'])
        self.row.refresh_from_db()
        self.assertEqual(self.row.publication_status, 'removed')

    def test_error_does_not_erase_booking_or_invent_confirmation(self):
        self.create_google()
        self.assertTrue(self.feedback(state='error', error='uncertain_create').data['applied'])
        self.row.refresh_from_db()
        self.assertEqual(self.row.publication_status, 'error')
        self.assertEqual(self.row.status, 'scheduled')
        self.assertEqual(self.row.publication_error, 'uncertain_create')
        self.assertTrue(self.feedback().data['applied'])
        self.row.refresh_from_db()
        self.assertEqual(self.row.publication_status, 'confirmed')

    def test_status_audit_failure_rolls_back_feedback(self):
        self.create_google()
        with patch(
            'core.isolation_publication.AuditEvent.objects.create',
            side_effect=RuntimeError('audit'),
        ):
            with self.assertRaises(RuntimeError):
                self.feedback()
        self.row.refresh_from_db()
        self.assertEqual(self.row.publication_status, 'pending')
