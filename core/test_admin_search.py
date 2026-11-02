from copy import copy
from uuid import uuid4
from io import BytesIO
from django.test import TestCase, override_settings
from openpyxl import load_workbook
from . import test_isolation_payroll as fixtures
from .models import IsolationVisit, Prospect, AuditEvent


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class SearchTests(TestCase):
    setUp = fixtures.PayrollTests.setUp
    auth = fixtures.PayrollTests.auth

    def test_combined_filters_must_match_the_same_appointment_and_exports_match(self):
        self.auth(90, 'administrator')
        current = IsolationVisit.objects.get(pk=self.visit.pk)
        second = copy(current)
        second.pk = None
        second.request_id = uuid4()
        second.setter_id = 22
        second.client_id = 73
        second.save()
        url = '/api/admin-search/'
        self.assertEqual(self.client.get(url, {'setter_id': 21, 'target_id': 73}).data['count'], 0)
        query = {'setter_id': 21, 'target_id': 72, 'appointment_id': current.pk}
        result = self.client.get(url, query)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['count'], 1)
        self.assertEqual(result.data['results'][0]['appointment_id'], current.pk)
        response = self.client.get(url, {**query, 'file': 'xlsx'})
        self.assertEqual(response.status_code, 200)
        book = load_workbook(BytesIO(response.content))
        self.assertEqual(book.active.max_row, 2)
        self.assertEqual(book.active['F2'].value, current.pk)
        self.assertEqual(
            self.client.get(url, {**query, 'file': 'pdf'})['Content-Type'], 'application/pdf'
        )
        audit = AuditEvent.objects.filter(action='isolation.admin_search.exported').first()
        self.assertNotIn('phone', audit.metadata['filters'])

    def test_phone_formatting_appointments_optional_and_permissions(self):
        self.auth(90, 'administrator')
        Prospect.objects.filter(pk=self.visit.prospect_id).update(raw_phone='+1 (514) 555-1234')
        result = self.client.get('/api/admin-search/', {'phone': '5145551234'})
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['count'], 1)
        self.assertEqual(
            self.client.get('/api/admin-search/', {'from_date': '2026-11-01'}).status_code, 400
        )
        for role in ('setter', 'client', 'closer'):
            self.auth(21, role)
            self.assertEqual(self.client.get('/api/admin-search/').status_code, 403)
