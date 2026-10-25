"""Calendly bookings keep the existing contact lease, assignment and qualification rules."""

import hashlib
import json
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from packages.calendar_connectors.calendly_bridge import rpc
from packages.calendar_connectors.providers import instant, ProviderError
from .appointments import (
    BookingInput,
    active_assignment,
    attest,
    calendar_lock,
    prevent_overlap,
    output,
    audit,
)
from .advisor_availability import ensure_open
from .leases import writer, held, Conflict, LEASE_SECONDS
from .models import CalendlyBooking, Contact, AdvisorAssignment, Appointment, BusinessAudit
from .qualification import snapshot as qualification_snapshot
from .visibility import visible_contacts


def bridge(user, assignment, action, data=None):
    return rpc(
        settings.PORTAL_INTERNAL_URL.rstrip('/'),
        'portal',
        action,
        {
            'actor': user.pk,
            'role': user.role,
            'owner': assignment.advisor_id,
            **(data or {}),
        },
    )


def assignment_for(request, pk):
    writer(request)
    row = get_object_or_404(AdvisorAssignment, pk=pk, active=True)
    if request.user.role == 'setter' and row.setter_id != request.user.pk:
        raise PermissionDenied('Réservation limitée à vos conseillers attribués.')
    return row


@api_view(['GET'])
def slots(request):
    try:
        row = assignment_for(request, int(request.query_params.get('assignment_id', '')))
        start = instant(request.query_params.get('start'))
        end = instant(request.query_params.get('end'))
        contact = get_object_or_404(
            visible_contacts(request.user), pk=int(request.query_params.get('contact_id', ''))
        )
    except (ValueError, TypeError, ProviderError):
        raise ValidationError('Attribution, prospect et période valides requis.') from None
    if not timezone.now() < start < end <= start + timedelta(days=7):
        raise ValidationError('Choisissez une période future de sept jours au maximum.')
    result = bridge(
        request.user, row, 'slots', {'starts_at': start.isoformat(), 'ends_at': end.isoformat()}
    )
    duration = result.get('duration')
    if (
        type(duration) is not int
        or not 1 <= duration <= 1440
        or not isinstance(result.get('slots'), list)
    ):
        raise ValidationError('Créneaux Calendly indisponibles.')
    available = []
    for value in result['slots']:
        try:
            when = instant(value)
            if not start <= when < end:
                continue
            prevent_overlap(contact.pk, row.advisor_id, when, when + timedelta(minutes=duration))
            ensure_open(row.advisor_id, when, when + timedelta(minutes=duration))
            available.append(value)
        except Conflict:
            continue
    result['slots'] = available
    return Response(result, headers={'Cache-Control': 'no-store'})


class CalendlyInput(BookingInput):
    event_type = serializers.CharField(max_length=300)


def apply_result(booking, result, actor):
    state = result.get('state')
    if state not in ('confirmed', 'rejected', 'uncertain', 'dispatching'):
        raise ValidationError('Réponse de réservation Calendly invalide.')
    with transaction.atomic():
        Contact.objects.filter(pk=booking.contact_id).update(revision=F('revision'))
        calendar_lock(booking.assignment.advisor_id)
        booking = CalendlyBooking.objects.select_related(
            'assignment', 'contact', 'appointment'
        ).get(pk=booking.pk)
        if booking.appointment_id:
            return output(booking.appointment, actor)
        if state == 'confirmed':
            remote = result.get('appointment') or {}
            if (
                instant(remote.get('starts_at')) != booking.starts_at
                or instant(remote.get('ends_at')) != booking.ends_at
                or remote.get('status') not in ('scheduled', 'cancelled')
            ):
                raise Conflict('Réservation Calendly à rapprocher avant confirmation.')
            prevent_overlap(
                booking.contact_id,
                booking.assignment.advisor_id,
                booking.starts_at,
                booking.ends_at,
                booking_id=booking.pk,
            )
            data = booking.snapshot
            appointment = Appointment.objects.create(
                request_id=booking.pk,
                fingerprint=booking.fingerprint,
                contact=booking.contact,
                assignment=booking.assignment,
                setter_id=booking.assignment.setter_id,
                setter_name=data['setter_name'],
                advisor_id=booking.assignment.advisor_id,
                advisor_name=data['advisor_name'],
                booked_by_id=booking.actor_id,
                starts_at=booking.starts_at,
                ends_at=booking.ends_at,
                timezone='America/Toronto',
                qualification_snapshot=data['qualification'],
                calendar='calendly',
                status=remote['status'],
            )
            booking.appointment = appointment
            booking.state = 'confirmed'
            audit(
                actor, appointment, 'appointment.booked', external={'result': 'calendly_confirmed'}
            )
        else:
            booking.state = 'rejected' if state == 'rejected' else 'uncertain'
        booking.save()
        return (
            output(booking.appointment, actor)
            if booking.appointment_id
            else {
                'request_id': str(booking.pk),
                'state': booking.state,
                'pending': booking.state != 'rejected',
            }
        )


