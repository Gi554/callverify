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


class Invitation(models.Model):
    import uuid
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    username = models.CharField(max_length=150,unique=True)
    email = models.EmailField()
    workspace = models.CharField(max_length=20)
    role = models.CharField(max_length=30)
    issuer = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    token_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True)
    revoked_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(models.functions.Lower('username'),name='invitation_username_ci'),
            models.UniqueConstraint(models.functions.Lower('email'),name='invitation_email_ci')]
