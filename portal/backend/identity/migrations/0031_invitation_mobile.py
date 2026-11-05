from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('identity', '0030_reminder_phone')]

    operations = [
        migrations.AddField(
            model_name='invitation',
            name='mobile',
            field=models.CharField(blank=True, default='', max_length=10),
        ),
    ]
