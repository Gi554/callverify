from datetime import timedelta
from uuid import uuid4
from django.test import TestCase, override_settings
from django.utils import timezone
from . import test_isolation_visits as fixtures
from .models import IsolationVisit, IsolationVisitResult, Prospect


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class RebookingTests(TestCase):
    setUp = fixtures.IsolationVisitTests.setUp
    auth = fixtures.IsolationVisitTests.auth
    proof = fixtures.IsolationVisitTests.proof
    payload = fixtures.IsolationVisitTests.payload
    book = fixtures.IsolationVisitTests.book

    def absent(self):
        response = self.book()
        self.assertEqual(response.status_code, 201)
        visit = IsolationVisit.objects.get(pk=response.data['id'])
        visit.starts_at = timezone.now() - timedelta(days=2)
        visit.ends_at = visit.starts_at + timedelta(hours=1)
        visit.save()
        IsolationVisitResult.objects.create(
            visit=visit,
            performed=False,
            closed=False,
            outcome='not_performed',
            note='Personne absente',
            author_client_id=72,
        )
        return visit

    def test_rebooking_is_a_new_occurrence_with_immutable_old_result_and_same_process(self):
        old = self.absent()
        self.request_id = uuid4()
        response = self.book(previous_visit_id=old.pk, revision=1)
        self.assertEqual(response.status_code, 201, response.data)
        new = IsolationVisit.objects.get(pk=response.data['id'])
        self.assertNotEqual(new.pk, old.pk)
        self.assertEqual(new.previous_visit_id, old.pk)
        self.assertEqual(new.process_id, old.process_id)
        self.assertEqual(new.prospect_id, old.prospect_id)
        self.assertFalse(old.result.performed)
        self.assertEqual(IsolationVisitResult.objects.count(), 1)
        self.assertEqual(self.book(previous_visit_id=old.pk, revision=1).status_code, 200)
        self.assertEqual(IsolationVisit.objects.count(), 2)
        self.assertEqual(Prospect.objects.count(), 1)
        self.assertEqual(self.client.get(f'/api/visits/{old.pk}/').data['next_visit_id'], new.pk)

    def test_omitting_previous_cannot_start_another_paid_process(self):
        old = self.absent()
        self.request_id = uuid4()
        response = self.book(revision=1)
        self.assertEqual(response.status_code, 201)
        new = IsolationVisit.objects.get(pk=response.data['id'])
        self.assertEqual(new.previous_visit_id, old.pk)
        self.assertEqual(new.process_id, old.process_id)

    def test_stale_or_foreign_previous_is_rejected_and_old_cannot_be_overwritten(self):
        old = self.absent()
        self.request_id = uuid4()
        self.assertEqual(self.book(previous_visit_id=old.pk + 100, revision=1).status_code, 409)
        self.assertEqual(IsolationVisit.objects.count(), 1)
        self.assertEqual(self.book(previous_visit_id=old.pk, revision=1).status_code, 201)
        self.request_id = uuid4()
        self.assertEqual(self.book(previous_visit_id=old.pk, revision=2).status_code, 409)
        self.assertEqual(
            self.client.post(
                f'/api/visits/{old.pk}/reschedule/',
                {
                    'revision': old.revision,
                    'proof': self.proof(),
                    'reason': 'Remplacer',
                    'starts_at': self.start.isoformat(),
                    'ends_at': self.end.isoformat(),
                    'timezone': 'UTC',
                },
                format='json',
            ).status_code,
            409,
        )
        self.assertFalse(IsolationVisitResult.objects.get(visit=old).performed)

    def test_history_and_upcoming_are_disjoint_and_client_scoped(self):
        old = self.absent()
        self.request_id = uuid4()
        self.book(previous_visit_id=old.pk, revision=1)
        self.auth(72, 'client')
        history = self.client.get('/api/visits/?period=history').data
        upcoming = self.client.get('/api/visits/?period=upcoming').data
        self.assertEqual([row['id'] for row in history['results']], [old.pk])
        self.assertEqual(history['count'], 1)
        self.assertEqual(upcoming['count'], 1)
        self.auth(73, 'client')
        self.assertEqual(self.client.get('/api/visits/?period=history').data['count'], 0)
