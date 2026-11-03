from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo
from django.test import TestCase, override_settings
from .isolation_payable import setter_payable
from .models import IsolationVisit, IsolationVisitResult
from .visit_fixtures import VisitFixture

ZONE = ZoneInfo('America/Toronto')
WEEK = {'from': '2026-11-02', 'to': '2026-11-08'}


def confirmed(day, hour=12):
    """The moment attendance is confirmed, in November 2026 (Monday 2 is the first day)."""
    return patch(
        'packages.payable_ledger.current_time',
        return_value=datetime(2026, 11, day, hour, tzinfo=ZONE),
    )


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class SetterPayableTests(TestCase):
    setUp = VisitFixture.setUp
    auth = VisitFixture.auth

    def visit_of(self, process=None, setter=21):
        start = datetime(2026, 10, 26, 10, tzinfo=ZONE)
        return IsolationVisit.objects.create(
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

    def confirm(self, visit, day=4, closed=False, performed=True, outcome='completed'):
        with confirmed(day):
            IsolationVisitResult.objects.update_or_create(
                visit=visit,
                defaults={
                    'performed': performed,
                    'closed': closed,
                    'outcome': outcome,
                    'note': '',
                },
            )
        return visit

    def test_week_of_confirmation_counts_one_presence_per_process_and_other_setters_apart(self):
        first = self.confirm(self.visit_of())
        # A relaunch of the same process is a new occurrence, never a second payable.
        self.confirm(self.visit_of(process=first.process_id), closed=True)
        self.confirm(self.visit_of(), closed=True)
        self.confirm(self.visit_of(), closed=None)
        self.confirm(self.visit_of(), performed=False, outcome='not_performed')
        self.confirm(self.visit_of(), performed=False, outcome='unqualified')
        self.confirm(self.visit_of(setter=22))
        data = setter_payable(21, WEEK)
        self.assertEqual(data['from'], '2026-11-02')
        self.assertEqual(data['to'], '2026-11-08')
        self.assertEqual(data['payable'], 3)
        self.assertEqual(data['presented_closed'], 1)
        self.assertEqual(data['presented_not_closed'], 2)
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
        self.assertEqual(setter_payable(22, WEEK)['payable'], 1)

    def test_a_later_sale_or_cancellation_never_changes_a_counted_week(self):
        visit = self.confirm(self.visit_of(), day=4, closed=False)
        self.confirm(visit, day=11, closed=True)
        IsolationVisit.objects.filter(pk=visit.pk).update(status='cancelled')
        week = setter_payable(21, WEEK)
        self.assertEqual((week['payable'], week['presented_not_closed']), (1, 1))
        self.assertEqual(
            setter_payable(21, {'from': '2026-11-09', 'to': '2026-11-15'})['payable'], 0
        )

    def test_dashboard_and_statistics_show_the_same_figures_to_the_setter_only(self):
        self.confirm(self.visit_of(), closed=True)
        now = datetime(2026, 11, 5, 12, tzinfo=ZONE)
        with patch('django.utils.timezone.now', return_value=now):
            data = setter_payable(21)
            self.auth(21, 'setter')
            self.assertEqual(
                self.client.get('/api/workspace-dashboard/').data['weekly_payable'], data
            )
            stats = self.client.get('/api/workspace-statistics/?week_of=2026-11-04').data
            self.assertEqual(stats['payable']['payable'], 1)
            self.auth(22, 'setter')
            self.assertEqual(
                self.client.get('/api/workspace-dashboard/').data['weekly_payable']['payable'], 0
            )
