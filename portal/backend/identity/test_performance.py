from django.contrib.auth import get_user_model
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIClient

from packages.request_timing import RequestTimingMiddleware
from .models import Membership, PerformanceSample


@override_settings(DEBUG=True, MFA_ENABLED=False)
class PerformanceTests(TestCase):
    def test_samples_are_scoped_and_shown_only_in_supervision(self):
        setter = get_user_model().objects.create_user('setter')
        Membership.objects.create(user=setter, workspace='assurance', role='setter')
        client = APIClient()
        client.force_login(setter)
        sample = dict(
            area='assurance',
            operation='booking',
            elapsed_ms=100,
            server_ms=20,
            sql_ms=5,
            failed=False,
        )
        url = '/api/portal/performance/'
        self.assertEqual(
            client.post(url, [{**sample, 'area': 'isolation'}], format='json').status_code, 403
        )
        rows = [sample, {**sample, 'elapsed_ms': 500}, {**sample, 'failed': True}]
        self.assertEqual(client.post(url, rows, format='json').status_code, 204)
        self.assertEqual(PerformanceSample.objects.count(), 3)
        overview = '/api/portal/platform-overview/'
        self.assertEqual(client.get(overview).status_code, 403)
        client.force_login(get_user_model().objects.create_user('operator', is_superuser=True))
        report = client.get(overview).data['performance'][0]
        self.assertEqual(
            (report['total'], report['errors'], report['median_ms'], report['p95_ms']),
            (3, 1, 300, 500),
        )

    def test_server_timing_uses_durations_without_sql_content(self):
        def view(request):
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            return HttpResponse('ok')

        middleware = RequestTimingMiddleware(view)
        request = RequestFactory().get('/', HTTP_X_ORVIA_TIMING='1')
        self.assertRegex(middleware(request)['Server-Timing'], r'^app;dur=[\d.]+, db;dur=[\d.]+$')
        self.assertNotIn('Server-Timing', middleware(RequestFactory().get('/')))
