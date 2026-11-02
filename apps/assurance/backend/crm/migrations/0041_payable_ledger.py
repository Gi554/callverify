from datetime import timedelta
from zoneinfo import ZoneInfo
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

ZONE = ZoneInfo('America/Toronto')


def backfill(apps, schema_editor):
    """Attendance already confirmed is counted in the week it was first recorded."""
    Report = apps.get_model('assurance', 'AppointmentReport')
    Entry = apps.get_model('assurance', 'PayableEntry')
    alias = schema_editor.connection.alias
    rows = []
    for report in Report.objects.using(alias).filter(performed=True).select_related('appointment'):
        day = report.created_at.astimezone(ZONE).date()
        rows.append(
            Entry(
                appointment_id=report.appointment_id,
                setter_id=report.appointment.setter_id,
                setter_name=report.appointment.setter_name,
                counted_at=report.created_at,
                week_start=day - timedelta(days=day.weekday()),
                confirmed_by_id=report.author_id,
            )
        )
    Entry.objects.using(alias).bulk_create(rows, batch_size=500)


class Migration(migrations.Migration):
    dependencies = [('assurance', '0040_admin_alert_reviews')]

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
                ('confirmed_by_id', models.PositiveBigIntegerField(blank=True, null=True)),
                ('withdrawn_at', models.DateTimeField(blank=True, null=True)),
                (
                    'appointment',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='payable_entry',
                        to='assurance.appointment',
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
                        to='assurance.payableentry',
                    ),
                ),
            ],
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
