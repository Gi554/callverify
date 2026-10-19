from datetime import timedelta
from unittest.mock import patch
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.management import call_command
from django.db import connection,close_old_connections,transaction
from django.test import TestCase,TransactionTestCase,override_settings
from django.utils import timezone
from .models import PortalMail,AccessAudit,Invitation,Membership
from .mail_queue import enqueue,dispatch,claim_next

@override_settings(DEBUG=True,PORTAL_MAIL_KEY='',EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class MailQueueTests(TestCase):
    def setUp(self):
        mail.outbox=[]
        self.user=get_user_model().objects.create_user('recipient',email='recipient@example.test',password='Initial-Password!6241')
    def queued(self,**changes):
        token=default_token_generator.make_token(self.user)
        return enqueue(user=self.user,subject='Recovery',body='Private link '+token,recipient=self.user.email,
            guard={'kind':'recovery','user':self.user.pk,'token':token},expires_at=timezone.now()+timedelta(minutes=30),**changes)
    def test_encrypted_persistence_no_smtp_in_request_and_erasure_after_delivery(self):
        row=self.queued();self.assertEqual(len(mail.outbox),0)
        self.assertNotIn('Private',row.payload);self.assertNotIn(self.user.email,row.payload)
        self.assertEqual(dispatch()['sent'],1);row.refresh_from_db()
        self.assertEqual(row.status,'sent');self.assertEqual(row.payload,'');self.assertIsNone(row.lease_until)
        self.assertEqual(len(mail.outbox),1);self.assertEqual(dispatch()['sent'],0)
        self.assertNotIn(self.user.email,str(list(AccessAudit.objects.values())))
    def test_retry_schedule_and_terminal_failure_erase_secrets(self):
        row=self.queued()
        with patch('portal.backend.identity.mail_queue.send_mail',side_effect=RuntimeError('private credentials')):
            for attempt in range(1,6):
                PortalMail.objects.filter(pk=row.pk).update(next_attempt_at=timezone.now()-timedelta(seconds=1))
                before=timezone.now();result=dispatch();row.refresh_from_db()
                self.assertEqual(row.attempts,attempt)
                if attempt<5:
                    self.assertEqual(result['retry'],1);self.assertEqual(row.status,'pending')
                    self.assertGreaterEqual(row.next_attempt_at,before+timedelta(seconds=60*2**(attempt-1)))
                    self.assertEqual(sum(dispatch().values()),0)
                else:self.assertEqual(result['failed'],1);self.assertEqual(row.payload,'')
        self.assertNotIn('private credentials',str(list(AccessAudit.objects.values())))
    def test_expired_or_invalidated_links_are_not_sent(self):
        row=self.queued();PortalMail.objects.filter(pk=row.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(dispatch()['expired'],1)
        self.queued();self.user.set_password('New-Password!4628');self.user.save()
        self.assertEqual(dispatch()['expired'],1);self.assertEqual(len(mail.outbox),0)
    def test_revoked_invitation_and_inactive_issuer_are_discarded(self):
        from .invitations import digest
        Membership.objects.create(user=self.user,workspace='assurance',role='administrator')
        row=Invitation.objects.create(username='invitee',email='invitee@example.test',workspace='assurance',role='setter',issuer=self.user,token_hash=digest('token'),expires_at=timezone.now()+timedelta(hours=24))
        def queued():return enqueue(user=self.user,subject='Invite',body='secret',recipient=row.email,guard={'kind':'invitation','id':str(row.pk),'hash':row.token_hash},expires_at=row.expires_at)
        queued();row.revoked_at=timezone.now();row.save();self.assertEqual(dispatch()['expired'],1)
        row.revoked_at=None;row.save();queued();Membership.objects.update(active=False);self.assertEqual(dispatch()['expired'],1)
        self.assertEqual(len(mail.outbox),0)
    def test_claim_lease_prevents_second_worker_and_recovers_after_crash(self):
        row=self.queued();claimed=claim_next();self.assertEqual(claimed.pk,row.pk);self.assertIsNone(claim_next())
        PortalMail.objects.filter(pk=row.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        self.assertEqual(dispatch()['sent'],1);row.refresh_from_db();self.assertEqual(row.attempts,2)
    def test_queue_and_audit_are_atomic_and_command_is_usable(self):
        with patch('portal.backend.identity.mail_queue.AccessAudit.objects.create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.queued()
        self.assertEqual(PortalMail.objects.count(),0)
        self.queued()
        from io import StringIO
        output=StringIO();call_command('dispatch_portal_mail',status=True,stdout=output)
        self.assertIn("'pending': 1",output.getvalue());self.assertEqual(len(mail.outbox),0)
        output=StringIO();call_command('dispatch_portal_mail',limit=10,stdout=output)
        self.assertIn("'sent': 1",output.getvalue());self.assertNotIn(self.user.email,output.getvalue())
    def test_decryption_failure_never_sends_plaintext_or_logs_exception(self):
        row=self.queued();PortalMail.objects.filter(pk=row.pk).update(payload='corrupted')
        self.assertEqual(dispatch()['retry'],1);self.assertEqual(len(mail.outbox),0)

@skipUnless(connection.vendor=='postgresql','Concurrent claims require PostgreSQL')
@override_settings(DEBUG=True,PORTAL_MAIL_KEY='',PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ConcurrentMailTests(TransactionTestCase):
    def test_only_one_worker_claims_the_same_message(self):
        user=get_user_model().objects.create_user('recipient',email='r@example.test',password='Initial-Password!6241')
        enqueue(user=user,subject='test',body='test',recipient=user.email,guard={'kind':'recovery','user':user.pk,'token':'test'},expires_at=timezone.now()+timedelta(minutes=5))
        def attempt(_):
            close_old_connections()
            try:
                row=claim_next();return str(row.pk) if row else None
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,range(2)))
        self.assertEqual(sum(value is not None for value in results),1)
        self.assertEqual(PortalMail.objects.get().attempts,1)
