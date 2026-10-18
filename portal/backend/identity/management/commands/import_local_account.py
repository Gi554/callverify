"""Explicit local-only transition, preserving the existing password hash."""
import sqlite3
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand,CommandError

class Command(BaseCommand):
    help='Copier un compte local existant vers le portail, sans accorder de droits métier'
    def add_arguments(self,parser):parser.add_argument('username')
    def handle(self,username,**options):
        if not settings.DEBUG:raise CommandError('Migration locale seulement ; procédure production distincte requise')
        with sqlite3.connect((settings.BASE_DIR/'db.sqlite3').as_uri()+'?mode=ro',uri=True) as connection:
            row=connection.execute('SELECT username,password,email,is_active FROM core_adminuser WHERE username=?',(username,)).fetchone()
        if not row:raise CommandError('Compte historique absent')
        if get_user_model().objects.filter(username=username).exists():raise CommandError('Compte central déjà présent ; aucun écrasement')
        get_user_model().objects.create(username=row[0],password=row[1],email=row[2],is_active=bool(row[3]))
        self.stdout.write('Compte copié ; attribuer explicitement les espaces avec grant_workspace')
