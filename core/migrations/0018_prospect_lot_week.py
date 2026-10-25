from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0017_isolationfollowup')]

    operations = [
        migrations.AddField(
            model_name='prospect',
            name='lot_week',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='prospect',
            name='assigned_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
