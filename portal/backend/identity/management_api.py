"""Delegated access administration, strictly confined to the actor's workspace."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction, IntegrityError
from django.db.models import Q, F, Exists, OuterRef
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .models import Membership, AccessAudit, ROLES
from .client_policy import available as client_available, immutable as client_immutable
from .advisor_quotas import quota_field, check_quota


def require_admin(user, workspace):
    if (
        workspace not in ROLES
        or not Membership.objects.filter(
            user=user, workspace=workspace, role='administrator', active=True
        ).exists()
    ):
        raise PermissionDenied('Administration non autorisée dans cet espace')


def lock_admin(user, workspace):
    # A consistent order serializes concurrent changes to this workspace's grants.
    rows = list(Membership.objects.select_for_update().filter(workspace=workspace).order_by('pk'))
    if not any(
        row.user_id == user.pk and row.active and row.role == 'administrator' for row in rows
    ):
        raise PermissionDenied('Administration non autorisée dans cet espace')
    return rows


class MembershipOutput(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    can_delete = serializers.SerializerMethodField()

    def get_can_delete(self, row):
        protected = getattr(row, '_protected_account', None)
        if protected is None:
            protected = Membership.objects.filter(
                user_id=row.user_id, role='administrator'
            ).exists()
        return not (protected or row.user.is_staff or row.user.is_superuser)

    account_active = serializers.BooleanField(source='user.is_active', read_only=True)

    class Meta:
        model = Membership
        fields = [
            'id',
            'username',
            'email',
            'role',
            'active',
            'account_active',
            'prospect_quota',
            'can_delete',
        ]


class AccessInput(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(
        required=False, write_only=True, trim_whitespace=False, max_length=256
    )
    role = serializers.CharField()
    existing = serializers.BooleanField(default=False)
    prospect_quota = quota_field()

    def validate_username(self, value):
        for validator in get_user_model()._meta.get_field('username').validators:
            try:
                validator(value)
            except DjangoValidationError:
                raise serializers.ValidationError('Identifiant invalide')
        return value

    def validate_role(self, value):
        if value not in ROLES[self.context['workspace']]:
            raise serializers.ValidationError('Rôle incompatible avec cet espace')
        return value

    def validate(self, data):
        if data['existing']:
            if data.get('password') or data.get('email'):
                raise serializers.ValidationError(
                    'Aucun changement du compte existant n’est autorisé ici'
                )
        else:
            if not data.get('password'):
                raise serializers.ValidationError({'password': 'Mot de passe initial requis'})
            candidate = get_user_model()(username=data['username'], email=data.get('email', ''))
            try:
                validate_password(data['password'], candidate)
            except DjangoValidationError as error:
                raise serializers.ValidationError({'password': error.messages})
        return data


class GrantUpdate(serializers.Serializer):
    role = serializers.CharField(required=False)
    active = serializers.BooleanField(required=False)
    prospect_quota = quota_field()

    def validate(self, data):
        if not data:
            raise serializers.ValidationError('Aucune modification fournie')
        if 'role' in data and data['role'] not in ROLES[self.context['workspace']]:
            raise serializers.ValidationError({'role': 'Rôle incompatible avec cet espace'})
        return data


class AccessPagination(PageNumberPagination):
    page_size = 25


@api_view(['GET', 'POST'])
def users(request, workspace):
    require_admin(request.user, workspace)
    if request.method == 'GET':
        qs = (
            Membership.objects.filter(workspace=workspace)
            .exclude(role='closer')
            .annotate(
                _protected_account=Exists(
                    Membership.objects.filter(user_id=OuterRef('user_id'), role='administrator')
                )
            )
            .select_related('user')
            .order_by('user__username', 'pk')
        )
        term = request.query_params.get('search', '').strip()[:150]
        if term:
            qs = qs.filter(Q(user__username__icontains=term) | Q(user__email__icontains=term))
        pager = AccessPagination()
        page = pager.paginate_queryset(qs, request)
        return pager.get_paginated_response(MembershipOutput(page, many=True).data)
    serializer = AccessInput(data=request.data, context={'workspace': workspace})
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    check_quota(workspace, values['role'], values.get('prospect_quota'))
    try:
        with transaction.atomic():
            lock_admin(request.user, workspace)
            client_available(workspace, values['role'])
            if values['existing']:
                user = (
                    get_user_model()
                    .objects.select_for_update()
                    .filter(username=values['username'], is_active=True)
                    .first()
                )
                if not user:
                    raise ValidationError('Compte indisponible ou déjà associé à cet espace')
            else:
                if get_user_model().objects.filter(username=values['username']).exists():
                    raise ValidationError(
                        'Identifiant indisponible ; utilisez l’ajout d’un compte existant si vous êtes autorisé'
                    )
                user = get_user_model().objects.create_user(
                    values['username'], password=values['password'], email=values.get('email', '')
                )
            if Membership.objects.filter(user=user, workspace=workspace).exists():
                raise ValidationError('Compte indisponible ou déjà associé à cet espace')
            row = Membership.objects.create(
                user=user,
                workspace=workspace,
                role=values['role'],
                prospect_quota=values.get('prospect_quota'),
            )
            AccessAudit.objects.create(
                user=request.user,
                action='membership.granted',
                workspace=workspace,
                metadata={
                    'subject': user.pk,
                    'role': row.role,
                    'existing': values['existing'],
                    'prospect_quota': row.prospect_quota,
                },
            )
    except IntegrityError:
        raise ValidationError('Identifiant ou accès déjà utilisé')
    return Response(MembershipOutput(row).data, status=201)


@api_view(['PATCH', 'DELETE'])
def update_access(request, workspace, pk):
    require_admin(request.user, workspace)
    if request.method == 'DELETE':
        return remove_access(request, workspace, pk)
    serializer = GrantUpdate(data=request.data, context={'workspace': workspace})
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        rows = lock_admin(request.user, workspace)
        row = next((item for item in rows if item.pk == pk), None)
        if not row:
            return Response({'detail': 'Accès introuvable dans cet espace'}, status=404)
        if row.user_id == request.user.pk:
            raise ValidationError('Modification de votre propre accès interdite')
        get_user_model().objects.select_for_update().get(pk=row.user_id)
        before = {'role': row.role, 'active': row.active, 'prospect_quota': row.prospect_quota}
        changes = dict(serializer.validated_data)
        role = changes.get('role', row.role)
        if role not in ROLES[workspace]:
            raise ValidationError({'role': 'Rôle retiré : choisissez un rôle disponible.'})
        client_immutable(row, role)
        client_available(workspace, role, exclude=row.pk)
        # Leaving the advisor role drops a quota that no longer applies.
        if role != 'advisor' and row.prospect_quota is not None:
            changes.setdefault('prospect_quota', None)
        check_quota(workspace, role, changes.get('prospect_quota', row.prospect_quota))
        for key, value in changes.items():
            setattr(row, key, value)
        row.save(update_fields=list(changes))
        AccessAudit.objects.create(
            user=request.user,
            action='membership.updated',
            workspace=workspace,
            metadata={
                'subject': row.user_id,
                'before': before,
                'after': {
                    'role': row.role,
                    'active': row.active,
                    'prospect_quota': row.prospect_quota,
                },
            },
        )
    return Response(MembershipOutput(row).data)


class DeleteInput(serializers.Serializer):
    confirm_username = serializers.CharField(max_length=150, trim_whitespace=False)
    reason = serializers.CharField(max_length=1000)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError('Champs non autorisés.')
        return data


def remove_access(request, workspace, pk):
    data = DeleteInput(data=request.data)
    data.is_valid(raise_exception=True)
    from .models import (
        CalendarConnection,
        CalendarAuthorization,
        CalendlyConnection,
        PhoneExtension,
        SessionGeneration,
    )

    with transaction.atomic():
        rows = lock_admin(request.user, workspace)
        row = next((item for item in rows if item.pk == pk), None)
        if row is None:
            return Response({'detail': 'Accès introuvable dans cet espace.'}, status=404)
        subject = get_user_model().objects.select_for_update().get(pk=row.user_id)
        if (
            subject.pk == request.user.pk
            or subject.is_staff
            or subject.is_superuser
            or Membership.objects.filter(user=subject, role='administrator').exists()
        ):
            raise PermissionDenied(
                'Un administrateur ne peut pas supprimer un compte administrateur.'
            )
        if subject.username != data.validated_data['confirm_username']:
            raise ValidationError('Saisissez exactement l’identifiant du compte à supprimer.')
        before = {'role': row.role, 'active': row.active, 'prospect_quota': row.prospect_quota}
        row.delete()
        remaining = Membership.objects.filter(user=subject).exists()
        CalendarConnection.objects.filter(user=subject, workspace=workspace).update(
            connected=False,
            auto_sync=False,
            payload='',
            expires_at=None,
            revision=F('revision') + 1,
        )
        CalendarAuthorization.objects.filter(user=subject, workspace=workspace).update(
            used=True, verifier=''
        )
        if workspace == 'assurance':
            CalendlyConnection.objects.filter(user=subject).update(
                connected=False, payload='', expires_at=None, revision=F('revision') + 1
            )
        if not remaining:
            # Keep the historical identity because calls, audit and financial records reference it.
            subject.is_active = False
            subject.save(update_fields=['is_active'])
            SessionGeneration.objects.get_or_create(user=subject)
            SessionGeneration.objects.filter(user=subject).update(generation=F('generation') + 1)
            PhoneExtension.objects.filter(user=subject).update(
                extension=None, revision=F('revision') + 1
            )
        AccessAudit.objects.create(
            user=request.user,
            workspace=workspace,
            action='membership.deleted',
            metadata={
                'subject': subject.pk,
                'subject_username': subject.username,
                'before': before,
                'after': {'deleted': True, 'active': False},
                'account_disabled': not remaining,
                'reason': data.validated_data['reason'],
            },
        )
    result = Response(
        {'deleted': True, 'account_disabled': not remaining, 'history_preserved': True}
    )
    result['Cache-Control'] = 'no-store'
    return result
