from copy import copy
from uuid import uuid4
from io import BytesIO
from django.test import TestCase, override_settings
from openpyxl import load_workbook
from .payable_fixtures import AppointmentFixture
from .models import Appointment


@override_settings(DEBUG=True)
class SearchTests(TestCase):
    setUp = AppointmentFixture.setUp
    auth = AppointmentFixture.auth

    def test_same_row_filters_and_export_permissions(self):
        row = Appointment.objects.get(pk=self.appointment.pk)
        other = copy(row)
        other.pk = None
        other.request_id = uuid4()
        other.setter_id = 22
        other.advisor_id = 32
        other.save()
        url = '/api/assurance/admin-search/'
        self.assertEqual(self.client.get(url, {'setter_id': 21, 'target_id': 32}).data['count'], 0)
        query = {'setter_id': 21, 'target_id': 31, 'appointment_id': row.pk}
        response = self.client.get(url, query)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 1)
        excel = self.client.get(url, {**query, 'file': 'xlsx'})
        self.assertEqual(excel.status_code, 200)
        self.assertEqual(load_workbook(BytesIO(excel.content)).active.max_row, 2)
        self.assertEqual(self.client.get(url, {**query, 'file': 'pdf'}).status_code, 200)
        self.auth('setter', 21)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.auth('advisor', 31)
        self.assertEqual(self.client.get(url).status_code, 403)
