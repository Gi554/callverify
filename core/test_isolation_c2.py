from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4
from django.test import TestCase,override_settings
from django.utils import timezone
from packages.access.tickets import issue
from . import test_isolation_visits as fixtures
from .models import Prospect,IsolationVisit,AuditEvent


@override_settings(DEBUG=True,SECURE_SSL_REDIRECT=False)
class IsolationC2Tests(TestCase):
    setUp=fixtures.IsolationVisitTests.setUp
    auth=fixtures.IsolationVisitTests.auth
    proof=fixtures.IsolationVisitTests.proof
    payload=fixtures.IsolationVisitTests.payload
    book=fixtures.IsolationVisitTests.book

    @property
    def draft_url(self):return f'/api/work-queue/{self.prospect.pk}/c2/'

    def save(self,**changes):
        return self.client.post(self.draft_url,{'revision':0,'c2':{**fixtures.C2_DATA,**changes}},format='json')

    def test_partial_draft_keeps_unknown_answers_and_does_not_touch_lookup(self):
        response=self.client.post(self.draft_url,{'revision':0,'c2':{'city':'Québec'}},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertIsNone(response.data['c2']['attic_accessible'])
        self.assertIsNone(response.data['c2']['monthly_electricity'])
        self.prospect.refresh_from_db()
        self.assertEqual(self.prospect.assignment_revision,1)
        self.assertEqual(self.prospect.raw_phone,'4165550123')
        self.assertEqual(self.prospect.c2['city'],'Québec')
        self.assertEqual(self.client.get(self.draft_url)['Cache-Control'],'no-store')
        self.assertEqual(self.book(revision=1).status_code,400)
        self.external_check.assert_not_called()
        self.assertFalse(IsolationVisit.objects.exists())

    def test_validation_rejects_unknown_fields_invalid_ranges_postal_and_phone(self):
        for changes in ({'age':-1},{'age':121},{'construction_year':timezone.now().year+1},
                        {'construction_year':1200},{'monthly_electricity':'-0.01'},
                        {'monthly_electricity':'1.999'},{'attic_accessible':'unknown'},
                        {'postal_code':'invalid'},{'phone':'numéro fourni'},{'insurance':'life'}):
            response=self.save(**changes)
            self.assertEqual(response.status_code,400,(changes,response.data))
        self.prospect.refresh_from_db();self.assertEqual(self.prospect.assignment_revision,0)

    def test_normalization_preserves_no_and_zero(self):
        response=self.save(postal_code='h2x1y4',monthly_electricity='0',age=0,attic_accessible=False)
        self.assertEqual(response.status_code,200,response.data)
        data=response.data['c2']
        self.assertEqual(data['postal_code'],'H2X 1Y4')
        self.assertEqual(data['monthly_electricity'],'0.00')
        self.assertEqual(self.book(revision=1).status_code,201)

    def test_every_required_field_blocks_new_booking_but_electricity_is_optional(self):
        for key in fixtures.C2_DATA:
            if key=='monthly_electricity':continue
            self.prospect.c2={k:v for k,v in fixtures.C2_DATA.items() if k!=key};self.prospect.save()
            response=self.book()
            self.assertEqual(response.status_code,400,(key,response.data))
            self.prospect.refresh_from_db();self.assertEqual(self.prospect.assignment_revision,0)
        self.prospect.c2=fixtures.C2_DATA.copy();self.prospect.save()
        self.assertEqual(self.book().status_code,201)

    def test_scope_revision_and_space_guards(self):
        self.auth(22,'setter');self.assertEqual(self.client.get(self.draft_url).status_code,404)
        self.assertEqual(self.save().status_code,404)
        self.auth(72,'client');self.assertEqual(self.client.get(self.draft_url).status_code,403)
        self.assertEqual(self.save().status_code,403)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(21,'assurance','setter'))
        self.assertEqual(self.client.get(self.draft_url).status_code,401)
        self.auth(21,'setter');self.assertEqual(self.save().status_code,200)
        self.assertEqual(self.save(city='Autre').status_code,409)
        self.prospect.refresh_from_db();self.assertEqual(self.prospect.c2['city'],'Montréal')

    def test_booking_captures_copy_preserved_by_edit_replay_report_and_cancel(self):
        first=self.book();self.assertEqual(first.status_code,201,first.data)
        snapshot=first.data['c2_snapshot']
        self.assertEqual(snapshot['fields']['attic_accessible'],False)
        self.assertEqual(snapshot['campaign_id'],self.prospect.campaign_id)
        self.assertEqual(snapshot['setter_id'],21)
        self.assertTrue(snapshot['captured_at'])
        response=self.client.post(self.draft_url,{'revision':1,'c2':{**fixtures.C2_DATA,'address':'Nouvelle adresse'}},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(self.book().data['c2_snapshot'],snapshot)
        url=f"{self.url}{first.data['id']}/"
        change={'revision':0,'proof':self.proof(),'reason':'Report','starts_at':(self.start+timedelta(days=1)).isoformat(),
                'ends_at':(self.end+timedelta(days=1)).isoformat(),'timezone':'UTC'}
        moved=self.client.post(url+'reschedule/',change,format='json')
        self.assertEqual(moved.status_code,200,moved.data)
        self.assertEqual(moved.data['c2_snapshot'],snapshot)
        cancelled=self.client.post(url+'cancel/',{'revision':1,'reason':'Annulation'},format='json')
        self.assertEqual(cancelled.status_code,200,cancelled.data)
        self.assertEqual(cancelled.data['c2_snapshot'],snapshot)
        self.auth(72,'client')
        self.assertEqual(self.client.get(url).data['c2_snapshot'],snapshot)
        self.assertNotIn('Nouvelle adresse',str(self.client.get(url).data))
        self.auth(73,'client');self.assertEqual(self.client.get(url).status_code,404)

    def test_old_visits_have_no_invented_copy_and_remain_reschedulable(self):
        row=IsolationVisit.objects.create(prospect=self.prospect,request_id=uuid4(),fingerprint='old',client_id=72,client_name='Client',
            setter_id=21,setter_name='Setter',booked_by_id=21,starts_at=self.start,ends_at=self.end,timezone='UTC')
        Prospect.objects.filter(pk=self.prospect.pk).update(c2={})
        url=f'{self.url}{row.pk}/'
        self.assertEqual(self.client.get(url).data['c2_snapshot'],{})
        response=self.client.post(url+'reschedule/',{'revision':0,'proof':self.proof(),'reason':'Report',
            'starts_at':(self.start+timedelta(days=1)).isoformat(),'ends_at':(self.end+timedelta(days=1)).isoformat(),'timezone':'UTC'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['c2_snapshot'],{})

    def test_audit_failure_rolls_back_draft_and_revision(self):
        with patch('core.isolation_c2.AuditEvent.objects.create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.save(city='Autre')
        self.prospect.refresh_from_db();self.assertEqual(self.prospect.assignment_revision,0)
        self.assertEqual(self.prospect.c2,fixtures.C2_DATA)

    def test_new_c2_never_becomes_a_lookup_result(self):
        before=self.client.get(f'/api/work-queue/{self.prospect.pk}/').data
        self.assertEqual(self.save(phone='4185550100').status_code,200)
        after=self.client.get(f'/api/work-queue/{self.prospect.pk}/').data
        for key in ('raw_phone','phone','validity','line_status','commercial_status'):
            self.assertEqual(before[key],after[key])
