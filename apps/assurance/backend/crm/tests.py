from django.test import TestCase,override_settings
from rest_framework.test import APIClient
from packages.access.tickets import issue
from django.conf import settings
from unittest import skipUnless
if 'apps.assurance.backend.crm' in settings.INSTALLED_APPS:
    from .models import Contact

@override_settings(DEBUG=True)
@skipUnless(settings.ROOT_URLCONF=='apps.assurance.backend.urls','Service Assurance indépendant')
class AssuranceTests(TestCase):
    def setUp(self):self.client=APIClient()
    def authorize(self,subject,role,space='assurance'):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(subject,space,role))
    def test_isolation_ticket_and_anonymous_are_denied(self):
        self.assertEqual(self.client.get('/api/assurance/contacts/').status_code,401)
        self.authorize(1,'administrator','isolation')
        self.assertEqual(self.client.get('/api/assurance/contacts/').status_code,401)
    def test_advisor_only_sees_assigned_contact_and_no_setter_fields(self):
        visible=Contact.objects.create(name='A',phone='original phone',assigned_advisor_id=7,created_by_id=123)
        hidden=Contact.objects.create(name='B',phone='other',assigned_advisor_id=8,created_by_id=124)
        self.authorize(7,'advisor')
        rows=self.client.get('/api/assurance/contacts/').data['results']
        self.assertEqual([r['id'] for r in rows],[visible.pk])
        self.assertNotIn('created_by_id',rows[0]);self.assertNotIn('assigned_advisor_id',rows[0])
        self.assertEqual(self.client.get(f'/api/assurance/contacts/{hidden.pk}/').status_code,404)
    def test_contact_read_preserves_original_phone_without_technical_processing(self):
        Contact.objects.create(name='Client',phone='Original tel 01.00.00',created_by_id=1)
        self.authorize(1,'administrator')
        response=self.client.get('/api/assurance/contacts/')
        self.assertEqual(response.data['results'][0]['phone'],'Original tel 01.00.00')
    def test_setter_edit_is_blocked_until_locking_exists(self):
        self.authorize(1,'setter')
        self.assertEqual(self.client.post('/api/assurance/contacts/',{'name':'A','phone':'x'}).status_code,405)
    def test_no_twilio_or_normalization_endpoints(self):
        self.authorize(1,'administrator')
        self.assertEqual(self.client.post('/api/assurance/lookup/').status_code,404)
        self.assertEqual(self.client.post('/api/assurance/calls/').status_code,404)

