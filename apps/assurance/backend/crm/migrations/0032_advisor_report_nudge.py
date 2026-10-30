from django.db import migrations, models
from django.utils import timezone


def activate(apps, schema_editor):
    policy = apps.get_model('assurance', 'ReminderPolicy')
    # Existing policies start with future meetings, never a retrospective mail burst.
    policy.objects.filter(pk=1).update(
        report_grace_hours=1,
        report_reminders_from=timezone.now(),
    )


class Migration(migrations.Migration):
    dependencies = [('assurance', '0031_merge_20261025_1711')]
    operations = [
        migrations.AlterField(
            model_name='reminderpolicy',
            name='report_grace_hours',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='reminderpolicy',
            name='report_reminders_from',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.RunPython(activate, migrations.RunPython.noop),
    ]