@api_view(['POST'])
def book(request):
    writer(request)
    serializer = CalendlyInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if data['timezone'] != 'America/Toronto':
        raise ValidationError('Les rendez-vous Calendly utilisent l’heure de Montréal.')
    assignment = get_object_or_404(AdvisorAssignment, pk=data['assignment_id'])
    claims = attest(data['proof'], request.user, assignment)
    canonical = {
        key: str(value)
        for key, value in data.items()
        if key not in ('proof', 'token', 'request_id')
    }
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    booking = CalendlyBooking.objects.filter(pk=data['request_id']).first()
    if booking and (booking.actor_id != request.user.pk or booking.fingerprint != digest):
        raise Conflict('Identifiant de réservation déjà utilisé.')
    if not booking:
        with transaction.atomic():
            now = timezone.now()
            if not held(data['contact_id'], request.user, data['token'], now).update(
                lease_expires_at=now + timedelta(seconds=LEASE_SECONDS)
            ):
                raise Conflict('Prenez en charge le prospect avant de réserver.')
            contact = Contact.objects.get(pk=data['contact_id'])
            if not contact.email or (
                'contact_revision' in data and contact.revision != data['contact_revision']
            ):
                raise Conflict(
                    'Courriel valide et qualification à jour requis. Rechargez la fiche.'
                )
            active_assignment(assignment.pk)
            calendar_lock(assignment.advisor_id)
            existing = CalendlyBooking.objects.filter(pk=data['request_id']).first()
            if existing:
                if existing.actor_id != request.user.pk or existing.fingerprint != digest:
                    raise Conflict('Identifiant de réservation déjà utilisé.')
                booking = existing
            else:
                ensure_open(assignment.advisor_id, data['starts_at'], data['ends_at'])
                prevent_overlap(
                    contact.pk, assignment.advisor_id, data['starts_at'], data['ends_at']
                )
                if data['starts_at'] <= now:
                    raise ValidationError('Créneau futur requis.')
                booking = CalendlyBooking.objects.create(
                    request_id=data['request_id'],
                    contact=contact,
                    assignment=assignment,
                    actor_id=request.user.pk,
                    fingerprint=digest,
                    starts_at=data['starts_at'],
                    ends_at=data['ends_at'],
                    event_type=data['event_type'],
                    snapshot={
                        'name': contact.name,
                        'email': contact.email,
                        'qualification': qualification_snapshot(contact),
                        'setter_name': claims['setter']['name'],
                        'advisor_name': claims['advisor']['name'],
                    },
                )
                BusinessAudit.objects.create(
                    actor_id=request.user.pk,
                    action='calendly.booking_requested',
                    object_id=contact.pk,
                    metadata={'request_id': str(booking.pk), 'advisor_id': assignment.advisor_id},
                )
    if booking.appointment_id:
        return Response(
            output(
                Appointment.objects.select_related('contact', 'assignment').get(
                    pk=booking.appointment_id
                ),
                request.user,
            )
        )
    result = bridge(
        request.user,
        assignment,
        'reserve',
        {
            'request_id': str(booking.pk),
            'event_type': booking.event_type,
            'starts_at': booking.starts_at.isoformat(),
            'ends_at': booking.ends_at.isoformat(),
            'name': booking.snapshot['name'],
            'email': booking.snapshot['email'],
        },
    )
    value = apply_result(booking, result, request.user)
    return Response(
        value, status=201 if 'id' in value else 202, headers={'Cache-Control': 'no-store'}
    )


@api_view(['GET', 'POST'])
def pending(request):
    writer(request)
    rows = CalendlyBooking.objects.select_related('assignment', 'appointment__contact').filter(
        actor_id=request.user.pk
    )
    if request.method == 'GET':
        try:
            contact = get_object_or_404(
                visible_contacts(request.user), pk=int(request.query_params.get('contact_id', ''))
            )
        except ValueError:
            raise ValidationError('Prospect requis.') from None
        row = (
            rows.filter(contact=contact, state__in=['pending', 'uncertain'])
            .order_by('updated_at')
            .first()
        )
        return Response(
            {'request_id': str(row.pk) if row else None}, headers={'Cache-Control': 'no-store'}
        )
    if not isinstance(request.data, dict) or set(request.data) != {'request_id'}:
        raise ValidationError('Identifiant de demande seul requis.')
    booking = get_object_or_404(rows, pk=request.data['request_id'])
    if booking.appointment_id:
        return Response(
            output(booking.appointment, request.user), headers={'Cache-Control': 'no-store'}
        )
    result = bridge(
        request.user,
        booking.assignment,
        'reserve',
        {
            'request_id': str(booking.pk),
            'event_type': booking.event_type,
            'starts_at': booking.starts_at.isoformat(),
            'ends_at': booking.ends_at.isoformat(),
            'name': booking.snapshot['name'],
            'email': booking.snapshot['email'],
        },
    )
    value = apply_result(booking, result, request.user)
    return Response(value, headers={'Cache-Control': 'no-store'})
