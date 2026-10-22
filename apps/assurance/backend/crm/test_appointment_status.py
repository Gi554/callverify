from datetime import timedelta
from importlib import import_module
from uuid import uuid4
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone

from . import tests as fixtures
from .appointment_status import LABELS, output
from .models import Appointment, AppointmentReport, BusinessAudit, FollowUpTask


@override_settings(DEBUG=True)
class AppointmentStatusTests(TestCase):
    def setUp(self):
        self.fixture = fixtures.ReportTests()
        self.fixture.setUp()
        self.client = self.fixture.client
        self.row = self.fixture.appointment
        self.url = '/api/assurance/appointments/'

    def clone(self, **changes):
        values = {field.attname: getattr(self.row, field.attname)
                  for field in Appointment._meta.fields
                  if not field.primary_key and field.name not in ('created_at', 'request_id')}
        return Appointment.objects.create(**{**values, 'request_id': uuid4(), **changes})

    def test_filters_partition_statuses_and_keep_unknown_separate(self):
        future = timezone.now() + timedelta(days=2)
        rows = {'report_due': self.row,
                'scheduled': self.clone(starts_at=future, ends_at=future+timedelta(hours=1)),
                'rescheduled': self.clone(starts_at=future, ends_at=future+timedelta(hours=1), reschedule_count=2),
                'cancelled': self.clone(status='cancelled')}
        for state in ('performed', 'absent', 'not_performed'):
            rows[state] = self.clone()
            AppointmentReport.objects.create(appointment=rows[state], author_id=31,
                performed=state=='performed', outcome=state, note='Motif explicite')
        for state in LABELS:
            response = self.client.get(self.url, {'business_status': state})
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual([row['id'] for row in response.data['results']], [rows[state].pk])
            self.assertEqual(response.data['results'][0]['business_status'], state)
        self.assertEqual(self.client.get(self.url, {'business_status':'invented'}).status_code, 400)
        self.fixture.auth(32, 'advisor')
        self.assertEqual(self.client.get(self.url, {'business_status':'absent'}).data['count'], 0)

    def test_explicit_absence_retry_and_immutable_outcome(self):
        self.assertEqual(self.fixture.report(outcome='absent').status_code, 201)
        self.assertEqual(self.fixture.report(outcome='absent').status_code, 200)
        self.assertEqual(self.fixture.report(outcome='not_performed').status_code, 409)
        self.assertEqual(FollowUpTask.objects.count(), 1)
        result = self.client.get(self.fixture.url).data
        self.assertEqual(result['outcome_label'], 'Absent')
        self.assertEqual(BusinessAudit.objects.get(action='appointment.reported').metadata['outcome'], 'absent')
        history=self.client.get(f'/api/assurance/contacts/{self.row.contact_id}/interactions/',{'type':'report'})
        self.assertEqual(history.status_code,200,history.data)
        self.assertEqual(history.data['results'][0]['state'],'absent')

    def test_legacy_negative_note_does_not_infer_absence(self):
        self.assertEqual(self.fixture.report().status_code, 201)
        self.assertEqual(self.client.get(self.fixture.url).data['outcome'], 'not_performed')
        response = self.client.get(self.url+str(self.row.pk)+'/')
        self.assertEqual(response.data['business_status'], 'not_performed')

    def test_inconsistent_presence_is_rejected_before_any_write(self):
        for performed, outcome in ((True,'absent'), (True,'not_performed'), (False,'performed')):
            self.assertEqual(self.fixture.report(performed=performed,outcome=outcome).status_code, 400)
        self.assertFalse(AppointmentReport.objects.exists())

    def test_report_supersedes_reschedule_and_due_is_not_absent(self):
        self.row.reschedule_count=2
        self.row.save()
        self.assertEqual(output(self.row)['business_status'], 'report_due')
        self.fixture.report(performed=True,outcome='performed')
        self.row=Appointment.objects.get(pk=self.row.pk)
        self.assertEqual(output(self.row)['business_status'], 'performed')

    def test_statistics_and_exports_separate_absences_other_and_pending(self):
        self.fixture.report(outcome='absent')
        legacy=self.clone()
        AppointmentReport.objects.create(appointment=legacy,author_id=31,performed=False,note='No show')
        self.clone()
        self.fixture.auth(21,'setter')
        params={'from':(timezone.now()-timedelta(days=1)).date().isoformat(),
                'to':(timezone.now()+timedelta(days=1)).date().isoformat()}
        response=self.client.get('/api/assurance/statistics/',params)
        self.assertEqual(response.status_code,200,response.data)
        totals=response.data['totals']
        self.assertEqual((totals['absent'],totals['other_not_performed'],totals['not_performed'],totals['reports_due']),(1,1,2,1))
        for kind in ('csv','xlsx'):
            exported=self.client.get('/api/assurance/statistics/',{**params,'export':kind})
            self.assertEqual(exported.status_code,200)
            if kind=='csv':self.assertIn('Absences',exported.content.decode('utf-8-sig'))

    def test_backfill_uses_only_audit_evidence_and_never_infers_absence(self):
        legacy=AppointmentReport.objects.create(appointment=self.row,author_id=31,performed=False,note='No show')
        untouched=self.clone()
        for _ in range(2):
            BusinessAudit.objects.create(actor_id=21,object_id=self.row.pk,action='appointment.rescheduled')
        BusinessAudit.objects.create(actor_id=21,object_id=untouched.pk,action='appointment.updated')
        migration=import_module('apps.assurance.backend.crm.migrations.0026_appointment_reschedule_count_and_more')
        migration.restore_evidence(apps,SimpleNamespace(connection=connection))
        legacy.refresh_from_db();self.row.refresh_from_db();untouched.refresh_from_db()
        self.assertEqual(legacy.outcome,'not_performed')
        self.assertEqual(self.row.reschedule_count,2)
        self.assertIsNotNone(self.row.rescheduled_at)
        self.assertEqual(untouched.reschedule_count,0)


@override_settings(DEBUG=True)
class RescheduleStatusTests(TestCase):
    def test_reschedule_counts_once_and_preserves_snapshot(self):
        fixture=fixtures.AppointmentTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        booked=fixture.book()
        self.assertEqual(booked.status_code,201,booked.data)
        url=fixture.url+str(booked.data['id'])+'/reschedule/'
        payload=fixture.reschedule_payload()
        changed=fixture.client.post(url,payload,format='json')
        self.assertEqual(changed.status_code,200,changed.data)
        self.assertEqual(changed.data['business_status'],'rescheduled')
        self.assertEqual(changed.data['reschedule_count'],1)
        self.assertIsNotNone(changed.data['rescheduled_at'])
        self.assertEqual(changed.data['qualification_snapshot'],booked.data['qualification_snapshot'])
        self.assertEqual(fixture.client.post(url,payload,format='json').status_code,409)
        self.assertEqual(Appointment.objects.get(pk=booked.data['id']).reschedule_count,1)
