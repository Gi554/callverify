from datetime import date, datetime, timedelta, timezone as dt_timezone
from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import Agreement, Contact, ContactDocument, AgreementDocument, BusinessAudit


@override_settings(DEBUG=True)
class DeadlineTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.auth(99, 'administrator')
        self.url = '/api/assurance/agreement-deadlines/'
        self.registry = '/api/assurance/agreement-registry/'
        self.contact = Contact.objects.create(name='Alice', phone='PRIVATE', created_by_id=21)
        self.today = date(2026, 10, 20)
        self.clock = patch(
            'apps.assurance.backend.crm.agreement_registry.timezone.now',
            return_value=datetime(2026, 10, 20, 12, tzinfo=dt_timezone.utc),
        )
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.rows = [
            self.create(-1),
            self.create(0),
            self.create(30),
            self.create(31),
            self.create(None),
            self.create(-1, status='archived'),
            self.create(1, status='draft'),
        ]

    def auth(self, pk, role, workspace='assurance'):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, workspace, role))

    def create(self, offset, status='tracking', **changes):
        return Agreement.objects.create(
            contact=self.contact,
            request_id=uuid4(),
            fingerprint='private',
            kind='mandate',
            reference=str(uuid4()),
            status=status,
            ends_on=self.today + timedelta(days=offset) if offset is not None else None,
            **changes,
        )

    def test_summary_today_inclusive_horizon_and_exclusion_drafts_archives_undated(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                'overdue': 1,
                'upcoming': 2,
                'undated': 1,
                'as_of': self.today,
                'timezone': 'UTC',
                'horizon_days': 30,
            },
        )
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(self.client.get(self.url, {'horizon_days': '7'}).data['upcoming'], 1)
        self.assertEqual(self.client.get(self.url, {'horizon_days': '90'}).data['upcoming'], 3)

    def test_opening_alert_does_not_clear_or_change_state_or_audit(self):
        before = list(Agreement.objects.values('id', 'status', 'revision', 'ends_on'))
        for _ in range(2):
            self.assertEqual(
                self.client.get(self.registry, {'deadline': 'overdue'}).data['count'], 1
            )
        self.assertEqual(
            before, list(Agreement.objects.values('id', 'status', 'revision', 'ends_on'))
        )
        self.assertFalse(BusinessAudit.objects.exists())

    def test_deadline_filters_badges_days_and_counts_combine_with_other_filters(self):
        response = self.client.get(self.registry, {'deadline': 'upcoming'})
        self.assertEqual(response.data['count'], 2)
        self.assertEqual([row['days_to_end'] for row in response.data['results']], [0, 30])
        self.assertTrue(
            all(row['deadline_state'] == 'upcoming' for row in response.data['results'])
        )
        response = self.client.get(self.registry, {'deadline': 'overdue'})
        self.assertEqual(response.data['results'][0]['days_to_end'], -1)
        response = self.client.get(self.registry, {'deadline': 'upcoming', 'status': 'archived'})
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['deadlines']['upcoming'], 0)
        response = self.client.get(self.registry, {'search': 'no match'})
        self.assertEqual(response.data['deadlines']['undated'], 0)
        states = {
            row['id']: row['deadline_state']
            for row in self.client.get(self.registry).data['results']
        }
        self.assertEqual(states[self.rows[4].pk], 'undated')
        self.assertEqual(states[self.rows[5].pk], 'not_tracked')
        self.assertEqual(states[self.rows[3].pk], 'later')

    def test_counts_not_inflated_by_linked_documents(self):
        for _ in range(3):
            doc = ContactDocument.objects.create(
                contact=self.contact,
                request_id=uuid4(),
                author_id=21,
                channel='internal',
                filename='private.pdf',
                content_type='application/pdf',
                size=1,
                content=b'x',
                sha256='x',
            )
            AgreementDocument.objects.create(agreement=self.rows[0], document=doc)
        response = self.client.get(self.registry)
        self.assertEqual(response.data['deadlines']['overdue'], 1)

    def test_permissions_spaces_and_strict_filters(self):
        for query in (
            {'horizon_days': '0'},
            {'horizon_days': '365'},
            {'as_of': '2020-01-01'},
            {'status': 'tracking'},
        ):
            self.assertEqual(self.client.get(self.url, query).status_code, 400)
        self.assertEqual(
            self.client.get(self.url + '?horizon_days=7&horizon_days=30').status_code, 400
        )
        self.assertEqual(self.client.get(self.registry, {'deadline': 'unknown'}).status_code, 400)
        for pk, role in ((21, 'setter'), (31, 'advisor')):
            self.auth(pk, role)
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(
                self.client.get(self.registry, {'deadline': 'upcoming'}).status_code, 403
            )
        self.auth(99, 'administrator', 'isolation')
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_deadline_recalculated_after_date_status_and_utc_day_change(self):
        Agreement.objects.filter(pk=self.rows[0].pk).update(status='archived')
        self.assertEqual(self.client.get(self.url).data['overdue'], 0)
        Agreement.objects.filter(pk=self.rows[3].pk).update(ends_on=self.today)
        self.assertEqual(self.client.get(self.url).data['upcoming'], 3)
        with patch(
            'apps.assurance.backend.crm.agreement_registry.timezone.now',
            return_value=datetime(2026, 10, 21, 0, 1, tzinfo=dt_timezone.utc),
        ):
            result = self.client.get(self.url).data
            self.assertEqual(result['as_of'], date(2026, 10, 21))
            self.assertEqual(result['overdue'], 2)

    def test_summary_no_private_details_and_post_refused(self):
        response = self.client.get(self.url)
        self.assertNotIn('PRIVATE', str(response.data))
        self.assertNotIn('reference', response.data)
        self.assertNotIn('contact', response.data)
        self.assertEqual(self.client.post(self.url, {}, format='json').status_code, 405)
