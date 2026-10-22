from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import TaskDelivery


def enqueue(kind, object_id):
    delivery, _ = TaskDelivery.objects.get_or_create(kind=kind, object_id=object_id)
    transaction.on_commit(lambda: dispatch(delivery.pk))
    return delivery


def dispatch(pk):
    from .tasks import execute_delivery

    with transaction.atomic():
        delivery = TaskDelivery.objects.select_for_update().get(pk=pk)
        if delivery.status != 'pending' or delivery.available_at > timezone.now():
            return
        delivery.status = 'dispatched'
        delivery.attempts += 1
        delivery.save()
    try:
        execute_delivery.delay(pk)
    except Exception as error:
        # Persisted outbox survives a failed publish, without failing the API request.
        TaskDelivery.objects.filter(pk=pk, status='dispatched').update(
            status='failed' if delivery.attempts >= 25 else 'pending',
            available_at=timezone.now()
            + timedelta(seconds=min(300, 2 ** min(delivery.attempts, 8))),
            error=type(error).__name__,
        )


def dispatch_pending():
    from .models import ImportBatch, ExportJob, LookupCheck, CallAttempt

    stale = timezone.now() - timedelta(minutes=35)
    for row in TaskDelivery.objects.filter(status='dispatched', updated_at__lt=stale):
        model = {
            'import': ImportBatch,
            'export': ExportJob,
            'lookup': LookupCheck,
            'voice': CallAttempt,
        }[row.kind]
        obj = model.objects.filter(pk=row.object_id).first()
        if obj and obj.status in ('pending', 'queued'):
            row.status = 'pending'
            row.save()
        elif obj and obj.status == 'completed':
            row.status = 'completed'
            row.save()
        else:
            row.status = 'failed'
            row.error = 'Opération interrompue à examiner'
            row.save()
    for pk in TaskDelivery.objects.filter(
        status='pending', available_at__lte=timezone.now()
    ).values_list('pk', flat=True)[:500]:
        dispatch(pk)
