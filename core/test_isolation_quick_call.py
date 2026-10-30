import uuid
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import AdminUser, AuditEvent, Campaign, PhoneNumber, Prospect, Suppression


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class IsolationQuickCallTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = AdminUser.objects.create_user('legacy-admin', is_staff=True)
        self.client = APIClient()
        self.url = '/api/work-queue/quick-call/'

    def auth(self, pk, role):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, 'isolation', role))

    def dial(self, phone):
        return self.client.post(self.url, {'phone': phone}, format='json')

    def test_unknown_number_creates_a_callable_prospect_owned_by_the_caller(self):
        self.auth(21, 'setter')
        response = self.dial('(416) 555-0123')
        self.assertEqual((response.status_code, response.data['created']), (201, True))
        row = Prospect.objects.get(pk=response.data['id'])
        self.assertEqual(
            (row.compliance, row.assigned_setter_id, row.phone.e164, row.campaign.name),
            ('allowed', 21, '+14165550123', 'Appels directs'),
        )
        self.assertTrue(AuditEvent.objects.filter(action='isolation.prospect.quick_call_created'))
        intent = self.client.post(
            f'/api/work-queue/{row.pk}/call-intent/',
            {'revision': row.assignment_revision, 'request_id': str(uuid.uuid4())},
            format='json',
        )
        self.assertEqual(intent.status_code, 200)
        self.assertEqual(self.dial('416 555 0123').data, {'id': row.pk, 'created': False})
        self.assertEqual(Campaign.objects.filter(name='Appels directs').count(), 1)

    def test_known_prospect_is_reused_only_when_visible_and_callable(self):
        campaign = Campaign.objects.create(
            owner=self.owner, portal_workspace='isolation', name='Import', purpose='', source=''
        )
        phone = PhoneNumber.objects.create(e164='+14165550124')
        waiting = Prospect.objects.create(
            campaign=campaign, phone=phone, raw_phone='4165550124', assigned_setter_id=21
        )
        self.auth(21, 'setter')
        self.assertEqual(self.dial('4165550124').status_code, 400)
        Prospect.objects.filter(pk=waiting.pk).update(compliance='allowed')
        self.assertEqual(self.dial('4165550124').data, {'id': waiting.pk, 'created': False})
        self.auth(22, 'setter')
        self.assertEqual(self.dial('4165550124').status_code, 403)
        self.auth(91, 'administrator')
        self.assertEqual(self.dial('4165550124').data['id'], waiting.pk)

    def test_excluded_invalid_and_other_roles_are_refused(self):
        Suppression.objects.create(e164='+14165550125', reason='Demande du client')
        self.auth(21, 'setter')
        self.assertEqual(self.dial('4165550125').status_code, 400)
        self.assertEqual(self.dial('555-0125').status_code, 400)
        self.assertEqual(self.dial('abc').status_code, 400)
        self.assertEqual(
            self.client.post(self.url, {'phone': '4165550126', 'x': 1}, format='json').status_code,
            400,
        )
        self.auth(31, 'client')
        self.assertEqual(self.dial('4165550126').status_code, 403)
        self.assertEqual(Prospect.objects.count(), 0)
