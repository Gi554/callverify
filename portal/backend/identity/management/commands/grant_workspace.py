from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from portal.backend.identity.models import Membership, ROLES, AccessAudit
from portal.backend.identity.client_policy import available, immutable
from django.db import transaction, IntegrityError
from rest_framework.exceptions import ValidationError


class Command(BaseCommand):
    help = 'Accorder un rôle dans un espace à un compte central existant'

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('workspace', choices=ROLES)
        parser.add_argument('role')

    def handle(self, username, workspace, role, **options):
        if role not in ROLES[workspace]:
            raise CommandError('Rôle incompatible')
        user = get_user_model().objects.filter(username=username).first()
        if not user:
            raise CommandError('Créer le compte central avant attribution')
        try:
            with transaction.atomic():
                row = Membership.objects.filter(user=user, workspace=workspace).first()
                if row:
                    immutable(row, role)
                available(workspace, role, exclude=row.pk if row else None)
                obj, _ = Membership.objects.update_or_create(
                    user=user, workspace=workspace, defaults={'role': role, 'active': True}
                )
                AccessAudit.objects.create(
                    user=user, action='membership.granted', workspace=workspace
                )
        except (ValidationError, IntegrityError):
            raise CommandError(
                'Client Isolation unique permanent : réactivez son compte existant ; aucune attribution modifiée.'
            ) from None
        self.stdout.write(f'{workspace} : rôle {obj.role} accordé')
