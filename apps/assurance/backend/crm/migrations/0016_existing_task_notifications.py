from django.db import migrations

def populate(apps,schema_editor):
    Task=apps.get_model('assurance','FollowUpTask')
    Notification=apps.get_model('assurance','TaskNotification')
    alias=schema_editor.connection.alias
    for pk in Task.objects.using(alias).filter(closed_at__isnull=True,notifications__isnull=True).values_list('pk',flat=True).iterator():
        Notification.objects.using(alias).get_or_create(event_key=f'existing:{pk}',defaults={'task_id':pk,'kind':'existing'})

class Migration(migrations.Migration):
    dependencies=[('assurance','0015_tasknotification_tasknotificationread')]
    operations=[migrations.RunPython(populate,migrations.RunPython.noop)]
