from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import TestCase, override_settings

from . import tests as fixtures
from .advisor_availability import closed_periods, ensure_open
from .leases import Conflict
from .models import AdvisorSchedule, BusinessAudit


@override_settings(DEBUG=True)
class AdvisorAvailabilityTests(TestCase):
    def setUp(self):
        self.fixture = fixtures.AppointmentTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client = self.fixture.client
        self.url = '/api/assurance/advisor-availability/'

    def save(self, **changes):
        self.fixture.authorize(31, 'advisor')
        return self.client.post(
            self.url,
            {
                'revision': 0,
                'enabled': True,
                'timezone': 'UTC',
                'windows': [
                    {'weekday': self.fixture.start.weekday(), 'start': '10:00', 'end': '12:00'}
                ],
                **changes,
            },
            format='json',
        )

    def test_personal_scope_validation_and_revision(self):
        for role in ('setter', 'administrator'):
            self.fixture.authorize(21, role)
            self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.save().status_code, 200)
        self.assertEqual(self.save().status_code, 409)
        self.fixture.authorize(32, 'advisor')
        self.assertFalse(self.client.get(self.url).data['enabled'])
        self.assertEqual(
            BusinessAudit.objects.filter(action='advisor.availability_updated').count(), 1
        )
        for changes in (
            {'revision': 1, 'timezone': 'Invalid/Zone'},
            {'revision': 1, 'windows': [{'weekday': 0, 'start': '17:00', 'end': '09:00'}]},
            {'revision': 1, 'advisor_id': 32},
            {'revision': 1, 'windows': [{'weekday': 7, 'start': '09:00', 'end': '17:00'}]},
            {
                'revision': 1,
                'windows': [
                    {'weekday': 0, 'start': '09:00', 'end': '12:00'},
                    {'weekday': 0, 'start': '11:00', 'end': '13:00'},
                ],
            },
        ):
            self.assertEqual(self.save(**changes).status_code, 400)

    def test_book_and_reschedule_enforce_hours_before_provider_check(self):
        self.assertEqual(self.save().status_code, 200)
        self.fixture.authorize(21)
        row = self.fixture.book()
        self.assertEqual(row.status_code, 201, row.data)
        self.fixture.external_check.reset_mock()
        later = self.fixture.start.replace(hour=13)
        response = self.fixture.book(
            starts_at=later.isoformat(), ends_at=(later + timedelta(minutes=30)).isoformat()
        )
        self.assertEqual(response.status_code, 409)
        response = self.client.post(
            f'/api/assurance/appointments/{row.data["id"]}/reschedule/',
            self.fixture.reschedule_payload(),
            format='json',
        )
        self.assertEqual(response.status_code, 409)
        self.fixture.external_check.assert_not_called()

    def test_closed_hours_are_in_slot_query_and_no_hours_means_closed(self):
        self.save(windows=[])
        self.fixture.authorize(21)
        response = self.client.get(
            '/api/assurance/appointments/availability/',
            {
                'assignment_id': self.fixture.assignment.pk,
                'start': self.fixture.start.isoformat(),
                'end': self.fixture.end.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['working_hours_enabled'])
        self.assertEqual(response.data['busy'][0]['reason'], 'working_hours')
        self.assertEqual(self.fixture.book().status_code, 409)

    def test_hours_use_advisor_timezone_and_preserve_unconfigured_legacy(self):
        self.assertEqual(self.fixture.book().status_code, 201)
        self.save(
            timezone='America/Toronto', windows=[{'weekday': 0, 'start': '09:00', 'end': '17:00'}]
        )
        first = datetime.fromisoformat('2026-11-02T14:00:00+00:00')
        ensure_open(31, first, first + timedelta(minutes=30))
        with self.assertRaises(Conflict):
            ensure_open(31, first - timedelta(hours=1), first)

    def test_dst_nonexistent_window_does_not_advertise_free_time(self):
        first = datetime(2027, 3, 14, 5, tzinfo=timezone.utc)
        last = first + timedelta(hours=23)
        rules = {
            'enabled': True,
            'timezone': 'America/Toronto',
            'windows': [{'weekday': 6, 'start': '02:00', 'end': '04:00'}],
        }
        self.assertEqual(
            closed_periods(rules, first, last),
            [{'starts_at': first, 'ends_at': last, 'reason': 'working_hours'}],
        )

    def test_audit_failure_rolls_back_configuration(self):
        with patch.object(
            BusinessAudit.objects, 'create', side_effect=RuntimeError('audit failed')
        ):
            with self.assertRaises(RuntimeError):
                self.save()
        self.assertFalse(AdvisorSchedule.objects.filter(advisor_id=31).exists())
