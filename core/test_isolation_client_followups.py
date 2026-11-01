from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from packages.access.isolation_visits import issue_booking
from packages.calendar_connectors.booking import Unavailable
from . import test_isolation_client as fixtures
from .test_isolation_visits import C2_DATA
from .models import (
    IsolationClientFollowUp,
    IsolationFollowUp,
    IsolationVisit,
    IsolationNotice,
    Prospect,
)
from .isolation_client_followups import due_notices


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class ClientFollowUpTests(TestCase):
    setUp = fixtures.IsolationClientTests.setUp
    auth = fixtures.IsolationClientTests.auth
    report = fixtures.IsolationClientTests.report
    payload = fixtures.IsolationClientTests.payload

    def absent(self, **changes):
        return self.report(
            performed=False,
            closed=False,
            outcome='not_performed',
            follow_up_owner='client',
            absence_reason='Prospect indisponible',
            **changes,
        )

    def test_personal_choice_is_owned_and_creates_no_setter_task(self):
        due = timezone.now() + timedelta(days=2)
        response = self.absent(follow_up_at=due.isoformat())
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.absent(follow_up_at=due.isoformat()).status_code, 200)
        self.assertFalse(IsolationFollowUp.objects.exists())
        self.assertFalse(IsolationNotice.objects.filter(recipient_role='setter').exists())
        row = IsolationClientFollowUp.objects.get()
        self.assertEqual(row.due_at, due)
        base = f'/api/client-follow-ups/{row.pk}/'
        self.assertEqual(self.client.get('/api/client-follow-ups/').data['count'], 1)
        self.auth(73, 'client')
        self.assertEqual(self.client.get('/api/client-follow-ups/').data['count'], 0)
        self.assertEqual(self.client.get(base + 'prospect/').status_code, 404)
        self.auth(21, 'setter')
        self.assertEqual(self.client.get('/api/client-follow-ups/').status_code, 403)
        self.auth(91, 'administrator')
        self.assertEqual(self.client.get('/api/client-follow-ups/').data['count'], 1)
        self.assertEqual(
            self.client.post(base + 'update_plan/', {}, format='json').status_code, 403
        )

    def test_personal_date_edit_is_versioned_and_due_notice_is_unique_and_revalidated(self):
        self.absent()
        row = IsolationClientFollowUp.objects.get()
        due = timezone.now() + timedelta(hours=1)
        base = f'/api/client-follow-ups/{row.pk}/update_plan/'
        body = {'revision': 0, 'note': 'Rappeler en soirée', 'due_at': due.isoformat()}
        self.assertEqual(self.client.post(base, body, format='json').status_code, 200)
        self.assertEqual(self.client.post(base, body, format='json').status_code, 409)
        due_notices()
        self.assertFalse(IsolationNotice.objects.filter(kind='personal_followup').exists())
        with patch('django.utils.timezone.now', return_value=due):
            due_notices()
            due_notices()
            self.assertEqual(self.client.get('/api/isolation-notices/').data['count'], 1)
            self.assertEqual(IsolationNotice.objects.filter(kind='personal_followup').count(), 1)
            later = due + timedelta(days=1)
            body.update(revision=1, due_at=later.isoformat())
            self.assertEqual(self.client.post(base, body, format='json').status_code, 200)
            self.assertEqual(self.client.get('/api/isolation-notices/').data['count'], 0)

    def test_switching_responsibility_and_correcting_presence_preserves_one_active_plan(self):
        self.absent()
        response = self.report(
            revision=1,
            performed=False,
            closed=False,
            outcome='not_performed',
            follow_up_owner='setter',
            absence_reason='Absent',
            reason='Confier au setter',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNotNone(IsolationClientFollowUp.objects.get().closed_at)
        self.assertIsNone(IsolationFollowUp.objects.get().closed_at)
        self.assertIn('Absent', IsolationFollowUp.objects.get().note)
        response = self.absent(revision=2, reason='Le client reprend le suivi')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(IsolationClientFollowUp.objects.get().closed_at)
        self.assertIsNotNone(IsolationFollowUp.objects.get().closed_at)
        self.assertEqual(
            self.report(revision=3, closed=False, reason='Présence confirmée').status_code, 201
        )
        self.assertIsNotNone(IsolationClientFollowUp.objects.get().closed_at)

    def test_client_rebooks_same_prospect_and_process_then_personal_plan_leaves_active_list(self):
        self.prospect.c2 = C2_DATA.copy()
        self.prospect.save()
        self.absent()
        row = IsolationClientFollowUp.objects.get()
        self.prospect.refresh_from_db()
        start = timezone.now() + timedelta(days=7)
        body = {
            'prospect_id': self.prospect.pk,
            'request_id': str(uuid4()),
            'revision': self.prospect.assignment_revision,
            'client_followup_id': row.pk,
            'proof': issue_booking(
                72, self.prospect.pk, 21, 'Setter', 72, 'Client', followup=row.pk
            ),
            'publication': 'google',
            'starts_at': start.isoformat(),
            'ends_at': (start + timedelta(hours=1)).isoformat(),
            'timezone': 'UTC',
        }
        with patch('core.isolation_visits.external_check', side_effect=Unavailable()):
            self.assertEqual(self.client.post('/api/visits/', body, format='json').status_code, 503)
        self.assertIsNone(IsolationClientFollowUp.objects.get().closed_at)
        with patch('core.isolation_visits.external_check', return_value={'result': 'available'}):
            response = self.client.post('/api/visits/', body, format='json')
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(self.client.post('/api/visits/', body, format='json').status_code, 200)
        new = IsolationVisit.objects.get(pk=response.data['id'])
        self.assertEqual(new.previous_visit_id, self.visit.pk)
        self.assertEqual(new.process_id, self.visit.process_id)
        self.assertEqual(new.prospect_id, self.prospect.pk)
        self.assertEqual(new.c2_snapshot['fields']['address'], C2_DATA['address'])
        self.assertEqual(Prospect.objects.count(), 1)
        self.assertEqual(self.client.get('/api/client-follow-ups/').data['count'], 0)
        self.assertEqual(IsolationClientFollowUp.objects.get().programmed_visit_id, new.pk)
        self.assertEqual(IsolationVisit.objects.count(), 2)

    def test_personal_scope_cannot_be_substituted_or_used_by_another_client(self):
        self.absent()
        row = IsolationClientFollowUp.objects.get()
        start = timezone.now() + timedelta(days=7)
        query = {
            'prospect_id': str(self.prospect.pk),
            'client_followup_id': row.pk,
            'proof': issue_booking(
                72, self.prospect.pk, 21, 'Setter', 72, 'Client', followup=row.pk + 1
            ),
            'start': start.isoformat(),
            'end': (start + timedelta(days=1)).isoformat(),
        }
        self.assertEqual(
            self.client.post('/api/visits/availability/', query, format='json').status_code, 403
        )
        self.auth(73, 'client')
        self.assertEqual(
            self.client.post('/api/visits/availability/', query, format='json').status_code, 404
        )
