from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from . import test_isolation_client as fixtures
from .models import IsolationVisitResult, IsolationFollowUp, IsolationNotice


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class ResultV2Tests(TestCase):
    setUp = fixtures.IsolationClientTests.setUp
    auth = fixtures.IsolationClientTests.auth
    report = fixtures.IsolationClientTests.report
    payload = fixtures.IsolationClientTests.payload

    def test_client_records_sale_independently_and_false_presence_refuses_sale(self):
        self.assertEqual(
            self.report(performed=False, closed=True, outcome='not_performed', note='').status_code,
            400,
        )
        first = self.report(closed=True, note='')
        self.assertEqual(first.status_code, 201, first.data)
        self.assertTrue(first.data['closed'])
        self.assertFalse(IsolationFollowUp.objects.exists())
        self.assertEqual(self.report(closed=True, note='').status_code, 200)
        self.assertEqual(IsolationNotice.objects.count(), 1)
        self.assertEqual(IsolationNotice.objects.get().kind, 'closed')
        self.assertEqual(
            self.report(
                revision=1, closed=False, reason='Vente non finalisée', note=''
            ).status_code,
            201,
        )
        self.assertFalse(IsolationVisitResult.objects.get().closed)
        self.assertEqual(IsolationNotice.objects.count(), 2)

    def test_no_show_creates_one_callback_and_private_notice_then_allows_requalification_queue(
        self,
    ):
        response = self.report(performed=False, closed=False, outcome='not_performed', note='')
        self.assertEqual(response.status_code, 201, response.data)
        task = IsolationFollowUp.objects.get()
        self.assertEqual(task.absence_visit_id, self.visit.pk)
        self.assertLessEqual(task.due_at, timezone.now() + timedelta(hours=24))
        self.assertEqual(
            self.report(
                performed=False, closed=False, outcome='not_performed', note=''
            ).status_code,
            200,
        )
        self.assertEqual(IsolationFollowUp.objects.count(), 1)
        self.auth(21, 'setter')
        feed = self.client.get('/api/isolation-notices/?unread=true')
        self.assertEqual(feed.data['count'], 1)
        pk = feed.data['results'][0]['id']
        self.assertEqual(
            self.client.post(f'/api/isolation-notices/{pk}/read/', {}, format='json').status_code,
            200,
        )
        task.refresh_from_db()
        self.assertIsNone(task.closed_at)
        self.assertFalse(IsolationVisitResult.objects.get().performed)
        active = self.client.get('/api/work-queue/?queue=active')
        self.assertIn(self.prospect.pk, [r['id'] for r in active.data['results']])
        self.auth(22, 'setter')
        self.assertEqual(self.client.get('/api/isolation-notices/').data['count'], 0)
        self.assertEqual(
            self.client.post(f'/api/isolation-notices/{pk}/read/', {}, format='json').status_code,
            404,
        )

    def test_result_failure_rolls_back_task_and_notice_and_correction_reopens_a_closed_followup(
        self,
    ):
        with patch('core.isolation_notices.notice', side_effect=RuntimeError('notice')):
            with self.assertRaises(RuntimeError):
                self.report(performed=False, closed=False, outcome='not_performed', note='')
        self.assertFalse(IsolationVisitResult.objects.exists())
        self.assertFalse(IsolationFollowUp.objects.exists())
        self.report(performed=False, closed=False, outcome='not_performed', note='')
        task = IsolationFollowUp.objects.get()
        task.closed_at = timezone.now()
        task.resolution = 'Traité'
        task.save()
        self.report(revision=1, performed=True, closed=False, reason='Présence confirmée', note='')
        response = self.report(
            revision=2,
            performed=False,
            closed=False,
            outcome='not_performed',
            reason='Correction finale',
            note='',
        )
        self.assertEqual(response.status_code, 201, response.data)
        task.refresh_from_db()
        self.assertIsNone(task.closed_at)
        self.assertEqual(IsolationFollowUp.objects.count(), 1)
