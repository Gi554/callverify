from datetime import datetime, timezone as utc
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .isolation_sms import remind_client
from .models import AccessAudit, Membership, ReminderPhone, SmsAttempt

URL = '/api/portal/reminder-phone/'
STARTS = datetime(2026, 11, 1, 15, 30, tzinfo=utc.utc)


class Fixture(TestCase):
    def setUp(self):
        cache.clear()
        users = get_user_model().objects
        self.client_user = users.create_user('charles', email='charles@example.test')
        Membership.objects.create(user=self.client_user, workspace='isolation', role='client')
        self.setter = users.create_user('setter', email='setter@example.test')
        Membership.objects.create(user=self.setter, workspace='isolation', role='setter')
        self.api = APIClient(enforce_csrf_checks=True)
        self.api.force_login(self.client_user)
        self.csrf = self.api.get('/api/portal/csrf/').data['csrfToken']

    def put(self, data):
        return self.api.put(URL, data, format='json', HTTP_X_CSRFTOKEN=self.csrf)


@override_settings(DEBUG=True)
class ReminderPhoneApiTests(Fixture):
    def test_empty_by_default_then_saved_normalized_and_cleared_with_audit(self):
        self.assertEqual(self.api.get(URL).data, {'available': True, 'mobile': ''})
        self.assertEqual(self.put({'mobile': '+1 (438) 738-8944'}).data['mobile'], '4387388944')
        self.assertEqual(self.api.get(URL).data['mobile'], '4387388944')
        self.assertEqual(self.put({'mobile': ''}).data['mobile'], '')
        actions = AccessAudit.objects.filter(action='account.reminder_phone_changed')
        self.assertEqual(actions.count(), 2)
        self.assertNotIn('4387388944', str(list(actions.values_list('metadata', flat=True))))

    def test_invalid_number_and_extra_fields_are_refused(self):
        for body in ({'mobile': '123'}, {'mobile': 5}, {'mobile': '4387388944', 'x': 1}):
            self.assertEqual(self.put(body).status_code, 400)
        self.assertEqual(ReminderPhone.objects.count(), 0)

    def test_only_the_isolation_client_has_the_field(self):
        self.api.force_login(self.setter)
        self.assertEqual(self.api.get(URL).data, {'available': False, 'mobile': ''})
        self.assertEqual(self.put({'mobile': '4387388944'}).data['available'], False)
        self.assertEqual(ReminderPhone.objects.count(), 0)

    def test_anonymous_is_refused(self):
        self.assertIn(APIClient().get(URL).status_code, (401, 403))


@override_settings(
    DEBUG=True,
    NEWT_SMS_ENABLED=True,
    NEWT_SMS_CALLER_ID='4387388939',
    NEWT_USERNAME='test',
    NEWT_PASSWORD='test',
    NEWT_SMS_AUTOMATIC_FROM='2026-01-01T00:00:00Z',
    ISOLATION_PROSPECT_SMS_ENABLED=False,
)
class ClientReminderSmsTests(Fixture):
    def remind(self, event=7, eligible=True):
        with patch('portal.backend.identity.isolation_sms.eligible', return_value=eligible):
            return remind_client(self.client_user, event, STARTS)

    @patch('portal.backend.identity.isolation_sms.sms.send', return_value='accepted')
    def test_no_sms_while_the_number_is_not_set(self, send):
        self.assertEqual(self.remind(), 0)
        send.assert_not_called()

    @patch('portal.backend.identity.isolation_sms.sms.send', return_value='accepted')
    def test_one_sms_to_the_chosen_number_once_per_event(self, send):
        ReminderPhone.objects.create(user=self.client_user, mobile='4387388944')
        self.assertEqual(self.remind(), 1)
        self.assertEqual(self.remind(), 0)
        self.assertEqual(self.remind(event=8), 1)
        self.assertEqual(send.call_count, 2)
        self.assertEqual(send.call_args.args[2], '4387388944')
        self.assertIn('01/11/2026 à 10:30', send.call_args.args[4])
        self.assertEqual(
            set(SmsAttempt.objects.values_list('kind', flat=True)), {'client_reminder'}
        )

    @patch('portal.backend.identity.isolation_sms.sms.send', return_value='accepted')
    def test_a_result_filled_meanwhile_sends_nothing(self, send):
        ReminderPhone.objects.create(user=self.client_user, mobile='4387388944')
        self.assertEqual(self.remind(eligible=False), 0)
        send.assert_not_called()

    @override_settings(NEWT_SMS_AUTOMATIC_FROM='')
    @patch('portal.backend.identity.isolation_sms.sms.send', return_value='accepted')
    def test_nothing_is_sent_while_automatic_sms_is_not_activated(self, send):
        ReminderPhone.objects.create(user=self.client_user, mobile='4387388944')
        self.assertEqual(self.remind(), 0)
        send.assert_not_called()
