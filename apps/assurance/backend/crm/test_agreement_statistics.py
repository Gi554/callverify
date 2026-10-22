from datetime import date, datetime, timezone
from unittest.mock import patch
from django.test import TestCase, override_settings
from . import test_agreement_registry as fixtures
from .models import Agreement, AgreementDocument, ContactDocument, BusinessAudit
from uuid import uuid4


@override_settings(DEBUG=True)
class AgreementStatisticsTests(TestCase):
    auth = fixtures.RegistryTests.auth
    create = fixtures.RegistryTests.create

    def setUp(self):
        fixtures.RegistryTests.setUp(self)
        Agreement.objects.all().delete()
        self.clock = patch(
            'apps.assurance.backend.crm.agreement_registry.timezone.now',
            return_value=datetime(2026, 10, 20, tzinfo=timezone.utc),
        )
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.create('DRAFT', ends_on=date(2026, 10, 1))
        self.create('ARCHIVE', kind='contract', status='archived')
        for ref, end in [
            ('PAST', date(2026, 10, 19)),
            ('TODAY', date(2026, 10, 20)),
            ('BOUND', date(2026, 11, 19)),
            ('LATER', date(2026, 11, 20)),
            ('NONE', None),
        ]:
            self.create(ref, status='tracking', ends_on=end)

    def stats(self, query=None):
        response = self.client.get(self.url, query or {})
        self.assertEqual(response.status_code, 200)
        return response.data['statistics']

    def test_exhaustive_exclusive_categories_and_utc_boundaries(self):
        result = self.stats()
        self.assertEqual(result['total'], 7)
        self.assertEqual(result['by_kind'], {'mandate': 6, 'contract': 1})
        self.assertEqual(result['by_status'], {'draft': 1, 'tracking': 5, 'archived': 1})
        self.assertEqual(
            result['by_deadline'],
            {'overdue': 1, 'upcoming': 2, 'later': 1, 'undated': 1, 'not_tracked': 2},
        )
        for key in ('by_kind', 'by_status', 'by_deadline'):
            self.assertEqual(sum(result[key].values()), result['total'])
        self.assertEqual(result['as_of'], date(2026, 10, 20))
        self.assertEqual(result['timezone'], 'UTC')
        self.assertFalse(BusinessAudit.objects.exists())

    def test_all_filters_including_deadline_and_horizon(self):
        result = self.stats(
            {'kind': 'mandate', 'status': 'tracking', 'deadline': 'upcoming', 'horizon_days': '7'}
        )
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['by_deadline']['upcoming'], 1)
        self.assertEqual(result['horizon_days'], 7)
        self.assertEqual(
            self.stats({'search': 'BOUND', 'ends_from': '2026-11-19', 'ends_to': '2026-11-19'})[
                'total'
            ],
            1,
        )
        self.assertEqual(self.stats({'status': 'archived'})['by_deadline']['not_tracked'], 1)

    def test_empty_results_zeroes_no_personal_details(self):
        result = self.stats({'search': 'missing'})
        self.assertEqual(result['total'], 0)
        for key in ('by_kind', 'by_status', 'by_deadline'):
            self.assertTrue(all(n == 0 for n in result[key].values()))
        for text in ('Alice', 'PRIVATE', 'reference', 'contact'):
            self.assertNotIn(text, str(result))

    def test_all_pages_without_document_join_multiplication(self):
        agreement = Agreement.objects.get(reference='TODAY')
        for n in range(3):
            doc = ContactDocument.objects.create(
                contact=self.contact,
                request_id=uuid4(),
                author_id=21,
                channel='internal',
                filename='private.pdf',
                content_type='application/pdf',
                size=1,
                content=b'x',
                sha256='hash',
            )
            AgreementDocument.objects.create(agreement=agreement, document=doc)
        for n in range(30):
            self.create(f'EXTRA-{n}')
        first = self.stats()
        second = self.stats({'page': 2})
        self.assertEqual(first, second)
        self.assertEqual(first['total'], 37)
        self.assertEqual(first['by_deadline']['upcoming'], 2)

    def test_existing_access_controls_and_validation_apply(self):
        for role in ('setter', 'advisor'):
            self.auth(21, role)
            self.assertEqual(self.client.get(self.url).status_code, 403)
        self.auth(99, 'administrator', 'isolation')
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.auth(99, 'administrator')
        self.assertEqual(self.client.get(self.url, {'horizon_days': '1'}).status_code, 400)
        self.assertEqual(
            self.client.get(self.url + '?status=draft&status=tracking').status_code, 400
        )
