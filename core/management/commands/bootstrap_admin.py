import base64
import getpass
import secrets
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.password_validation import validate_password
from core.models import AdminUser

class Command(BaseCommand):
    help = 'Créer le premier superadministrateur avec MFA, dans un terminal privé.'
    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('--email', default='')
    def handle(self, *args, **options):
        if AdminUser.objects.filter(is_superuser=True).exists():
            raise CommandError('Un superadministrateur existe déjà')
        password = getpass.getpass('Mot de passe (12 caractères minimum): ')
        validate_password(password)
        secret = base64.b32encode(secrets.token_bytes(20)).decode()
        user = AdminUser.objects.create_superuser(options['username'], options['email'], password,
            mfa_secret=secret, mfa_enabled=True)
        from core.security import generate_backup_codes
        self.stdout.write('Codes de secours à conserver en coffre privé: ' + ', '.join(generate_backup_codes(user)))
        self.stdout.write(f'Compte créé: {user.username}. Ajouter ce secret à votre application TOTP: {secret}')
        self.stdout.write('Conserver le secret en coffre privé. Il ne sera plus affiché par la plateforme.')
