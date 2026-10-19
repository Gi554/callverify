import json
from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import Contact,ContactImport,ContactFieldSchema

@override_settings(DEBUG=True)
class CustomImportTests(TestCase):
    def setUp(self):
        self.client=APIClient();self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(99,'assurance','administrator'));self.url='/api/assurance/imports/'
        self.fields=[{'key':'city','label':'Ville','type':'text','active':True,'required':True,'choices':[]}, {'key':'flag','label':'Accord','type':'boolean','active':True,'required':True,'choices':[]}, {'key':'date','label':'Date','type':'date','active':True,'required':False,'choices':[]}, {'key':'kind','label':'Type','type':'choice','active':True,'required':False,'choices':['A','B']}]
        ContactFieldSchema.objects.create(pk=1,revision=3,fields=self.fields)
    def upload(self,content='Phone;City;Flag;Date;Kind\nraw;Paris;non;2026-10-20;A\n',**changes):
        data={'file':SimpleUploadedFile('contacts.csv',content.encode()),'has_header':'true','mode':'confirm','request_id':str(uuid4()),'mapping':json.dumps({'phone':0}),'custom_mapping':json.dumps({'city':1,'flag':2,'date':3,'kind':4}),'schema_revision':'3',**changes}
        return self.client.post(self.url,data,format='multipart')
    def test_typed_values_raw_phone_and_mapping_persist(self):
        response=self.upload();self.assertEqual(response.status_code,201,response.data);row=Contact.objects.get();self.assertEqual(row.phone,'raw');self.assertEqual(row.custom_values,{'city':'Paris','flag':False,'date':'2026-10-20','kind':'A'})
        self.assertEqual(ContactImport.objects.get().mapping['schema_revision'],3)
    def test_invalid_rows_report_physical_lines_without_importing_them(self):
        response=self.upload('Phone;City;Flag;Date;Kind\nraw;Paris;maybe;2026-10-20;A\nraw;Paris;oui;bad;A\nraw;Paris;oui;2026-10-20;C\nraw;Paris;1;;B\n')
        self.assertEqual(response.data['imported'],1);self.assertEqual([r['line'] for r in response.data['report']],[2,3,4]);self.assertTrue(Contact.objects.get().custom_values['flag'])
    def test_raw_import_bypasses_business_required_but_partial_mapping_enforces_it(self):
        response=self.upload(custom_mapping='{}',schema_revision='');self.assertEqual(response.data['imported'],1);self.assertEqual(Contact.objects.get().custom_values,{})
        response=self.upload(custom_mapping=json.dumps({'city':1}));self.assertEqual(response.data['rejected'],1)
    def test_invalid_mapping_schema_and_archived_fields(self):
        for changes in ({'schema_revision':'2'},{'custom_mapping':json.dumps({'unknown':1})},{'custom_mapping':json.dumps({'city':0})},{'custom_mapping':json.dumps({'city':True})},{'custom_mapping':'[]'}):
            self.assertIn(self.upload(**changes).status_code,(400,409),changes)
        fields=self.fields;fields[0]['active']=False;ContactFieldSchema.objects.update(fields=fields)
        self.assertEqual(self.upload().status_code,400);self.assertFalse(Contact.objects.exists())
    def test_replay_after_schema_change_and_changed_content_refused(self):
        key=str(uuid4());self.assertEqual(self.upload(request_id=key).status_code,201)
        ContactFieldSchema.objects.update(revision=4)
        self.assertEqual(self.upload(request_id=key).status_code,200);self.assertEqual(Contact.objects.count(),1)
        self.assertEqual(self.upload(request_id=key,custom_mapping='{}').status_code,409)
    def test_schema_change_during_validation_refuses_entire_batch(self):
        from .imports import validate_values
        def mutate(values,fields):
            validate_values(values,fields);ContactFieldSchema.objects.update(revision=4)
        with patch('apps.assurance.backend.crm.imports.validate_values',side_effect=mutate):self.assertEqual(self.upload().status_code,409)
        self.assertFalse(Contact.objects.exists());self.assertFalse(ContactImport.objects.exists())
    def test_preview_no_writes_admin_only_and_audit_rollback(self):
        response=self.upload(mode='preview');self.assertEqual(response.data['custom_schema']['revision'],3);self.assertFalse(Contact.objects.exists())
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(21,'assurance','setter'));self.assertEqual(self.upload().status_code,403)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(99,'assurance','administrator'))
        with patch('apps.assurance.backend.crm.imports.BusinessAudit.objects.create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.upload()
        self.assertFalse(Contact.objects.exists());self.assertFalse(ContactImport.objects.exists())

    def test_xlsx_date_and_boolean_cells_are_typed_without_evaluating_formulas(self):
        from openpyxl import Workbook
        from io import BytesIO
        from datetime import datetime
        workbook=Workbook();sheet=workbook.active;sheet.append(['Phone','City','Flag','Date','Kind']);sheet.append(['raw','Paris',False,datetime(2026,10,20),'A']);sheet.append(['raw','Paris',True,'=TODAY()','B'])
        buffer=BytesIO();workbook.save(buffer)
        response=self.client.post(self.url,{'file':SimpleUploadedFile('contacts.xlsx',buffer.getvalue()),'mode':'confirm','request_id':str(uuid4()),'mapping':json.dumps({'phone':0}),'custom_mapping':json.dumps({'city':1,'flag':2,'date':3,'kind':4}),'schema_revision':'3'},format='multipart')
        self.assertEqual(response.status_code,201,response.data);self.assertEqual(response.data['imported'],1);self.assertEqual(response.data['rejected'],1);self.assertEqual(Contact.objects.get().custom_values['date'],'2026-10-20')
