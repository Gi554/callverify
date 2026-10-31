from celery import shared_task
from .services import process_import, run_lookup, build_export
from .models import ImportBatch
from .rate_limit import RateLimited


@shared_task(bind=True, max_retries=300)
def execute_delivery(self, pk):
    from .models import TaskDelivery

    row = TaskDelivery.objects.get(pk=pk)
    if row.status == 'completed':
        return
    try:
        from .voice import submit_attempt

        {
            'import': import_task,
            'lookup': lookup_task,
            'export': export_task,
            'voice': submit_attempt,
        }[row.kind](row.object_id)
        row.status = 'completed'
        row.error = ''
    except RateLimited as error:
        raise self.retry(exc=error, countdown=2)
    except Exception as error:
        row.status = 'failed'
        row.error = type(error).__name__
    row.save()


@shared_task
def dispatch_task():
    from .delivery import dispatch_pending

    dispatch_pending()


@shared_task
def purge_task():
    from .maintenance import purge_files

    return purge_files()


@shared_task(acks_late=True)
def import_task(batch_id):
    try:
        return process_import(batch_id)
    except Exception as error:
        ImportBatch.objects.filter(pk=batch_id).update(
            status='error', report={'error': type(error).__name__}
        )
        raise


@shared_task(rate_limit='5/s')
def lookup_task(check_id):
    run_lookup(check_id)


@shared_task
def export_task(job_id):
    build_export(job_id)


@shared_task
def isolation_reminders_task():
    from .isolation_reminders import generate

    return generate()
