from django.core.management.base import BaseCommand
from core.models import AdminUser
class Command(BaseCommand):
    help='Chiffrer les anciens secrets MFA avant le déploiement.'
    def handle(self,*args,**options):
        count=0
        for user in AdminUser.objects.exclude(mfa_secret='').exclude(mfa_secret__startswith='enc:'):
            user.save(update_fields=['mfa_secret']);count+=1
        self.stdout.write(f'{count} secrets chiffrés')
