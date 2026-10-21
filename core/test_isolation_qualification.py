from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from packages.access.tickets import issue
from .models import AdminUser, Campaign, PhoneNumber, Prospect


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class IsolationQualificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(41, 'isolation', 'administrator'))

    def test_administrator_creates_a_centrally_scoped_campaign(self):
        response = self.client.post('/api/qualification/', {
            'name': 'Qualification Isolation', 'source': 'Recette', 'budget': '3.0000',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        campaign = Campaign.objects.get(pk=response.data['id'])
        self.assertEqual(campaign.portal_workspace, 'isolation')
        self.assertEqual(campaign.portal_owner_id, 41)
        self.assertFalse(campaign.owner.is_active)
        self.assertTrue(campaign.owner.password.startswith('!'))

    def test_setter_cannot_operate_the_qualification_process(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(42, 'isolation', 'setter'))
        self.assertEqual(self.client.get('/api/qualification/').status_code, 403)

    def test_results_do_not_expose_legacy_campaigns(self):
        legacy_owner = AdminUser.objects.create_user('legacy-owner', is_staff=True)
        legacy = Campaign.objects.create(owner=legacy_owner, name='Legacy', purpose='', source='')
        isolated = Campaign.objects.create(owner=legacy_owner, portal_workspace='isolation', portal_owner_id=41,
                                            name='Isolation', purpose='', source='')
        phone = PhoneNumber.objects.create(e164='+14165550124')
        Prospect.objects.create(campaign=legacy, phone=phone, raw_phone='5145550124')
        Prospect.objects.create(campaign=isolated, phone=phone, raw_phone='5145550124')
        response = self.client.get('/api/qualification/results/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['campaign'], isolated.pk)
