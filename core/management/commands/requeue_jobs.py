from django.core.management.base import BaseCommand
from core.delivery import dispatch_pending

class Command(BaseCommand):
    help = 'Redispatcher les tâches en attente après une panne du broker. Ne relance pas les requêtes fournisseur incertaines.'
    def handle(self, *args, **options):
        dispatch_pending()
        self.stdout.write('Demandes en attente traitées ; les opérations fournisseur incertaines restent à examiner.')
