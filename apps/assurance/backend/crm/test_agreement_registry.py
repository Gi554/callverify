from datetime import date
from uuid import uuid4
from django.test import TestCase,override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import Agreement,Contact,ContactDocument,AgreementDocument,BusinessAudit

@override_settings(DEBUG=True)
class RegistryTests(TestCase):
    def setUp(self):
        self.client=APIClient();self.auth(99,'administrator');self.url='/api/assurance/agreement-registry/'
        self.contact=Contact.objects.create(name='Alice Martin',phone='PRIVATE PHONE',created_by_id=21,custom_values={'secret':'PRIVATE DATA'})
        self.first=self.create('MAND-001',starts_on=date(2026,10,1),ends_on=date(2026,12,31))
        self.second=self.create('CONT-002',kind='contract',status='archived')
    def auth(self,pk,role,workspace='assurance'):self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(pk,workspace,role))
    def create(self,reference,**changes):return Agreement.objects.create(contact=self.contact,request_id=uuid4(),fingerprint='private fingerprint',kind=changes.pop('kind','mandate'),reference=reference,**changes)
    def test_admin_allowlist_document_count_and_no_write(self):
        for active in (True,False):
            document=ContactDocument.objects.create(contact=self.contact,request_id=uuid4(),author_id=21,channel='internal',filename='PRIVATE DOCUMENT.pdf',content_type='application/pdf',size=8,content=b'private bytes',sha256='private hash')
            AgreementDocument.objects.create(agreement=self.first,document=document,active=active)
        response=self.client.get(self.url);self.assertEqual(response.status_code,200);self.assertEqual(response.data['count'],2);self.assertEqual(response['Cache-Control'],'no-store')
        row=next(row for row in response.data['results'] if row['id']==self.first.pk);self.assertEqual(row['document_count'],1);self.assertEqual(row['contact'],{'id':self.contact.pk,'name':'Alice Martin'})
        for secret in ('PRIVATE','fingerprint','created_by_id','author_id','lease','request_id'):self.assertNotIn(secret,str(response.data))
        self.assertFalse(BusinessAudit.objects.exists());self.assertEqual(self.client.post(self.url,{},format='json').status_code,405)
    def test_search_reference_and_prospect_case_insensitive_and_combined_filters(self):
        self.assertEqual(self.client.get(self.url,{'search':'mand-001'}).data['count'],1)
        self.assertEqual(self.client.get(self.url,{'search':'alice','kind':'contract','status':'archived'}).data['results'][0]['id'],self.second.pk)
        self.assertEqual(self.client.get(self.url,{'search':'PRIVATE PHONE'}).data['count'],0)
        self.assertEqual(self.client.get(self.url,{'kind':'mandate','status':'archived'}).data['count'],0)
    def test_date_bounds_inclusive_exclude_nulls(self):
        response=self.client.get(self.url,{'starts_from':'2026-10-01','starts_to':'2026-10-01','ends_from':'2026-12-31','ends_to':'2026-12-31'})
        self.assertEqual(response.data['count'],1);self.assertEqual(response.data['results'][0]['id'],self.first.pk)
        self.assertEqual(self.client.get(self.url,{'starts_from':'2026-10-02'}).data['count'],0)
        self.assertEqual(self.client.get(self.url).data['count'],2)
    def test_invalid_and_repeated_filters_refused(self):
        for query in ({'status':'signed'},{'kind':'unknown'},{'search':'x'*251},{'starts_from':'bad'},{'starts_from':'2026-12-01','starts_to':'2026-10-01'},{'page':'0'},{'amount':10}):self.assertEqual(self.client.get(self.url,query).status_code,400,query)
        self.assertEqual(self.client.get(self.url+'?kind=mandate&kind=contract').status_code,400)
    def test_roles_spaces_and_authentication(self):
        for pk,role in ((21,'setter'),(31,'advisor')):
            self.auth(pk,role);self.assertEqual(self.client.get(self.url).status_code,403)
        self.auth(99,'administrator','isolation');self.assertEqual(self.client.get(self.url).status_code,401)
        self.client.credentials();self.assertEqual(self.client.get(self.url).status_code,401)
    def test_pagination_stable_ties_and_fixed_size(self):
        for n in range(30):self.create(f'REF-{n}')
        Agreement.objects.update(updated_at=timezone.now())
        one=self.client.get(self.url).data;two=self.client.get(self.url,{'page':2}).data
        ids=[row['id'] for row in one['results']+two['results']];self.assertEqual(ids,sorted(ids,reverse=True));self.assertEqual(len(set(ids)),32);self.assertEqual(len(one['results']),25)
    def test_open_contact_uses_existing_protected_route_without_new_permissions(self):
        row=self.client.get(self.url).data['results'][0]
        result=self.client.get(f'/api/assurance/contacts/{row["contact"]["id"]}/');self.assertEqual(result.status_code,200)
        self.auth(31,'advisor');self.assertEqual(self.client.get(self.url).status_code,403);self.assertEqual(self.client.get(f'/api/assurance/contacts/{self.contact.pk}/').status_code,404)
