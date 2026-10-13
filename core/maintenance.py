from datetime import timedelta
from django.utils import timezone
from .models import ExportJob, ImportBatch, PlatformSettings

def purge_files():
    config,_ = PlatformSettings.objects.get_or_create(pk=1)
    count = 0
    for job in ExportJob.objects.filter(expires_at__lte=timezone.now()).exclude(file=''):
        job.file.delete(save=False)
        job.status='expired';job.save(update_fields=['file','status']);count+=1
    for batch in ImportBatch.objects.filter(created_at__lt=timezone.now()-timedelta(days=config.import_retention_days),
            status__in=['completed','error']).exclude(original=''):
        batch.original.delete(save=True);count+=1
    return count
