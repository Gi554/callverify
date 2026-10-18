from django.conf import settings
from django.db import models

ROLES = {
    'assurance': {'administrator','setter','advisor'},
    'isolation': {'administrator','setter','client'},
}

class Membership(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='workspace_memberships')
    workspace = models.CharField(max_length=20,choices=[(key,key) for key in ROLES])
    role = models.CharField(max_length=30)
    active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['user','workspace'],name='unique_workspace_membership')]
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.role not in ROLES.get(self.workspace,set()):
            raise ValidationError('Rôle incompatible avec cet espace')

class AccessAudit(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True)
    action = models.CharField(max_length=60)
    workspace = models.CharField(max_length=20,blank=True)
    metadata = models.JSONField(default=dict,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
