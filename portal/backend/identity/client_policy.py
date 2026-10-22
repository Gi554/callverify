"""Isolation has one permanent client slot; Assurance advisors are independent."""

from rest_framework.exceptions import ValidationError
from .models import Membership


def available(workspace, role, exclude=None):
    if workspace != 'isolation' or role != 'client':
        return
    qs = Membership.objects.filter(workspace='isolation', role='client')
    if exclude is not None:
        qs = qs.exclude(pk=exclude)
    if qs.exists():
        raise ValidationError(
            'Le client unique Isolation est déjà configuré, même si son accès est suspendu. Réactivez son compte existant.'
        )


def immutable(row, role):
    if row.workspace == 'isolation' and row.role == 'client' and role != 'client':
        raise ValidationError(
            'Le rôle du client unique Isolation est permanent. Vous pouvez suspendre ou réactiver son accès.'
        )
