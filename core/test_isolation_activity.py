from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase,TransactionTestCase,override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from packages.access.isolation import issue_owner
from .models import Prospect,ProspectActivity,AuditEvent
from .test_isolation_work import fixture

def assigned_fixture():
    row=fixture();row.assigned_setter_id=21;row.assigned_setter_name='Setter';row.save()
    return row

@override_settings(DEBUG=True,SECURE_SSL_REDIRECT=False)
class IsolationActivityTests(TestCase):
    def setUp(self):
        self.row=assigned_fixture();self.client=APIClient();self.auth(21,'setter')
        self.base=f'/api/work-queue/{self.row.pk}/';self.request_id=uuid4()
    def auth(self,pk,role):self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(pk,'isolation',role))
    def payload(self,**changes):return {'revision':0,'request_id':str(self.request_id),'kind':'note','body':'Observation commerciale',**changes}
    def post(self,**changes):return self.client.post(self.base+'activities/',self.payload(**changes),format='json')
    def test_append_only_notes_idempotence_and_audit(self):
        first=self.post();self.assertEqual(first.status_code,201,first.data)
        self.assertEqual(self.post().status_code,200);self.assertEqual(ProspectActivity.objects.count(),1)
        self.assertEqual(self.post(body='Autre texte').status_code,409)
        self.row.refresh_from_db();self.assertEqual(self.row.assignment_revision,1)
        self.assertEqual(self.row.commercial_status,'to_contact')
        result=self.client.get(self.base+'activities/');self.assertEqual(result.data['count'],1)
        self.assertEqual(result.data['results'][0]['author_portal_id'],21);self.assertEqual(result['Cache-Control'],'no-store')
        self.assertEqual(self.client.delete(self.base+'activities/').status_code,405)
        self.assertTrue(AuditEvent.objects.filter(action='isolation.prospect.activity_added').exists())
    def test_qualification_callback_and_history_without_changing_lookup(self):
        callback=(timezone.now()+timedelta(days=1)).isoformat()
        self.assertEqual(self.post(kind='qualification',status='callback',callback_at=callback).status_code,201)
        self.row.refresh_from_db();self.assertIsNotNone(self.row.callback_at)
        self.assertEqual(self.post(revision=1,request_id=str(uuid4()),kind='qualification',status='unreachable').status_code,201)
        self.row.refresh_from_db();self.assertIsNone(self.row.callback_at)
        self.assertEqual(self.row.phone.line_status,'unknown');self.assertEqual(self.row.phone.validity,'valid')
        event=ProspectActivity.objects.order_by('-pk').first()
        self.assertEqual(event.changes['before']['status'],'callback');self.assertIsNotNone(event.changes['before']['callback_at'])
        self.assertEqual(event.changes['after']['status'],'unreachable')
    def test_invalid_combinations_dates_and_stale_revision_rejected(self):
        for change in ({'body':' '},{'status':'interested'},{'kind':'qualification'},
            {'kind':'qualification','status':'unknown'}, {'kind':'qualification','status':'callback'},
            {'kind':'qualification','status':'callback','callback_at':'2020-01-01T00:00:00Z'},
            {'kind':'qualification','status':'callback','callback_at':'2030-01-01T00:00:00'},
            {'kind':'qualification','status':'interested','callback_at':'2030-01-01T00:00:00Z'}, {'author_portal_id':22}):
            self.assertEqual(self.post(**change).status_code,400,change)
        self.assertEqual(self.post(revision=99).status_code,409)
        self.assertEqual(ProspectActivity.objects.count(),0)
    def test_assignment_scope_applies_to_read_write_and_replay(self):
        self.post();self.auth(22,'setter')
        self.assertEqual(self.client.get(self.base+'activities/').status_code,404);self.assertEqual(self.post().status_code,404)
        self.auth(91,'administrator')
        self.assertEqual(self.client.post(self.base+'assign/',{'revision':1,'reason':'Transfert',
            'proof':issue_owner(91,self.row.pk,22,'Setter 22')},format='json').status_code,200)
        self.auth(21,'setter');self.assertEqual(self.post().status_code,404)
        self.auth(22,'setter');self.assertEqual(self.client.get(self.base+'activities/').data['count'],1)
        self.assertEqual(self.post(revision=2).status_code,409)
    def test_due_callbacks_persist_on_read_and_transfer_with_owner(self):
        self.post(kind='qualification',status='callback',callback_at=(timezone.now()+timedelta(days=1)).isoformat())
        Prospect.objects.filter(pk=self.row.pk).update(callback_at=timezone.now()-timedelta(minutes=1))
        self.assertEqual(self.client.get('/api/workspace-dashboard/').data['callbacks_due'],1)
        self.assertEqual(self.client.get('/api/work-queue/?due=true').data['count'],1)
        self.client.get(self.base+'activities/')
        self.assertEqual(self.client.get('/api/workspace-dashboard/').data['callbacks_due'],1)
        self.assertEqual(self.client.get('/api/work-queue/?commercial_status=interested').data['count'],0)
        self.auth(91,'administrator')
        self.client.post(self.base+'assign/',{'revision':1,'reason':'Transfert','proof':issue_owner(91,self.row.pk,22,'Setter 22')},format='json')
        self.auth(21,'setter');self.assertEqual(self.client.get('/api/workspace-dashboard/').data['callbacks_due'],0)
        self.auth(22,'setter');self.assertEqual(self.client.get('/api/workspace-dashboard/').data['callbacks_due'],1)
    def test_audit_failure_rolls_back_activity_qualification_and_revision(self):
        with patch('core.isolation_activity.AuditEvent.objects.create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.post(kind='qualification',status='interested')
        self.row.refresh_from_db();self.assertEqual(self.row.commercial_status,'to_contact');self.assertEqual(self.row.assignment_revision,0)
        self.assertEqual(ProspectActivity.objects.count(),0)
    def test_stale_authorized_read_cannot_write_after_transfer_even_with_guessed_revision(self):
        original=self.row
        Prospect.objects.filter(pk=self.row.pk).update(assigned_setter_id=22,assignment_revision=1)
        original.assignment_revision=1
        with patch('core.isolation_work.WorkViewSet.get_object',return_value=original):
            self.assertEqual(self.post(revision=1).status_code,409)
        self.assertEqual(ProspectActivity.objects.count(),0)
    def test_retry_callback_after_due_date_returns_existing_event(self):
        due=timezone.now()+timedelta(minutes=1)
        values={'kind':'qualification','status':'callback','callback_at':due.isoformat()}
        self.assertEqual(self.post(**values).status_code,201)
        with patch('core.isolation_activity.timezone.now',return_value=due+timedelta(minutes=1)):
            self.assertEqual(self.post(**values).status_code,200)

@override_settings(DEBUG=True,SECURE_SSL_REDIRECT=False)
class IsolationActivityConcurrencyTests(TransactionTestCase):
    def setUp(self):
        from django.db import connection
        if connection.vendor!='postgresql':self.skipTest('Concurrence vérifiée dans CI PostgreSQL')
        self.row=assigned_fixture();self.url=f'/api/work-queue/{self.row.pk}/'
    def race(self,operations):
        from django.db import connections
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        barrier=Barrier(2)
        def execute(operation):
            try:
                actor,role,path,payload=operation
                client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(actor,'isolation',role))
                barrier.wait(timeout=10);return client.post(self.url+path,payload,format='json').status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(execute,operations))
    def payload(self,status):return {'revision':0,'request_id':str(uuid4()),'kind':'qualification','body':'Résultat','status':status}
    def test_two_qualifications_cannot_overwrite(self):
        results=self.race([(21,'setter','activities/',self.payload(status)) for status in ('interested','unreachable')])
        self.assertEqual(sorted(results),[201,409]);self.assertEqual(ProspectActivity.objects.count(),1)
        self.row.refresh_from_db();self.assertEqual(self.row.assignment_revision,1)
    def test_transfer_and_commercial_write_cannot_both_use_same_revision(self):
        results=self.race([(21,'setter','activities/',self.payload('interested')),
            (91,'administrator','assign/',{'revision':0,'reason':'Transfert','proof':issue_owner(91,self.row.pk,22,'Setter')})])
        self.assertEqual(sum(code in (200,201) for code in results),1)
        self.assertTrue(all(code in (200,201,404,409) for code in results))
        self.row.refresh_from_db();self.assertEqual(self.row.assignment_revision,1)
