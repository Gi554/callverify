"""Soumettre un import de 1000 lignes fictives via Redis, dans une base jetable."""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from core.models import AdminUser,Campaign,ImportBatch
from core.delivery import enqueue
if not settings.DEBUG or os.getenv('RECETTE_DISPOSABLE')!='true':
    raise RuntimeError('Disposable development database required')
user=AdminUser.objects.get(username='recette')
with transaction.atomic():
    campaign=Campaign.objects.create(owner=user,name='Recette asynchrone · 1000 lignes',source='Données fictives',purpose='Validation des workers')
    content='telephone,nom\n'+''.join(f'416555{100+i%100:04d},Contact fictif {i}\n' for i in range(1000))
    batch=ImportBatch.objects.create(campaign=campaign,status='queued',mapping={'phone':'telephone','name':'nom'})
    batch.original.save('recette-1000.csv',ContentFile(content.encode()))
    enqueue('import',batch.pk)
print('Import de recette soumis:',batch.pk)
