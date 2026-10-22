from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .test_isolation_client import client_fixture
from .models import IsolationVisitResult, IsolationVisitSupplement, Prospect, AuditEvent


def fixture():
    prospect, visit = client_fixture()
    IsolationVisitResult.objects.create(
        visit=visit, author_client_id=72, performed=True, outcome='completed', note='Initial'
    )
    return prospect, visit


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class SupplementTests(TestCase):
    def setUp(self):
        self.prospect, self.visit = fixture()
        self.client = APIClient()
        self.auth(72, 'client')
        self.request_id = uuid4()
        self.url = f'/api/visits/{self.visit.pk}/supplements/'

    def auth(self, pk, role):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, 'isolation', role))

    def post(self, **changes):
        return self.client.post(
            self.url,
            {'request_id': str(self.request_id), 'note': 'Précision ultérieure', **changes},
            format='json',
        )

    def test_append_only_retry_preserves_original_result_and_statistics(self):
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.post(note='Autre').status_code, 409)
        self.assertEqual(
            self.post(request_id=str(uuid4()), note='Deuxième précision').status_code, 201
        )
        self.assertEqual(IsolationVisitSupplement.objects.count(), 2)
        self.assertEqual(IsolationVisitResult.objects.get().note, 'Initial')
        self.assertEqual(self.client.get('/api/client-dashboard/').data['reported'], 1)
        self.assertEqual(self.client.get(self.url).data['count'], 2)
        self.assertEqual(self.client.delete(self.url).status_code, 405)
        self.assertEqual(
            AuditEvent.objects.filter(action='isolation.visit.supplement_added').count(), 2
        )

    def test_only_client_of_visit_writes_and_current_staff_read(self):
        self.post()
        self.auth(73, 'client')
        self.assertEqual(self.post().status_code, 404)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        for pk, role in ((21, 'setter'), (91, 'administrator')):
            self.auth(pk, role)
            self.assertEqual(self.post().status_code, 403)
            self.assertEqual(self.client.get(self.url).data['count'], 1)
        Prospect.objects.filter(pk=self.prospect.pk).update(assigned_setter_id=22)
        self.auth(21, 'setter')
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.auth(22, 'setter')
        self.assertEqual(self.client.get(self.url).data['count'], 1)

    def test_initial_result_required_and_payload_validated(self):
        self.assertEqual(self.post(note=' ').status_code, 400)
        self.assertEqual(self.post(performed=False).status_code, 400)
        IsolationVisitResult.objects.all().delete()
        self.assertEqual(self.post().status_code, 409)
        self.assertEqual(IsolationVisitSupplement.objects.count(), 0)

    def test_audit_failure_rolls_back_supplement(self):
        with patch(
            'core.isolation_client.AuditEvent.objects.create', side_effect=RuntimeError('audit')
        ):
            with self.assertRaises(RuntimeError):
                self.post()
        self.assertEqual(IsolationVisitSupplement.objects.count(), 0)

    def test_pagination_and_uuid_reuse(self):
        for index in range(27):
            self.post(request_id=str(uuid4()), note=str(index))
        self.assertEqual(len(self.client.get(self.url).data['results']), 25)
        self.assertEqual(len(self.client.get(self.url, {'page': 2}).data['results']), 2)
        first = IsolationVisitSupplement.objects.first()
        self.assertEqual(
            self.post(request_id=str(first.request_id), note='Different').status_code, 409
        )


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class SupplementConcurrencyTests(TransactionTestCase):
    def test_identical_parallel_requests_create_one_supplement(self):
        from django.db import connection, connections
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        if connection.vendor != 'postgresql':
            self.skipTest('Concurrence vérifiée dans CI PostgreSQL')
        _, visit = fixture()
        barrier = Barrier(2)
        request_id = str(uuid4())

        def submit(_):
            try:
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(72, 'isolation', 'client'))
                barrier.wait(timeout=10)
                return client.post(
                    f'/api/visits/{visit.pk}/supplements/',
                    {'request_id': request_id, 'note': 'Précision'},
                    format='json',
                ).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, [0, 1]))
        self.assertEqual(sorted(results), [200, 201])
        self.assertEqual(IsolationVisitSupplement.objects.count(), 1)
