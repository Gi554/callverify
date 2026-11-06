from django.db import migrations


def replace_legacy_smoker(apps, schema_editor):
    Contact = apps.get_model('assurance', 'Contact')
    alias = schema_editor.connection.alias
    rows = Contact.objects.using(alias).exclude(assurance_qualification={})
    for row in rows.only('pk', 'assurance_qualification').iterator():
        values = dict(row.assurance_qualification or {})
        if 'smoker' in values:
            values.pop('smoker', None)
            values.setdefault('has_investments', None)
            Contact.objects.using(alias).filter(pk=row.pk).update(assurance_qualification=values)


def reverse_replace(apps, schema_editor):
    Contact = apps.get_model('assurance', 'Contact')
    alias = schema_editor.connection.alias
    rows = Contact.objects.using(alias).exclude(assurance_qualification={})
    for row in rows.only('pk', 'assurance_qualification').iterator():
        values = dict(row.assurance_qualification or {})
        values.pop('has_investments', None)
        Contact.objects.using(alias).filter(pk=row.pk).update(assurance_qualification=values)


class Migration(migrations.Migration):
    dependencies = [('assurance', '0041_payable_ledger')]

    operations = [migrations.RunPython(replace_legacy_smoker, reverse_replace)]
