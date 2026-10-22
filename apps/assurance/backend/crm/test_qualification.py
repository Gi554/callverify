from copy import deepcopy
from unittest.mock import patch
from datetime import timedelta
from django.test import TestCase,override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import Contact,ContactNote,BusinessAudit,Appointment
from . import tests as fixtures

@override_settings(DEBUG=True)
class QualificationTests(TestCase):
    def setUp(self):
        self.fixture=fixtures.AppointmentTests(methodName='test_booking_is_idempotent_and_keeps_one_responsible_setter')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups);self.client=self.fixture.client;self.contact=self.fixture.contact;self.token=self.fixture.token
        self.url=f'/api/assurance/contacts/{self.contact.pk}/qualification/'
        self.values={'age':43,'profession':'full_time','marital_status':'common_law','has_children':True,
            'homeowner':True,'smoker':False,'has_advisor':None,'insurances':['life','group'],
            'additional_notes':'Disponibilité le matin','advisor_notes':'Préparer les protections existantes'}
    def auth(self,pk,role):self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(pk,'assurance',role))
    def save(self,values=None,revision=0,**changes):
        return self.client.post(self.url,{'token':self.token,'contact_revision':revision,'qualification':self.values if values is None else values,**changes},format='json')
    def test_typed_fields_persist_and_unknown_is_not_no(self):
        data=self.client.get(self.url).data;self.assertEqual(data['qualification'],{})
        response=self.save();self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['qualification'],self.values);self.assertEqual(response.data['contact_revision'],1)
        self.assertEqual(response['Cache-Control'],'no-store')
        self.assertIsNone(response.data['qualification']['has_advisor']);self.assertIs(response.data['qualification']['smoker'],False)
        self.assertEqual(self.save(revision=0).status_code,409)
        self.assertEqual(BusinessAudit.objects.filter(action='contact.assurance_qualification_updated').count(),1)
        self.assertEqual(self.save(revision=1).data['contact_revision'],1)
    def test_validation_rejects_unknown_choices_contradictions_and_bad_age(self):
        for changes in ({'age':-1},{'age':121},{'age':12.5},{'profession':'invented'},{'marital_status':'invented'},
                        {'smoker':'unknown'},{'insurances':['none_known','life']},{'insurances':['life','life']},
                        {'insurances':['invented']},{'private_notes':'Injected'},{'advisor_notes':'x'*3001}):
            values={**self.values,**changes};self.assertEqual(self.save(values).status_code,400,changes)
        self.assertEqual(self.save({}).status_code,200)
        self.contact.refresh_from_db();self.assertIsNone(self.contact.assurance_qualification['age'])
        self.assertEqual(self.contact.assurance_qualification['insurances'],[])
    def test_fresh_lease_and_revision_required_and_audit_failure_rolls_back(self):
        from uuid import uuid4
        self.assertEqual(self.save(token=str(uuid4())).status_code,409)
        with patch('apps.assurance.backend.crm.qualification.BusinessAudit.objects.create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.save()
        self.contact.refresh_from_db();self.assertEqual(self.contact.assurance_qualification,{})
    def test_booking_captures_coordinates_and_qualification_without_internal_notes(self):
        self.save();self.fixture.contact.refresh_from_db()
        ContactNote.objects.create(contact=self.contact,request_id=__import__('uuid').uuid4(),author_id=21,channel='internal',body='INTERNAL SECRET')
        response=self.fixture.book(contact_revision=1);self.assertEqual(response.status_code,201,response.data)
        row=response.data;self.assertEqual(row['qualification_snapshot']['qualification'],self.values)
        self.assertEqual(row['qualification_snapshot']['contact']['phone'],self.contact.phone)
        self.assertNotIn('INTERNAL SECRET',str(row));self.assertNotIn('custom_values',str(row))
        changed=deepcopy(self.values);changed['advisor_notes']='FUTURE INTERNAL DRAFT'
        self.save(changed,revision=1)
        self.auth(31,'advisor')
        advisor=self.client.get(f"/api/assurance/appointments/{row['id']}/");self.assertEqual(advisor.status_code,200)
        self.assertEqual(advisor.data['qualification_snapshot']['qualification'],self.values)
        self.assertNotIn('FUTURE INTERNAL DRAFT',str(advisor.data));self.assertNotIn('SECRET SETTER',str(advisor.data))
        contact_view=self.client.get(self.url);self.assertEqual(contact_view.data['source'],'appointment_snapshot')
        self.assertEqual(contact_view.data['snapshot']['qualification'],self.values)
        self.assertEqual(self.save().status_code,403)
        self.auth(32,'advisor');self.assertEqual(self.client.get(f"/api/assurance/appointments/{row['id']}/").status_code,404)
        self.assertEqual(self.client.get(self.url).status_code,404)
    def test_assigned_advisor_without_booking_cannot_read_live_qualification(self):
        self.save();Contact.objects.filter(pk=self.contact.pk).update(assigned_advisor_id=31)
        self.auth(31,'advisor');response=self.client.get(self.url)
        self.assertEqual(response.status_code,200);self.assertIsNone(response.data['snapshot'])
        self.assertNotIn('Disponibilité le matin',str(response.data))
    def test_stale_qualification_revision_cannot_be_booked(self):
        self.save();response=self.fixture.book(contact_revision=0)
        self.assertEqual(response.status_code,409);self.assertFalse(Appointment.objects.exists())

    def test_snapshot_is_preserved_by_idempotent_retry_reschedule_and_cancellation(self):
        self.save();body=self.fixture.payload(contact_revision=1)
        first=self.client.post(self.fixture.url,body,format='json');self.assertEqual(first.status_code,201,first.data)
        captured=first.data['qualification_snapshot']
        again=self.client.post(self.fixture.url,body,format='json');self.assertEqual(again.data['qualification_snapshot'],captured)
        url=self.fixture.url+str(first.data['id'])+'/'
        rescheduled=self.client.post(url+'reschedule/',self.fixture.reschedule_payload(),format='json')
        self.assertEqual(rescheduled.status_code,200,rescheduled.data);self.assertEqual(rescheduled.data['qualification_snapshot'],captured)
        cancelled=self.client.post(url+'cancel/',{'revision':1,'reason':'Indisponibilité'},format='json')
        self.assertEqual(cancelled.status_code,200,cancelled.data);self.assertEqual(cancelled.data['qualification_snapshot'],captured)
