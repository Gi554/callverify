from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from packages.access.isolation_visits import issue_closer
from . import test_isolation_client as fixtures
from .models import IsolationVisit,IsolationVisitResult,AuditEvent


@override_settings(DEBUG=True,SECURE_SSL_REDIRECT=False)
class CloserTests(TestCase):
    def setUp(self):
        self.prospect,self.visit=fixtures.client_fixture();self.client=APIClient()
        self.auth(72,'client');self.assign_url=f'/api/visits/{self.visit.pk}/assign-closer/'
        self.base=f'/api/closer-visits/{self.visit.pk}/'
    def auth(self,pk,role,space='isolation'):self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(pk,space,role))
    def assign(self,**changes):return self.client.post(self.assign_url,{'revision':0,'proof':issue_closer(72,self.visit.pk,77,'Closer test'),'reason':'Secteur Montréal',**changes},format='json')
    def prepare(self):
        response=self.assign();self.assertEqual(response.status_code,200,response.data)
        self.auth(77,'closer')
    def payload(self,**changes):return {'request_id':str(uuid4()),'revision':1,'performed':True,'closed':True,'note':'','reason':'',**changes}
    def report(self,**changes):return self.client.post(self.base+'result/',self.payload(**changes),format='json')

    def test_assignment_and_closer_scope_are_separate_from_client_and_setter(self):
        self.prepare()
        self.assertEqual(self.client.get('/api/closer-visits/').data['count'],1)
        self.assertEqual(self.client.get('/api/closer-visits/dashboard/').data['results_due'],1)
        self.assertEqual(self.client.get(self.base).data['closer'],{'id':77,'name':'Closer test'})
        for url in ('/api/visits/','/api/work-queue/','/api/workspace-statistics/','/api/client-prospects/'):
            self.assertEqual(self.client.get(url).status_code,403,url)
        self.auth(78,'closer');self.assertEqual(self.client.get(self.base).status_code,404)
        self.assertEqual(self.report().status_code,404)
        self.assertEqual(self.client.get('/api/closer-visits/').data['count'],0)
        self.auth(21,'setter');self.assertEqual(self.client.get(self.base).status_code,403)
        self.auth(77,'closer','assurance');self.assertEqual(self.client.get(self.base).status_code,401)

    def test_assignment_rejects_forgery_cross_visit_stale_and_setter(self):
        self.assertEqual(self.assign(proof=issue_closer(72,self.visit.pk+1,77,'Closer')).status_code,400)
        self.assertEqual(self.assign(proof=issue_closer(73,self.visit.pk,77,'Closer')).status_code,400)
        self.assertEqual(self.assign(revision=9).status_code,409)
        self.auth(21,'setter');self.assertEqual(self.assign().status_code,403)
        self.auth(73,'client');self.assertEqual(self.assign().status_code,404)
        self.auth(72,'client');self.assertEqual(self.assign().status_code,200)
        self.assertEqual(self.assign().status_code,409)

    def test_explicit_result_optional_note_and_retry(self):
        self.prepare();body=self.payload()
        response=self.client.post(self.base+'result/',body,format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(self.client.post(self.base+'result/',body,format='json').status_code,200)
        self.assertEqual(AuditEvent.objects.filter(action='isolation.visit.closer_reported').count(),1)
        row=IsolationVisitResult.objects.get();self.assertTrue(row.closed);self.assertTrue(row.performed)
        self.assertEqual(row.author_closer_id,77);self.assertIsNone(row.author_client_id)
        self.assertEqual(self.client.get(self.base).data['result']['closed'],True)
        self.assertEqual(self.client.post(self.base+'result/',{**body,'closed':False},format='json').status_code,409)
        self.auth(72,'client');self.assertEqual(self.client.get(f'/api/visits/{self.visit.pk}/').data['result']['closed'],True)

    def test_nonheld_result_and_unknown_legacy_sale_are_not_inferred(self):
        self.prepare()
        self.assertEqual(self.report(performed=False,closed=True).status_code,400)
        self.assertEqual(self.report(performed=False,closed=False).status_code,201)
        self.assertEqual(self.client.get(self.base).data['result']['performed'],False)
        self.assertFalse(IsolationVisitResult.objects.get().closed)

    def test_correction_requires_revision_reason_and_preserves_before_after(self):
        self.prepare();self.report()
        self.assertEqual(self.report(revision=2,closed=False).status_code,400)
        self.assertEqual(self.report(revision=1,closed=False,reason='Erreur de saisie').status_code,409)
        response=self.report(revision=2,closed=False,reason='Erreur de saisie',note='À suivre')
        self.assertEqual(response.status_code,200,response.data)
        history=self.client.get(self.base+'history/').data['results']
        self.assertEqual(len(history),2);self.assertTrue(history[0]['before']['closed']);self.assertFalse(history[0]['after']['closed'])
        self.assertEqual(history[0]['reason'],'Erreur de saisie')
        self.assertEqual(IsolationVisitResult.objects.count(),1)

    def test_reassignment_removes_old_closer_write_and_preserves_existing_result(self):
        self.prepare();self.report()
        self.auth(72,'client')
        response=self.assign(revision=2,proof=issue_closer(72,self.visit.pk,78,'Autre closer'))
        self.assertEqual(response.status_code,200,response.data)
        self.auth(77,'closer');self.assertEqual(self.report(revision=3).status_code,404)
        self.assertEqual(self.client.get(self.base+'history/').status_code,404)
        self.auth(78,'closer');self.assertEqual(self.client.get(self.base).data['result']['closed'],True)
        self.assertEqual(self.report(revision=3,closed=False,reason='Correction contrôlée').status_code,200)

    def test_legacy_result_remains_unknown_until_explicit_correction(self):
        IsolationVisitResult.objects.create(visit=self.visit,author_client_id=72,performed=True,outcome='interested',note='Intéressé')
        self.prepare();self.assertIsNone(self.client.get(self.base).data['result']['closed'])
        self.assertEqual(self.report().status_code,400)
        self.assertEqual(self.report(reason='Qualification de la vente').status_code,200)
        history=self.client.get(self.base+'history/').data['results'][0]
        self.assertIsNone(history['before']['closed']);self.assertEqual(history['before']['author_client_id'],72)

    def test_future_cancelled_and_audit_failure_do_not_save_results(self):
        self.prepare()
        IsolationVisit.objects.filter(pk=self.visit.pk).update(ends_at=timezone.now()+timedelta(hours=1))
        self.assertEqual(self.report().status_code,409)
        IsolationVisit.objects.filter(pk=self.visit.pk).update(ends_at=self.visit.ends_at,status='cancelled')
        self.assertEqual(self.report().status_code,409)
        IsolationVisit.objects.filter(pk=self.visit.pk).update(status='scheduled')
        with patch('core.isolation_closers.AuditEvent.objects.create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.report()
        self.assertFalse(IsolationVisitResult.objects.exists())
        self.visit.refresh_from_db();self.assertEqual(self.visit.revision,1)
