"""Fixture de recette uniquement : à exécuter sur une base jetable, jamais en production."""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django

django.setup()
from django.conf import settings
from core.models import AdminUser, Campaign

if not settings.DEBUG or os.getenv('RECETTE_DISPOSABLE') != 'true':
    raise RuntimeError('Requires DEBUG=true and RECETTE_DISPOSABLE=true on a disposable database')
user = AdminUser.objects.create_user(
    'recette',
    password='LocalRecette-2026!',
    is_staff=True,
    is_superuser=True,
    mfa_enabled=True,
    mfa_secret='JBSWY3DPEHPK3PXP',
    email='recette@example.invalid',
)
Campaign.objects.create(
    owner=user,
    name='Recette · Canada',
    source='Données fictives',
    purpose='Qualification de démonstration',
    budget=10,
)
print('Fixture recette créée dans la base jetable.')
