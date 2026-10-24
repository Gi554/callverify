from unittest.mock import patch, Mock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command, CommandError
from django.utils import timezone
from packages.access.mail_bridge import verify
from .models import Membership, PortalMail, AssuranceMailRelay, AssuranceMailCursor
from .assurance_mail import sync, fetch
from .mail_queue import dispatch
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from django.db import connection, close_old_connections
from django.test import TransactionTestCase


@override_settings(
    DEBUG=True,
    PORTAL_MAIL_KEY='',
    PORTAL_PUBLIC_URL='http://localhost:5173',
    ASSURANCE_INTERNAL_URL='http://assurance:8000',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class AssuranceMailTests(TestCase):
    def setUp(self):
        mail.outbox = []
        self.user = get_user_model().objects.create_user(
            'setter', email='setter@example.test', password='Initial-Password!6241'
        )
        self.grant = Membership.objects.create(user=self.user, workspace='assurance', role='setter')
        self.events = {
            'events': [
                {'id': 1, 'setter_id': self.user.pk, 'created_at': timezone.now().isoformat()}
            ]
        }

    def sync(self, events=None):
        with patch(
            'portal.backend.identity.assurance_mail.fetch', return_value=events or self.events
        ):
            return sync()

    def test_queue_is_idempotent_and_content_is_minimal(self):
        self.assertEqual(self.sync()['queued'], 1)
        self.assertEqual(self.sync()['already_queued'], 1)
        self.assertEqual(PortalMail.objects.count(), 1)
        self.assertEqual(AssuranceMailRelay.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)
        with patch('portal.backend.identity.assurance_mail.eligible', return_value=True):
            self.assertEqual(dispatch()['sent'], 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn('http://localhost:5173/crm', mail.outbox[0].body)
        self.assertNotIn('setter', mail.outbox[0].body)
        self.assertNotIn('prospect', mail.outbox[0].body)
        html, mime = mail.outbox[0].alternatives[0]
        self.assertEqual(mime, 'text/html')
        self.assertIn('Consulter mon espace', html)
        self.assertNotIn(self.user.email, html)
        self.assertNotIn('setter', html)
        self.assertEqual(PortalMail.objects.get().payload, '')

    def test_role_account_email_and_ambiguous_address_checks(self):
        for attr, value in (('active', False), ('role', 'advisor')):
            setattr(self.grant, attr, value)
            self.grant.save()
            self.assertEqual(self.sync()['skipped'], 1)
            self.grant.active = True
            self.grant.role = 'setter'
            self.grant.save()
        self.user.email = ''
        self.user.save()
        self.assertEqual(self.sync()['skipped'], 1)
        self.user.email = 'setter@example.test'
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.sync()['skipped'], 1)
        self.user.is_active = True
        self.user.save()
        get_user_model().objects.create_user('duplicate', email=self.user.email)
        self.assertEqual(self.sync()['skipped'], 1)
        self.assertFalse(PortalMail.objects.exists())

    def test_sending_rechecks_central_rights_and_source_state(self):
        self.sync()
        self.grant.active = False
        self.grant.save()
        with patch('portal.backend.identity.assurance_mail.eligible') as source:
            self.assertEqual(dispatch()['expired'], 1)
            source.assert_not_called()
        self.grant.active = True
        self.grant.save()
        self.events['events'][0]['id'] = 2
        self.sync()
        with patch('portal.backend.identity.assurance_mail.eligible', return_value=False):
            self.assertEqual(dispatch()['expired'], 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_unavailable_source_retries_and_does_not_send(self):
        self.sync()
        with patch(
            'portal.backend.identity.assurance_mail.eligible',
            side_effect=RuntimeError('private token'),
        ):
            self.assertEqual(dispatch()['retry'], 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_reassignment_can_queue_for_new_recipient_without_repeating_old(self):
        self.sync()
        other = get_user_model().objects.create_user('other', email='other@example.test')
        Membership.objects.create(user=other, workspace='assurance', role='setter')
        self.events['events'][0]['setter_id'] = other.pk
        self.assertEqual(self.sync()['queued'], 1)
        self.assertEqual(self.sync()['already_queued'], 1)
        self.assertEqual(AssuranceMailRelay.objects.count(), 2)

    def test_batch_cursor_and_validation(self):
        events = {
            'events': [
                {'id': i, 'setter_id': self.user.pk, 'created_at': timezone.now().isoformat()}
                for i in range(1, 101)
            ]
        }
        self.assertEqual(self.sync(events)['queued'], 100)
        self.assertEqual(AssuranceMailCursor.objects.get().after_id, 100)
        self.sync({'events': []})
        self.assertEqual(AssuranceMailCursor.objects.get().after_id, 0)
        with self.assertRaises(ValueError):
            self.sync({'events': [{'id': 'bad'}]})
        self.assertEqual(PortalMail.objects.count(), 100)

    def test_queue_failure_rolls_back_ledger_and_cursor_allows_retry(self):
        with patch('portal.backend.identity.mail_queue.enqueue', side_effect=RuntimeError('queue')):
            with self.assertRaises(RuntimeError):
                self.sync()
        self.assertFalse(AssuranceMailRelay.objects.exists())
        self.assertEqual(AssuranceMailCursor.objects.get().after_id, 0)
        self.assertEqual(self.sync()['queued'], 1)

    def test_http_credentials_are_purpose_bound_and_redirects_are_refused(self):
        with patch(
            'portal.backend.identity.assurance_mail.requests.get',
            return_value=Mock(status_code=200, json=lambda: {'events': []}),
        ) as get:
            self.assertEqual(
                fetch('/api/assurance/internal/mail-events/?after=0', 'events', after=0),
                {'events': []},
            )
            kwargs = get.call_args.kwargs
            verify(kwargs['headers']['Authorization'][7:], 'events', after=0)
            self.assertFalse(kwargs['allow_redirects'])
            self.assertEqual(kwargs['timeout'], 5)
        with patch(
            'portal.backend.identity.assurance_mail.requests.get',
            return_value=Mock(status_code=302),
        ):
            with self.assertRaises(RuntimeError):
                fetch('/test', 'events', after=0)

    def test_command_never_logs_exception_or_signed_token(self):
        with patch(
            'portal.backend.identity.management.commands.relay_assurance_mail.sync',
            side_effect=RuntimeError('secret'),
        ):
            with self.assertRaises(CommandError) as error:
                call_command('relay_assurance_mail')
        self.assertNotIn('secret', str(error.exception))

    def test_advisor_reminder_uses_own_stream_and_role(self):
        self.grant.role = 'advisor'
        self.grant.save()
        events = {
            'events': [
                {
                    'id': 1,
                    'recipient_id': self.user.pk,
                    'role': 'advisor',
                    'created_at': timezone.now().isoformat(),
                }
            ]
        }
        with patch('portal.backend.identity.assurance_mail.fetch', return_value=events):
            self.assertEqual(sync('reminders')['queued'], 1)
            self.assertEqual(sync('reminders')['already_queued'], 1)
        self.assertEqual(AssuranceMailRelay.objects.get().stream, 'reminders')
        with patch('portal.backend.identity.assurance_mail.eligible', return_value=True) as source:
            self.assertEqual(dispatch()['sent'], 1)
            source.assert_called_once_with(1, self.user.pk, stream='reminders')
        self.assertNotIn('setter', mail.outbox[0].body)
        self.assertNotIn(self.user.email, mail.outbox[0].body)
        self.assertIn('http://localhost:5173/crm', mail.outbox[0].body)

    def test_incident_and_reminder_ids_do_not_collide(self):
        self.sync()
        events = {
            'events': [
                {
                    'id': 1,
                    'recipient_id': self.user.pk,
                    'role': 'setter',
                    'created_at': timezone.now().isoformat(),
                }
            ]
        }
        with patch('portal.backend.identity.assurance_mail.fetch', return_value=events):
            self.assertEqual(sync('reminders')['queued'], 1)
        self.assertEqual(PortalMail.objects.count(), 2)
        self.assertEqual(AssuranceMailCursor.objects.count(), 2)

    def test_reminder_wrong_role_or_resolved_source_is_not_sent(self):
        events = {
            'events': [
                {
                    'id': 1,
                    'recipient_id': self.user.pk,
                    'role': 'advisor',
                    'created_at': timezone.now().isoformat(),
                }
            ]
        }
        with patch('portal.backend.identity.assurance_mail.fetch', return_value=events):
            self.assertEqual(sync('reminders')['skipped'], 1)
        self.grant.role = 'advisor'
        self.grant.save()
        with patch('portal.backend.identity.assurance_mail.fetch', return_value=events):
            self.assertEqual(sync('reminders')['queued'], 1)
        with patch('portal.backend.identity.assurance_mail.eligible', return_value=False):
            self.assertEqual(dispatch()['expired'], 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_reminder_stream_http_operation_is_separate(self):
        from .assurance_mail import eligible

        with patch(
            'portal.backend.identity.assurance_mail.requests.get',
            return_value=Mock(status_code=200, json=lambda: {'eligible': True}),
        ) as get:
            self.assertTrue(eligible(1, self.user.pk, stream='reminders'))
            verify(
                get.call_args.kwargs['headers']['Authorization'][7:],
                'reminder_eligible',
                event=1,
                user=self.user.pk,
            )
            self.assertIn('/reminder-mail-events/', get.call_args.args[0])

    def escalation_feed(self):
        return {
            'events': [
                {
                    'id': 1,
                    'recipient_id': 0,
                    'role': 'administrator',
                    'created_at': timezone.now().isoformat(),
                }
            ]
        }

    def admins(self):
        users = []
        for name in ('admin-a', 'admin-b'):
            user = get_user_model().objects.create_user(name, email=name + '@example.test')
            Membership.objects.create(user=user, workspace='assurance', role='administrator')
            users.append(user)
        return users

    def test_escalation_fans_out_only_to_explicit_assurance_administrators(self):
        admins = self.admins()
        other = get_user_model().objects.create_user(
            'isolation-admin', email='isolation@example.test'
        )
        Membership.objects.create(user=other, workspace='isolation', role='administrator')
        get_user_model().objects.create_user(
            'super', email='super@example.test', is_superuser=True, is_staff=True
        )
        with patch(
            'portal.backend.identity.assurance_mail.fetch', return_value=self.escalation_feed()
        ):
            self.assertEqual(sync('escalations')['queued'], 2)
            self.assertEqual(sync('escalations')['already_queued'], 2)
        self.assertEqual(AssuranceMailCursor.objects.get().pk, 3)
        with patch('portal.backend.identity.assurance_mail.eligible', return_value=True) as source:
            self.assertEqual(dispatch()['sent'], 2)
            self.assertEqual(source.call_count, 2)
            self.assertTrue(
                all(call.kwargs == {'stream': 'escalations'} for call in source.call_args_list)
            )
        self.assertEqual(
            {message.to[0] for message in mail.outbox}, {user.email for user in admins}
        )
        self.assertTrue(
            all(
                'setter' not in message.body and 'prospect' not in message.body
                for message in mail.outbox
            )
        )

    def test_escalation_rechecks_admin_grant_before_smtp(self):
        admins = self.admins()
        with patch(
            'portal.backend.identity.assurance_mail.fetch', return_value=self.escalation_feed()
        ):
            sync('escalations')
        Membership.objects.filter(user=admins[0], workspace='assurance').update(active=False)
        with patch('portal.backend.identity.assurance_mail.eligible', return_value=True):
            result = dispatch()
            self.assertEqual(result['expired'], 1)
            self.assertEqual(result['sent'], 1)
        self.assertEqual(mail.outbox[0].to, [admins[1].email])

    def test_escalation_cannot_be_injected_into_reminder_stream_or_target_a_user(self):
        feed = self.escalation_feed()
        with patch('portal.backend.identity.assurance_mail.fetch', return_value=feed):
            with self.assertRaises(ValueError):
                sync('reminders')
        feed['events'][0]['recipient_id'] = self.user.pk
        with patch('portal.backend.identity.assurance_mail.fetch', return_value=feed):
            with self.assertRaises(ValueError):
                sync('escalations')
        self.assertFalse(PortalMail.objects.exists())

    def test_escalation_eligibility_uses_own_signed_operation(self):
        from .assurance_mail import eligible

        with patch(
            'portal.backend.identity.assurance_mail.requests.get',
            return_value=Mock(status_code=200, json=lambda: {'eligible': True}),
        ) as get:
            self.assertTrue(eligible(1, self.user.pk, stream='escalations'))
            verify(
                get.call_args.kwargs['headers']['Authorization'][7:],
                'escalation_eligible',
                event=1,
                user=self.user.pk,
            )
            self.assertIn('/escalation-mail-events/', get.call_args.args[0])


@skipUnless(connection.vendor == 'postgresql', 'Concurrent relay deduplication requires PostgreSQL')
@override_settings(
    DEBUG=True,
    PORTAL_MAIL_KEY='',
    PORTAL_PUBLIC_URL='http://localhost:5173',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class ConcurrentRelayTests(TransactionTestCase):
    def test_two_relays_queue_one_email_for_the_same_event_and_recipient(self):
        user = get_user_model().objects.create_user('setter', email='setter@example.test')
        Membership.objects.create(user=user, workspace='assurance', role='setter')
        events = {
            'events': [{'id': 1, 'setter_id': user.pk, 'created_at': timezone.now().isoformat()}]
        }

        def attempt(_):
            close_old_connections()
            try:
                return sync()
            finally:
                close_old_connections()

        with patch('portal.backend.identity.assurance_mail.fetch', return_value=events):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(attempt, range(2)))
        self.assertEqual(sum(row['queued'] for row in results), 1)
        self.assertEqual(AssuranceMailRelay.objects.count(), 1)
        self.assertEqual(PortalMail.objects.count(), 1)
