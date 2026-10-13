from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connection
class Command(BaseCommand):
    help='Vérifier les prérequis configurés pour une mise en production, sans appels fournisseur.'
    def handle(self,*args,**options):
        checks={'DEBUG désactivé':not settings.DEBUG,'PostgreSQL configuré':connection.vendor=='postgresql',
            'Clé MFA fournie':bool(settings.MFA_ENCRYPTION_KEY),'SMTP configuré':bool(settings.EMAIL_HOST_USER),
            'Lookup configuré':bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN),
            'Origine HTTPS du frontend':settings.FRONTEND_URL.startswith('https://')}
        for name,ok in checks.items():self.stdout.write(f'{"OK" if ok else "À CONFIGURER"}: {name}')
        if not all(checks.values()):raise CommandError('Compléter les informations de déploiement et relancer ce contrôle.')
