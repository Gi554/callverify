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
        rows=self.client.get('/api/assurance/contacts/').data
        self.assertEqual([r['id'] for r in rows],[visible.pk])
        self.assertNotIn('created_by_id',rows[0]);self.assertNotIn('assigned_advisor_id',rows[0])
        self.assertEqual(self.client.get(f'/api/assurance/contacts/{hidden.pk}/').status_code,404)
    def test_contact_read_preserves_original_phone_without_technical_processing(self):
        Contact.objects.create(name='Client',phone='Original tel 01.00.00',created_by_id=1)
        self.authorize(1,'administrator')
        response=self.client.get('/api/assurance/contacts/')
        self.assertEqual(response.data[0]['phone'],'Original tel 01.00.00')
    def test_setter_edit_is_blocked_until_locking_exists(self):
        self.authorize(1,'setter')
        self.assertEqual(self.client.post('/api/assurance/contacts/',{'name':'A','phone':'x'}).status_code,405)
    def test_no_twilio_or_normalization_endpoints(self):
        self.authorize(1,'administrator')
        self.assertEqual(self.client.post('/api/assurance/lookup/').status_code,404)
        self.assertEqual(self.client.post('/api/assurance/calls/').status_code,404)
