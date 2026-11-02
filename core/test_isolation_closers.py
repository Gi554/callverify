"""Retirement of closer access must preserve historical visits and client follow-up."""

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .test_isolation_client import client_fixture
from .models import IsolationVisit, IsolationVisitResult


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class RetiredCloserTests(TestCase):
    def setUp(self):
        self.prospect, self.visit = client_fixture()
        IsolationVisit.objects.filter(pk=self.visit.pk).update(
            closer_id=77, closer_name='Ancien représentant'
        )
        self.client = APIClient()

    def auth(self, user_id, role):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(user_id, 'isolation', role))

    def test_retired_routes_and_tickets_cannot_be_used(self):
        self.auth(77, 'closer')
        for path in ('/api/visits/', '/api/workspace-statistics/', '/api/client-prospects/'):
            self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.get('/api/closer-visits/').status_code, 404)
        self.auth(72, 'client')
        self.assertEqual(
            self.client.post(f'/api/visits/{self.visit.pk}/assign-closer/', {}).status_code, 404
        )

    def test_client_keeps_historical_attribution_and_can_report_without_closer(self):
        IsolationVisitResult.objects.create(
            visit=self.visit,
            performed=True,
            closed=False,
            outcome='completed',
            author_closer_id=77,
            note='Historique',
        )
        self.auth(72, 'client')
        url = f'/api/visits/{self.visit.pk}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['closer'], {'id': 77, 'name': 'Ancien représentant'})
        result = self.client.post(
            url + 'result/',
            {
                'revision': 0,
                'performed': True,
                'closed': True,
                'outcome': 'closed',
                'note': 'Vente confirmée par le client',
                'reason': 'Suivi du client',
            },
            format='json',
        )
        self.assertEqual(result.status_code, 201, result.data)
        self.assertEqual(IsolationVisit.objects.get(pk=self.visit.pk).closer_id, 77)
        self.assertTrue(IsolationVisitResult.objects.get(visit=self.visit).closed)
