"""Append-only notes with server-derived visibility; never forward internal notes to advisors."""

from datetime import timedelta
from django.db import transaction
from django.db.models import Q, F
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from .models import ContactNote, BusinessAudit
from .leases import held, Conflict, LEASE_SECONDS
from django.utils import timezone


class NoteInput(serializers.Serializer):
    request_id = serializers.UUIDField()
    body = serializers.CharField(max_length=5000)
    token = serializers.UUIDField(required=False, write_only=True)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError('Champs non autorisés')
        return data


def output(row, user):
    result = {'id': row.pk, 'body': row.body, 'created_at': row.created_at, 'channel': row.channel}
    if user.role == 'advisor' and row.channel == 'internal':
        result.update(body=row.advisor_body, channel='shared')
    if user.role == 'administrator':
        result.update(
            author_id=row.author_id,
            advisor_visible=row.advisor_visible,
            advisor_body=row.advisor_body,
            sharing_revision=row.sharing_revision,
        )
    return result


def visible_notes(contact, user):
    qs = ContactNote.objects.filter(contact=contact)
    if user.role == 'advisor':
        return qs.filter(
            Q(channel='advisor', author_id=user.pk) | Q(channel='internal', advisor_visible=True)
        )
    if user.role == 'setter':
        return qs.filter(channel='internal')
    return qs


class ContactNoteMixin:
    @action(detail=True, methods=['get', 'post'])
    def notes(self, request, pk=None):
        contact = self.get_object()
        user = request.user
        qs = visible_notes(contact, user).order_by('-pk')
        if request.method == 'GET':
            response = self.get_paginated_response(
                [output(row, user) for row in self.paginate_queryset(qs)]
            )
            response['Cache-Control'] = 'no-store'
            return response
        serializer = NoteInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        channel = 'advisor' if user.role == 'advisor' else 'internal'

        def replay(row):
            if (
                row.contact_id != contact.pk
                or row.author_id != user.pk
                or row.channel != channel
                or row.body != data['body']
            ):
                raise Conflict('Identifiant de note déjà utilisé')
            return Response(output(row, user))

        existing = ContactNote.objects.filter(request_id=data['request_id']).first()
        if existing:
            return replay(existing)
        with transaction.atomic():
            if channel == 'internal':
                now = timezone.now()
                if not held(contact.pk, user, data.get('token'), now).update(
                    lease_expires_at=now + timedelta(seconds=LEASE_SECONDS)
                ):
                    raise Conflict('Prenez en charge la fiche avant d’ajouter une note interne')
            row, created = ContactNote.objects.get_or_create(
                request_id=data['request_id'],
                defaults={
                    'contact': contact,
                    'author_id': user.pk,
                    'channel': channel,
                    'body': data['body'],
                },
            )
            if not created:
                return replay(row)
            BusinessAudit.objects.create(
                actor_id=user.pk,
                object_id=contact.pk,
                action='contact.note_added',
                metadata={'note_id': row.pk, 'channel': channel},
            )
        return Response(output(row, user), status=201)


class NoteSharingInput(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    enabled = serializers.BooleanField()
    body = serializers.CharField(max_length=5000, required=False)
    reviewed = serializers.BooleanField(default=False)
    reason = serializers.CharField(max_length=1000)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError('Champs non autorisés')
        if data['enabled'] and (not data['reviewed'] or not data.get('body')):
            raise serializers.ValidationError(
                'Version destinée au conseiller et vérification explicite requises'
            )
        return data


class NoteSharingMixin:
    @action(detail=True, methods=['post'], url_path=r'notes/(?P<note_id>[0-9]+)/sharing')
    def share_note(self, request, pk=None, note_id=None):
        if request.user.role != 'administrator':
            raise PermissionDenied('Publication réservée à l’administration')
        contact = self.get_object()
        serializer = NoteSharingInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            qs = ContactNote.objects.filter(contact=contact, pk=note_id, channel='internal')
            row = get_object_or_404(qs)
            if row.sharing_revision != data['revision']:
                raise Conflict('Partage modifié : actualisez')
            before = {
                'enabled': row.advisor_visible,
                'body': row.advisor_body,
                'revision': row.sharing_revision,
            }
            body = data['body'] if data['enabled'] else ''
            if not qs.filter(sharing_revision=data['revision']).update(
                advisor_visible=data['enabled'],
                advisor_body=body,
                sharing_revision=F('sharing_revision') + 1,
            ):
                raise Conflict('Partage modifié : actualisez')
            row.refresh_from_db()
            BusinessAudit.objects.create(
                actor_id=request.user.pk,
                object_id=contact.pk,
                action='contact.note_sharing_changed',
                metadata={
                    'note_id': row.pk,
                    'before': before,
                    'after': {
                        'enabled': row.advisor_visible,
                        'body': row.advisor_body,
                        'revision': row.sharing_revision,
                    },
                    'reason': data['reason'],
                    'reviewed': data['reviewed'],
                },
            )
        response = Response(output(row, request.user))
        response['Cache-Control'] = 'no-store'
        return response
