from uuid import uuid4
from unittest import skipUnless
from unittest.mock import patch
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor
from django.db import connection,close_old_connections
from django.test import TestCase,TransactionTestCase,override_settings
from rest_framework.test import APIClient
from packages.access.tickets import issue
from packages.access.isolation import issue_owner
from .models import Prospect,ProspectActivity,ProspectActivityShare,IsolationVisit,AuditEvent
from .test_isolation_client import client_fixture


def observation(prospect,body='Texte interne'):
    return ProspectActivity.objects.create(prospect=prospect,request_id=uuid4(),fingerprint='test',author_portal_id=21,
        author_role='setter',kind='note',body=body)


@override_settings(DEBUG=True,SECURE_SSL_REDIRECT=False)
class IsolationSharingTests(TestCase):
    def setUp(self):
        self.prospect,self.visit=client_fixture();self.activity=observation(self.prospect);self.client=APIClient()
        self.url=f'/api/visits/{self.visit.pk}/activities/';self.auth(21,'setter')
    def auth(self,pk,role,workspace='isolation'):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(pk,workspace,role))
    def publish(self,**changes):
        return self.client.post(self.url,{'activity_id':self.activity.pk,'revision':0,'visible':True,'reason':'Note autorisée',**changes},format='json')
    def test_default_private_explicit_publish_and_revoke(self):
        self.auth(72,'client');self.assertEqual(self.client.get(self.url).data['count'],0)
        self.auth(21,'setter');self.assertFalse(self.client.get(self.url).data['results'][0]['shared'])
        self.assertEqual(self.publish().status_code,200)
        self.auth(72,'client');result=self.client.get(self.url)
        self.assertEqual(result.data['count'],1);self.assertEqual(result['Cache-Control'],'no-store')
        row=result.data['results'][0];self.assertEqual(row['body'],'Texte interne');self.assertEqual(row['author_portal_id'],21)
        self.assertEqual(set(row),{'id','kind','body','changes','author_portal_id','author_role','created_at','shared'})
        self.auth(21,'setter');self.assertEqual(self.publish(revision=1,visible=False).status_code,200)
        self.auth(72,'client');self.assertEqual(self.client.get(self.url).data['count'],0)
        self.assertEqual(ProspectActivity.objects.count(),1);self.assertEqual(ProspectActivityShare.objects.count(),1)
        self.assertEqual(AuditEvent.objects.filter(action='isolation.prospect.activity_visibility_changed').count(),2)
    def test_clients_are_isolated_even_for_same_prospect(self):
        other=IsolationVisit.objects.create(prospect=self.prospect,request_id=uuid4(),fingerprint='test',client_id=73,client_name='Autre',
            setter_id=21,setter_name='Setter',booked_by_id=21,starts_at=self.visit.starts_at,ends_at=self.visit.ends_at,timezone='UTC')
        self.publish();self.auth(73,'client')
        self.assertEqual(self.client.get(self.url).status_code,404)
        self.assertEqual(self.client.get(f'/api/visits/{other.pk}/activities/').data['count'],0)
        self.auth(72,'client');self.assertEqual(self.client.get(self.url).data['count'],1)
    def test_clients_and_assurance_cannot_publish_or_read_internal_sources(self):
        self.auth(72,'client');self.assertEqual(self.publish().status_code,403)
        self.assertEqual(self.client.get(f'/api/work-queue/{self.prospect.pk}/activities/').status_code,403)
        self.auth(99,'administrator','assurance');self.assertEqual(self.client.get(self.url).status_code,401)
        self.assertEqual(self.publish().status_code,401);self.assertFalse(ProspectActivityShare.objects.exists())
    def test_foreign_activity_bad_fields_and_empty_reason_are_rejected_atomically(self):
        other=Prospect.objects.create(campaign=self.prospect.campaign,raw_phone='Autre')
        foreign=observation(other)
        for changes in ({'activity_id':foreign.pk},{'reason':' '},{'client_id':73},{'body':'Remplacement'}):
            self.assertEqual(self.publish(**changes).status_code,400,changes)
        self.prospect.refresh_from_db();self.assertEqual(self.prospect.assignment_revision,0)
        self.assertFalse(ProspectActivityShare.objects.exists())
    def test_revision_retries_and_transfer_current_owner_only(self):
        self.assertEqual(self.publish().status_code,200)
        self.assertEqual(self.publish().status_code,409)
        self.assertEqual(self.publish(revision=1).status_code,409)
        Prospect.objects.filter(pk=self.prospect.pk).update(assigned_setter_id=22,assignment_revision=2)
        self.assertEqual(self.publish(revision=2,visible=False).status_code,404)
        self.auth(22,'setter');self.assertEqual(self.publish(revision=2,visible=False).status_code,200)
        self.assertEqual(self.client.get(self.url).data['results'][0]['author_portal_id'],21)
        self.auth(91,'administrator');self.assertEqual(self.publish(revision=3).status_code,200)
    def test_publication_covers_same_clients_visits_and_cancelled_history(self):
        self.publish();IsolationVisit.objects.filter(pk=self.visit.pk).update(status='cancelled')
        self.auth(72,'client');self.assertEqual(self.client.get(self.url).data['count'],1)
        second=IsolationVisit.objects.create(prospect=self.prospect,request_id=uuid4(),fingerprint='second',client_id=72,client_name='Client',
            setter_id=21,setter_name='Setter',booked_by_id=21,starts_at=self.visit.starts_at,ends_at=self.visit.ends_at,timezone='UTC')
        second_url=f'/api/visits/{second.pk}/activities/'
        self.assertEqual(self.client.get(second_url).data['count'],1)
        self.auth(21,'setter');self.assertEqual(self.client.post(second_url,{'activity_id':self.activity.pk,'revision':1,'visible':False,'reason':'Retrait'},format='json').status_code,200)
        self.auth(72,'client');self.assertEqual(self.client.get(self.url).data['count'],0)
        self.assertEqual(self.client.patch(self.url,{},format='json').status_code,405)
        self.assertEqual(self.client.delete(self.url).status_code,405)
        self.assertEqual(self.client.get(self.url+'?page=2').status_code,404)
    def test_audit_failure_rolls_back_visibility_and_revision(self):
        with patch('core.isolation_sharing.AuditEvent.objects.create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.publish()
        self.prospect.refresh_from_db();self.assertEqual(self.prospect.assignment_revision,0)
        self.assertFalse(ProspectActivityShare.objects.exists())
    def test_only_published_qualifications_are_returned_without_technical_or_audit_data(self):
        self.activity.kind='qualification';self.activity.changes={'before':{'status':'to_contact','callback_at':None},'after':{'status':'interested','callback_at':None}};self.activity.save()
        observation(self.prospect,'Ne pas publier');self.publish();self.auth(72,'client')
        rows=self.client.get(self.url).data;self.assertEqual(rows['count'],1)
        self.assertEqual(rows['results'][0]['changes']['after']['status'],'interested')
        self.assertNotIn('Ne pas publier',str(rows));self.assertNotIn('Note autorisée',str(rows))
        self.prospect.refresh_from_db();self.assertEqual(self.prospect.phone.line_status,'unknown');self.assertEqual(self.prospect.commercial_status,'to_contact')


@skipUnless(connection.vendor=='postgresql','Sharing concurrency requires PostgreSQL')
@override_settings(DEBUG=True,SECURE_SSL_REDIRECT=False)
class IsolationSharingConcurrencyTests(TransactionTestCase):
    def setUp(self):self.prospect,self.visit=client_fixture();self.activity=observation(self.prospect)
    def race(self,assignment=False):
        barrier=Barrier(2)
        def attempt(index):
            close_old_connections()
            try:
                client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(91 if assignment and index else 21,'isolation','administrator' if assignment and index else 'setter'))
                barrier.wait(timeout=10)
                if assignment and index:
                    return client.post(f'/api/work-queue/{self.prospect.pk}/assign/',{'revision':0,'reason':'Transfert','proof':issue_owner(91,self.prospect.pk,22,'Nouveau setter')},format='json').status_code
                return client.post(f'/api/visits/{self.visit.pk}/activities/',{'activity_id':self.activity.pk,'revision':0,'visible':True,'reason':'Publication'},format='json').status_code
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(attempt,range(2)))
    def test_two_publications_have_one_winner(self):
        self.assertEqual(sorted(self.race()),[200,409]);self.assertEqual(ProspectActivityShare.objects.filter(visible=True).count(),1)
        self.assertEqual(AuditEvent.objects.filter(action='isolation.prospect.activity_visibility_changed').count(),1)
    def test_assignment_and_publication_share_the_same_revision(self):
        codes=self.race(assignment=True)
        if codes[1]==200:self.assertIn(codes[0],(404,409))
        else:self.assertEqual(codes,[200,409])
        self.prospect.refresh_from_db();self.assertEqual(self.prospect.assignment_revision,1)
        self.assertEqual(ProspectActivityShare.objects.filter(visible=True).exists(),codes[0]==200)
