from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4
from datetime import timedelta
from django.test import TestCase,override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import Contact,ContactFieldSchema,BusinessAudit,Appointment,AdvisorAssignment

@override_settings(DEBUG=True)
class SharedFieldTests(TestCase):
    def setUp(self):
        self.client=APIClient();self.contact=Contact.objects.create(name='Prospect',phone='raw',created_by_id=21,assigned_advisor_id=31,custom_values={'city':'Montréal','flag':False,'secret':'SECRET VALUE','archived':'ARCHIVED VALUE','unknown':'UNKNOWN VALUE'})
        self.base=f'/api/assurance/contacts/{self.contact.pk}/';self.url=self.base+'shared_fields/'
        self.fields=[{'key':'city','label':'Ville','type':'text','active':True,'required':False,'choices':[],'advisor_visible':True},
            {'key':'flag','label':'Accord','type':'boolean','active':True,'required':False,'choices':[],'advisor_visible':True},
            {'key':'secret','label':'SECRET LABEL','type':'text','active':True,'required':False,'choices':[],'advisor_visible':False},
            {'key':'archived','label':'ARCHIVED LABEL','type':'text','active':False,'required':False,'choices':[],'advisor_visible':True}]
        ContactFieldSchema.objects.create(pk=1,fields=deepcopy(self.fields))
        self.auth(31,'advisor')
    def auth(self,pk,role,workspace='assurance'):self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(pk,workspace,role))
    def configure(self,fields,revision=0):return self.client.post('/api/assurance/contact-fields/',{'fields':fields,'revision':revision,'reason':'Choix explicite des champs partagés'},format='json')
    def test_explicit_allowlist_preserves_false_and_excludes_private_schema_values(self):
        response=self.client.get(self.url);self.assertEqual(response.status_code,200);self.assertEqual(response['Cache-Control'],'no-store')
        self.assertEqual(response.data,{'fields':[{'key':'city','label':'Ville','type':'text','value':'Montréal'},{'key':'flag','label':'Accord','type':'boolean','value':False}]})
        for secret in ('SECRET','ARCHIVED','UNKNOWN','author_id','created_by_id','revision','choices','required'):self.assertNotIn(secret,str(response.data))
        self.assertEqual(BusinessAudit.objects.count(),0)
    def test_legacy_missing_or_nonboolean_flags_are_private_by_default(self):
        for value in (None,'true',1):
            fields=deepcopy(self.fields)
            for field in fields:
                if value is None:field.pop('advisor_visible',None)
                else:field['advisor_visible']=value
            ContactFieldSchema.objects.update(fields=fields)
            self.assertEqual(self.client.get(self.url).data,{'fields':[]})
        self.auth(99,'administrator');fields=deepcopy(self.fields)
        for field in fields:field.pop('advisor_visible')
        response=self.configure(fields);self.assertEqual(response.status_code,200)
        self.assertTrue(all(field['advisor_visible'] is False for field in response.data['fields']))
        self.auth(31,'advisor');self.assertEqual(self.client.get(self.url).data,{'fields':[]})
        ContactFieldSchema.objects.all().delete();self.assertEqual(self.client.get(self.url).data,{'fields':[]})
    def test_admin_can_revoke_and_archive_without_changing_values(self):
        self.auth(99,'administrator');fields=deepcopy(self.fields);fields[0]['advisor_visible']=False;fields[1]['active']=False
        self.assertEqual(self.configure(fields).status_code,200)
        audit=BusinessAudit.objects.get(action='schema.contact_fields_changed');self.assertTrue(audit.metadata['before']['fields'][0]['advisor_visible']);self.assertFalse(audit.metadata['after']['fields'][0]['advisor_visible'])
        self.auth(31,'advisor');self.assertEqual(self.client.get(self.url).data,{'fields':[]})
        self.contact.refresh_from_db();self.assertEqual(self.contact.custom_values['city'],'Montréal');self.assertEqual(self.contact.revision,0)
    def test_schema_change_admin_revision_reason_validation_and_rollback(self):
        self.auth(21,'setter');self.assertEqual(self.configure(self.fields).status_code,403)
        self.auth(99,'administrator');self.assertEqual(self.configure(self.fields,revision=99).status_code,409)
        fields=deepcopy(self.fields);fields[0]['advisor_visible']=False
        with patch('apps.assurance.backend.crm.custom_fields.BusinessAudit.objects.create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.configure(fields)
        self.assertTrue(ContactFieldSchema.objects.get().fields[0]['advisor_visible'])
        fields[0]['advisor_visible']='not-a-boolean';self.assertEqual(self.configure(fields).status_code,400)
    def test_owner_scope_and_workspace_read_only_and_no_full_schema_leak(self):
        self.assertEqual(self.client.get(self.base+'custom_fields/').status_code,403)
        self.assertEqual(self.client.get('/api/assurance/contact-fields/').status_code,403)
        self.assertEqual(self.client.post(self.url,{'values':{'city':'overwrite'}},format='json').status_code,405)
        self.auth(32,'advisor');self.assertEqual(self.client.get(self.url).status_code,404)
        Contact.objects.filter(pk=self.contact.pk).update(assigned_advisor_id=None)
        self.auth(31,'advisor');self.assertEqual(self.client.get(self.url).status_code,404)
        self.auth(31,'advisor','isolation');self.assertEqual(self.client.get(self.url).status_code,401)
        for role in ('administrator','setter'):
            self.auth(99,role);self.assertEqual(self.client.get(self.url).status_code,403)
    def test_appointment_grants_contact_visibility_without_setter_metadata(self):
        assignment=AdvisorAssignment.objects.create(setter_id=21,setter_name='SECRET SETTER',advisor_id=32,advisor_name='Advisor')
        start=timezone.now()+timedelta(days=1)
        Appointment.objects.create(contact=self.contact,assignment=assignment,request_id=uuid4(),fingerprint='secret fingerprint',setter_id=21,setter_name='SECRET SETTER',advisor_id=32,advisor_name='Advisor',booked_by_id=99,starts_at=start,ends_at=start+timedelta(hours=1),timezone='UTC')
        self.auth(32,'advisor');response=self.client.get(self.url);self.assertEqual(response.status_code,200);self.assertNotIn('SECRET',str(response.data))
    def test_unset_value_and_internal_writes_remain_authoritative(self):
        Contact.objects.filter(pk=self.contact.pk).update(custom_values={})
        self.assertIsNone(self.client.get(self.url).data['fields'][0]['value'])
        self.auth(21,'setter');token=self.client.post(self.base+'lease/',{},format='json').data['token']
        response=self.client.post(self.base+'custom_fields/',{'token':token,'revision':0,'schema_revision':0,'values':{'city':'Québec','flag':False,'secret':'INTERNAL ONLY'}},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.auth(31,'advisor');data=self.client.get(self.url).data;self.assertEqual(data['fields'][0]['value'],'Québec');self.assertNotIn('INTERNAL ONLY',str(data))
