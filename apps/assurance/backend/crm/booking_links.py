"""Public scheduling links, shared only with the advisor's assigned setters."""

from urllib.parse import urlsplit
from django.db import transaction
from django.db.models import F
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .models import AdvisorSchedule, BusinessAudit
from .leases import Conflict


class LinkInput(serializers.Serializer):
    url = serializers.URLField(max_length=2048, allow_blank=True)
    revision = serializers.IntegerField(min_value=0)

    def validate_url(self, value):
        if value:
            parsed = urlsplit(value)
            if parsed.scheme != 'https' or parsed.username or parsed.password:
                raise ValidationError('Lien public HTTPS sans identifiant ni mot de passe requis.')
        return value

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés.')
        return data


def manage(request, advisor_id):
    if request.method == 'GET':
        row = AdvisorSchedule.objects.filter(pk=advisor_id).first()
    else:
        if request.user.role not in ('advisor', 'administrator'):
            raise PermissionDenied('Modification réservée au conseiller et à l’administration.')
        data = LinkInput(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            AdvisorSchedule.objects.get_or_create(pk=advisor_id)
            row = AdvisorSchedule.objects.get(pk=advisor_id)
            before = row.booking_url
            if not AdvisorSchedule.objects.filter(
                pk=advisor_id, booking_revision=data.validated_data['revision']
            ).update(
                booking_url=data.validated_data['url'], booking_revision=F('booking_revision') + 1
            ):
                raise Conflict('Lien modifié : rechargez avant d’enregistrer.')
            row.refresh_from_db()
            # Do not copy a potentially long provider query into the audit trail.
            BusinessAudit.objects.create(
                actor_id=request.user.pk,
                action='advisor.booking_link_changed',
                object_id=advisor_id,
                metadata={
                    'before_configured': bool(before),
                    'configured': bool(row.booking_url),
                    'revision': row.booking_revision,
                },
            )
    response = Response(
        {'url': row.booking_url if row else '', 'revision': row.booking_revision if row else 0}
    )
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['GET', 'POST'])
def own(request):
    if request.user.role != 'advisor':
        raise PermissionDenied('Lien personnel réservé au conseiller Assurance.')
    return manage(request, request.user.pk)
