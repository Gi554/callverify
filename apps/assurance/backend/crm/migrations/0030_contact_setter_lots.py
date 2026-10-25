from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('assurance', '0029_advisorschedule_availability_and_more')]

    operations = [
        migrations.AddField(
            model_name='contact',
            name='assigned_setter_id',
            field=models.PositiveBigIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='contact',
            name='assigned_setter_name',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
        migrations.AddField(
            model_name='contact',
            name='assigned_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
