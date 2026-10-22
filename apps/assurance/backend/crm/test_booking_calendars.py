import json
from unittest.mock import patch, Mock
from django.test import override_settings, TestCase
from . import tests as fixtures
from .models import Appointment, BusinessAudit
from .calendar_checks import check, Unavailable
from .leases import Conflict
from packages.access.calendar_checks import verify


@override_settings(DEBUG=True, PORTAL_INTERNAL_URL='http://portal:8000')
class BookingCalendarTests(TestCase):
    setUp = fixtures.AppointmentTests.setUp
    authorize = fixtures.AppointmentTests.authorize
    proof = fixtures.AppointmentTests.proof
    payload = fixtures.AppointmentTests.payload
    book = fixtures.AppointmentTests.book
    reschedule_payload = fixtures.AppointmentTests.reschedule_payload

    def test_external_check_is_required_and_audited_before_booking(self):
        self.external_check.return_value = {'result': 'free', 'checked_at': self.start.isoformat()}
        result = self.book()
        self.assertEqual(result.status_code, 201, result.data)
        args = self.external_check.call_args.args
        self.assertEqual(args[0].pk, 21)
        self.assertEqual(args[1:], (31, self.start, self.end))
        self.assertEqual(
            BusinessAudit.objects.get(action='appointment.booked').metadata['external_check'][
                'result'
            ],
            'free',
        )

    def test_busy_or_unavailable_rolls_back_and_does_not_consume_uuid(self):
        payload = self.payload()
        for error, status in ((Conflict('Occupied'), 409), (Unavailable(), 503)):
            self.external_check.side_effect = error
            result = self.client.post(self.url, payload, format='json')
            self.assertEqual(result.status_code, status, result.data)
            self.assertFalse(Appointment.objects.exists())
            self.assertFalse(BusinessAudit.objects.filter(action='appointment.booked').exists())
        self.external_check.side_effect = None
        self.assertEqual(self.client.post(self.url, payload, format='json').status_code, 201)
        self.external_check.reset_mock()
        self.assertEqual(self.client.post(self.url, payload, format='json').status_code, 200)
        self.external_check.assert_not_called()

    def test_reschedule_checks_existing_source_but_cancel_never_checks(self):
        row = self.book().data
        self.external_check.reset_mock()
        self.external_check.side_effect = Conflict('Occupied')
        result = self.client.post(
            self.url + str(row['id']) + '/reschedule/', self.reschedule_payload(), format='json'
        )
        self.assertEqual(result.status_code, 409)
        self.assertEqual(self.external_check.call_args.args[-1], row['id'])
        self.assertEqual(Appointment.objects.get().revision, 0)
        self.external_check.reset_mock()
        self.assertEqual(
            self.client.post(
                self.url + str(row['id']) + '/cancel/',
                {'revision': 0, 'reason': 'Cancel'},
                format='json',
            ).status_code,
            200,
        )
        self.external_check.assert_not_called()

    def test_bridge_signs_server_values_and_fails_closed(self):
        user = Mock(pk=21, role='setter')
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.status_code = 200
        response.raw.read.return_value = json.dumps(
            {'result': 'free', 'checked_at': self.start.isoformat()}
        ).encode()
        with patch(
            'packages.calendar_connectors.booking.requests.post', return_value=response
        ) as post:
            self.assertEqual(check(user, 31, self.start, self.end, 7)['result'], 'free')
            claims = verify(post.call_args.kwargs['json']['proof'])
            self.assertEqual(claims['owner'], 31)
            self.assertEqual(claims['source_id'], 7)
            self.assertFalse(post.call_args.kwargs['allow_redirects'])
            response.raw.read.return_value = b'{"result":"free"}'
            with self.assertRaises(Unavailable):
                check(user, 31, self.start, self.end)
            response.raw.read.return_value = json.dumps(
                {'result': 'busy', 'checked_at': self.start.isoformat()}
            ).encode()
            with self.assertRaises(Conflict):
                check(user, 31, self.start, self.end)
            response.status_code = 503
            with self.assertRaises(Unavailable):
                check(user, 31, self.start, self.end)
