"""Scoped advisor updates, separate from setter leases and booking snapshots."""

from copy import deepcopy
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .leases import Conflict
from .models import Appointment, AppointmentReport, BusinessAudit, Contact, FollowUpTask
from .notifications import notify
from .policies import policy
from .qualification import FIELDS, Qualification
from .reports import ReportInput

PUBLIC_FIELDS = [field for field in FIELDS if field['key'] != 'additional_notes']
PUBLIC_KEYS = {field['key'] for field in PUBLIC_FIELDS}


class ClientInput(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    name = serializers.CharField(max_length=250)
    phone = serializers.CharField(max_length=250)
    # Preserve raw imported values, as with the existing contact editor.
    email = serializers.CharField(max_length=254, allow_blank=True)
    qualification = serializers.DictField()

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError('Champs non autorisés.')
        if set(data['qualification']) - PUBLIC_KEYS:
            raise serializers.ValidationError('Champ de qualification non partagé.')
        return data


class ResultInput(ReportInput):
    sale_concluded = serializers.BooleanField()
    reason = serializers.CharField(max_length=1000, allow_blank=True, default='')

    def validate(self, data):
        data = super().validate(data)
        if data['sale_concluded'] and not data['performed']:
            raise serializers.ValidationError('Une vente exige un rendez-vous tenu.')
        return data


def advisor_only(user):
    if user.role != 'advisor':
        raise PermissionDenied('Action réservée au conseiller du rendez-vous.')


def client_output(contact):
    return {
        'revision': contact.revision,
        'name': contact.name,
        'phone': contact.phone,
        'email': contact.email,
        'fields': PUBLIC_FIELDS,
        'qualification': {
            key: deepcopy(value)
            for key, value in contact.assurance_qualification.items()
            if key in PUBLIC_KEYS
        },
    }


def result_output(report):
    return (
        None
        if report is None
        else {
            key: getattr(report, key)
            for key in ('performed', 'outcome', 'sale_concluded', 'problem', 'note')
        }
    )


def saved_result(appointment, result, user):
    from .appointments import output

    return {
        'result': result,
        'revision': appointment.revision,
        'appointment': output(appointment, user),
    }


class AdvisorWorkspaceMixin:
    @action(detail=True, methods=['get', 'post'], url_path='client-record')
    def client_record(self, request, pk=None):
        advisor_only(request.user)
        original = self.get_object()
        with transaction.atomic():
            # Match the contact-first lock order used by booking and setter edits.
            if request.method == 'POST':
                Contact.objects.filter(pk=original.contact_id).update(revision=F('revision'))
                Appointment.objects.filter(pk=original.pk).update(revision=F('revision'))
            contact = Contact.objects.get(pk=original.contact_id)
            appointment = Appointment.objects.get(pk=original.pk)
            if appointment.advisor_id != request.user.pk or contact.assigned_advisor_id not in (
                None,
                request.user.pk,
            ):
                raise PermissionDenied('Ce client est attribué à un autre conseiller.')
            if request.method == 'POST':
                serializer = ClientInput(data=request.data)
                serializer.is_valid(raise_exception=True)
                data = serializer.validated_data
                if contact.revision != data['revision']:
                    raise Conflict('Fiche modifiée : rechargez avant de réessayer.')
                if contact.lease_expires_at and contact.lease_expires_at > timezone.now():
                    raise Conflict('Fiche en cours de modification par un autre utilisateur.')
                qualification = Qualification(
                    data={**contact.assurance_qualification, **data['qualification']}
                )
                qualification.is_valid(raise_exception=True)
                before = client_output(contact)
                contact.name, contact.phone, contact.email = (
                    data['name'],
                    data['phone'],
                    data['email'],
                )
                contact.assurance_qualification = qualification.validated_data
                if before != client_output(contact):
                    contact.revision += 1
                    contact.save(
                        update_fields=[
                            'name',
                            'phone',
                            'email',
                            'assurance_qualification',
                            'revision',
                            'updated_at',
                        ]
                    )
                    BusinessAudit.objects.create(
                        actor_id=request.user.pk,
                        object_id=contact.pk,
                        action='contact.advisor_updated',
                        metadata={
                            'before': before,
                            'after': client_output(contact),
                            'appointment_id': appointment.pk,
                        },
                    )
        response = Response(client_output(contact))
        response['Cache-Control'] = 'no-store'
        return response

    @action(detail=True, methods=['get', 'post'], url_path='advisor-result')
    def advisor_result(self, request, pk=None):
        advisor_only(request.user)
        original = self.get_object()
        if request.method == 'GET':
            return Response(
                {
                    'result': result_output(
                        AppointmentReport.objects.filter(appointment=original).first()
                    )
                }
            )
        serializer = ResultInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        values = {
            key: data[key] for key in ('performed', 'outcome', 'sale_concluded', 'problem', 'note')
        }
        with transaction.atomic():
            Appointment.objects.filter(pk=original.pk).update(revision=F('revision'))
            appointment = Appointment.objects.get(pk=original.pk)
            if appointment.advisor_id != request.user.pk:
                raise PermissionDenied('Rendez-vous réattribué à un autre conseiller.')
            report = AppointmentReport.objects.filter(appointment=appointment).first()
            before = result_output(report)
            if before == values:
                return Response(saved_result(appointment, before, request.user))
            if appointment.status != 'scheduled' or appointment.ends_at > timezone.now():
                raise Conflict('Résultat attendu après la fin d’un rendez-vous non annulé.')
            if appointment.revision != data['revision']:
                raise Conflict('Rendez-vous modifié : rechargez avant de réessayer.')
            if report and not data['reason'].strip():
                raise serializers.ValidationError('Précisez le motif de la correction.')
            if report:
                for key, value in values.items():
                    setattr(report, key, value)
                report.save(update_fields=list(values))
            else:
                report = AppointmentReport.objects.create(
                    appointment=appointment, author_id=request.user.pk, **values
                )
            appointment.revision += 1
            appointment.save(update_fields=['revision', 'updated_at'])
            if not report.performed or report.problem:
                rules = policy()
                task, created = FollowUpTask.objects.get_or_create(
                    appointment=appointment,
                    defaults={
                        'setter_id': appointment.setter_id,
                        'reason': report.note,
                        'due_at': timezone.now() + timedelta(hours=rules.initial_hours),
                        'priority': rules.default_priority,
                        'policy_revision': rules.revision,
                    },
                )
                if created:
                    notify(task, 'report', f'report:{report.pk}')
            BusinessAudit.objects.create(
                actor_id=request.user.pk,
                object_id=appointment.pk,
                action='appointment.advisor_result_updated',
                metadata={
                    'before': before,
                    'after': values,
                    'reason': data['reason'],
                    'revision': appointment.revision,
                },
            )
        return Response(saved_result(appointment, values, request.user))
