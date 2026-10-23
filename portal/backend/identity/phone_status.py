"""Manual status observation for a locally assigned post; no call capability."""

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from packages.newt.directory import DirectoryUnavailable
from packages.newt.status import fetch_status
from .management_api import require_admin
from .models import PhoneDirectoryGate, PhoneExtension, Membership, AccessAudit
from .phone_directory import DirectoryThrottle


class Unavailable(APIException):
    status_code = 503
    default_detail = 'État NEWT indisponible, non configuré ou réponse non confirmée. Statut indéterminé ; aucun appel lancé.'


@api_view(['POST'])
@throttle_classes([DirectoryThrottle])
def status(request, workspace, pk):
    for space in ('assurance', 'isolation'):
        require_admin(request.user, space)
    if workspace not in ('assurance', 'isolation') or request.data or request.query_params:
        raise ValidationError('Requête invalide')
    if not settings.NEWT_STATUS_ENABLED or not settings.NEWT_USERNAME or not settings.NEWT_PASSWORD:
        raise Unavailable()
    try:
        with transaction.atomic():
            PhoneDirectoryGate.objects.get_or_create(pk=1)
            PhoneDirectoryGate.objects.filter(pk=1).update(revision=F('revision'))
            for space in ('assurance', 'isolation'):
                require_admin(request.user, space)
            member = Membership.objects.filter(
                pk=pk,
                workspace=workspace,
                role__in=('setter', 'administrator'),
                active=True,
                user__is_active=True,
            ).first()
            if member is None:
                raise ValidationError('Appelant actif introuvable dans cet espace')
            # Serialize with reassignment; never take the post from the browser.
            from django.contrib.auth import get_user_model

            get_user_model().objects.filter(pk=member.user_id).update(password=F('password'))
            link = PhoneExtension.objects.filter(
                user_id=member.user_id, extension__isnull=False
            ).first()
            if link is None:
                raise ValidationError('Aucun poste associé')
            observation = fetch_status(
                settings.NEWT_USERNAME, settings.NEWT_PASSWORD, link.extension
            )
            AccessAudit.objects.create(
                user=request.user,
                workspace=workspace,
                action='phone.status_read',
                metadata={'target_id': member.user_id, 'observations': observation['observations']},
            )
    except DirectoryUnavailable:
        raise Unavailable() from None
    labels = {'R': 'Sonnerie du poste', 'C': 'En communication', 'H': 'En attente'}
    response = Response(
        {
            'extension': link.extension,
            **observation,
            'states': [{'code': code, 'label': labels[code]} for code in observation['codes']],
            'definition': 'États du poste confirmés par Phonetico : R = Ringing, C = On Call, H = On Hold. Ils ne prouvent ni le décrochage humain du destinataire ni la validité de son numéro. Sans observation, disponibilité indéterminée.',
            'source': 'NEWT 244',
            'checked_at': timezone.now(),
        }
    )
    response['Cache-Control'] = 'no-store'
    return response
