from datetime import timedelta
from importlib import import_module
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch
from django.apps import apps
from django.db import connection
from django.test import TestCase,override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .test_isolation_activity import assigned_fixture
from .models import Prospect,ProspectActivity,IsolationFollowUp,IsolationVisit,AuditEvent


@override_settings(DEBUG=True,SECURE_SSL_REDIRECT=False)
class FollowUpTests(TestCase):
    def setUp(self):
        self.prospect=assigned_fixture();self.client=APIClient();self.auth(21,'setter')
        self.base=f'/api/work-queue/{self.prospect.pk}/';self.due=timezone.now()+timedelta(days=1)
    def auth(self,pk,role,space='isolation'):self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(pk,space,role))
    def call_payload(self,**changes):return {'request_id':str(uuid4()),'revision':0,'result':'voicemail','note':'',**changes}
    def call(self,**changes):return self.client.post(self.base+'call-result/',self.call_payload(**changes),format='json')
    def task_payload(self,**changes):return {'request_id':str(uuid4()),'revision':0,'note':'Rappeler le prospect','due_at':self.due.isoformat(),**changes}
    def task(self,**changes):return self.client.post(self.base+'follow-ups/',self.task_payload(**changes),format='json')

    def test_search_filters_before_pagination_without_widening_setter_scope(self):
        own=IsolationFollowUp.objects.create(prospect=self.prospect,request_id=uuid4(),fingerprint='test',created_by_id=21,
            note='Dossier rénovation',due_at=self.due)
        other=Prospect.objects.create(campaign=self.prospect.campaign,raw_phone='+10000000002',name='Rénovation hors périmètre',
            assigned_setter_id=22,assigned_setter_name='Autre setter')
        IsolationFollowUp.objects.create(prospect=other,request_id=uuid4(),fingerprint='test',created_by_id=22,
            note='Dossier rénovation',due_at=self.due)
        response=self.client.get('/api/follow-ups/',{'state':'upcoming','search':'rénovation'})
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['count'],1)
        self.assertEqual(response.data['results'][0]['id'],own.pk)
        self.assertEqual(response.data['results'][0]['owner_name'],'Setter')
        self.assertEqual(self.client.get('/api/follow-ups/',{'search':'absent'}).data['count'],0)
        self.auth(90,'administrator')
        self.assertEqual(self.client.get('/api/follow-ups/',{'state':'upcoming','search':'rénovation'}).data['count'],2)

    def test_results_are_declared_and_do_not_change_lookup_or_commercial_status(self):
        for index,result in enumerate(('voicemail','invalid_number','disconnected','not_interested','unreachable')):
            response=self.call(result=result,revision=index)
            self.assertEqual(response.status_code,201,response.data)
            self.assertEqual(response.data['changes']['result'],result)
        self.prospect.refresh_from_db();self.prospect.phone.refresh_from_db()
        self.assertEqual(self.prospect.phone.line_status,'unknown')
        self.assertEqual(self.prospect.commercial_status,'to_contact')
        self.assertEqual(ProspectActivity.objects.filter(kind='call_result').count(),5)
        self.assertFalse(IsolationFollowUp.objects.exists())
        self.assertFalse(IsolationVisit.objects.exists())

    def test_callback_is_atomic_and_idempotent(self):
        body=self.call_payload(result='callback',due_at=self.due.isoformat(),note='Après-midi')
        first=self.client.post(self.base+'call-result/',body,format='json')
        self.assertEqual(first.status_code,201,first.data)
        self.assertEqual(self.client.post(self.base+'call-result/',body,format='json').status_code,200)
        self.assertEqual(IsolationFollowUp.objects.count(),1)
        self.assertEqual(ProspectActivity.objects.count(),1)
        task=IsolationFollowUp.objects.get();self.assertEqual(task.note,'Après-midi')
        self.prospect.refresh_from_db();self.assertEqual(self.prospect.assignment_revision,1)
        self.assertEqual(self.prospect.callback_at,self.due)
        self.assertEqual(self.client.post(self.base+'call-result/',{**body,'note':'Autre'},format='json').status_code,409)

    def test_manual_create_retry_edit_close_and_history(self):
        body=self.task_payload()
        response=self.client.post(self.base+'follow-ups/',body,format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(self.client.post(self.base+'follow-ups/',body,format='json').status_code,200)
        task=response.data;url=f"/api/follow-ups/{task['id']}/"
        edited=self.client.post(url+'edit/',{'revision':0,'note':'Demain soir','due_at':(self.due+timedelta(hours=2)).isoformat()},format='json')
        self.assertEqual(edited.status_code,200,edited.data)
        self.assertEqual(self.client.post(url+'edit/',{'revision':0,'note':'Périmé','due_at':self.due.isoformat()},format='json').status_code,409)
        self.assertEqual(self.client.post(url+'close/',{'revision':1,'resolution':' '},format='json').status_code,400)
        closed=self.client.post(url+'close/',{'revision':1,'resolution':'Prospect rappelé'},format='json')
        self.assertEqual(closed.status_code,200,closed.data)
        self.assertIsNotNone(closed.data['closed_at'])
        self.assertEqual(self.client.get('/api/follow-ups/').data['count'],0)
        self.assertEqual(self.client.get('/api/follow-ups/?state=closed').data['count'],1)
        self.prospect.refresh_from_db();self.assertIsNone(self.prospect.callback_at)
        kinds=list(ProspectActivity.objects.values_list('kind',flat=True))
        self.assertEqual(kinds,['callback_created','callback_updated','callback_closed'])

    def test_tasks_follow_reassignment_and_former_owner_loses_access(self):
        task=self.task().data;url=f"/api/follow-ups/{task['id']}/"
        Prospect.objects.filter(pk=self.prospect.pk).update(assigned_setter_id=22,assignment_revision=1)
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(self.client.post(url+'close/',{'revision':0,'resolution':'Essai'},format='json').status_code,404)
        self.auth(22,'setter');row=self.client.get(url).data
        self.assertEqual(row['owner_id'],22);self.assertEqual(row['created_by_id'],21)
        self.assertEqual(self.client.post(url+'close/',{'revision':0,'resolution':'Pris en charge'},format='json').status_code,200)

    def test_future_date_offset_and_conditional_fields_validation(self):
        for changes in ({'result':'callback'},{'result':'callback','due_at':self.due.replace(tzinfo=None).isoformat()},
                        {'result':'callback','due_at':(timezone.now()-timedelta(hours=1)).isoformat()},
                        {'due_at':self.due.isoformat()},{'appointment_id':1},{'result':'appointment_booked'},{'result':'invented'}, {'extra':True}):
            self.assertEqual(self.call(**changes).status_code,400,changes)
        self.assertEqual(self.task(due_at=self.due.replace(tzinfo=None).isoformat()).status_code,400)
        self.assertEqual(self.task(revision=99).status_code,409)
        self.assertFalse(IsolationFollowUp.objects.exists());self.assertFalse(ProspectActivity.objects.exists())

    def test_booked_result_requires_existing_authorized_visit(self):
        visit=IsolationVisit.objects.create(prospect=self.prospect,request_id=uuid4(),fingerprint='test',client_id=72,client_name='Client',
            setter_id=21,setter_name='Setter',booked_by_id=21,starts_at=self.due,ends_at=self.due+timedelta(hours=1),timezone='UTC')
        self.assertEqual(self.call(result='appointment_booked',appointment_id=visit.pk+1).status_code,400)
        IsolationVisit.objects.filter(pk=visit.pk).update(status='cancelled')
        self.assertEqual(self.call(result='appointment_booked',appointment_id=visit.pk).status_code,400)
        IsolationVisit.objects.filter(pk=visit.pk).update(status='scheduled',setter_id=22)
        self.assertEqual(self.call(result='appointment_booked',appointment_id=visit.pk).status_code,400)
        IsolationVisit.objects.filter(pk=visit.pk).update(setter_id=21)
        saved=self.call(result='appointment_booked',appointment_id=visit.pk)
        self.assertEqual(saved.status_code,201,saved.data)
        self.assertEqual(saved.data['changes']['appointment_id'],visit.pk)
        self.assertEqual(IsolationVisit.objects.count(),1)

    def test_role_and_workspace_guards(self):
        self.task()
        for role in ('client','closer'):
            self.auth(72,role)
            self.assertEqual(self.client.get('/api/follow-ups/').status_code,403)
            self.assertEqual(self.call().status_code,403)
        self.auth(22,'setter');self.assertEqual(self.client.get('/api/follow-ups/').data['count'],0)
        self.assertEqual(self.task().status_code,404)
        self.auth(21,'setter','assurance');self.assertEqual(self.client.get('/api/follow-ups/').status_code,401)
        self.auth(91,'administrator');self.assertEqual(self.client.get('/api/follow-ups/').data['count'],1)

    def test_filters_counts_and_remaining_earliest_task(self):
        first=self.task().data
        second=self.task(revision=1,due_at=(self.due+timedelta(days=1)).isoformat()).data
        IsolationFollowUp.objects.filter(pk=first['id']).update(due_at=timezone.now()-timedelta(hours=1))
        self.assertEqual(self.client.get('/api/follow-ups/?state=overdue').data['count'],1)
        self.assertEqual(self.client.get('/api/follow-ups/?state=upcoming').data['count'],1)
        self.assertEqual(self.client.get('/api/workspace-dashboard/').data['open_follow_ups'],2)
        self.assertEqual(self.client.get('/api/work-queue/?due=true').data['count'],1)
        self.client.post(f"/api/follow-ups/{first['id']}/close/",{'revision':0,'resolution':'Traité'},format='json')
        self.prospect.refresh_from_db();self.assertEqual(self.prospect.callback_at,self.due+timedelta(days=1))

    def test_legacy_callback_creates_task_and_migration_preserves_existing_dates(self):
        body={'request_id':str(uuid4()),'revision':0,'kind':'qualification','body':'Rappel demandé','status':'callback','callback_at':self.due.isoformat()}
        response=self.client.post(self.base+'activities/',body,format='json')
        self.assertEqual(response.status_code,201,response.data);self.assertEqual(IsolationFollowUp.objects.count(),1)
        self.assertEqual(self.client.post(self.base+'activities/',body,format='json').status_code,200)
        self.assertEqual(IsolationFollowUp.objects.count(),1)
        IsolationFollowUp.objects.all().delete()
        migration=import_module('core.migrations.0017_isolationfollowup')
        migration.preserve_callbacks(apps,SimpleNamespace(connection=connection))
        migrated=IsolationFollowUp.objects.get();self.assertEqual(migrated.due_at,self.due)
        self.assertIsNone(migrated.created_by_id)

    def test_audit_failure_rolls_back_call_task_and_revision(self):
        with patch('core.isolation_followups.AuditEvent.objects.create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.call(result='callback',due_at=self.due.isoformat())
        self.assertFalse(IsolationFollowUp.objects.exists());self.assertFalse(ProspectActivity.objects.exists())
        self.prospect.refresh_from_db();self.assertEqual(self.prospect.assignment_revision,0)

    def test_retries_after_due_time_do_not_duplicate_existing_callback(self):
        body=self.call_payload(result='callback',due_at=self.due.isoformat())
        self.assertEqual(self.client.post(self.base+'call-result/',body,format='json').status_code,201)
        with patch('core.isolation_followups.timezone.now',return_value=self.due+timedelta(hours=1)):
            self.assertEqual(self.client.post(self.base+'call-result/',body,format='json').status_code,200)
        manual=self.task_payload(revision=1,due_at=(self.due+timedelta(hours=2)).isoformat())
        self.assertEqual(self.client.post(self.base+'follow-ups/',manual,format='json').status_code,201)
        with patch('core.isolation_followups.timezone.now',return_value=self.due+timedelta(hours=3)):
            self.assertEqual(self.client.post(self.base+'follow-ups/',manual,format='json').status_code,200)
        self.assertEqual(IsolationFollowUp.objects.count(),2)

    def test_call_and_task_events_cannot_be_published_to_the_client(self):
        result=self.call().data
        visit=IsolationVisit.objects.create(prospect=self.prospect,request_id=uuid4(),fingerprint='test',client_id=72,client_name='Client',
            setter_id=21,setter_name='Setter',booked_by_id=21,starts_at=self.due,ends_at=self.due+timedelta(hours=1),timezone='UTC')
        url=f'/api/visits/{visit.pk}/activities/'
        response=self.client.post(url,{'activity_id':result['id'],'revision':1,'visible':True,'reason':'Essai'},format='json')
        self.assertEqual(response.status_code,400,response.data)
        self.auth(72,'client');self.assertEqual(self.client.get(url).data['count'],0)
