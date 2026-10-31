from datetime import timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo
from django.test import TestCase, override_settings
from . import test_isolation_visits as fixtures
from .models import IsolationWorkingHours, IsolationVisit, AuditEvent


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class HoursTests(TestCase):
    setUp = fixtures.IsolationVisitTests.setUp
    auth = fixtures.IsolationVisitTests.auth
    proof = fixtures.IsolationVisitTests.proof
    payload = fixtures.IsolationVisitTests.payload
    book = fixtures.IsolationVisitTests.book

    def settings(self, windows=None, revision=0, enabled=True):
        self.auth(72, 'client')
        return self.client.post(
            '/api/isolation-working-hours/',
            {'enabled': enabled, 'revision': revision, 'windows': windows or []},
            format='json',
        )

    def test_config_is_client_or_admin_only_versioned_validated_and_audited(self):
        self.assertEqual(self.client.get('/api/isolation-working-hours/').status_code, 403)
        self.auth(72, 'client')
        initial = self.client.get('/api/isolation-working-hours/').data
        self.assertEqual(initial['timezone'], 'America/Toronto')
        self.assertFalse(initial['enabled'])
        self.assertEqual(
            self.settings([{'weekday': 0, 'start': '09:00', 'end': '17:00'}]).status_code, 200
        )
        self.assertEqual(self.settings(revision=0).status_code, 409)
        for windows in (
            [{'weekday': 7, 'start': '09:00', 'end': '17:00'}],
            [{'weekday': 0, 'start': '17:00', 'end': '09:00'}],
            [
                {'weekday': 0, 'start': '09:00', 'end': '17:00'},
                {'weekday': 0, 'start': '16:00', 'end': '18:00'},
            ],
        ):
            self.assertEqual(self.settings(windows, revision=1).status_code, 400)
        self.assertEqual(
            AuditEvent.objects.filter(action='isolation.working_hours.updated').count(), 1
        )
        self.auth(90, 'administrator')
        self.assertEqual(self.client.get('/api/isolation-working-hours/').status_code, 200)

    def test_hours_guard_booking_and_closed_periods_in_quebec(self):
        zone = ZoneInfo('America/Toronto')
        self.start = self.start.astimezone(zone).replace(hour=10, minute=0, second=0)
        self.start += timedelta(days=(7 - self.start.weekday()) % 7)
        self.end = self.start + timedelta(hours=1)
        self.settings([{'weekday': 0, 'start': '09:00', 'end': '11:00'}])
        self.auth(21, 'setter')
        self.assertEqual(self.book(timezone='America/Toronto').status_code, 201)
        start = self.start + timedelta(days=1)
        denied = self.book(
            request_id='a0c1d565-b5e4-4672-9ee2-8117b87f10ea',
            revision=1,
            timezone='America/Toronto',
            starts_at=start.isoformat(),
            ends_at=(start + timedelta(hours=1)).isoformat(),
        )
        self.assertEqual(denied.status_code, 409)
        self.assertEqual(IsolationVisit.objects.count(), 1)
        data = self.client.get(
            '/api/visits/availability/',
            {
                'prospect_id': self.prospect.pk,
                'start': self.start.replace(hour=0).isoformat(),
                'end': self.start.replace(hour=23).isoformat(),
            },
        ).data
        self.assertTrue(any(row['reason'] == 'working_hours' for row in data['busy']))

    def test_live_periods_use_attested_client_and_return_no_event_details(self):
        self.auth(21, 'setter')
        body = {
            'prospect_id': str(self.prospect.pk),
            'start': self.start.isoformat(),
            'end': self.end.isoformat(),
            'proof': self.proof(),
        }
        period = {'start': self.start.isoformat(), 'end': self.end.isoformat()}
        with patch(
            'packages.calendar_connectors.booking.check', return_value={'busy': [period]}
        ) as check:
            response = self.client.post('/api/visits/availability/', body, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['external_calendar'], 'checked_now')
            self.assertEqual(response.data['busy'][0]['reason'], 'external')
            self.assertEqual(check.call_args.args[1], 72)
            self.assertTrue(check.call_args.kwargs['include_busy'])
            self.assertEqual(
                self.client.post(
                    '/api/visits/availability/', {**body, 'proof': 'bad'}, format='json'
                ).status_code,
                400,
            )
            self.assertEqual(check.call_count, 1)
            self.auth(22, 'setter')
            self.assertEqual(
                self.client.post('/api/visits/availability/', body, format='json').status_code, 404
            )

    def test_hours_audit_failure_rolls_back(self):
        with patch(
            'core.isolation_hours.AuditEvent.objects.create', side_effect=RuntimeError('audit')
        ):
            with self.assertRaises(RuntimeError):
                self.settings()
        self.assertFalse(IsolationWorkingHours.objects.exists())