@override_settings(DEBUG=True)
@skipUnless(settings.ROOT_URLCONF=='apps.assurance.backend.urls','Service Assurance indépendant')
class RawImportTests(TestCase):
    def setUp(self):
        self.client=APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(17,'assurance','administrator'))
        self.url='/api/assurance/imports/'
    def upload(self,content=b'Nom;Telephone;Courriel\nAlice;001 abc;not-an-email\n',**kwargs):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return self.client.post(self.url,{'file':SimpleUploadedFile('contacts.csv',content),'has_header':'true',**kwargs},format='multipart')
    def confirm(self,content=None,**kwargs):
        from uuid import uuid4
        import json
        args={'mode':'confirm','request_id':str(uuid4()),'mapping':json.dumps({'name':0,'phone':1,'email':2}),**kwargs}
        return self.upload(**({'content':content} if content is not None else {}),**args)
    def test_preview_has_no_side_effects_and_preserves_strings(self):
        from .models import ContactImport
        response=self.upload()
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['rows'][0]['values'][1],'001 abc')
        self.assertEqual(Contact.objects.count(),0);self.assertEqual(ContactImport.objects.count(),0)
    def test_raw_duplicates_and_bad_format_are_imported_without_lookup(self):
        content=b'Nom;Telephone;Courriel\nAlice; 001 abc ;bad-email\nAlice; 001 abc ;bad-email\n'
        response=self.confirm(content)
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(response.data['imported'],2)
        self.assertEqual(list(Contact.objects.values_list('phone',flat=True)),[' 001 abc ',' 001 abc '])
        self.assertEqual(Contact.objects.first().source_values,['Alice',' 001 abc ','bad-email'])
        self.assertEqual(Contact.objects.first().import_batch.mapping,{'name':0,'phone':1,'email':2})
    def test_rejected_rows_report_physical_line_and_valid_rows_survive(self):
        response=self.confirm(b'Nom;Telephone;Courriel\n\nMissing;;\nOK;raw;\n')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(response.data['total'],2);self.assertEqual(response.data['imported'],1)
        self.assertEqual(response.data['report'],[{'line':3,'reason':'Téléphone manquant'}])
        self.assertEqual(Contact.objects.first().source_row,4)
    def test_idempotent_retry_and_conflicting_payload(self):
        from uuid import uuid4
        key=str(uuid4())
        first=self.confirm(request_id=key);retry=self.confirm(request_id=key)
        self.assertEqual(first.data['id'],retry.data['id']);self.assertEqual(Contact.objects.count(),1)
        conflict=self.confirm(b'Nom;Telephone;Courriel\nOther;changed;\n',request_id=key)
        self.assertEqual(conflict.status_code,409);self.assertEqual(Contact.objects.count(),1)
    def test_no_header_keeps_first_line(self):
        import json
        response=self.confirm(b'001\n002\n',has_header='false',mapping=json.dumps({'phone':0}))
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(list(Contact.objects.values_list('phone',flat=True)),['001','002'])
    def test_xlsx_first_sheet_and_formula_are_not_evaluated(self):
        from openpyxl import Workbook
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        from uuid import uuid4
        book=Workbook();sheet=book.active;sheet.append(['Phone']);sheet.append(['=1+1'])
        book.create_sheet('Ignore').append(['other'])
        stream=BytesIO();book.save(stream)
        response=self.client.post(self.url,{'file':SimpleUploadedFile('sample.xlsx',stream.getvalue()),'mode':'confirm','mapping':'{"phone":0}','request_id':str(uuid4())},format='multipart')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(Contact.objects.get().phone,'=1+1')
    def test_permissions_protect_imports_and_history(self):
        self.confirm()
        for role in ('setter','advisor'):
            self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(5,'assurance',role))
            self.assertEqual(self.upload().status_code,403)
            self.assertEqual(self.client.get(self.url).status_code,403)
    def test_invalid_mapping_does_not_write_contacts_or_batches(self):
        from .models import ContactImport
        for mapping in ('{}','{"phone":99}','{"phone":0,"name":0}','{"phone":true}','[]'):
            response=self.confirm(mapping=mapping)
            self.assertEqual(response.status_code,400,response.data)
        self.assertEqual(Contact.objects.count(),0);self.assertEqual(ContactImport.objects.count(),0)
    def test_bad_file_and_row_limit(self):
        from unittest.mock import patch
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.assertEqual(self.client.post(self.url,{'file':SimpleUploadedFile('bad.xlsx',b'bad')},format='multipart').status_code,400)
        with patch('apps.assurance.backend.crm.imports.MAX_ROWS',1):
            self.assertEqual(self.upload(b'Phone\na\nb\n').status_code,400)
        with patch('apps.assurance.backend.crm.imports.MAX_BYTES',2):
            self.assertEqual(self.upload().status_code,400)
    def test_search_and_pagination_never_expand_advisor_scope(self):
        own=Contact.objects.create(name='Visible',phone='raw',created_by_id=17,assigned_advisor_id=5,source_values=['secret setter'])
        Contact.objects.create(name='Hidden',phone='raw',created_by_id=17,assigned_advisor_id=6)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(5,'assurance','advisor'))
        response=self.client.get('/api/assurance/contacts/?search=raw')
        self.assertEqual(response.data['count'],1)
        self.assertEqual(response.data['results'][0]['id'],own.pk)
        self.assertNotIn('source_values',response.data['results'][0])
        self.assertNotIn('import_batch',response.data['results'][0])
        self.assertEqual(self.client.get('/api/assurance/contacts/?search=Hidden').data['count'],0)
    def test_import_history_excludes_actor_and_raw_data(self):
        self.confirm()
        response=self.client.get(self.url)
        self.assertEqual(response.data['count'],1)
        self.assertNotIn('created_by_id',response.data['results'][0])
        self.assertNotIn('source_values',str(response.data))
    def test_5000_rows_are_imported_without_deduplication(self):
        content=('Nom;Telephone;Courriel\n'+'Volume;unverified;raw\n'*5000).encode()
        response=self.confirm(content)
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(response.data['imported'],5000)
        self.assertEqual(Contact.objects.count(),5000)
    def test_audit_failure_rolls_back_batch_and_contacts(self):
        from unittest.mock import patch
        from .models import ContactImport
        with patch('apps.assurance.backend.crm.imports.BusinessAudit.objects.create',side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):self.confirm()
        self.assertFalse(Contact.objects.exists());self.assertFalse(ContactImport.objects.exists())
