"""Append-only ledger of appointments counted as payable, shared by Assurance and Isolation.

Rules (client validation, November 2026):
- an appointment is counted once, in the week the attendance is confirmed, whatever its planned
  date was;
- a week already closed is never modified: a confirmation or correction made later is counted in
  the current week, and a later withdrawal is only kept in the history;
- in Isolation the category (closed or not) is frozen when counted: a later sale is recorded in
  the history but does not move the appointment nor count it a second time.
"""

from datetime import timedelta
from django.db.models.signals import post_save, pre_save
from django.utils import timezone
from .quebec_period import ZONE


def current_time():
    return timezone.now()


def week_of(moment):
    day = moment.astimezone(ZONE).date()
    return day - timedelta(days=day.weekday())


def connect(result_model, entry_model, history_model, parent, split_sales=False, process=None):
    """Keep the ledger in step with every saved result, whichever screen recorded it."""

    def before(sender, instance, **kwargs):
        instance._payable_before = None
        if instance.pk:
            fields = ['performed'] + (['closed'] if split_sales else [])
            instance._payable_before = (
                result_model.objects.filter(pk=instance.pk).values(*fields).first()
            )

    def after(sender, instance, created, **kwargs):
        now = current_time()
        item = getattr(instance, parent)
        entry = entry_model.objects.filter(**{parent: item}).first()
        previous = getattr(instance, '_payable_before', None)
        closed = getattr(instance, 'closed', None) is True
        actor = (
            getattr(instance, 'author_id', None)
            or getattr(instance, 'author_client_id', None)
            or getattr(instance, 'author_closer_id', None)
        )
        week = week_of(now)

        def note(kind, old='', new='', late=False):
            history_model.objects.create(
                entry=entry,
                kind=kind,
                old_value=old,
                new_value=new,
                late=late,
                actor_id=actor,
                created_at=now,
            )

        if instance.performed:
            extra = {'closed_at_count': closed} if split_sales else {}
            if (
                entry is None
                and process
                and (
                    entry_model.objects.filter(
                        **{f'{parent}__{process}': getattr(item, process)},
                        withdrawn_at__isnull=True,
                    )
                    .exclude(**{parent: item})
                    .exists()
                )
            ):
                # One presence credit per process: a further visit of the same prospect
                # process (reschedule, relaunch) is a new occurrence, never a second payment.
                return
            if entry is None:
                entry = entry_model.objects.create(
                    **{parent: item},
                    setter_id=item.setter_id,
                    setter_name=item.setter_name,
                    counted_at=now,
                    week_start=week,
                    confirmed_by_id=actor,
                    **extra,
                )
                note('counted')
            elif entry.withdrawn_at is not None:
                # Confirmed again after a withdrawal: counted now, in the current week.
                entry.counted_at, entry.week_start, entry.withdrawn_at = now, week, None
                entry.confirmed_by_id = actor
                if split_sales:
                    entry.closed_at_count = closed
                entry.save()
                note('counted')
            elif split_sales and previous is not None and (previous['closed'] is True) != closed:
                # The commercial status moves; the paid appointment stays where it was counted.
                note(
                    'sale_status_changed',
                    'closed' if previous['closed'] is True else 'not_closed',
                    'closed' if closed else 'not_closed',
                    late=closed and entry.week_start < week,
                )
        elif entry is not None and entry.withdrawn_at is None:
            if entry.week_start == week:
                entry.withdrawn_at = now
                entry.save(update_fields=['withdrawn_at'])
                note('withdrawn')
            else:
                note('withdrawn_after_week')

    uid = f'payable-ledger-{result_model.__name__}'
    pre_save.connect(before, sender=result_model, weak=False, dispatch_uid=uid + '-pre')
    post_save.connect(after, sender=result_model, weak=False, dispatch_uid=uid + '-post')
