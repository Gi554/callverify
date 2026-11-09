"""New-account invitations: no access exists before a single-use acceptance."""

import hashlib
import secrets
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .mail_queue import enqueue
from .email_layout import layout, first_name
from django.db import transaction, IntegrityError
from django.db.models import Q, F
from django.utils import timezone
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .models import Invitation, Membership, AccessAudit, ROLES, ReminderPhone
from .management_api import (
    require_admin,
    lock_admin,
    AccessInput,
    AccessPagination,
    release_previously_deleted_login,
)
from .client_policy import available as client_available
from .advisor_quotas import quota_field, check_quota
from .recovery import public_url, ResetThrottle


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


class InviteInput(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    role = serializers.CharField()
    prospect_quota = quota_field()
    mobile = serializers.CharField(required=False, allow_blank=True, max_length=40)

    def validate_username(self, value):
        return AccessInput().validate_username(value)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        if data['role'] not in ROLES[self.context['workspace']]:
            raise ValidationError('Rôle incompatible avec cet espace')
        check_quota(self.context['workspace'], data['role'], data.get('prospect_quota'))
        if data.get('mobile'):
            from .isolation_sms import destination

            value = destination(data['mobile'])
            if not value:
                raise ValidationError({'mobile': 'Numéro mobile canadien invalide'})
            data['mobile'] = value
        return data


def output(row):
    return {
        'id': str(row.pk),
        'username': row.username,
        'email': row.email,
        'role': row.role,
        'mobile': row.mobile,
        'prospect_quota': row.prospect_quota,
        'expires_at': row.expires_at,
        'status': 'accepted'
        if row.accepted_at
        else 'revoked'
        if row.revoked_at
        else 'expired'
        if row.expires_at <= timezone.now()
        else 'pending',
    }


def available(username, email):
    if (
        get_user_model()
        .objects.filter(Q(username__iexact=username) | Q(email__iexact=email))
        .exists()
    ):
        raise ValidationError('Compte déjà présent : utilisez l’association d’un compte existant')


SPACES = {'assurance': 'Assurance', 'isolation': 'Isolation'}
ROLE_NAMES = {
    'administrator': 'Administrateur',
    'setter': 'Setter',
    'advisor': 'Conseiller',
    'client': 'Client',
}


def deliver(row, token):
    space = SPACES.get(row.workspace, row.workspace)
    role = ROLE_NAMES.get(row.role, row.role)
    link = f'{public_url()}/crm#invite={row.pk}:{token}'
    assurance_advisor = row.workspace == 'assurance' and row.role == 'advisor'
    if assurance_advisor:
        role = 'Conseiller en sécurité financière'
        subject = 'Bienvenue dans l’univers de Martinien !'
        title = 'Bienvenue dans l’univers de Martinien !'
        intro = (
            'Je suis ravi de pouvoir collaborer avec vous. Dans le cadre de notre partenariat, '
            'je vous invite à accéder à ORVIA, ma plateforme professionnelle dédiée à la '
            'transmission et au suivi de vos rendez-vous.'
        )
        signature = 'Martinien Affanoukpe'
        notice = (
            'Ce lien personnel expire dans 24 heures et ne peut être utilisé qu’une seule fois. '
            'Si vous n’attendiez pas cette invitation, veuillez me contacter.'
        )
        greeting_name = first_name(row.username).split(' ', 1)[0]
    else:
        subject = f'Orvia CRM — Votre invitation à l’espace {space}'
        title = 'Bienvenue dans votre équipe'
        intro = (
            f'Vous êtes invité dans l’espace {space} en tant que {role}. '
            'Activez votre compte en choisissant votre mot de passe.'
        )
        signature = 'l’équipe Orvia CRM'
        notice = (
            'Ce lien personnel expire dans 24 heures et ne peut être utilisé qu’une fois. '
            'Si vous n’attendiez pas cette invitation, contactez votre administrateur.'
        )
        greeting_name = row.username
    if assurance_advisor:
        greeting = f'Bonjour {greeting_name},' if greeting_name else 'Bonjour,'
        body = (
            f'Bienvenue dans l’univers de Martinien !\n\n{greeting}\n\n'
            f'{intro}\n\n'
            'Vous avez été invité en qualité de Conseiller en sécurité financière dans votre '
            'espace Assurance.\n\nEspace : Assurance\n'
            'Votre rôle : Conseiller en sécurité financière\n'
            f'Votre identifiant : {row.username}\n\n'
            f'ACTIVER MON COMPTE\n{link}\n\n{notice}\n\n'
            'Cordialement,\nMartinien Affanoukpe\n\n'
            'Gardez vos liens d’accès confidentiels : aucun mot de passe ne vous sera jamais '
            'demandé par e-mail.'
        )
    else:
        body = (
            f'Bonjour,\n\nVous êtes invité dans l’espace {space} en tant que {role}.\n'
            f'Votre identifiant : {row.username}\n\n'
            'Pour activer votre compte, ouvrez ce lien et choisissez votre mot de passe :\n'
            f'{link}\n\n'
            'Ce lien expire dans 24 heures. Ensuite, connectez-vous avec votre identifiant '
            f'et votre mot de passe : votre espace {space} s’ouvrira directement.\n\nOrvia CRM'
        )
    enqueue(
        user=row.issuer,
        workspace=row.workspace,
        subject=subject,
        html=layout(
            title=title,
            intro=intro,
            details=(
                ('Votre espace' if assurance_advisor else 'Espace', space),
                ('Votre rôle', role),
                ('Votre identifiant', row.username),
            ),
            action='ACTIVER MON COMPTE' if assurance_advisor else 'Activer mon compte',
            name=greeting_name,
            url=link,
            notice=notice,
            signature=signature,
        ),
        body=body,
        recipient=row.email,
        guard={'kind': 'invitation', 'id': str(row.pk), 'hash': row.token_hash},
        expires_at=row.expires_at,
    )
    return True


@api_view(['GET', 'POST'])
def invitations(request, workspace):
    require_admin(request.user, workspace)
    if request.method == 'GET':
        pager = AccessPagination()
        page = pager.paginate_queryset(
            Invitation.objects.filter(workspace=workspace)
            .exclude(role='closer')
            .order_by('-created_at'),
            request,
        )
        response = pager.get_paginated_response([output(row) for row in page])
        response['Cache-Control'] = 'no-store'
        return response
    data = InviteInput(data=request.data, context={'workspace': workspace})
    data.is_valid(raise_exception=True)
    values = data.validated_data
    token = secrets.token_urlsafe(32)
    try:
        with transaction.atomic():
            lock_admin(request.user, workspace)
            # Accounts deleted by older builds were anonymised but could retain
            # their old login. Release that stale identity before checking
            # uniqueness so the same account can be invited again.
            release_previously_deleted_login(values['username'])
            available(values['username'], values['email'])
            client_available(workspace, values['role'])
            if Invitation.objects.filter(username__iexact=values['username']).exists():
                raise ValidationError(
                    'Identifiant déjà invité ; renvoyez ou révoquez l’invitation existante'
                )
            row = Invitation.objects.create(
                **values,
                workspace=workspace,
                issuer=request.user,
                token_hash=digest(token),
                expires_at=timezone.now() + timedelta(hours=24),
            )
            AccessAudit.objects.create(
                user=request.user,
                workspace=workspace,
                action='invitation.created',
                metadata={
                    'invitation': str(row.pk),
                    'role': row.role,
                    'prospect_quota': row.prospect_quota,
                },
            )
            deliver(row, token)
    except IntegrityError:
        raise ValidationError('Identifiant déjà utilisé')
    return Response({**output(row), 'mail_queued': True}, status=201)


@api_view(['POST', 'DELETE'])
def invitation_action(request, workspace, pk):
    require_admin(request.user, workspace)
    if request.method == 'DELETE':
        with transaction.atomic():
            lock_admin(request.user, workspace)
            row = Invitation.objects.select_for_update().filter(pk=pk, workspace=workspace).first()
            if not row:
                return Response({'detail': 'Invitation introuvable'}, status=404)
            if row.accepted_at:
                return Response({'detail': 'Une invitation acceptée ne peut pas être supprimée'}, status=409)
            AccessAudit.objects.create(
                user=request.user,
                workspace=workspace,
                action='invitation.deleted',
                metadata={
                    'invitation': str(row.pk),
                    'username': row.username,
                    'email': row.email,
                    'role': row.role,
                },
            )
            row.delete()
        return Response(status=204)
    if set(request.data) != {'action'} or request.data['action'] not in ('revoke', 'resend'):
        raise ValidationError('Action invalide')
    token = secrets.token_urlsafe(32)
    with transaction.atomic():
        lock_admin(request.user, workspace)
        row = Invitation.objects.select_for_update().filter(pk=pk, workspace=workspace).first()
        if not row:
            return Response({'detail': 'Invitation introuvable'}, status=404)
        if row.accepted_at or row.revoked_at or row.role not in ROLES.get(workspace, set()):
            return Response({'detail': 'Invitation déjà clôturée'}, status=409)
        if request.data['action'] == 'revoke':
            row.revoked_at = timezone.now()
        else:
            client_available(workspace, row.role)
            available(row.username, row.email)
            row.issuer = request.user
            row.token_hash = digest(token)
            row.expires_at = timezone.now() + timedelta(hours=24)
        row.save()
        AccessAudit.objects.create(
            user=request.user,
            workspace=workspace,
            action='invitation.' + request.data['action'],
            metadata={'invitation': str(row.pk)},
        )
        if request.data['action'] == 'resend':
            deliver(row, token)
    return Response({**output(row), 'mail_queued': request.data['action'] == 'resend'})


class AcceptInput(serializers.Serializer):
    id = serializers.UUIDField()
    token = serializers.CharField(max_length=100, write_only=True)
    password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)
    confirmation = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        if data['password'] != data['confirmation']:
            raise ValidationError('La confirmation ne correspond pas')
        return data


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([ResetThrottle])
def accept(request):
    SessionAuthentication().enforce_csrf(request)
    data = AcceptInput(data=request.data)
    data.is_valid(raise_exception=True)
    values = data.validated_data
    try:
        with transaction.atomic():
            # Match administration's lock order: workspace grants, then invitation.
            initial = Invitation.objects.filter(pk=values['id']).first()
            if not initial:
                raise ValidationError('Invitation invalide ou expirée')
            lock_admin(initial.issuer, initial.workspace)
            if not Invitation.objects.filter(pk=initial.pk).update(token_hash=F('token_hash')):
                raise ValidationError('Invitation invalide ou expirée')
            row = Invitation.objects.get(pk=initial.pk)
            if (
                row.role not in ROLES.get(row.workspace, set())
                or row.accepted_at
                or row.revoked_at
                or row.expires_at <= timezone.now()
                or not secrets.compare_digest(row.token_hash, digest(values['token']))
            ):
                raise ValidationError('Invitation invalide ou expirée')
            if not row.issuer.is_active or row.issuer_id != initial.issuer_id:
                raise ValidationError('Invitation indisponible')
            available(row.username, row.email)
            client_available(row.workspace, row.role)
            user = get_user_model()(username=row.username, email=row.email)
            try:
                validate_password(values['password'], user)
            except DjangoValidationError as error:
                raise ValidationError({'password': error.messages})
            user.set_password(values['password'])
            user.save()
            Membership.objects.create(
                user=user,
                workspace=row.workspace,
                role=row.role,
                prospect_quota=row.prospect_quota,
            )
            if row.mobile:
                ReminderPhone.objects.update_or_create(user=user, defaults={'mobile': row.mobile})
            row.accepted_at = timezone.now()
            row.save(update_fields=['accepted_at'])
            AccessAudit.objects.create(
                user=user,
                workspace=row.workspace,
                action='invitation.accepted',
                metadata={'invitation': str(row.pk), 'issuer': row.issuer_id, 'role': row.role},
            )
    except IntegrityError:
        raise ValidationError('Compte déjà présent ou invitation déjà utilisée')
    response = Response(status=204)
    response['Cache-Control'] = 'no-store'
    return response
