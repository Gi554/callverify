"""Manual local assignments only. No provider connector or network operation."""

from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.db.models import F, Q
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .models import PhoneExtension, Membership, AccessAudit
from .management_api import require_admin, lock_admin, AccessPagination
from .calendars import StrictInput, validated


class AssignmentInput(StrictInput):
    membership_id = serializers.IntegerField(min_value=1)
    extension = serializers.RegexField(r'^[0-9]{1,10}$', required=False)
    revision = serializers.IntegerField(min_value=0, required=False)
    remove = serializers.BooleanField(default=False)
    reason = serializers.CharField(max_length=1000)

    def validate(self, data):
        super().validate(data)
        if not data['remove'] and not data.get('extension'):
            raise ValidationError('Poste requis')
        return data


@api_view(['GET', 'POST'])
def assignments(request, workspace):
    require_admin(request.user, workspace)
    targets = (
        Membership.objects.filter(workspace=workspace)
        .filter(Q(role='setter') | Q(user__phoneextension__extension__isnull=False))
        .select_related('user')
        .order_by('pk')
    )
    if request.method == 'GET':
        pager = AccessPagination()
        rows = pager.paginate_queryset(targets, request)
        links = {
            link.user_id: link
            for link in PhoneExtension.objects.filter(user_id__in=[row.user_id for row in rows])
        }
        response = pager.get_paginated_response(
            [
                {
                    'membership_id': row.pk,
                    'username': row.user.username,
                    'eligible': row.role == 'setter' and row.active and row.user.is_active,
                    'extension': (links[row.user_id].extension or '')
                    if row.user_id in links
                    else '',
                    'revision': links[row.user_id].revision if row.user_id in links else None,
                }
                for row in rows
            ]
        )
        response['Cache-Control'] = 'no-store'
        return response
    data = validated(AssignmentInput, request.data)
    try:
        with transaction.atomic():
            lock_admin(request.user, workspace)
            target = targets.filter(pk=data['membership_id']).first()
            if target is None:
                raise ValidationError('Setter introuvable dans cet espace')
            get_user_model().objects.filter(pk=target.user_id).update(password=F('password'))
            target.user.refresh_from_db()
            # A physical post is global to a user, so other-space admins must not change it.
            other = (
                Membership.objects.filter(user=target.user, role='setter', active=True)
                .exclude(workspace=workspace)
                .exists()
            )
            if other:
                for space in Membership.objects.filter(
                    user=target.user, role='setter', active=True
                ).values_list('workspace', flat=True):
                    require_admin(request.user, space)
            link = PhoneExtension.objects.filter(user=target.user).first()
            before = link.extension if link else ''
            if link:
                if data.get('revision') != link.revision:
                    raise ValidationError('Association modifiée : actualisez')
                if data['remove']:
                    if not PhoneExtension.objects.filter(pk=link.pk, revision=link.revision).update(
                        extension=None, revision=F('revision') + 1
                    ):
                        raise ValidationError('Association modifiée : actualisez')
                else:
                    if target.role != 'setter' or not target.active or not target.user.is_active:
                        raise ValidationError('Setter actif requis')
                    if not PhoneExtension.objects.filter(pk=link.pk, revision=link.revision).update(
                        extension=data['extension'], revision=F('revision') + 1
                    ):
                        raise ValidationError('Association modifiée : actualisez')
            else:
                if data.get('revision') is not None or data['remove']:
                    raise ValidationError('Association absente : actualisez')
                if target.role != 'setter' or not target.active or not target.user.is_active:
                    raise ValidationError('Setter actif requis')
                PhoneExtension.objects.create(user=target.user, extension=data['extension'])
            AccessAudit.objects.create(
                user=request.user,
                workspace=workspace,
                action='phone.extension_assigned',
                metadata={
                    'target_id': target.user_id,
                    'before': before,
                    'after': '' if data['remove'] else data['extension'],
                    'reason': data['reason'],
                },
            )
    except IntegrityError:
        raise ValidationError(
            'Ce poste est déjà associé : aucune modification enregistrée'
        ) from None
    return Response(status=204)
