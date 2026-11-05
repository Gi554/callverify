"""Mobile number an Isolation client chooses for its reminder SMS (empty until it is set)."""

from django.db import transaction
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .isolation_sms import destination
from .models import AccessAudit, Membership, ReminderPhone


def is_client(user):
    return Membership.objects.filter(
        user=user, workspace='isolation', role='client', active=True
    ).exists()


def mobile_of(user):
    row = ReminderPhone.objects.filter(user=user).first()
    return row.mobile if row else ''


def output(user):
    response = Response({'available': True, 'mobile': mobile_of(user)})
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['GET', 'PUT'])
def reminder_phone(request):
    if not is_client(request.user):
        response = Response({'available': False, 'mobile': ''})
        response['Cache-Control'] = 'no-store'
        return response
    if request.method == 'GET':
        return output(request.user)
    if set(request.data) - {'mobile'}:
        raise ValidationError('Champs non autorisés')
    raw = request.data.get('mobile', '')
    if not isinstance(raw, str) or len(raw) > 40:
        raise ValidationError({'mobile': 'Numéro de téléphone invalide.'})
    number = ''
    if raw.strip():
        number = destination(raw)
        if number is None:
            raise ValidationError({'mobile': 'Saisissez un numéro mobile canadien valide.'})
    with transaction.atomic():
        ReminderPhone.objects.update_or_create(user=request.user, defaults={'mobile': number})
        AccessAudit.objects.create(
            user=request.user,
            action='account.reminder_phone_changed',
            workspace='isolation',
            metadata={'set': bool(number)},
        )
    return output(request.user)
