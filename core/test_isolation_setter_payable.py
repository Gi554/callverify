from datetime import datetime, timedelta, timezone as utc
from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase, override_settings
from . import test_isolation_client as fixtures
from .models import IsolationVisit, IsolationVisitResult
from .isolation_compensation import setter_payable


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class SetterPayableTests(TestCase):
    setUp = fixtures.IsolationClientTests.setUp
    auth = fixtures.IsolationClientTests.auth

    def add_visit(
        self, start, closed=False, performed=True, process=None, setter=21, outcome='completed'
    ):
        row = IsolationVisit.objects.create(
            prospect=self.prospect,
            request_id=uuid4(),
            fingerprint='payable',
            client_id=72,
            client_name='Client',
            setter_id=setter,
            setter_name='Setter',
            booked_by_id=setter,
            starts_at=start,
            ends_at=start + timedelta(minutes=30),
            timezone='America/Toronto',
            **({'process_id': process} if process else {}),
        )
        IsolationVisitResult.objects.create(
            visit=row, performed=performed, closed=closed, outcome=outcome, note=''
        )
        return row

    def test_quebec_week_counts_one_presence_per_process_and_no_sale_is_payable(self):
        now = datetime(2026, 11, 2, 4, tzinfo=utc.utc)  # Still Sunday in Quebec.
        old = self.add_visit(datetime(2026, 10, 25, 20, tzinfo=utc.utc))
        self.add_visit(
            datetime(2026, 11, 1, 20, tzinfo=utc.utc), closed=True, process=old.process_id
        )
        held = self.add_visit(datetime(2026, 11, 1, 21, tzinfo=utc.utc), closed=False)
        self.add_visit(datetime(2026, 11, 1, 22, tzinfo=utc.utc), process=held.process_id)
        self.add_visit(datetime(2026, 11, 1, 20, tzinfo=utc.utc), closed=True)
        self.add_visit(datetime(2026, 11, 1, 20, tzinfo=utc.utc), closed=None)
        self.add_visit(
            datetime(2026, 11, 1, 20, tzinfo=utc.utc), performed=False, outcome='not_performed'
        )
        self.add_visit(
            datetime(2026, 11, 1, 20, tzinfo=utc.utc), performed=False, outcome='unqualified'
        )
        self.add_visit(datetime(2026, 11, 1, 20, tzinfo=utc.utc), setter=22)
        with patch('django.utils.timezone.now', return_value=now):
            data = setter_payable(21)
            self.assertEqual(data['from'], '2026-10-26')
            self.assertEqual(data['to'], '2026-11-01')
            self.assertEqual(data['payable'], 3)
            self.assertEqual(data['presented_not_closed'], 1)
            self.assertEqual(data['presented_closed'], 1)
            self.assertEqual(data['sale_unknown'], 1)
            self.auth(21, 'setter')
            self.assertEqual(
                self.client.get('/api/workspace-dashboard/').data['weekly_payable'], data
            )
            stats = self.client.get('/api/workspace-statistics/?week_of=2026-11-01').data
            self.assertEqual(stats['payable'], data)
            self.assertEqual(
                set(data),
                {
                    'from',
                    'to',
                    'timezone',
                    'payable',
                    'presented_closed',
                    'presented_not_closed',
                    'sale_unknown',
                },
            )
            self.auth(22, 'setter')
            self.assertEqual(
                self.client.get('/api/workspace-dashboard/').data['weekly_payable']['payable'], 0
            )

    def test_correction_recomputes_credit_without_duplicate_or_automatic_validation(self):
        first = self.add_visit(self.visit_start(), closed=False)
        later = self.add_visit(
            first.starts_at + timedelta(minutes=10), closed=True, process=first.process_id
        )
        data = setter_payable(
            21,
            {'from': first.starts_at.date().isoformat(), 'to': first.starts_at.date().isoformat()},
        )
        self.assertEqual(data['payable'], 1)
        self.assertEqual(data['presented_not_closed'], 1)
        IsolationVisitResult.objects.filter(visit=first).update(
            performed=False, outcome='unqualified'
        )
        data = setter_payable(
            21,
            {'from': first.starts_at.date().isoformat(), 'to': first.starts_at.date().isoformat()},
        )
        self.assertEqual(data['payable'], 1)
        self.assertEqual(data['presented_closed'], 1)
        IsolationVisit.objects.filter(pk=later.pk).update(status='cancelled')
        self.assertEqual(
            setter_payable(
                21,
                {
                    'from': first.starts_at.date().isoformat(),
                    'to': first.starts_at.date().isoformat(),
                },
            )['payable'],
            0,
        )

    def visit_start(self):
        from django.utils import timezone

        return (timezone.now() - timedelta(days=1)).replace(
            hour=18, minute=0, second=0, microsecond=0
        )
