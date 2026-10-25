from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('identity', '0019_calendlyauthorization_calendlyconnection'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CallRules',
            fields=[
                ('id', models.PositiveSmallIntegerField(primary_key=True, serialize=False)),
                ('enforce_hours', models.BooleanField(default=True)),
                ('timezone', models.CharField(default='America/Montreal', max_length=60)),
                ('weekday_start', models.TimeField(default='09:30')),
                ('weekday_end', models.TimeField(default='21:30')),
                ('weekend_start', models.TimeField(default='10:00')),
                ('weekend_end', models.TimeField(default='18:00')),
                ('revision', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='CallExclusion',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                ('number', models.CharField(max_length=11, unique=True)),
                ('reason', models.CharField(blank=True, default='', max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'created_by',
                    models.ForeignKey(
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name='+',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
