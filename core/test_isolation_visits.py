from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase,TransactionTestCase,override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from packages.access.isolation import issue_owner
from packages.access.isolation_visits import issue_booking
from .models import Prospect,IsolationVisit,AuditEvent
from .test_isolation_activity import assigned_fixture

@override_settings(DEBUG=True,SECURE_SSL_REDIRECT=False)
class IsolationVisitTests(TestCase):
    def setUp(self):
        external=patch('core.isolation_visits.external_check',return_value={'result':'internal_only','checked_at':'2026-10-21T10:00:00+00:00'})
        self.external_check=external.start();self.addCleanup(external.stop)
        self.prospect=assigned_fixture();self.client=APIClient();self.auth(21,'setter')
        self.start=(timezone.now()+timedelta(days=7)).replace(microsecond=0);self.end=self.start+timedelta(hours=1)
        self.request_id=uuid4();self.url='/api/visits/'
    def auth(self,pk,role):self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(pk,'isolation',role))
    def proof(self,actor=21,setter=21,client=72):return issue_booking(actor,self.prospect.pk,setter,'Setter',client,'Client')
    def payload(self,**changes):return {'prospect_id':self.prospect.pk,'request_id':str(self.request_id),'revision':0,'proof':self.proof(),
        'starts_at':self.start.isoformat(),'ends_at':self.end.isoformat(),'timezone':'UTC',**changes}
    def book(self,**changes):return self.client.post(self.url,self.payload(**changes),format='json')
    def test_booking_retry_and_original_participants(self):
        first=self.book();self.assertEqual(first.status_code,201,first.data)
        self.assertEqual(first.data['calendar'],'internal');self.assertEqual(first.data['original_setter']['id'],21)
        self.assertEqual(self.book().status_code,200);self.assertEqual(IsolationVisit.objects.count(),1)
        self.assertEqual(self.book(starts_at=(self.start+timedelta(minutes=5)).isoformat()).status_code,409)
        self.prospect.refresh_from_db();self.assertEqual(self.prospect.assignment_revision,1)
        self.assertEqual(self.prospect.commercial_status,'to_contact')
    def test_overlap_rejected_adjacent_accepted(self):
        self.book()
        self.assertEqual(self.book(request_id=str(uuid4()),revision=1).status_code,409)
        self.assertEqual(self.book(request_id=str(uuid4()),revision=1,starts_at=self.end.isoformat(),ends_at=(self.end+timedelta(hours=1)).isoformat()).status_code,201)
        self.assertEqual(IsolationVisit.objects.count(),2)
    def test_admin_booking_keeps_responsible_setter_separate_from_actor(self):
        self.auth(91,'administrator')
        response=self.book(proof=self.proof(actor=91))
        self.assertEqual(response.status_code,201,response.data)
        row=IsolationVisit.objects.get();self.assertEqual(row.setter_id,21);self.assertEqual(row.booked_by_id,91)
        self.assertEqual(AuditEvent.objects.get(action='isolation.visit.booked').metadata['actor_portal_id'],91)
    def test_slot_and_proof_validation(self):
        for changes in ({'starts_at':'2020-01-01T10:00:00Z','ends_at':'2020-01-01T11:00:00Z'},
            {'starts_at':self.start.replace(tzinfo=None).isoformat()}, {'ends_at':self.start.isoformat()}, {'timezone':'Mars/Test'},
            {'starts_at':'2027-03-14T02:30:00-05:00','ends_at':'2027-03-14T04:30:00-04:00','timezone':'America/Toronto'},
            {'proof':issue(21,'isolation','setter')},{'proof':self.proof(actor=22)}, {'booked_by_id':99}):
            self.assertEqual(self.book(**changes).status_code,400,changes)
        self.assertEqual(self.book(revision=9).status_code,409)
        with patch('django.core.signing.time.time',return_value=1000):expired=self.proof()
        self.assertEqual(self.book(proof=expired).status_code,400)
        self.assertEqual(IsolationVisit.objects.count(),0)
    def test_transfer_moves_visibility_but_preserves_original_setter(self):
        row=self.book().data;self.auth(91,'administrator')
        self.assertEqual(self.client.post(f'/api/work-queue/{self.prospect.pk}/assign/',{'revision':1,'reason':'Transfert',
            'proof':issue_owner(91,self.prospect.pk,22,'Nouveau')},format='json').status_code,200)
        self.auth(21,'setter');self.assertEqual(self.client.get(f'{self.url}{row["id"]}/').status_code,404)
        self.auth(22,'setter');response=self.client.get(f'{self.url}{row["id"]}/')
        self.assertEqual(response.status_code,200);self.assertEqual(response.data['original_setter']['id'],21)
        change={key:row[key] for key in ('starts_at','ends_at','timezone','revision')}
        change.update(starts_at=(self.start+timedelta(days=1)).isoformat(),ends_at=(self.end+timedelta(days=1)).isoformat(),reason='Report',proof=self.proof(actor=22,setter=22))
        self.assertEqual(self.client.post(f'{self.url}{row["id"]}/reschedule/',change,format='json').status_code,200)
        self.assertEqual(IsolationVisit.objects.get().setter_id,21)
    def test_reschedule_cancel_versions_and_history(self):
        row=self.book().data;url=f'{self.url}{row["id"]}/'
        change={'revision':0,'proof':self.proof(),'reason':'Report','starts_at':(self.start+timedelta(days=1)).isoformat(),
            'ends_at':(self.end+timedelta(days=1)).isoformat(),'timezone':'UTC'}
        self.assertEqual(self.client.post(url+'reschedule/',change,format='json').status_code,200)
        self.assertEqual(self.client.post(url+'reschedule/',change,format='json').status_code,409)
        self.assertEqual(self.client.post(url+'cancel/',{'revision':1,'reason':' '},format='json').status_code,400)
        self.assertEqual(self.client.post(url+'cancel/',{'revision':1,'reason':'Indisponible'},format='json').status_code,200)
        self.assertEqual(self.client.get(url+'history/').status_code,403)
        self.auth(91,'administrator');entries=self.client.get(url+'history/').data['results']
        self.assertEqual(len(entries),3);self.assertEqual(entries[0]['action'],'isolation.visit.cancelled')
        self.assertEqual(entries[1]['metadata']['before']['starts_at'],self.start.isoformat())
    def test_cancel_keeps_history_even_if_prospect_unassigned(self):
        row=self.book().data;self.auth(91,'administrator')
        self.client.post(f'/api/work-queue/{self.prospect.pk}/unassign/',{'revision':1,'reason':'Retrait'},format='json')
        self.assertEqual(self.client.post(f'{self.url}{row["id"]}/cancel/',{'revision':0,'reason':'Retrait'},format='json').status_code,200)
        self.assertEqual(IsolationVisit.objects.count(),1)
    def test_passed_visit_cannot_be_rewritten_or_marked_performed(self):
        row=self.book().data
        IsolationVisit.objects.filter(pk=row['id']).update(starts_at=timezone.now()-timedelta(hours=2),ends_at=timezone.now()-timedelta(hours=1))
        self.assertEqual(self.client.post(f'{self.url}{row["id"]}/cancel/',{'revision':0,'reason':'Effacer'},format='json').status_code,409)
        self.assertEqual(IsolationVisit.objects.get().status,'scheduled')
    def test_cross_space_client_and_other_setter_are_denied(self):
        row=self.book().data
        self.auth(22,'setter');self.assertEqual(self.client.get(self.url).data['count'],0)
        self.assertEqual(self.client.get(f'{self.url}{row["id"]}/').status_code,404)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(21,'assurance','setter'))
        self.assertEqual(self.client.get(self.url).status_code,401)
        self.auth(72,'client');self.assertEqual(self.client.get(self.url).data['count'],1)
        self.auth(73,'client');self.assertEqual(self.client.get(self.url).data['count'],0)
    def test_audit_failure_rolls_back_visit_and_prospect_revision(self):
        with patch('core.isolation_visits.AuditEvent.objects.create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.book()
        self.assertEqual(IsolationVisit.objects.count(),0)
        self.prospect.refresh_from_db();self.assertEqual(self.prospect.assignment_revision,0)

@override_settings(DEBUG=True,SECURE_SSL_REDIRECT=False)
class IsolationVisitConcurrencyTests(TransactionTestCase):
    def setUp(self):
        external=patch('core.isolation_visits.external_check',return_value={'result':'internal_only','checked_at':'2026-10-21T10:00:00+00:00'})
        self.external_check=external.start();self.addCleanup(external.stop)
        from django.db import connection
        if connection.vendor!='postgresql':self.skipTest('Concurrence dans CI PostgreSQL')
        self.prospect=assigned_fixture();self.other=Prospect.objects.create(campaign=self.prospect.campaign,raw_phone='autre',assigned_setter_id=22)
        self.start=(timezone.now()+timedelta(days=7)).replace(microsecond=0);self.end=self.start+timedelta(hours=1)
    def payload(self,prospect,actor):return {'prospect_id':prospect.pk,'revision':0,'request_id':str(uuid4()),
        'proof':issue_booking(actor,prospect.pk,actor,'Setter',72,'Client'),'starts_at':self.start.isoformat(),'ends_at':self.end.isoformat(),'timezone':'UTC'}
    def race(self,operations):
        from django.db import connections
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        barrier=Barrier(2)
        def execute(operation):
            try:
                actor,action=operation;client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(actor,'isolation','setter'))
                barrier.wait(timeout=10);return action(client).status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(execute,operations))
    def test_same_client_across_prospects_has_one_booking_winner(self):
        results=self.race([(21,lambda api:api.post('/api/visits/',self.payload(self.prospect,21),format='json')),
            (22,lambda api:api.post('/api/visits/',self.payload(self.other,22),format='json'))])
        self.assertEqual(sorted(results),[201,409]);self.assertEqual(IsolationVisit.objects.count(),1)
    def test_same_request_concurrent_retry_is_idempotent(self):
        payload=self.payload(self.prospect,21)
        action=lambda api:api.post('/api/visits/',payload,format='json')
        results=self.race([(21,action),(21,action)])
        self.assertEqual(sorted(results),[200,201]);self.assertEqual(IsolationVisit.objects.count(),1)
        self.assertEqual(AuditEvent.objects.filter(action='isolation.visit.booked').count(),1)
    def test_reschedule_and_new_booking_cannot_claim_same_slot(self):
        client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(21,'isolation','setter'))
        row=client.post('/api/visits/',self.payload(self.prospect,21),format='json').data
        target=self.start+timedelta(hours=2);end=self.end+timedelta(hours=2)
        change={'revision':0,'proof':issue_booking(21,self.prospect.pk,21,'Setter',72,'Client'),'reason':'Report',
            'starts_at':target.isoformat(),'ends_at':end.isoformat(),'timezone':'UTC'}
        other={**self.payload(self.other,22),'starts_at':target.isoformat(),'ends_at':end.isoformat()}
        results=self.race([(21,lambda api:api.post(f'/api/visits/{row["id"]}/reschedule/',change,format='json')),
            (22,lambda api:api.post('/api/visits/',other,format='json'))])
        self.assertEqual(results.count(409),1);self.assertEqual(IsolationVisit.objects.filter(status='scheduled',starts_at=target).count(),1)
