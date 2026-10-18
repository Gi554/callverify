from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase,TransactionTestCase,override_settings
from django.utils import timezone
from django.core import signing
from rest_framework.test import APIClient
from packages.access.tickets import issue
from packages.access.followups import issue_owner,verify_owner
from .models import FollowUpTask,BusinessAudit

def task_fixture():
    from .tests import ReportTests
    fixture=ReportTests(methodName='test_negative_report_creates_one_task_for_original_setter_and_retry_is_idempotent')
    fixture.setUp();fixture.report()
    task=FollowUpTask.objects.get()
    client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(99,'assurance','administrator'))
    return client,task,f'/api/assurance/follow-ups/{task.pk}/'

@override_settings(DEBUG=True)
class TaskAssignmentTests(TestCase):
    def setUp(self):self.client,self.task,self.url=task_fixture()
    def auth(self,pk,role):self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(pk,'assurance',role))
    def payload(self,**changes):return {'revision':0,'proof':issue_owner(99,self.task.pk,22,'Nouveau setter'),'reason':'Répartition du suivi',**changes}
    def reassign(self,**changes):return self.client.post(self.url+'reassign/?state=all',self.payload(**changes),format='json')
    def test_move_task_and_alert_but_preserve_origin_deadline_and_report(self):
        due_at=self.task.due_at
        response=self.reassign();self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['assigned_setter_id'],22);self.assertEqual(response.data['original_setter_id'],21)
        self.task.refresh_from_db();self.assertEqual(self.task.revision,1);self.assertEqual(self.task.setter_id,22)
        self.assertEqual(self.task.due_at,due_at)
        self.assertEqual(self.task.appointment.setter_id,21);self.assertEqual(self.task.priority,'normal')
        self.assertFalse(self.task.appointment.report.performed);self.assertEqual(FollowUpTask.objects.count(),1)
        self.auth(21,'setter');self.assertEqual(self.client.get('/api/assurance/dashboard/').data['open_follow_ups'],0)
        self.assertEqual(self.client.get(self.url).status_code,404)
        self.auth(22,'setter');self.assertEqual(self.client.get('/api/assurance/dashboard/').data['open_follow_ups'],1)
        row=self.client.get(self.url).data
        self.assertNotIn('original_setter_id',row);self.assertNotIn('assigned_setter_id',row)
        self.assertEqual(self.client.get(self.url+'history/').status_code,403)
        self.assertEqual(self.client.post(self.url+'close/',{'revision':1,'resolution':'Suivi terminé'},format='json').status_code,200)
    def test_admin_history_preserves_before_after_and_reason(self):
        self.reassign()
        row=self.client.get(self.url+'history/').data['results'][0]
        self.assertEqual(row['action'],'appointment.follow_up_reassigned');self.assertEqual(row['actor_id'],99)
        self.assertEqual(row['metadata']['before']['setter_id'],21);self.assertEqual(row['metadata']['after']['setter_id'],22)
        self.assertEqual(row['metadata']['original_setter_id'],21)
    def test_admin_only_and_invalid_or_wrong_purpose_proof(self):
        for pk,role in ((21,'setter'),(31,'advisor')):
            self.auth(pk,role);self.assertEqual(self.reassign().status_code,403)
        self.auth(99,'administrator')
        proofs=[issue_owner(98,self.task.pk,22,'Setter'),issue_owner(99,self.task.pk+1,22,'Setter'),
            issue(22,'assurance','setter'),'invalid']
        with patch('django.core.signing.time.time',return_value=1000):proofs.append(issue_owner(99,self.task.pk,22,'Setter'))
        for proof in proofs:self.assertEqual(self.reassign(proof=proof).status_code,400)
        with self.assertRaises(signing.BadSignature):verify_owner(issue_owner(99,self.task.pk,22,'Setter')+'x',99,self.task.pk)
    def test_stale_closed_same_owner_and_invalid_payload_rejected(self):
        self.assertEqual(self.reassign(revision=99).status_code,409)
        self.assertEqual(self.reassign(proof=issue_owner(99,self.task.pk,21,'Original')).status_code,400)
        self.assertEqual(self.reassign(reason=' ').status_code,400)
        self.assertEqual(self.reassign(setter_id=22).status_code,400)
        self.client.post(self.url+'close/',{'revision':0,'resolution':'Terminé'},format='json')
        self.assertEqual(self.reassign(revision=1).status_code,409)
    def test_incident_and_reopening_keep_current_owner(self):
        self.reassign();self.auth(22,'setter')
        self.client.post(self.url+'close/',{'revision':1,'resolution':'Terminé'},format='json')
        self.auth(99,'administrator')
        self.assertEqual(self.client.post(self.url+'reopen/?state=all',{'revision':2,'priority':'high',
            'due_at':(timezone.now()+timedelta(days=1)).isoformat(),'reason':'Reprise'},format='json').status_code,200)
        from uuid import uuid4
        self.auth(31,'advisor')
        self.assertEqual(self.client.post(f'/api/assurance/appointments/{self.task.appointment_id}/incidents/',
            {'request_id':str(uuid4()),'note':'À revoir'},format='json').status_code,201)
        self.task.refresh_from_db();self.assertEqual(self.task.setter_id,22)
        self.assertEqual(self.client.get(self.url).status_code,403)
    def test_audit_failure_rolls_back_assignment(self):
        with patch('apps.assurance.backend.crm.reports.BusinessAudit.objects.create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.reassign()
        self.task.refresh_from_db();self.assertEqual(self.task.setter_id,21);self.assertEqual(self.task.revision,0)
    def test_form_loaded_by_old_owner_cannot_close_after_reassignment(self):
        original=self.task;self.reassign();self.auth(21,'setter')
        # Simulate transfer between authorization/read and conditional write,
        # even if an attacker guesses the next revision in the submitted body.
        original.revision=1
        with patch('apps.assurance.backend.crm.reports.FollowUpViewSet.get_object',return_value=original):
            self.assertEqual(self.client.post(self.url+'close/',{'revision':1,'resolution':'Ancien responsable'},format='json').status_code,409)
        self.task.refresh_from_db();self.assertIsNone(self.task.closed_at)
    def test_statistics_keep_original_appointment_cohort_and_explain_transfer(self):
        self.reassign()
        result=self.client.get('/api/assurance/statistics/').data
        self.assertEqual(result['setters']['results'][0]['setter_id'],21)
        self.assertEqual(result['setters']['results'][0]['open_tasks'],1)
        self.assertIn('réattribué',result['definition'])
        self.auth(22,'setter')
        self.assertEqual(self.client.get('/api/assurance/dashboard/').data['open_follow_ups'],1)
        self.assertEqual(self.client.get('/api/assurance/statistics/').data['totals']['appointments'],0)

@override_settings(DEBUG=True)
class ConcurrentTaskAssignmentTests(TransactionTestCase):
    def race(self,operations):
        from django.db import connection,connections
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        if connection.vendor!='postgresql':self.skipTest('Concurrence vérifiée dans la CI PostgreSQL')
        barrier=Barrier(2)
        def execute(index):
            try:
                actor,role,action=operations[index];client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(actor,'assurance',role))
                barrier.wait(timeout=10);return action(client).status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(execute,[0,1]))
    def fixture(self):
        from django.db import connection
        if connection.vendor!='postgresql':self.skipTest('Concurrence vérifiée dans la CI PostgreSQL')
        return task_fixture()
    def test_simultaneous_reassignments_have_one_winner(self):
        _,task,url=self.fixture()
        def operation(target):return lambda client:client.post(url+'reassign/?state=all',{'revision':0,'proof':issue_owner(99,task.pk,target,'Setter'),'reason':'Transfert'},format='json')
        results=self.race([(99,'administrator',operation(22)),(99,'administrator',operation(23))])
        self.assertEqual(sorted(results),[200,409]);task.refresh_from_db();self.assertEqual(task.revision,1)
        self.assertEqual(BusinessAudit.objects.filter(action='appointment.follow_up_reassigned').count(),1)
    def test_reassignment_and_old_owner_closure_cannot_both_succeed(self):
        _,task,url=self.fixture()
        results=self.race([(99,'administrator',lambda client:client.post(url+'reassign/?state=all',
            {'revision':0,'proof':issue_owner(99,task.pk,22,'Setter'),'reason':'Transfert'},format='json')),
            (21,'setter',lambda client:client.post(url+'close/',{'revision':0,'resolution':'Traité'},format='json'))])
        self.assertEqual(results.count(200),1);self.assertTrue(all(code in (200,409,404) for code in results))
        task.refresh_from_db();self.assertEqual(task.revision,1)
        self.assertEqual(task.setter_id,22 if task.closed_at is None else 21)
