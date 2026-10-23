from datetime import timedelta
from copy import copy
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from .models import AppointmentReport, BusinessAudit, Contact, FollowUpTask
from . import tests as existing_tests


@override_settings(DEBUG=True)
class AdvisorWorkspaceTests(TestCase):
    def setUp(self):
        existing_tests.ReportTests.setUp(self)
        self.result_url = self.url.replace('/report/', '/advisor-result/')
        self.client_url = self.url.replace('/report/', '/client-record/')
        self.contact = self.appointment.contact
        self.contact.assigned_advisor_id = 31
        self.contact.assurance_qualification = {
            'age': 45,
            'additional_notes': 'INTERNAL DRAFT',
            'advisor_notes': 'Shared note',
        }
        self.contact.save()
        self.appointment.qualification_snapshot = {'original': 'immutable'}
        self.appointment.save()

    auth = existing_tests.ReportTests.auth

    def result(self, **values):
        return self.client.post(
            self.result_url,
            {'revision': 0, 'performed': True, 'sale_concluded': False, 'note': '', **values},
            format='json',
        )

    def edit(self, **values):
        return self.client.post(
            self.client_url,
            {
                'revision': 0,
                'name': 'Updated client',
                'phone': '001 raw phone',
                'email': 'original raw email',
                'qualification': {'age': 46},
                **values,
            },
            format='json',
        )

    def test_report_explicit_sale_retry_and_audited_correction(self):
        response = self.client.get(self.result_url)
        self.assertEqual(response.json(), {'result': None})
        saved = self.result(sale_concluded=True)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.data['appointment']['business_status'], 'performed')
        self.assertNotIn('setter', saved.data['appointment'])
        self.assertEqual(self.result(sale_concluded=True).status_code, 200)
        self.assertEqual(AppointmentReport.objects.count(), 1)
        self.assertEqual(
            BusinessAudit.objects.filter(action='appointment.advisor_result_updated').count(), 1
        )
        self.assertEqual(self.result(revision=1).status_code, 400)
        self.assertEqual(self.result(revision=0, reason='Correction').status_code, 409)
        self.assertEqual(self.result(revision=1, reason='Client changed decision').status_code, 200)
        report = AppointmentReport.objects.get()
        self.assertIs(report.sale_concluded, False)
        audit = BusinessAudit.objects.filter(action='appointment.advisor_result_updated').last()
        self.assertIs(audit.metadata['before']['sale_concluded'], True)
        self.assertEqual(audit.metadata['reason'], 'Client changed decision')

    def test_absent_sale_rejected_and_follow_up_never_duplicated_or_erased(self):
        self.assertEqual(
            self.result(performed=False, sale_concluded=True, note='Absent').status_code, 400
        )
        self.assertEqual(self.result(performed=False).status_code, 400)
        self.assertEqual(self.result(performed=False, note='Absent').status_code, 200)
        self.assertEqual(self.result(performed=False, note='Absent').status_code, 200)
        self.assertEqual(FollowUpTask.objects.count(), 1)
        self.assertEqual(self.result(revision=1, reason='Presence corrected').status_code, 200)
        self.assertEqual(FollowUpTask.objects.count(), 1)
        self.assertIsNone(FollowUpTask.objects.get().closed_at)

    def test_old_report_has_unknown_sale_and_can_be_completed(self):
        AppointmentReport.objects.create(
            appointment=self.appointment, performed=True, author_id=31, outcome='performed'
        )
        self.assertIsNone(self.client.get(self.result_url).data['result']['sale_concluded'])
        self.assertEqual(self.result(reason='Complete legacy record').status_code, 200)
        self.assertIs(AppointmentReport.objects.get().sale_concluded, False)

    def test_future_cancelled_and_wrong_roles_cannot_report(self):
        self.appointment.ends_at = timezone.now() + timedelta(hours=1)
        self.appointment.save()
        self.assertEqual(self.result().status_code, 409)
        self.appointment.ends_at = timezone.now() - timedelta(hours=1)
        self.appointment.status = 'cancelled'
        self.appointment.save()
        self.assertEqual(self.result().status_code, 409)
        self.auth(32, 'advisor')
        self.assertEqual(self.result().status_code, 404)
        self.assertEqual(self.edit().status_code, 404)
        for role in ('setter', 'administrator'):
            self.auth(21, role)
            self.assertEqual(self.result().status_code, 403)
            self.assertEqual(self.edit().status_code, 403)

    def test_edit_public_client_fields_preserves_internal_notes_and_snapshot(self):
        self.assertNotIn('INTERNAL DRAFT', str(self.client.get(self.client_url).data))
        response = self.edit()
        self.assertEqual(response.status_code, 200, response.data)
        self.contact.refresh_from_db()
        self.appointment.refresh_from_db()
        self.assertEqual(self.contact.assurance_qualification['additional_notes'], 'INTERNAL DRAFT')
        self.assertEqual(self.contact.assurance_qualification['age'], 46)
        self.assertEqual(self.contact.phone, '001 raw phone')
        self.assertEqual(self.contact.email, 'original raw email')
        self.assertEqual(self.appointment.qualification_snapshot, {'original': 'immutable'})
        self.assertEqual(self.contact.revision, 1)
        self.assertEqual(self.edit().status_code, 409)

    def test_protected_fields_invalid_choices_and_reassigned_contact_are_rejected(self):
        for payload in (
            {'additional_notes': 'hack'},
            {'age': 200},
            {'insurances': ['none_known', 'life']},
        ):
            self.assertEqual(self.edit(qualification=payload).status_code, 400)
        self.assertEqual(self.edit(assigned_advisor_id=31).status_code, 400)
        Contact.objects.filter(pk=self.contact.pk).update(assigned_advisor_id=32)
        self.assertEqual(self.edit().status_code, 403)
        self.assertEqual(self.client.get(self.client_url).status_code, 403)

    def test_active_setter_lease_blocks_advisor_edit(self):
        Contact.objects.filter(pk=self.contact.pk).update(
            lease_owner_id=21, lease_expires_at=timezone.now() + timedelta(minutes=3)
        )
        self.assertEqual(self.edit().status_code, 409)
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.revision, 0)
        self.assertEqual(self.contact.lease_owner_id, 21)

    def test_scope_is_rechecked_after_locking_the_appointment(self):
        reassigned = copy(self.appointment)
        reassigned.advisor_id = 32
        with patch(
            'apps.assurance.backend.crm.advisor_workspace.Appointment.objects.get',
            return_value=reassigned,
        ):
            self.assertEqual(self.edit().status_code, 403)
            self.assertEqual(self.result().status_code, 403)
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.name, 'Prospect')
        self.assertFalse(AppointmentReport.objects.exists())

    def test_audit_failure_rolls_back_client_and_result(self):
        with patch.object(
            BusinessAudit.objects, 'create', side_effect=RuntimeError('audit failed')
        ):
            with self.assertRaises(RuntimeError):
                self.edit()
            with self.assertRaises(RuntimeError):
                self.result()
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.name, 'Prospect')
        self.assertFalse(AppointmentReport.objects.exists())
