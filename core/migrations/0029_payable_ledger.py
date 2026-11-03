from datetime import timedelta
from zoneinfo import ZoneInfo
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

ZONE = ZoneInfo('America/Toronto')


def backfill(apps, schema_editor):
    """Attendance already confirmed is counted in the week it was first recorded."""
    Result = apps.get_model('core', 'IsolationVisitResult')
    Entry = apps.get_model('core', 'PayableEntry')
    alias = schema_editor.connection.alias
    rows, seen = [], set()
    # One presence credit per process: the earliest confirmed visit of each process.
    ordered = (
        Result.objects.using(alias)
        .filter(performed=True)
        .select_related('visit')
        .order_by('created_at', 'pk')
    )
    for result in ordered:
        if result.visit.process_id in seen:
            continue
        seen.add(result.visit.process_id)
        day = result.created_at.astimezone(ZONE).date()
        rows.append(
            Entry(
                visit_id=result.visit_id,
                setter_id=result.visit.setter_id,
                setter_name=result.visit.setter_name,
                counted_at=result.created_at,
                week_start=day - timedelta(days=day.weekday()),
                closed_at_count=result.closed is True,
                confirmed_by_id=result.author_client_id or result.author_closer_id,
            )
        )
    Entry.objects.using(alias).bulk_create(rows, batch_size=500)


class Migration(migrations.Migration):
    dependencies = [('core', '0028_admin_alert_reviews')]

    operations = [
        migrations.CreateModel(
            name='PayableEntry',
            fields=[
                ('id', models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    )),
                ('setter_id', models.PositiveBigIntegerField(db_index=True)),
                ('setter_name', models.CharField(blank=True, max_length=150)),
                ('counted_at', models.DateTimeField(db_index=True)),
                ('week_start', models.DateField(db_index=True)),
                ('closed_at_count', models.BooleanField(default=False)),
                ('confirmed_by_id', models.PositiveBigIntegerField(blank=True, null=True)),
                ('withdrawn_at', models.DateTimeField(blank=True, null=True)),
                (
                    'visit',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='payable_entry',
                        to='core.isolationvisit',
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='PayableHistory',
            fields=[
                ('id', models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    )),
                ('kind', models.CharField(max_length=30)),
                ('old_value', models.CharField(blank=True, max_length=40)),
                ('new_value', models.CharField(blank=True, max_length=40)),
                ('late', models.BooleanField(default=False)),
                ('actor_id', models.PositiveBigIntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                (
                    'entry',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='history',
                        to='core.payableentry',
                    ),
                ),
            ],
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
