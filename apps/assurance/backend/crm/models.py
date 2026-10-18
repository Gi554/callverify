from django.db import models

class ContactImport(models.Model):
    request_id=models.UUIDField(unique=True)
    fingerprint=models.CharField(max_length=64)
    filename=models.CharField(max_length=250)
    created_by_id=models.PositiveBigIntegerField()
    created_at=models.DateTimeField(auto_now_add=True)
    total=models.PositiveIntegerField()
    imported=models.PositiveIntegerField()
    rejected=models.PositiveIntegerField()
    report=models.JSONField(default=list)
    columns=models.JSONField(default=list)
    mapping=models.JSONField(default=dict)

class Contact(models.Model):
    import_batch=models.ForeignKey(ContactImport,null=True,blank=True,on_delete=models.SET_NULL,related_name='contacts')
    source_row=models.PositiveIntegerField(null=True,blank=True)
    source_values=models.JSONField(default=list)
    name=models.CharField(max_length=250)
    phone=models.CharField(max_length=250)  # Original value; no technical normalization.
    email=models.EmailField(blank=True)
    status=models.CharField(max_length=40,default='to_contact')
    assigned_advisor_id=models.PositiveBigIntegerField(null=True,blank=True)
    created_by_id=models.PositiveBigIntegerField()
    updated_at=models.DateTimeField(auto_now=True)

class BusinessAudit(models.Model):
    actor_id=models.PositiveBigIntegerField()
    action=models.CharField(max_length=80)
    object_id=models.PositiveBigIntegerField()
    created_at=models.DateTimeField(auto_now_add=True)
