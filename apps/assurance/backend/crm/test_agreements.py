from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TestCase,TransactionTestCase,override_settings
from django.db import connection,close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import Contact,Agreement,BusinessAudit

@override_settings(DEBUG=True)
class AgreementTests(TestCase):
    def setUp(self):
        self.contact=Contact.objects.create(name='Prospect',phone='raw',created_by_id=21,assigned_advisor_id=31)
        self.client=APIClient();self.auth(99,'administrator');self.base=f'/api/assurance/contacts/{self.contact.pk}/';self.url=self.base+'agreements/'
        self.token=self.client.post(self.base+'lease/',{},format='json').data['token'];self.key=str(uuid4())
    def auth(self,pk,role,workspace='assurance'):self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(pk,workspace,role))
    def body(self,**changes):return {'token':self.token,'contact_revision':0,'request_id':self.key,'kind':'mandate','reference':'AMX-001','status':'draft','starts_on':None,'ends_on':None,'reason':'Ouverture du suivi',**changes}
    def create(self,**changes):return self.client.post(self.url,self.body(**changes),format='json')
    def edit(self,row,**changes):
        body=self.body(**changes);body.pop('kind');body.pop('request_id');body['revision']=changes.get('revision',0)
        return self.client.post(self.url+f'{row.pk}/edit/',body,format='json')
    def test_create_update_archive_history_and_no_side_effects(self):
        response=self.create();self.assertEqual(response.status_code,201,response.data);row=Agreement.objects.get();self.assertEqual(response.data['contact_revision'],1)
        response=self.edit(row,contact_revision=1,status='tracking',starts_on='2026-10-01',ends_on='2026-12-31');self.assertEqual(response.status_code,200,response.data)
        response=self.edit(row,contact_revision=2,revision=1,status='archived');self.assertEqual(response.status_code,200)
        self.contact.refresh_from_db();self.assertEqual(self.contact.revision,3);self.assertEqual(self.contact.status,'to_contact');self.assertEqual(self.contact.assigned_advisor_id,31)
        history=self.client.get(self.url+f'{row.pk}/history/');self.assertEqual(history.data['count'],3);self.assertEqual(history['Cache-Control'],'no-store');self.assertEqual(history.data['results'][0]['before']['status'],'tracking')
        self.assertNotIn('token',str(history.data));self.assertEqual(self.client.get(self.url).data['count'],1)
    def test_creation_retry_exact_no_duplicate_and_changed_actor_or_content_refused(self):
        self.create();self.assertEqual(self.create().status_code,200);self.assertEqual(Agreement.objects.count(),1);self.assertEqual(self.create(reference='Other').status_code,409)
        self.auth(98,'administrator');self.assertEqual(self.create().status_code,409)
    def test_lease_revision_expiry_and_kind_immutable(self):
        self.assertEqual(self.create(token=str(uuid4())).status_code,409);self.assertEqual(self.create(contact_revision=99).status_code,409)
        self.create();row=Agreement.objects.get();self.assertEqual(self.edit(row,contact_revision=0).status_code,409)
        self.assertEqual(self.edit(row,contact_revision=1,revision=99).status_code,409)
        body=self.body(contact_revision=1);body.pop('request_id');body['revision']=0
        self.assertEqual(self.client.post(self.url+f'{row.pk}/edit/',body,format='json').status_code,400)
        Contact.objects.filter(pk=self.contact.pk).update(lease_expires_at=timezone.now()-timedelta(seconds=1));self.assertEqual(self.edit(row,contact_revision=1).status_code,409)
    def test_internal_admin_only_on_list_create_update_and_history(self):
        self.create();row=Agreement.objects.get()
        for pk,role in ((21,'setter'),(31,'advisor')):
            self.auth(pk,role);self.assertEqual(self.client.get(self.url).status_code,403);self.assertEqual(self.create().status_code,403);self.assertEqual(self.edit(row).status_code,403);self.assertEqual(self.client.get(self.url+f'{row.pk}/history/').status_code,403)
        self.auth(99,'administrator','isolation');self.assertEqual(self.client.get(self.url).status_code,401)
    def test_dates_strict_fields_required_reason_and_unique_reference(self):
        for changes in ({'reference':' '},{'reason':' '},{'status':'signed'},{'starts_on':'2026-12-01','ends_on':'2026-10-01'},{'ends_on':'bad'},{'amount':120}):self.assertEqual(self.create(**changes).status_code,400,changes)
        self.assertEqual(self.create().status_code,201)
        self.assertEqual(self.create(request_id=str(uuid4()),contact_revision=1).status_code,409)
        self.assertEqual(self.create(request_id=str(uuid4()),contact_revision=1,kind='contract').status_code,201)
    def test_foreign_contact_update_and_history_do_not_leak(self):
        self.create();row=Agreement.objects.get();other=Contact.objects.create(name='Other',phone='raw',created_by_id=99)
        token=self.client.post(f'/api/assurance/contacts/{other.pk}/lease/',{},format='json').data['token'];body=self.body(token=token);body.pop('kind');body.pop('request_id');body['revision']=0
        url=f'/api/assurance/contacts/{other.pk}/agreements/{row.pk}/'
        self.assertEqual(self.client.post(url+'edit/',body,format='json').status_code,404);self.assertEqual(self.client.get(url+'history/').status_code,404)
    def test_audit_failure_rolls_back_creation_and_revision(self):
        with patch('apps.assurance.backend.crm.agreements.BusinessAudit.objects.create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.create()
        self.assertFalse(Agreement.objects.exists());self.contact.refresh_from_db();self.assertEqual(self.contact.revision,0)
    def test_noop_does_not_increment_and_history_is_paginated(self):
        self.create();row=Agreement.objects.get();response=self.edit(row,contact_revision=1);self.assertEqual(response.status_code,200);self.assertEqual(response.data['contact_revision'],1)
        for n in range(26):BusinessAudit.objects.create(actor_id=99,action='contact.agreement_changed',object_id=self.contact.pk,metadata={'agreement_id':row.pk,'after':{'revision':n},'reason':'test'})
        result=self.client.get(self.url+f'{row.pk}/history/');self.assertEqual(result.data['count'],27);self.assertEqual(len(result.data['results']),25)
        self.assertEqual(self.client.delete(self.url+f'{row.pk}/edit/').status_code,405)

    def test_audit_failure_rolls_back_edit_and_reference_can_reopen(self):
        self.create();row=Agreement.objects.get()
        with patch('apps.assurance.backend.crm.agreements.BusinessAudit.objects.create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.edit(row,contact_revision=1,status='archived')
        row.refresh_from_db();self.assertEqual(row.status,'draft');self.assertEqual(row.revision,0)
        self.assertEqual(self.edit(row,contact_revision=1,status='archived').status_code,200)
        self.assertEqual(self.edit(row,contact_revision=2,revision=1,status='tracking').status_code,200)

@skipUnless(connection.vendor=='postgresql','Agreement concurrency requires PostgreSQL')
@override_settings(DEBUG=True)
class AgreementConcurrencyTests(TransactionTestCase):
    def test_two_edits_same_version_only_one_commits(self):
        fixture=AgreementTests(methodName='test_create_update_archive_history_and_no_side_effects');fixture.setUp();fixture.create();row=Agreement.objects.get();barrier=Barrier(2)
        def worker(reference):
            close_old_connections()
            try:
                client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(99,'assurance','administrator'));body=fixture.body(reference=reference,contact_revision=1);body.pop('kind');body.pop('request_id');body['revision']=0;barrier.wait(timeout=10)
                return client.post(fixture.url+f'{row.pk}/edit/',body,format='json').status_code
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,['One','Two']))
        self.assertEqual(sorted(results),[200,409]);row.refresh_from_db();self.assertEqual(row.revision,1)

    def test_concurrent_same_creation_has_one_record(self):
        fixture=AgreementTests(methodName='test_create_update_archive_history_and_no_side_effects');fixture.setUp();barrier=Barrier(2)
        def worker(_):
            close_old_connections()
            try:
                client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(99,'assurance','administrator'));barrier.wait(timeout=10)
                return client.post(fixture.url,fixture.body(),format='json').status_code
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,range(2)))
        self.assertEqual(sorted(results),[200,201]);self.assertEqual(Agreement.objects.count(),1)
