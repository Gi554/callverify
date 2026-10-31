import json
from datetime import timedelta
from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from . import test_isolation_visits as fixtures
from .models import IsolationVisit, AuditEvent
from .calendar_checks import check, Unavailable
from .isolation_work import Conflict
from packages.access.calendar_checks import verify


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, PORTAL_INTERNAL_URL='http://portal:8000')
class IsolationBookingCalendarTests(TestCase):
    setUp = fixtures.IsolationVisitTests.setUp
    auth = fixtures.IsolationVisitTests.auth
    proof = fixtures.IsolationVisitTests.proof
    payload = fixtures.IsolationVisitTests.payload
    book = fixtures.IsolationVisitTests.book

    def test_checked_booking_preserves_author_and_audit(self):
        self.external_check.return_value = {'result': 'free', 'checked_at': self.start.isoformat()}
        response = self.book()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['original_setter']['id'], 21)
        self.assertEqual(response.data['client']['id'], 72)
        self.assertEqual(self.external_check.call_args.args[1:], (72, self.start, self.end))
        self.assertEqual(
            AuditEvent.objects.get(action='isolation.visit.booked').metadata['external_check'][
                'result'
            ],
            'free',
        )

    def test_refusal_rolls_back_revision_and_allows_same_uuid_after_resolution(self):
        for error, status in ((Conflict('Occupied'), 409), (Unavailable(), 503)):
            self.external_check.side_effect = error
            response = self.book()
            self.assertEqual(response.status_code, status, response.data)
            self.assertFalse(IsolationVisit.objects.exists())
            self.prospect.refresh_from_db()
            self.assertEqual(self.prospect.assignment_revision, 0)
        self.external_check.side_effect = None
        self.assertEqual(self.book().status_code, 201)
        self.external_check.reset_mock()
        self.assertEqual(self.book().status_code, 200)
        self.external_check.assert_not_called()

    def test_reschedule_checks_owned_event_and_cancel_works_offline(self):
        row = self.book().data
        url = self.url + str(row['id']) + '/'
        data = {
            'revision': 0,
            'proof': self.proof(),
            'reason': 'Report',
            'timezone': 'UTC',
            'starts_at': (self.start + timedelta(days=1)).isoformat(),
            'ends_at': (self.end + timedelta(days=1)).isoformat(),
        }
        self.external_check.side_effect = Unavailable()
        self.assertEqual(
            self.client.post(url + 'reschedule/', data, format='json').status_code, 503
        )
        self.assertEqual(self.external_check.call_args.args[-1], row['id'])
        self.assertEqual(IsolationVisit.objects.get().revision, 0)
        self.external_check.reset_mock()
        self.assertEqual(
            self.client.post(
                url + 'cancel/', {'revision': 0, 'reason': 'Annulation'}, format='json'
            ).status_code,
            200,
        )
        self.external_check.assert_not_called()

    def test_period_bridge_rejects_missing_calendar_invalid_or_private_payloads(self):
        from packages.calendar_connectors.booking import check as shared

        user = type('Actor', (), {'pk': 21, 'role': 'setter'})()
        good = {
            'result': 'busy',
            'checked_at': self.start.isoformat(),
            'busy': [{'start': self.start.isoformat(), 'end': self.end.isoformat()}],
        }
        for data, allowed in (
            (good, True),
            ({**good, 'result': 'internal_only'}, False),
            (
                {
                    **good,
                    'busy': [
                        {
                            'start': self.start.isoformat(),
                            'end': self.end.isoformat(),
                            'title': 'PRIVATE',
                        }
                    ],
                },
                False,
            ),
            ({**good, 'busy': [{'start': 'invalid', 'end': self.end.isoformat()}]}, False),
        ):
            response = Mock(status_code=200)
            response.raw.read.return_value = json.dumps(data).encode()
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=None)
            with patch(
                'packages.calendar_connectors.booking.requests.post', return_value=response
            ) as post:
                if allowed:
                    self.assertEqual(
                        shared(
                            user, 72, self.start, self.end, workspace='isolation', include_busy=True
                        ),
                        good,
                    )
                    self.assertTrue(post.call_args.args[0].endswith('/isolation/calendar-periods/'))
                else:
                    with self.assertRaises(Unavailable):
                        shared(
                            user, 72, self.start, self.end, workspace='isolation', include_busy=True
                        )

    def test_shared_bridge_uses_isolation_key_and_target_only(self):
        user = Mock(pk=21, role='setter')
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.status_code = 200
        response.raw.read.return_value = json.dumps(
            {'result': 'internal_only', 'checked_at': self.start.isoformat()}
        ).encode()
        with patch(
            'packages.calendar_connectors.booking.requests.post', return_value=response
        ) as post:
            self.assertEqual(check(user, 72, self.start, self.end)['result'], 'internal_only')
            self.assertEqual(
                post.call_args.args[0],
                'http://portal:8000/api/portal/internal/isolation/calendar-check/',
            )
            claims = verify(post.call_args.kwargs['json']['proof'], 'isolation')
            self.assertEqual(claims['owner'], 72)
