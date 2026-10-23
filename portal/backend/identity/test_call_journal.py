from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from packages.newt.cdr import local_instant
from packages.newt.directory import DirectoryUnavailable
from .call_journal import digest, reconcile, run, SETTLE
from .models import Membership, PhoneCallAttempt, AccessAudit

# 2026-10-15 09:40:00 in Montréal (EDT, UTC-4).
T0 = datetime(2026, 10, 15, 13, 40, tzinfo=dt_timezone.utc)


def line(extension, to, clock, duration):
    return {
        'from': extension,
        'to': to,
        'description': 'Québec',
        'dnid': '',
        'local_date': '2026-10-15',
        'local_time': clock,
        'timezone': 'America/Toronto',
        'occurred_at': local_instant('2026-10-15', clock),
        'duration_raw': duration,
        'amount_raw': '0',
    }


@override_settings(
    DEBUG=True,
    NEWT_CDR_HISTORY_ENABLED=True,
    NEWT_USERNAME='synthetic-user',
    NEWT_PASSWORD='synthetic-secret',
)
class CallJournalTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.setter = users.create_user('journal-setter')
        self.admin = users.create_user('journal-admin')
        Membership.objects.create(user=self.setter, workspace='assurance', role='setter')
        Membership.objects.create(user=self.admin, workspace='assurance', role='administrator')
        self.client = APIClient()

    def attempt(self, created_at, destination='14185547880', extension='509', **changes):
        row = PhoneCallAttempt.objects.create(
            request_id=uuid4(),
            user=self.setter,
            workspace='assurance',
            contact_id=42,
            contact_label='Dossier Alpha',
            extension=extension,
            fingerprint='x',
            **{'state': 'accepted', **changes},
            destination_digest=digest(destination),
        )
        PhoneCallAttempt.objects.filter(pk=row.pk).update(created_at=created_at)
        row.refresh_from_db()
        return row

    def test_matching_rules(self):
        first = self.attempt(T0 + timedelta(seconds=30))
        records = [
            line('510', '8193775864', '09:40:25', '8'),
            line('509', '4185547880', '09:40:50', '4'),
            line('509', '4185547880', '09:45:37', '44'),
        ]
        later = T0 + SETTLE + timedelta(minutes=10)
        status, matched = reconcile([first], records, later)[first.pk]
        self.assertEqual(status, 'matched')
        self.assertEqual(matched['duration'], 4)
        self.assertEqual(matched['at'], T0 + timedelta(seconds=50))
        # Two lines in the window: reported, never guessed.
        crowded = records + [line('509', '4185547880', '09:41:37', '44')]
        self.assertEqual(reconcile([first], crowded, later)[first.pk][0], 'ambiguous')
        # One line claimed by two commands is ambiguous for both.
        second = self.attempt(T0 + timedelta(seconds=40))
        both = reconcile([first, second], records, later)
        self.assertEqual({status for status, _ in both.values()}, {'ambiguous'})
        # Other extension or other number: no match; pending until the journal settles.
        other = self.attempt(T0 + timedelta(seconds=30), extension='511')
        self.assertEqual(
            reconcile([other], records, T0 + timedelta(minutes=5))[other.pk][0], 'pending'
        )
        self.assertEqual(reconcile([other], records, later)[other.pk][0], 'not_found')

    @patch('portal.backend.identity.call_journal.fetch_records')
    def test_administrator_reconciles_and_history_shows_duration(self, fetch):
        fetch.return_value = [line('509', '4185547880', '09:40:50', '4')]
        row = self.attempt(T0 + timedelta(seconds=30))
        rejected = self.attempt(T0, state='rejected')
        url = '/api/portal/assurance/call-history/reconcile/'
        self.client.force_login(self.setter)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.admin)
        with patch(
            'portal.backend.identity.call_journal.timezone.now',
            return_value=T0 + timedelta(hours=1),
        ):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data, {'checked': 1, 'matched': 1, 'ambiguous': 0, 'not_found': 0}
        )
        start, end = fetch.call_args.args[2:]
        self.assertEqual((end - start).days, 6)
        row.refresh_from_db()
        self.assertEqual((row.journal_status, row.journal_duration), ('matched', 4))
        rejected.refresh_from_db()
        self.assertEqual(rejected.journal_status, 'pending')
        audit = AccessAudit.objects.get(action='phone.journal_reconciled')
        self.assertNotIn('4185547880', str(audit.metadata))
        history = self.client.get('/api/portal/assurance/call-history/').data['results']
        entry = next(item for item in history if item['request_id'] == str(row.pk))
        self.assertEqual(entry['journal_status'], 'matched')
        self.assertEqual(entry['journal_duration'], 4)
        # A matched call is final: the next run neither refetches it nor changes it.
        fetch.reset_mock()
        with patch(
            'portal.backend.identity.call_journal.timezone.now',
            return_value=T0 + timedelta(hours=1),
        ):
            self.assertEqual(run('assurance')['checked'], 0)
        fetch.assert_not_called()

    @patch('portal.backend.identity.call_journal.fetch_records', side_effect=DirectoryUnavailable)
    def test_unavailable_journal_changes_nothing(self, fetch):
        row = self.attempt(T0)
        self.client.force_login(self.admin)
        with patch(
            'portal.backend.identity.call_journal.timezone.now',
            return_value=T0 + timedelta(hours=1),
        ):
            self.assertEqual(
                self.client.post('/api/portal/assurance/call-history/reconcile/').status_code, 503
            )
        row.refresh_from_db()
        self.assertIsNone(row.journal_checked_at)
        with override_settings(NEWT_CDR_HISTORY_ENABLED=False):
            self.assertEqual(
                self.client.post('/api/portal/assurance/call-history/reconcile/').status_code, 503
            )

    def test_digest_is_keyed_and_older_attempts_are_unavailable(self):
        self.assertNotIn('4185547880', digest('14185547880'))
        self.assertEqual(len(digest('14185547880')), 64)
        PhoneCallAttempt.objects.create(
            request_id=uuid4(),
            user=self.setter,
            workspace='assurance',
            contact_id=1,
            extension='509',
            fingerprint='y',
            state='accepted',
        )
        self.client.force_login(self.admin)
        row = self.client.get('/api/portal/assurance/call-history/').data['results'][0]
        self.assertEqual(row['journal_status'], 'unavailable')
