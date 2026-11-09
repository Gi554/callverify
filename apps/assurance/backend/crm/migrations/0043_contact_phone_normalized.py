import re

from django.db import migrations, models


def normalize(value):
    digits = re.sub(r'\D', '', str(value or ''))
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    return digits[:32]


def backfill(apps, schema_editor):
    Contact = apps.get_model('assurance', 'Contact')
    alias = schema_editor.connection.alias
    for row in Contact.objects.using(alias).only('pk', 'phone').iterator():
        Contact.objects.using(alias).filter(pk=row.pk).update(phone_normalized=normalize(row.phone))


class Migration(migrations.Migration):
    dependencies = [('assurance', '0042_replace_smoker_qualification')]

    operations = [
        migrations.AddField(
            model_name='contact',
            name='phone_normalized',
            field=models.CharField(blank=True, db_index=True, default='', max_length=32),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
