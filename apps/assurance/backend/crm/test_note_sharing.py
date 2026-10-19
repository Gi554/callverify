from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4
from django.test import TestCase,TransactionTestCase,override_settings
from django.db import connection,close_old_connections
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import Contact,ContactNote,BusinessAudit


def fixture():
    contact=Contact.objects.create(name='Contact',phone='raw',created_by_id=21,assigned_advisor_id=31)
    note=ContactNote.objects.create(contact=contact,request_id=uuid4(),author_id=21,channel='internal',body='SECRET SETTER original')
    return contact,note

@override_settings(DEBUG=True)
class NoteSharingTests(TestCase):
    def setUp(self):
        self.contact,self.note=fixture();self.client=APIClient();self.auth(99,'administrator')
        self.base=f'/api/assurance/contacts/{self.contact.pk}/';self.url=self.base+f'notes/{self.note.pk}/sharing/'
    def auth(self,pk,role,workspace='assurance'):self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(pk,workspace,role))
    def payload(self,**changes):return {'revision':0,'enabled':True,'body':'Informations utiles au rendez-vous','reviewed':True,'reason':'Version destinée au conseiller',**changes}
    def share(self,**changes):return self.client.post(self.url,self.payload(**changes),format='json')
    def test_private_default_then_only_public_copy_in_list_and_timeline(self):
        self.auth(31,'advisor');self.assertEqual(self.client.get(self.base+'notes/').data['count'],0)
        self.auth(99,'administrator');self.assertEqual(self.share().status_code,200)
        self.auth(31,'advisor');response=self.client.get(self.base+'notes/');self.assertEqual(response['Cache-Control'],'no-store');row=response.data['results'][0]
        self.assertEqual(row['body'],'Informations utiles au rendez-vous');self.assertEqual(row['channel'],'shared')
        timeline=self.client.get(self.base+'interactions/');self.assertEqual(timeline.data['results'][0]['detail'],row['body'])
        for secret in ('SECRET SETTER','author_id','sharing_revision','advisor_body','reviewed'):self.assertNotIn(secret,str(response.data)+str(timeline.data))
        self.note.refresh_from_db();self.assertEqual(self.note.body,'SECRET SETTER original');self.assertEqual(self.note.author_id,21)
    def test_revoke_removes_copy_and_preserves_original_and_internal_audit(self):
        self.share();self.assertEqual(self.share(revision=1,enabled=False,reviewed=False).status_code,200)
        self.auth(31,'advisor');self.assertEqual(self.client.get(self.base+'notes/').data['count'],0);self.assertEqual(self.client.get(self.base+'interactions/').data['count'],0)
        self.note.refresh_from_db();self.assertFalse(self.note.advisor_visible);self.assertEqual(self.note.advisor_body,'');self.assertEqual(self.note.body,'SECRET SETTER original')
        self.auth(21,'setter');self.assertEqual(self.client.get(self.base+'notes/').data['results'][0]['body'],'SECRET SETTER original')
        audit=BusinessAudit.objects.filter(action='contact.note_sharing_changed').order_by('-pk').first();self.assertEqual(audit.metadata['before']['body'],'Informations utiles au rendez-vous');self.assertFalse(audit.metadata['after']['enabled'])
    def test_only_admin_and_only_authorized_contact_scope(self):
        for pk,role in ((21,'setter'),(31,'advisor')):
            self.auth(pk,role);self.assertEqual(self.share().status_code,403)
        self.auth(99,'administrator');self.share()
        self.auth(32,'advisor');self.assertEqual(self.client.get(self.base+'notes/').status_code,404)
        self.auth(31,'advisor','isolation');self.assertEqual(self.client.get(self.base+'notes/').status_code,401)
        self.auth(31,'advisor');Contact.objects.filter(pk=self.contact.pk).update(assigned_advisor_id=None);self.assertEqual(self.client.get(self.base+'notes/').status_code,404)
    def test_personal_notes_and_other_contact_are_not_publishable(self):
        ContactNote.objects.filter(pk=self.note.pk).update(channel='advisor',author_id=31)
        self.assertEqual(self.share().status_code,404)
        ContactNote.objects.filter(pk=self.note.pk).update(channel='internal')
        other=Contact.objects.create(name='Other',phone='other',created_by_id=99)
        self.assertEqual(self.client.post(f'/api/assurance/contacts/{other.pk}/notes/{self.note.pk}/sharing/',self.payload(),format='json').status_code,404)
    def test_review_public_text_reason_and_strict_fields_required(self):
        for changes in ({'reviewed':False},{'body':' '},{'body':'x'*5001},{'reason':' '},{'author_id':31}):self.assertEqual(self.share(**changes).status_code,400,changes)
        self.note.refresh_from_db();self.assertFalse(self.note.advisor_visible)
        self.assertEqual(self.client.post(self.base+'notes/',{'request_id':str(uuid4()),'body':'new','advisor_visible':True},format='json').status_code,400)
    def test_stale_revision_and_publication_audit(self):
        self.assertEqual(self.share(revision=99).status_code,409);self.assertEqual(self.share().status_code,200);self.assertEqual(self.share().status_code,409)
        audit=BusinessAudit.objects.get(action='contact.note_sharing_changed');self.assertFalse(audit.metadata['before']['enabled']);self.assertTrue(audit.metadata['after']['enabled']);self.assertTrue(audit.metadata['reviewed']);self.assertEqual(audit.metadata['after']['revision'],1)
    def test_audit_failure_rolls_back_visibility_and_copy(self):
        with patch('apps.assurance.backend.crm.notes.BusinessAudit.objects.create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.share()
        self.note.refresh_from_db();self.assertFalse(self.note.advisor_visible);self.assertEqual(self.note.advisor_body,'');self.assertEqual(self.note.sharing_revision,0)
    def test_advisor_personal_notes_stay_private_and_do_not_become_shared(self):
        ContactNote.objects.create(contact=self.contact,request_id=uuid4(),author_id=32,channel='advisor',body='OTHER ADVISOR SECRET')
        self.auth(31,'advisor');result=self.client.post(self.base+'notes/',{'request_id':str(uuid4()),'body':'My own note'},format='json');self.assertEqual(result.status_code,201)
        self.assertEqual(result.data['channel'],'advisor');self.assertNotIn('OTHER ADVISOR SECRET',str(self.client.get(self.base+'notes/').data))

@skipUnless(connection.vendor=='postgresql','Note publication concurrency requires PostgreSQL')
@override_settings(DEBUG=True)
class ConcurrentNoteSharingTests(TransactionTestCase):
    def test_one_publication_for_same_revision(self):
        contact,note=fixture();barrier=Barrier(2)
        def worker(body):
            close_old_connections()
            try:
                client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(99,'assurance','administrator'));barrier.wait(timeout=10)
                return client.post(f'/api/assurance/contacts/{contact.pk}/notes/{note.pk}/sharing/',{'revision':0,'enabled':True,'body':body,'reviewed':True,'reason':'Version contrôlée'},format='json').status_code
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,['Version One','Version Two']))
        self.assertEqual(sorted(results),[200,409]);self.assertEqual(BusinessAudit.objects.filter(action='contact.note_sharing_changed').count(),1)
