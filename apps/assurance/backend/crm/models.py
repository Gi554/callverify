from django.db import models

class Contact(models.Model):
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
