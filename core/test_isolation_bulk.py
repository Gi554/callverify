import uuid
from unittest.mock import patch
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from django.test import TestCase,TransactionTestCase,override_settings
from django.db import connection,close_old_connections
from rest_framework.test import APIClient
from packages.access.tickets import issue
from packages.access.isolation import issue_owner
from .test_isolation_work import fixture
from .models import Prospect,AuditEvent,IsolationAssignmentBatch

def payload(rows,target=21,actor=91):
    return {'request_id':str(uuid.uuid4()),'setter_id':target,'reason':'Distribution de recette',
        'items':[{'id':row.pk,'revision':row.assignment_revision,**({'proof':issue_owner(actor,row.pk,target,'Setter')} if target else {})} for row in rows]}

@override_settings(DEBUG=True,SECURE_SSL_REDIRECT=False)
class BulkAssignmentTests(TestCase):
    def setUp(self):
        self.first=fixture();self.second=Prospect.objects.create(campaign=self.first.campaign,name='Second',raw_phone='4165550142')
        self.client=APIClient();self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(91,'isolation','administrator'))
        self.url='/api/work-queue/bulk-assign/'
    def post(self,body):return self.client.post(self.url,body,format='json')
    def test_batch_assignment_replay_and_unassignment(self):
        body=payload([self.first,self.second]);response=self.post(body)
        self.assertEqual(response.status_code,201);self.assertEqual(response.data['count'],2)
        self.assertEqual(Prospect.objects.filter(assigned_setter_id=21,assignment_revision=1).count(),2)
        self.assertEqual(AuditEvent.objects.filter(action='isolation.prospect.assigned').count(),2)
        replay={**body,'items':[{**item,'proof':'expired'} for item in body['items']]}
        self.assertEqual(self.post(replay).status_code,200)
        self.assertEqual(AuditEvent.objects.filter(action='isolation.prospect.assigned').count(),2)
        self.assertEqual(self.post({**body,'reason':'Different'}).status_code,409)
        self.first.refresh_from_db();self.second.refresh_from_db()
        self.assertEqual(self.post(payload([self.first,self.second],target=None)).status_code,201)
        self.assertEqual(Prospect.objects.filter(assigned_setter_id__isnull=True,assignment_revision=2).count(),2)
        self.first.phone.refresh_from_db();self.assertEqual(self.first.phone.line_status,'unknown')
    def test_stale_missing_or_identical_target_rolls_back_whole_batch(self):
        body=payload([self.first,self.second]);body['items'][1]['revision']=99
        self.assertEqual(self.post(body).status_code,409)
        self.assertFalse(Prospect.objects.filter(assigned_setter_id=21).exists());self.assertEqual(IsolationAssignmentBatch.objects.count(),0)
        body=payload([self.first,self.second]);body['items'][1]['id']=999999
        body['items'][1]['proof']=issue_owner(91,999999,21,'Setter')
        self.assertEqual(self.post(body).status_code,409)
        Prospect.objects.filter(pk=self.second.pk).update(assigned_setter_id=21)
        self.assertEqual(self.post(payload([self.first,self.second])).status_code,400)
        self.first.refresh_from_db();self.assertIsNone(self.first.assigned_setter_id);self.assertEqual(self.first.assignment_revision,0)
        self.assertEqual(AuditEvent.objects.filter(action='isolation.prospect.assigned').count(),0)
    def test_permissions_and_actor_bound_replays(self):
        body=payload([self.first]);self.assertEqual(self.post(body).status_code,201)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(92,'isolation','administrator'))
        self.assertEqual(self.post(body).status_code,409)
        for role in ('setter','client'):
            self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(91,'isolation',role));self.assertEqual(self.post(body).status_code,403)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(91,'assurance','administrator'));self.assertEqual(self.post(body).status_code,401)
    def test_bounded_input_proofs_and_duplicate_ids(self):
        body=payload([self.first])
        for changes in ({'items':[]},{'items':body['items']*26},{'items':body['items']*2},{'reason':' '},{'unexpected':True}):
            self.assertEqual(self.post({**body,**changes}).status_code,400)
        for proof in ('bad',issue_owner(92,self.first.pk,21,'Setter'),issue_owner(91,self.second.pk,21,'Setter'),issue_owner(91,self.first.pk,22,'Setter')):
            self.assertEqual(self.post({**body,'items':[{**body['items'][0],'proof':proof}]}).status_code,400)
        self.assertEqual(self.post({**body,'setter_id':None}).status_code,400)
        self.assertEqual(IsolationAssignmentBatch.objects.count(),0)
    def test_twenty_five_rows_are_supported_and_audited(self):
        rows=[self.first,self.second]+[Prospect.objects.create(campaign=self.first.campaign,raw_phone=str(i)) for i in range(23)]
        response=self.post(payload(rows));self.assertEqual(response.status_code,201);self.assertEqual(response.data['count'],25)
        self.assertEqual(Prospect.objects.filter(assigned_setter_id=21).count(),25)
        self.assertEqual(AuditEvent.objects.filter(metadata__batch=response.data['request_id']).count(),25)
    def test_audit_error_rolls_back_batch_and_all_assignments(self):
        with patch('core.isolation_bulk.AuditEvent.objects.create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.post(payload([self.first,self.second]))
        self.assertEqual(IsolationAssignmentBatch.objects.count(),0)
        self.assertFalse(Prospect.objects.filter(assignment_revision__gt=0).exists())

@skipUnless(connection.vendor=='postgresql','Concurrency requires PostgreSQL')
@override_settings(DEBUG=True,SECURE_SSL_REDIRECT=False)
class ConcurrentBulkTests(TransactionTestCase):
    def run_requests(self,bodies):
        def attempt(body):
            close_old_connections()
            try:
                client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(91,'isolation','administrator'))
                return client.post('/api/work-queue/bulk-assign/',body,format='json').status_code
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:return sorted(pool.map(attempt,bodies))
    def test_competing_batches_cannot_split_ownership(self):
        first=fixture();second=Prospect.objects.create(campaign=first.campaign,raw_phone='4165550142')
        bodies=[payload([first,second],21),payload([second,first],22)]
        self.assertEqual(self.run_requests(bodies),[201,409])
        self.assertEqual(len(set(Prospect.objects.values_list('assigned_setter_id',flat=True))),1)
        self.assertEqual(IsolationAssignmentBatch.objects.count(),1)
    def test_concurrent_retry_writes_one_batch(self):
        first=fixture();body=payload([first])
        self.assertEqual(self.run_requests([body,body]),[200,201])
        self.assertEqual(IsolationAssignmentBatch.objects.count(),1)
        self.assertEqual(AuditEvent.objects.filter(action='isolation.prospect.assigned').count(),1)
