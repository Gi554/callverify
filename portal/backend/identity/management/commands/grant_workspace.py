from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand,CommandError
from portal.backend.identity.models import Membership,ROLES,AccessAudit

class Command(BaseCommand):
    help='Accorder un rôle dans un espace à un compte central existant'
    def add_arguments(self,parser):
        parser.add_argument('username');parser.add_argument('workspace',choices=ROLES)
        parser.add_argument('role')
    def handle(self,username,workspace,role,**options):
        if role not in ROLES[workspace]:raise CommandError('Rôle incompatible')
        user=get_user_model().objects.filter(username=username).first()
        if not user:raise CommandError('Créer le compte central avant attribution')
        obj,_=Membership.objects.update_or_create(user=user,workspace=workspace,defaults={'role':role,'active':True})
        AccessAudit.objects.create(user=user,action='membership.granted',workspace=workspace)
        self.stdout.write(f'{workspace} : rôle {obj.role} accordé')
