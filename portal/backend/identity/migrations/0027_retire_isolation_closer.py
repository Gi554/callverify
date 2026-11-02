from django.db import migrations
from django.db.models import F
from django.utils import timezone


def retire_closers(apps, schema_editor):
    Membership = apps.get_model('identity', 'Membership')
    Audit = apps.get_model('identity', 'AccessAudit')
    Generation = apps.get_model('identity', 'SessionGeneration')
    Invitation = apps.get_model('identity', 'Invitation')
    for row in Membership.objects.filter(workspace='isolation', role='closer', active=True):
        row.active = False
        row.save(update_fields=['active'])
        generation, _ = Generation.objects.get_or_create(user_id=row.user_id)
        Generation.objects.filter(pk=generation.pk).update(generation=F('generation') + 1)
        Audit.objects.create(
            action='membership.role_retired', workspace='isolation',
            metadata={'subject': row.user_id, 'before': {'role': 'closer', 'active': True},
                      'after': {'role': 'closer', 'active': False},
                      'reason': 'Suppression du rôle Closer ; suivi assuré par le client Isolation.'},
        )
    Invitation.objects.filter(workspace='isolation', role='closer', accepted_at__isnull=True,
                              revoked_at__isnull=True).update(revoked_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [('identity', '0026_generated_reports')]
    operations = [migrations.RunPython(retire_closers, migrations.RunPython.noop)]
