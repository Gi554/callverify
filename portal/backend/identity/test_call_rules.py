from datetime import datetime
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from packages.access.phone_calls import issue
from .call_rules import normalize, refusal, window
from .models import AccessAudit, CallExclusion, CallRules, Membership, PhoneCallAttempt
from .models import PhoneExtension

MONTREAL = ZoneInfo('America/Montreal')


def moment(*args):
    return datetime(*args, tzinfo=MONTREAL)


class CallWindowTests(TestCase):
    def test_default_windows_follow_weekday_and_weekend_hours(self):
        row = CallRules.objects.create(pk=1)
        # Wednesday 28 October 2026 and Saturday 31 October 2026.
        self.assertTrue(window(row, moment(2026, 10, 28, 9, 30))[0])
        self.assertTrue(window(row, moment(2026, 10, 28, 21, 29))[0])
        self.assertFalse(window(row, moment(2026, 10, 28, 9, 29))[0])
        self.assertFalse(window(row, moment(2026, 10, 28, 21, 30))[0])
        self.assertFalse(window(row, moment(2026, 10, 31, 9, 59))[0])
        self.assertTrue(window(row, moment(2026, 10, 31, 10, 0))[0])
        self.assertFalse(window(row, moment(2026, 10, 31, 18, 0))[0])
        self.assertIn('09:30', window(row, moment(2026, 10, 28, 3, 0))[1])

    def test_switching_off_the_hours_keeps_the_exclusion_list(self):
        CallRules.objects.create(pk=1, enforce_hours=False)
        CallExclusion.objects.create(number='15145550101')
        night = moment(2026, 10, 28, 3, 0)
        self.assertEqual(refusal('15145550199', night), '')
        self.assertIn('exclusion', refusal('15145550101', night))

    def test_numbers_are_normalized_like_the_dialed_form(self):
        self.assertEqual(normalize('(514) 555-0101'), '15145550101')
        self.assertEqual(normalize('+1 514 555 0101'), '15145550101')
        self.assertIsNone(normalize('555-0101'))
        self.assertIsNone(normalize('abc'))


@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CallRulesApiTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('admin')
        self.setter = get_user_model().objects.create_user('setter')
        Membership.objects.create(user=self.admin, workspace='assurance', role='administrator')
        Membership.objects.create(user=self.setter, workspace='assurance', role='setter')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.rules = '/api/portal/workspaces/assurance/call-rules/'
        self.lists = '/api/portal/workspaces/assurance/call-exclusions/'

    def editable(self):
        data = self.client.get(self.rules).data
        return {k: data[k] for k in data if k not in ('allowed_now', 'message')}

    def test_admin_reads_and_updates_rules_with_revision(self):
        body = self.editable()
        self.assertEqual((body['weekday_start'], body['weekend_end']), ('09:30', '18:00'))
        body.update(weekday_start='09:00', enforce_hours=True)
        self.assertEqual(self.client.patch(self.rules, body, format='json').status_code, 200)
        self.assertEqual(self.client.patch(self.rules, body, format='json').status_code, 400)
        self.assertEqual(self.client.get(self.rules).data['weekday_start'], '09:00')
        self.assertTrue(AccessAudit.objects.filter(action='call_rules.updated').exists())

    def test_invalid_rules_are_refused(self):
        body = self.editable()
        for change in ({'timezone': 'Mars/Phobos'}, {'weekday_start': '22:00'}):
            response = self.client.patch(self.rules, {**body, **change}, format='json')
            self.assertEqual(response.status_code, 400)

    def test_exclusions_are_added_deduplicated_listed_and_removed(self):
        response = self.client.post(
            self.lists,
            {'numbers': '514 555 0101\n(514) 555-0101, 819-555-0102; abc', 'reason': 'Demande'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual((response.data['added'], response.data['invalid']), (2, ['abc']))
        again = self.client.post(self.lists, {'numbers': '5145550101'}, format='json')
        self.assertEqual((again.data['added'], again.data['already_listed']), (0, 1))
        listing = self.client.get(self.lists, {'search': '819'}).data
        self.assertEqual([row['number'] for row in listing['results']], ['18195550102'])
        pk = listing['results'][0]['id']
        self.assertEqual(self.client.delete(f'{self.lists}{pk}/').status_code, 204)
        self.assertEqual(CallExclusion.objects.count(), 1)

    def test_setters_and_other_workspace_admins_have_no_access(self):
        self.client.force_authenticate(self.setter)
        self.assertEqual(self.client.get(self.rules).status_code, 403)
        self.assertEqual(self.client.post(self.lists, {'numbers': '5145550101'}).status_code, 403)
        self.client.force_authenticate(self.admin)
        other = self.client.get('/api/portal/workspaces/isolation/call-rules/')
        self.assertEqual(other.status_code, 403)


@override_settings(
    DEBUG=True,
    NEWT_CALLS_ENABLED=True,
    NEWT_USERNAME='synthetic-user',
    NEWT_PASSWORD='synthetic-secret',
)
class CallDispatchGuardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('synthetic-setter')
        self.client = APIClient()
        self.client.force_login(self.user)
        Membership.objects.create(user=self.user, workspace='assurance', role='setter')
        PhoneExtension.objects.create(user=self.user, extension='501')
        eligible = patch('portal.backend.identity.phone_calls.eligible', return_value=True)
        eligible.start()
        self.addCleanup(eligible.stop)
        provider = patch('portal.backend.identity.phone_calls.place', return_value='accepted')
        self.provider = provider.start()
        self.addCleanup(provider.stop)

    def call(self, number='15145550101'):
        proof = issue(self.user.pk, 42, 3, uuid4(), number, uuid4())
        return self.client.post('/api/portal/assurance/calls/', {'proof': proof}, format='json')

    def test_call_outside_hours_is_refused_before_the_provider_and_audited(self):
        CallRules.objects.update_or_create(pk=1, defaults={'enforce_hours': True})
        night = moment(2026, 10, 28, 3, 0).astimezone(ZoneInfo('UTC'))
        with patch('portal.backend.identity.call_rules.current_time', return_value=night):
            response = self.call()
            options = self.client.get('/api/portal/assurance/calls/options/').data
        self.assertEqual(response.status_code, 400)
        self.assertIn('Appels autorisés', response.data['detail'])
        self.assertFalse(options['call_window']['allowed'])
        self.provider.assert_not_called()
        self.assertEqual(PhoneCallAttempt.objects.count(), 0)
        self.assertTrue(AccessAudit.objects.filter(action='phone.call_refused').exists())

    def test_excluded_number_is_refused_but_others_pass(self):
        CallRules.objects.update_or_create(pk=1, defaults={'enforce_hours': False})
        CallExclusion.objects.create(number='15145550101')
        refused = self.call('15145550101')
        self.assertEqual(refused.status_code, 400)
        self.assertIn('exclusion', refused.data['detail'])
        self.provider.assert_not_called()
        self.assertEqual(self.call('15145550102').data['state'], 'accepted')
        self.provider.assert_called_once()
