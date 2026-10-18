from unittest.mock import patch
from django.test import TestCase,TransactionTestCase,override_settings
from django.core.cache import cache
from rest_framework.test import APIClient
from packages.access.tickets import issue
from packages.access.isolation import issue_owner
from .models import AdminUser,Campaign,Prospect,PhoneNumber,AuditEvent

def fixture():
    cache.clear()
    admin=AdminUser.objects.create_user('legacy-admin',is_staff=True)
    campaign=Campaign.objects.create(owner=admin,name='Isolation',purpose='Test',source='Fictif')
    phone=PhoneNumber.objects.create(e164='+14165550123',line_status='unknown')
    row=Prospect.objects.create(campaign=campaign,phone=phone,name='Prospect',raw_phone='4165550123')
    return row

@override_settings(DEBUG=True,SECURE_SSL_REDIRECT=False)
class IsolationWorkTests(TestCase):
    def setUp(self):
        self.row=fixture();self.client=APIClient();self.auth(91,'administrator')
        self.base=f'/api/work-queue/{self.row.pk}/'
    def auth(self,pk,role,space='isolation'):self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(pk,space,role))
    def payload(self,**changes):return {'revision':0,'reason':'Distribution',
        'proof':issue_owner(91,self.row.pk,21,'Setter Isolation'),**changes}
    def assign(self,**changes):return self.client.post(self.base+'assign/',self.payload(**changes),format='json')
    def test_assignment_and_reassignment_transfer_scope(self):
        self.assertEqual(self.assign().status_code,200)
        self.auth(21,'setter');self.assertEqual(self.client.get('/api/work-queue/').data['count'],1)
        self.assertEqual(self.client.get('/api/workspace-dashboard/').data['prospects'],1)
        self.auth(22,'setter');self.assertEqual(self.client.get(self.base).status_code,404)
        self.auth(91,'administrator')
        self.assertEqual(self.assign(revision=1,proof=issue_owner(91,self.row.pk,22,'Autre setter')).status_code,200)
        self.auth(21,'setter');self.assertEqual(self.client.get(self.base).status_code,404)
        self.auth(22,'setter');self.assertEqual(self.client.get(self.base).data['assigned_setter']['id'],22)
        self.assertEqual(AdminUser.objects.count(),1)
    def test_no_legacy_admin_routes_or_assurance_client_access(self):
        self.auth(21,'setter')
        for url in ['/api/prospects/','/api/campaigns/','/api/lookups/','/api/calls/','/api/exports/','/api/audit/','/api/dashboard/']:
            self.assertEqual(self.client.get(url).status_code,403,url)
        self.assertEqual(self.assign().status_code,403)
        self.assertEqual(self.client.get(self.base+'history/').status_code,403)
        self.auth(21,'setter','assurance');self.assertEqual(self.client.get('/api/work-queue/').status_code,401)
        self.auth(21,'client');self.assertEqual(self.client.get('/api/work-queue/').status_code,403)
        self.client.credentials();self.assertEqual(self.client.get('/api/work-queue/').status_code,401)
    def test_unassignment_preserves_history_and_requires_current_revision(self):
        self.assign()
        self.assertEqual(self.assign().status_code,409)
        self.assertEqual(self.client.post(self.base+'unassign/',{'revision':0,'reason':'Retrait'},format='json').status_code,409)
        self.assertEqual(self.client.post(self.base+'unassign/',{'revision':1,'reason':'Retrait'},format='json').status_code,200)
        self.row.refresh_from_db();self.assertIsNone(self.row.assigned_setter_id);self.assertEqual(self.row.assignment_revision,2)
        entries=self.client.get(self.base+'history/').data['results']
        self.assertEqual(len(entries),2);self.assertEqual(entries[0]['metadata']['actor_portal_id'],91)
        self.assertEqual(entries[0]['metadata']['before']['setter_id'],21)
        self.assertEqual(self.client.get('/api/work-queue/?owner=unassigned').data['count'],1)
        self.auth(21,'setter');self.assertEqual(self.client.get(self.base).status_code,404)
    def test_proof_purpose_scope_expiry_and_input_validation(self):
        proofs=[issue_owner(90,self.row.pk,21,'Setter'),issue_owner(91,self.row.pk+1,21,'Setter'),
            issue(21,'isolation','setter'),'bad']
        with patch('django.core.signing.time.time',return_value=1000):proofs.append(issue_owner(91,self.row.pk,21,'Setter'))
        for proof in proofs:self.assertEqual(self.assign(proof=proof).status_code,400)
        self.assertEqual(self.assign(reason=' ').status_code,400)
        self.assertEqual(self.assign(setter_id=21).status_code,400)
        self.assertEqual(self.assign().status_code,200)
        self.assertEqual(self.assign(revision=1).status_code,400)
    def test_scoped_search_pagination_and_allowlist(self):
        self.assign()
        for index in range(27):Prospect.objects.create(campaign=self.row.campaign,name='Visible',raw_phone=str(index),assigned_setter_id=21,assigned_setter_name='Setter')
        Prospect.objects.create(campaign=self.row.campaign,name='Hidden',raw_phone='secret',assigned_setter_id=22)
        self.auth(21,'setter');first=self.client.get('/api/work-queue/').data
        self.assertEqual(first['count'],28);self.assertEqual(len(first['results']),25)
        self.assertEqual(len(self.client.get('/api/work-queue/?page=2').data['results']),3)
        self.assertEqual(self.client.get('/api/work-queue/?search=secret&owner=22').data['count'],0)
        row=self.client.get(self.base).data
        self.assertEqual(row['line_status'],'unknown')
        self.assertEqual(set(row),{'id','name','reference','raw_phone','phone','validity','line_status','campaign','assigned_setter','revision',
            'commercial_status','commercial_label','callback_at','callback_due'})
        self.assertEqual(self.client.patch(self.base,{'name':'changed'},format='json').status_code,405)
    def test_audit_failure_rolls_back_owner(self):
        with patch('core.isolation_work.AuditEvent.objects.create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.assign()
        self.row.refresh_from_db();self.assertIsNone(self.row.assigned_setter_id);self.assertEqual(self.row.assignment_revision,0)

@override_settings(DEBUG=True,SECURE_SSL_REDIRECT=False)
class IsolationAssignmentConcurrencyTests(TransactionTestCase):
    def test_concurrent_assignments_cannot_overwrite(self):
        from django.db import connection,connections
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        if connection.vendor!='postgresql':self.skipTest('Concurrence dans CI PostgreSQL')
        row=fixture();barrier=Barrier(2)
        def assign(target):
            try:
                client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(91,'isolation','administrator'))
                barrier.wait(timeout=10)
                return client.post(f'/api/work-queue/{row.pk}/assign/',{'revision':0,'reason':'Distribution',
                    'proof':issue_owner(91,row.pk,target,'Setter')},format='json').status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(assign,[21,22]))
        self.assertEqual(sorted(results),[200,409]);row.refresh_from_db();self.assertEqual(row.assignment_revision,1)
        self.assertEqual(AuditEvent.objects.filter(action='isolation.prospect.assigned').count(),1)
