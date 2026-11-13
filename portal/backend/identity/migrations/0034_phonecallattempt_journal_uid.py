from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('identity', '0033_platformincident')]

    operations = [
        migrations.AddField(
            model_name='phonecallattempt',
            name='journal_uid',
            field=models.CharField(blank=True, default='', max_length=80),
        ),
    ]
