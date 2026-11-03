"""Shared test fixture: one scheduled appointment, an administrator client and its auth helper."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import Appointment
from .test_notifications import fixture


class AppointmentFixture:
    def setUp(self):
        self.source = fixture()
        self.appointment = self.source.appointment
        self.client = APIClient()
        self.auth()
        zone = ZoneInfo('America/Toronto')
        self.start = datetime(2026, 10, 26, 10, tzinfo=zone)
        Appointment.objects.update(
            starts_at=self.start, ends_at=self.start + timedelta(hours=1), calendar='external_link'
        )

    def auth(self, role='administrator', pk=99):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, 'assurance', role))
