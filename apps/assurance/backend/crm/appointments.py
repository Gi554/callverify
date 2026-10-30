"""Internal appointments with server-side external availability confirmation."""

from packages.access.calendar_window import calendar_window
import hashlib
import json
from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.core import signing
from django.db import transaction, IntegrityError
from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from packages.access.assignments import verify_booking
from .models import (
    Appointment,
    AdvisorAssignment,
    AdvisorSchedule,
    Contact,
    BusinessAudit,
    CalendlyBooking,
    ContactCallOutcome,
    AppointmentNotification,
)
from .leases import Conflict, writer, held, LEASE_SECONDS
from .calendar_checks import check as external_check
from .appointment_status import output as business_status, filter_status
from .qualification import snapshot as qualification_snapshot, Qualification
from .reports import ReportMixin
from .advisor_workspace import AdvisorWorkspaceMixin
from .advisor_availability import ensure_open, configuration as working_hours, closed_periods
from .visibility import visible_contacts


class IntervalInput(serializers.Serializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    timezone = serializers.CharField(max_length=100)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        try:
            zone = ZoneInfo(data['timezone'])
        except (ZoneInfoNotFoundError, ValueError):
            raise ValidationError({'timezone': 'Fuseau IANA inconnu'})
        for key in ('starts_at', 'ends_at'):
            raw = parse_datetime(str(self.initial_data[key]))
            if raw is None or timezone.is_naive(raw):
                raise ValidationError(
                    {key: 'Date ISO 8601 avec décalage horaire explicite requise'}
                )
            if raw.astimezone(zone).utcoffset() != raw.utcoffset():
                raise ValidationError({key: 'Décalage incompatible avec le fuseau à cette date'})
        if not timedelta(0) < data['ends_at'] - data['starts_at'] <= timedelta(days=31):
            raise ValidationError('Fenêtre positive limitée à 31 jours')
        return data


class BookingInput(IntervalInput):
    contact_revision = serializers.IntegerField(min_value=0, required=False)
    contact_id = serializers.IntegerField(min_value=1)
    assignment_id = serializers.IntegerField(min_value=1)
    request_id = serializers.UUIDField()
    token = serializers.UUIDField(write_only=True)
    proof = serializers.CharField(max_length=8192, write_only=True)


class RescheduleInput(IntervalInput):
    revision = serializers.IntegerField(min_value=0)
    proof = serializers.CharField(max_length=8192, write_only=True)
    reason = serializers.CharField(max_length=1000)


class TransmissionInput(BookingInput):
    contact_revision = serializers.IntegerField(min_value=0)
    qualification = Qualification()
    meeting_type = serializers.ChoiceField(choices=['video', 'phone'])
    external_confirmed = serializers.BooleanField()

    def validate(self, data):
        data = super().validate(data)
        if not data['external_confirmed']:
            raise ValidationError(
                'Réservez et confirmez d’abord le rendez-vous dans l’outil externe.'
            )
        if data['timezone'] != 'America/Toronto':
            raise ValidationError('Utilisez le fuseau du Québec : America/Toronto.')
        if data['ends_at'] - data['starts_at'] > timedelta(hours=8):
            raise ValidationError('La rencontre est limitée à huit heures.')
        return data


class CancelInput(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=1000)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        return data


class AppointmentPagination(PageNumberPagination):
    page_size = 25
    # The monthly calendar reads a whole team month: larger pages, still bounded.
    page_size_query_param = 'page_size'
    max_page_size = 100


def attest(proof, user, assignment):
    try:
        claims = verify_booking(proof, user.pk)
    except (signing.BadSignature, TypeError, ValueError, UnicodeError):
        raise ValidationError('Confirmation de réservation absente, invalide ou expirée')
    if (
        claims['setter']['id'] != assignment.setter_id
        or claims['advisor']['id'] != assignment.advisor_id
    ):
        raise ValidationError('La confirmation ne correspond pas à cette attribution')
    if user.role == 'setter' and user.pk != assignment.setter_id:
        raise PermissionDenied('Réservation limitée à vos attributions')
    return claims


def active_assignment(pk):
    # A conditional write serializes booking against assignment suspension.
    if not AdvisorAssignment.objects.filter(pk=pk, active=True).update(updated_at=F('updated_at')):
        raise Conflict('Attribution suspendue ou indisponible')


def calendar_lock(advisor_id):
    AdvisorSchedule.objects.get_or_create(advisor_id=advisor_id)
    AdvisorSchedule.objects.filter(pk=advisor_id).update(version=F('version') + 1)


def prevent_overlap(contact_id, advisor_id, start, end, exclude=None, booking_id=None):
    pending = CalendlyBooking.objects.filter(
        state__in=['pending', 'uncertain'], starts_at__lt=end, ends_at__gt=start
    ).filter(Q(contact_id=contact_id) | Q(assignment__advisor_id=advisor_id))
    if booking_id:
        pending = pending.exclude(pk=booking_id)
    if pending.exists():
        raise Conflict('Une réservation Calendly est en cours de vérification sur ce créneau.')
    qs = Appointment.objects.filter(
        status='scheduled', starts_at__lt=end, ends_at__gt=start
    ).filter(Q(contact_id=contact_id) | Q(advisor_id=advisor_id))
    if exclude:
        qs = qs.exclude(pk=exclude)
    if qs.exists():
        raise Conflict('Créneau indisponible pour le conseiller ou le prospect')


def snapshot(row):
    return {
        'starts_at': row.starts_at.isoformat(),
        'ends_at': row.ends_at.isoformat(),
        'timezone': row.timezone,
        'status': row.status,
        'revision': row.revision,
    }


def audit(user, row, action, before=None, reason='', external=None):
    BusinessAudit.objects.create(
        actor_id=user.pk,
        object_id=row.pk,
        action=action,
        metadata={
            'contact_id': row.contact_id,
            'setter_id': row.setter_id,
            'advisor_id': row.advisor_id,
            'before': before,
            'after': snapshot(row),
            'reason': reason,
            **({'external_check': external} if external else {}),
        },
    )


def output(row, user):
    # Only the explicit qualification snapshot is shared. Internal notes, audit
    # reasons, assignment IDs and setter metadata remain outside advisor output.
    result = {
        'id': row.pk,
        'contact': {
            'id': row.contact_id,
            'name': row.contact.name,
            'phone': row.contact.phone,
            'email': row.contact.email,
        },
        'advisor': {'id': row.advisor_id, 'name': row.advisor_name},
        'starts_at': row.starts_at,
        'ends_at': row.ends_at,
        'timezone': row.timezone,
        'status': row.status,
        'revision': row.revision,
        'calendar': row.calendar,
        'meeting_type': row.meeting_type,
        'external_booking_url': row.external_booking_url,
        'qualification_snapshot': row.qualification_snapshot,
    }
    result.update(business_status(row))
    if row.calendar == 'external_link' and user.role in ('setter', 'administrator'):
        result['contact_revision'] = row.qualification_snapshot.get('contact_revision')
        result['call_outcome_recorded'] = True
    if row.calendar == 'calendly' and hasattr(row, 'calendly_booking'):
        metadata = row.calendly_booking.snapshot
        result['calendly'] = {
            **metadata.get('management', {}),
            'needs_review': bool(metadata.get('sync_review')),
            'conflict': bool(metadata.get('sync_conflict')),
        }
    if user.role != 'advisor':
        result['assignment_id'] = row.assignment_id
    if user.role == 'administrator':
        result.update(
            setter={'id': row.setter_id, 'name': row.setter_name}, booked_by_id=row.booked_by_id
        )
    return result


class AppointmentViewSet(AdvisorWorkspaceMixin, ReportMixin, viewsets.GenericViewSet):
    serializer_class = BookingInput
    pagination_class = AppointmentPagination
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        qs = Appointment.objects.select_related('contact', 'assignment', 'report').order_by(
            'starts_at', 'pk'
        )
        if user.role == 'setter':
            qs = qs.filter(setter_id=user.pk)
        elif user.role == 'advisor':
            qs = qs.filter(advisor_id=user.pk)
        elif user.role != 'administrator':
            raise PermissionDenied('Accès non autorisé')
        state = self.request.query_params.get('status', '')
        if state not in ('', 'scheduled', 'cancelled'):
            raise ValidationError('Statut invalide')
        if state:
            qs = qs.filter(status=state)
        contact = self.request.query_params.get('contact_id', '')
        if contact:
            try:
                contact = int(contact)
            except ValueError:
                raise ValidationError('Contact invalide')
            qs = qs.filter(contact_id=contact)
        # Team calendar filters only narrow the role scope applied above.
        for param in ('setter_id', 'advisor_id'):
            value = self.request.query_params.get(param, '')
            if value:
                if not value.isdigit():
                    raise ValidationError('Participant invalide')
                qs = qs.filter(**{param: int(value)})
        period = self.request.query_params.get('period', '')
        if period not in ('', 'upcoming', 'past'):
            raise ValidationError('Période invalide')
        if period == 'upcoming':
            qs = qs.filter(ends_at__gt=timezone.now())
        if period == 'past':
            qs = qs.filter(ends_at__lte=timezone.now()).order_by('-starts_at', '-pk')
        return calendar_window(
            filter_status(qs, self.request.query_params.get('business_status', '')),
            self.request.query_params,
        )

    def list(self, request):
        rows = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response([output(row, request.user) for row in rows])

    def retrieve(self, request, pk=None):
        return Response(output(self.get_object(), request.user))

    def create(self, request):
        writer(request)
        external_booking = self.action == 'transmit'
        serializer = (TransmissionInput if external_booking else BookingInput)(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        canonical = {
            key: (value.isoformat() if hasattr(value, 'isoformat') else value)
            for key, value in data.items()
            if key not in ('proof', 'token', 'request_id')
        }
        fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()

        def replay(row):
            if row.booked_by_id != request.user.pk or row.fingerprint != fingerprint:
                raise Conflict('Identifiant de réservation déjà utilisé')
            return Response(output(row, request.user))

        existing = (
            Appointment.objects.select_related('contact')
            .filter(request_id=data['request_id'])
            .first()
        )
        if existing:
            return replay(existing)
        assignment = get_object_or_404(AdvisorAssignment, pk=data['assignment_id'])
        claims = attest(data['proof'], request.user, assignment)
        contact = get_object_or_404(Contact, pk=data['contact_id'])
        if data['starts_at'] <= timezone.now():
            raise ValidationError('Le rendez-vous doit commencer dans le futur')
        try:
            with transaction.atomic():
                now = timezone.now()
                if not held(contact.pk, request.user, data['token'], now).update(
                    lease_expires_at=now + timedelta(seconds=LEASE_SECONDS)
                ):
                    raise Conflict('Prenez en charge la fiche avant de réserver')
                existing = (
                    Appointment.objects.select_related('contact')
                    .filter(request_id=data['request_id'])
                    .first()
                )
                if existing:
                    return replay(existing)
                contact = Contact.objects.get(pk=contact.pk)
                if 'contact_revision' in data and contact.revision != data['contact_revision']:
                    raise Conflict(
                        'Qualification ou coordonnées modifiées : rechargez avant de réserver.'
                    )
                active_assignment(assignment.pk)
                calendar_lock(assignment.advisor_id)
                if not external_booking:
                    ensure_open(assignment.advisor_id, data['starts_at'], data['ends_at'])
                if data['starts_at'] <= timezone.now():
                    raise ValidationError('Le rendez-vous doit commencer dans le futur')
                prevent_overlap(
                    contact.pk, assignment.advisor_id, data['starts_at'], data['ends_at']
                )
                external = (
                    {'result': 'reserved_by_setter_in_external_tool'}
                    if external_booking
                    else external_check(
                        request.user, assignment.advisor_id, data['starts_at'], data['ends_at']
                    )
                )
                extras = {}
                if external_booking:
                    schedule = AdvisorSchedule.objects.get(pk=assignment.advisor_id)
                    if not schedule.booking_url:
                        raise ValidationError('Le conseiller doit fournir son lien de réservation.')
                    values = dict(data['qualification'])
                    if 'additional_notes' not in request.data.get('qualification', {}):
                        values['additional_notes'] = contact.assurance_qualification.get(
                            'additional_notes', ''
                        )
                    before = contact.assurance_qualification
                    contact.assurance_qualification = values
                    contact.revision += 1
                    contact.save(
                        update_fields=['assurance_qualification', 'revision', 'updated_at']
                    )
                    BusinessAudit.objects.create(
                        actor_id=request.user.pk,
                        object_id=contact.pk,
                        action='contact.assurance_qualification_updated',
                        metadata={'before': before, 'after': values, 'revision': contact.revision},
                    )
                    extras = {
                        'calendar': 'external_link',
                        'meeting_type': data['meeting_type'],
                        'external_booking_url': schedule.booking_url,
                    }
                if data['starts_at'] <= timezone.now():
                    raise ValidationError('Le rendez-vous doit commencer dans le futur')
                shared_qualification = qualification_snapshot(contact)
                if external_booking:
                    shared_qualification['fields'] = [
                        field
                        for field in shared_qualification['fields']
                        if field['key'] != 'additional_notes'
                    ]
                    shared_qualification['qualification'].pop('additional_notes', None)
                row = Appointment.objects.create(
                    request_id=data['request_id'],
                    fingerprint=fingerprint,
                    contact=contact,
                    assignment=assignment,
                    qualification_snapshot=shared_qualification,
                    setter_id=assignment.setter_id,
                    setter_name=claims['setter']['name'],
                    advisor_id=assignment.advisor_id,
                    advisor_name=claims['advisor']['name'],
                    booked_by_id=request.user.pk,
                    **extras,
                    **{key: data[key] for key in ('starts_at', 'ends_at', 'timezone')},
                )
                audit(request.user, row, 'appointment.booked', external=external)
                if external_booking:
                    ContactCallOutcome.objects.create(
                        contact=contact,
                        setter_id=request.user.pk,
                        request_id=data['request_id'],
                        fingerprint=fingerprint,
                        result='appointment_booked',
                        appointment=row,
                    )
                    AppointmentNotification.objects.create(
                        appointment=row,
                        recipient_id=row.advisor_id,
                        role='advisor',
                        kind='appointment_transmitted',
                        event_key=f'transmitted:{row.pk}:{row.advisor_id}',
                    )
        except IntegrityError:
            existing = (
                Appointment.objects.select_related('contact')
                .filter(request_id=data['request_id'])
                .first()
            )
            if existing:
                return replay(existing)
            raise
        return Response(output(row, request.user), status=201)

    @action(detail=False, methods=['post'])
    def transmit(self, request):
        return self.create(request)

    @action(detail=True, methods=['post'])
    def reschedule(self, request, pk=None):
        writer(request)
        original = self.get_object()
        if original.calendar == 'calendly':
            raise Conflict(
                'Reprogrammez ce rendez-vous depuis Calendly ; Orvia recevra sa mise à jour.'
            )
        serializer = RescheduleInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        attest(data['proof'], request.user, original.assignment)
        if data['starts_at'] <= timezone.now():
            raise ValidationError('Le rendez-vous doit commencer dans le futur')
        with transaction.atomic():
            Contact.objects.filter(pk=original.contact_id).update(revision=F('revision'))
            active_assignment(original.assignment_id)
            calendar_lock(original.advisor_id)
            row = Appointment.objects.select_related('contact').get(pk=original.pk)
            if (
                row.revision != data['revision']
                or row.status != 'scheduled'
                or hasattr(row, 'report')
            ):
                raise Conflict('Rendez-vous modifié, annulé ou déjà renseigné')
            ensure_open(row.advisor_id, data['starts_at'], data['ends_at'])
            if data['starts_at'] <= timezone.now():
                raise ValidationError('Le rendez-vous doit commencer dans le futur')
            prevent_overlap(
                row.contact_id, row.advisor_id, data['starts_at'], data['ends_at'], row.pk
            )
            external = external_check(
                request.user, row.advisor_id, data['starts_at'], data['ends_at'], row.pk
            )
            if data['starts_at'] <= timezone.now():
                raise ValidationError('Le rendez-vous doit commencer dans le futur')
            before = snapshot(row)
            for key in ('starts_at', 'ends_at', 'timezone'):
                setattr(row, key, data[key])
            row.revision += 1
            row.rescheduled_at = timezone.now()
            row.reschedule_count += 1
            row.save(
                update_fields=[
                    'starts_at',
                    'ends_at',
                    'timezone',
                    'revision',
                    'updated_at',
                    'rescheduled_at',
                    'reschedule_count',
                ]
            )
            audit(request.user, row, 'appointment.rescheduled', before, data['reason'], external)
        return Response(output(row, request.user))

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        writer(request)
        original = self.get_object()
        if original.calendar == 'calendly':
            raise Conflict('Annulez ce rendez-vous depuis Calendly ; Orvia recevra sa mise à jour.')
        serializer = CancelInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            Contact.objects.filter(pk=original.contact_id).update(revision=F('revision'))
            calendar_lock(original.advisor_id)
            row = Appointment.objects.select_related('contact').get(pk=original.pk)
            if (
                row.revision != data['revision']
                or row.status != 'scheduled'
                or hasattr(row, 'report')
            ):
                raise Conflict('Rendez-vous modifié, annulé ou déjà renseigné')
            before = snapshot(row)
            row.status = 'cancelled'
            row.revision += 1
            row.save(update_fields=['status', 'revision', 'updated_at'])
            audit(request.user, row, 'appointment.cancelled', before, data['reason'])
        return Response(output(row, request.user))

    @action(detail=False, methods=['get'])
    def availability(self, request):
        """Busy CRM intervals for a bookable assignment; external calendars stay checked at booking."""
        writer(request)
        try:
            assignment = AdvisorAssignment.objects.get(
                pk=int(request.query_params.get('assignment_id', '')), active=True
            )
        except (ValueError, AdvisorAssignment.DoesNotExist):
            raise ValidationError('Attribution invalide ou suspendue')
        if request.user.role == 'setter' and assignment.setter_id != request.user.pk:
            raise PermissionDenied('Disponibilités limitées à vos attributions')
        start = parse_datetime(request.query_params.get('start', ''))
        end = parse_datetime(request.query_params.get('end', ''))
        if not start or not end or start.tzinfo is None or end.tzinfo is None:
            raise ValidationError('Période invalide : dates ISO 8601 avec décalage attendues')
        if not start < end <= start + timedelta(days=7):
            raise ValidationError('Période invalide : sept jours au maximum')
        scope = Q(advisor_id=assignment.advisor_id)
        contact = request.query_params.get('contact_id', '')
        if contact:
            if (
                not contact.isdigit()
                or not visible_contacts(request.user).filter(pk=int(contact)).exists()
            ):
                raise ValidationError('Prospect invalide')
            scope |= Q(contact_id=int(contact))
        rows = (
            Appointment.objects.filter(status='scheduled', starts_at__lt=end, ends_at__gt=start)
            .filter(scope)
            .order_by('starts_at', 'pk')
            .values('starts_at', 'ends_at', 'advisor_id')
        )
        # Times only: other prospects' identities are never exposed.
        rules = working_hours(assignment.advisor_id)
        return Response(
            {
                'busy': [
                    {
                        'starts_at': row['starts_at'],
                        'ends_at': row['ends_at'],
                        'reason': 'advisor'
                        if row['advisor_id'] == assignment.advisor_id
                        else 'contact',
                    }
                    for row in rows
                ]
                + closed_periods(rules, start, end),
                'working_hours_enabled': rules['enabled'],
                'external_calendar': 'checked_at_booking',
            }
        )

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        if request.user.role != 'administrator':
            raise PermissionDenied('Historique réservé aux administrateurs')
        row = self.get_object()
        entries = self.paginate_queryset(
            BusinessAudit.objects.filter(
                object_id=row.pk, action__startswith='appointment.'
            ).order_by('-pk')
        )
        return self.get_paginated_response(
            [
                {
                    'id': item.pk,
                    'action': item.action,
                    'actor_id': item.actor_id,
                    'created_at': item.created_at,
                    'metadata': item.metadata,
                }
                for item in entries
            ]
        )
