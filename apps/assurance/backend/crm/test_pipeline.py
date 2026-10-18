from copy import deepcopy
from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase,TransactionTestCase,override_settings
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import Contact,ContactPipeline,BusinessAudit,AppointmentReport,FollowUpTask
from .pipeline import DEFAULT_STAGES

@override_settings(DEBUG=True)
class PipelineTests(TestCase):
    def setUp(self):
        self.client=APIClient();self.auth(19,'setter')
        self.contact=Contact.objects.create(name='Prospect',phone='raw',created_by_id=19,assigned_advisor_id=7)
        self.base=f'/api/assurance/contacts/{self.contact.pk}/'
        self.token=self.client.post(self.base+'lease/',{},format='json').data['token']
    def auth(self,pk,role):self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(pk,'assurance',role))
    def change(self,**changes):
        return self.client.post(self.base+'commercial-status/',{'token':self.token,'revision':0,'pipeline_revision':0,
            'status':'in_progress','reason':'Contact en traitement',**changes},format='json')
    def configure(self,**changes):
        return self.client.post('/api/assurance/pipeline/',{'revision':0,'stages':deepcopy(DEFAULT_STAGES),'reason':'Configuration',**changes},format='json')
    def test_manual_transition_audited_and_no_report_or_task_inferred(self):
        response=self.change(status='appointment_done')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['revision'],1);self.assertEqual(response.data['status_label'],'RDV effectué')
        self.assertEqual(AppointmentReport.objects.count(),0);self.assertEqual(FollowUpTask.objects.count(),0)
        audit=BusinessAudit.objects.get(action='contact.status_changed')
        self.assertEqual(audit.actor_id,19);self.assertEqual(audit.metadata['before'],'to_contact')
        self.assertEqual(audit.metadata['after'],'appointment_done')
        self.assertEqual(self.change(status='appointment_done',revision=1).status_code,200)
        self.assertEqual(BusinessAudit.objects.filter(action='contact.status_changed').count(),1)
    def test_requires_lease_revision_pipeline_and_reason(self):
        for kwargs,expected in [({'token':str(uuid4())},409),({'revision':9},409),({'pipeline_revision':9},409),
            ({'status':'invented'},400),({'reason':' '},400),({'author_id':88},400)]:
            self.assertEqual(self.change(**kwargs).status_code,expected,kwargs)
        self.auth(20,'setter');self.assertEqual(self.change().status_code,409)
        self.auth(19,'setter');self.assertEqual(self.change().status_code,200)
        self.assertEqual(self.change(status='closed').status_code,409)
    def test_advisor_read_allowlist_and_no_status_edit(self):
        self.change();self.auth(7,'advisor')
        self.assertEqual(self.change().status_code,403)
        self.assertEqual(self.configure().status_code,403)
        self.assertEqual(self.client.get(self.base+'history/').status_code,403)
        data=self.client.get(self.base).data
        self.assertEqual(set(data),{'id','name','phone','email','status','status_label','updated_at','revision'})
        self.assertEqual(self.client.get('/api/assurance/pipeline/').status_code,200)
        self.auth(8,'advisor');self.assertEqual(self.client.get(self.base).status_code,404)
    def test_admin_configuration_archive_keeps_existing_value(self):
        self.change();self.assertEqual(self.configure().status_code,403);self.auth(1,'administrator')
        stages=deepcopy(DEFAULT_STAGES);stages[1].update(label='Traitement',active=False)
        stages.append({'key':'review','label':'À revoir','active':True})
        self.assertEqual(self.configure(stages=stages).status_code,200)
        self.assertEqual(self.configure(stages=stages).status_code,409)
        data=self.client.get(self.base).data
        self.assertEqual(data['status'],'in_progress');self.assertEqual(data['status_label'],'Traitement')
        self.auth(19,'setter')
        self.assertEqual(self.change(revision=1,pipeline_revision=1).status_code,400)
        self.assertEqual(self.change(revision=1,pipeline_revision=1,status='review').status_code,200)
        self.assertEqual(self.client.get('/api/assurance/contacts/?status=review').data['count'],1)
        self.assertEqual(self.client.get('/api/assurance/contacts/?status=closed').data['count'],0)
    def test_pipeline_validation_and_initial_stage_protection(self):
        self.auth(1,'administrator')
        for stages in [[],DEFAULT_STAGES+DEFAULT_STAGES,DEFAULT_STAGES[1:],
            [{**s,'active':False} for s in DEFAULT_STAGES],
            [{**s,'key':'bad key'} if i==1 else s for i,s in enumerate(DEFAULT_STAGES)]]:
            self.assertEqual(self.configure(stages=stages).status_code,400)
        self.assertEqual(ContactPipeline.objects.count(),0)
        self.assertEqual(self.configure().status_code,200)
        self.assertEqual(self.configure(revision=1,stages=DEFAULT_STAGES[:-1]).status_code,400)
    def test_status_and_configuration_rollback_when_audit_fails(self):
        with patch('apps.assurance.backend.crm.pipeline.BusinessAudit.objects.create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.change()
            self.auth(1,'administrator')
            with self.assertRaises(RuntimeError):self.configure()
        self.contact.refresh_from_db();self.assertEqual(self.contact.status,'to_contact');self.assertEqual(self.contact.revision,0)
        self.assertFalse(ContactPipeline.objects.exists())

@override_settings(DEBUG=True)
class ConcurrentPipelineTests(TransactionTestCase):
    def test_two_status_updates_cannot_overwrite(self):
        from django.db import connection,connections
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        if connection.vendor!='postgresql':self.skipTest('Concurrence vérifiée dans la CI PostgreSQL')
        fixture=PipelineTests(methodName='test_requires_lease_revision_pipeline_and_reason');fixture.setUp();barrier=Barrier(2)
        def change(status):
            try:
                client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(19,'assurance','setter'))
                barrier.wait(timeout=10)
                return client.post(fixture.base+'commercial-status/',{'token':fixture.token,'revision':0,'pipeline_revision':0,
                    'status':status,'reason':'Qualification'},format='json').status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(change,['callback','interested']))
        self.assertEqual(sorted(results),[200,409])
        fixture.contact.refresh_from_db();self.assertEqual(fixture.contact.revision,1)
        self.assertEqual(BusinessAudit.objects.filter(action='contact.status_changed').count(),1)
