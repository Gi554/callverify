from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('assurance', '0043_contact_phone_normalized')]

    operations = [
        migrations.CreateModel(
            name='CallSessionProgress',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('portal_user_id', models.PositiveBigIntegerField(unique=True)),
                ('active', models.BooleanField(default=False)),
                ('visited_contact_ids', models.JSONField(default=list)),
                ('current_contact_id', models.PositiveBigIntegerField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
