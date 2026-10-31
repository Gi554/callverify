from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from django.db import connection, close_old_connections
from django.test import TransactionTestCase
from copy import copy
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .test_notifications import fixture
from .models import Appointment, AppointmentReport, SetterRate, BusinessAudit


@override_settings(DEBUG=True)
class CompensationTests(TestCase):
    def setUp(self):
        self.source = fixture()
        self.appointment = self.source.appointment
        self.client = APIClient()
        self.auth()
        self.url = '/api/assurance/compensation/'
        zone = ZoneInfo('America/Toronto')
        self.start = datetime(2026, 10, 26, 10, tzinfo=zone)
        Appointment.objects.update(
            starts_at=self.start, ends_at=self.start + timedelta(hours=1), calendar='external_link'
        )
        self.query = '?from=2026-10-26&to=2026-11-01'

    def auth(self, role='administrator', pk=99):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, 'assurance', role))

    def rate(self, amount='12.50', revision=0):
        return self.client.post(
            self.url + '21/rate/',
            {'amount_cad': amount, 'revision': revision, 'reason': 'Tarif convenu'},
            format='json',
        )

    def summary(self):
        return self.client.get(self.url + self.query)

    def value(self, revision=1):
        return self.client.post(
            self.url + '21/value/',
            {
                'starts_on': '2026-10-26',
                'ends_on': '2026-11-01',
                'rate_revision': revision,
                'reason': 'Valorisation contrôlée',
            },
            format='json',
        )

    def report(self, **values):
        return self.source.report(performed=True, note='', **values)

    def clone(self):
        row = copy(Appointment.objects.get(pk=self.appointment.pk))
        row.pk = None
        row.request_id = uuid4()
        row.save()
        return row

    def test_rate_is_admin_only_validated_revisioned_and_audited(self):
        self.assertEqual(self.rate().status_code, 200)
        self.assertEqual(self.rate(revision=0).status_code, 409)
        self.assertEqual(self.rate('-1', 1).status_code, 400)
        self.assertEqual(self.rate('1.001', 1).status_code, 400)
        self.assertEqual(
            self.client.post(
                self.url + '999/rate/',
                {'amount_cad': '1', 'revision': 0, 'reason': 'x'},
                format='json',
            ).status_code,
            400,
        )
        self.assertEqual(SetterRate.objects.get().amount, Decimal('12.50'))
        self.assertEqual(
            BusinessAudit.objects.get(action='compensation.rate_changed').metadata['after'], '12.50'
        )
        for role in ('setter', 'advisor'):
            self.auth(role)
            self.assertEqual(self.summary().status_code, 403)
            self.assertEqual(self.rate(revision=1).status_code, 403)
            self.assertEqual(self.value().status_code, 403)
            self.assertEqual(
                self.client.get(self.url + '21/details/' + self.query).status_code, 403
            )

    def test_only_presence_earns_money_at_captured_rate(self):
        self.rate('0.10')
        self.assertEqual(self.report().status_code, 201)
        for endpoint in (self.source.url, self.source.url.replace('/report/', '/advisor-result/')):
            self.assertNotIn('unit_rate_cad', str(self.source.client.get(endpoint).data))
        for _ in range(2):
            row = self.clone()
            AppointmentReport.objects.create(
                appointment=row, performed=True, outcome='performed', author_id=31
            )
        absent = self.clone()
        AppointmentReport.objects.create(
            appointment=absent, performed=False, outcome='absent', author_id=31
        )
        self.clone()  # unreported
        self.assertEqual(self.value().data['valued'], 2)
        self.assertEqual(self.value().data['valued'], 0)
        self.rate('99.00', 1)
        totals = self.summary().data['totals']
        self.assertEqual(totals['booked'], 5)
        self.assertEqual(totals['transmitted'], 5)
        self.assertEqual(totals['payable'], 3)
        self.assertEqual(totals['absent'], 1)
        self.assertEqual(totals['amount_cad'], '0.30')
        Appointment.objects.filter(pk=absent.pk).update(status='cancelled')
        Appointment.objects.filter(pk=self.appointment.pk).update(status='cancelled')
        totals = self.summary().data['totals']
        self.assertEqual(totals['payable'], 2)
        self.assertEqual(totals['absent'], 0)
        self.assertEqual(totals['amount_cad'], '0.20')

    def test_missing_tariff_is_explicit_and_zero_is_a_real_price(self):
        self.assertEqual(self.report().status_code, 201)
        self.assertEqual(self.summary().data['totals']['unpriced'], 1)
        self.assertEqual(self.value().status_code, 400)
        self.rate('0.00')
        self.assertEqual(self.value().data['valued'], 1)
        self.assertEqual(self.summary().data['totals']['unpriced'], 0)
        self.assertEqual(self.rate('10.00', 1).status_code, 200)
        self.assertEqual(self.value(2).data['valued'], 0)
        self.assertEqual(AppointmentReport.objects.get().unit_rate_cad, Decimal('0.00'))

    def test_positive_correction_captures_once_and_negative_removes_accrual(self):
        self.rate('18.25')
        url = self.source.url.replace('/report/', '/advisor-result/')
        adviser = self.source.client
        self.assertEqual(
            adviser.post(url, {'revision': 0, 'performed': False}, format='json').status_code, 200
        )
        self.assertIsNone(AppointmentReport.objects.get().unit_rate_cad)
        self.assertEqual(
            adviser.post(
                url,
                {'revision': 1, 'performed': True, 'reason': 'Présence vérifiée'},
                format='json',
            ).status_code,
            200,
        )
        self.assertEqual(AppointmentReport.objects.get().unit_rate_cad, Decimal('18.25'))
        self.rate('22.00', 1)
        self.assertEqual(
            adviser.post(
                url, {'revision': 2, 'performed': False, 'reason': 'Correction'}, format='json'
            ).status_code,
            200,
        )
        self.assertEqual(self.summary().data['totals']['amount_cad'], '0.00')
        self.assertEqual(AppointmentReport.objects.get().unit_rate_cad, Decimal('18.25'))
        self.assertEqual(
            adviser.post(
                url,
                {'revision': 3, 'performed': True, 'reason': 'Présence définitive'},
                format='json',
            ).status_code,
            200,
        )
        self.assertEqual(self.summary().data['totals']['amount_cad'], '18.25')
        detail = self.client.get(self.url + '21/details/' + self.query).data['results'][0]
        self.assertEqual(detail['amount_cad'], '18.25')
        self.assertNotIn('note', detail)

    def test_quebec_week_bounds_include_the_dst_sunday(self):
        zone = ZoneInfo('America/Toronto')
        now = datetime(2026, 11, 1, 23, 30, tzinfo=zone)
        Appointment.objects.update(starts_at=now, ends_at=now + timedelta(minutes=20))
        with patch('django.utils.timezone.now', return_value=now):
            response = self.client.get(self.url)
        self.assertEqual(str(response.data['from']), '2026-10-26')
        self.assertEqual(str(response.data['to']), '2026-11-01')
        self.assertEqual(response.data['totals']['booked'], 1)
        Appointment.objects.update(
            starts_at=now + timedelta(hours=1), ends_at=now + timedelta(hours=2)
        )
        self.assertEqual(self.summary().data['totals']['booked'], 0)
        for query in (
            '?from=oops',
            '?from=2026-11-01&to=2026-10-01',
            '?from=2020-01-01&to=2026-11-01',
            '?to=9999-12-31',
        ):
            self.assertEqual(self.client.get(self.url + query).status_code, 400)

    def test_valuation_conflict_and_audit_failure_do_not_change_prices(self):
        self.report()
        self.rate()
        self.assertEqual(self.value(0).status_code, 409)
        with patch(
            'apps.assurance.backend.crm.compensation.BusinessAudit.objects.create',
            side_effect=RuntimeError('audit'),
        ):
            with self.assertRaises(RuntimeError):
                self.value()
        self.assertIsNone(AppointmentReport.objects.get().unit_rate_cad)


@skipUnless(connection.vendor == 'postgresql', 'Concurrent accruals require PostgreSQL')
@override_settings(DEBUG=True)
class CompensationConcurrencyTests(TransactionTestCase):
    def test_two_valuations_preserve_one_captured_price(self):
        source = fixture()
        source.report(performed=True, note='')
        SetterRate.objects.create(setter_id=21, amount=Decimal('12.50'), revision=1)
        stamp = (
            source.appointment.starts_at.astimezone(ZoneInfo('America/Toronto')).date().isoformat()
        )

        def attempt(_):
            close_old_connections()
            try:
                client = APIClient()
                client.credentials(
                    HTTP_AUTHORIZATION='Bearer ' + issue(99, 'assurance', 'administrator')
                )
                return client.post(
                    '/api/assurance/compensation/21/value/',
                    {
                        'starts_on': stamp,
                        'ends_on': stamp,
                        'rate_revision': 1,
                        'reason': 'Contrôle',
                    },
                    format='json',
                )
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual([r.status_code for r in results], [200, 200])
        self.assertEqual(sum(r.data['valued'] for r in results), 1)
        self.assertEqual(AppointmentReport.objects.get().unit_rate_cad, Decimal('12.50'))
