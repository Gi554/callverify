from django.core.management.base import BaseCommand
from core.maintenance import purge_files
class Command(BaseCommand):
    help='Purger les fichiers expirés selon les paramètres de conservation, en conservant les rapports.'
    def handle(self,*args,**options):
        self.stdout.write(f'{purge_files()} fichiers purgés')
