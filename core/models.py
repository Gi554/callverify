from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from uuid import uuid4


class AdminUser(AbstractUser):
    mfa_secret = models.CharField(max_length=512, blank=True)
    mfa_enabled = models.BooleanField(default=False)
    last_mfa_step = models.BigIntegerField(default=-1)
    backup_codes = models.JSONField(default=list)

    def save(self, *args, **kwargs):
        from .security import encrypt_secret

        if self.mfa_secret and not self.mfa_secret.startswith('enc:'):
            self.mfa_secret = encrypt_secret(self.mfa_secret)
        super().save(*args, **kwargs)


class Campaign(models.Model):
    owner = models.ForeignKey(AdminUser, on_delete=models.PROTECT)
    # Legacy CallVerify campaigns remain owned by a local administrator.  CRM
    # campaigns have an explicit central workspace marker and are only exposed
    # through the scoped Isolation qualification API.
    portal_workspace = models.CharField(max_length=30, blank=True, db_index=True)
    portal_owner_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    name = models.CharField(max_length=200)
    purpose = models.TextField()
    source = models.CharField(max_length=250)
    status = models.CharField(max_length=30, default='draft')
    budget = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    spent = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class PhoneNumber(models.Model):
    e164 = models.CharField(max_length=16, unique=True)
    country = models.CharField(max_length=2, blank=True)
    validity = models.CharField(max_length=20, default='valid')
    line_status = models.CharField(max_length=20, default='unknown')
    carrier = models.CharField(max_length=200, blank=True)
    line_type = models.CharField(max_length=40, blank=True)


class ImportBatch(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='imports')
    original = models.FileField(upload_to='imports/%Y/%m/')
    mapping = models.JSONField(default=dict)
    sheet = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=30, default='preview')
    report = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class Prospect(models.Model):
    c2 = models.JSONField(default=dict)
    commercial_status = models.CharField(max_length=30, default='to_contact')
    callback_at = models.DateTimeField(null=True, blank=True, db_index=True)
    assigned_setter_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    assigned_setter_name = models.CharField(max_length=150, blank=True)
    assignment_revision = models.PositiveIntegerField(default=0)
    # Weekly lot handed out by an administrator: Monday of the week and moment of the hand-out.
    lot_week = models.DateField(null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='prospects')
    phone = models.ForeignKey(PhoneNumber, null=True, on_delete=models.PROTECT)
    name = models.CharField(max_length=250, blank=True)
    reference = models.CharField(max_length=250, blank=True)
    raw_phone = models.CharField(max_length=250)
    validity = models.CharField(max_length=20, default='indeterminate')
    reason = models.TextField(blank=True)
    compliance = models.CharField(max_length=20, default='review')
    compliance_reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['campaign', 'phone'], name='unique_campaign_phone')
        ]


class ImportRow(models.Model):
    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name='rows')
    prospect = models.ForeignKey(Prospect, null=True, on_delete=models.SET_NULL)
    line = models.PositiveIntegerField()
    source = models.JSONField(default=dict)
    duplicate = models.BooleanField(default=False)
    error = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['batch', 'line'], name='unique_import_line')]


class LookupCheck(models.Model):
    phone = models.ForeignKey(PhoneNumber, on_delete=models.CASCADE, related_name='checks')
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, default='pending')
    response = models.JSONField(default=dict)
    error = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=4, null=True)
    packages = models.CharField(max_length=250, blank=True)
    provider_code = models.CharField(max_length=40, blank=True)
    checked_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ConsentEvidence(models.Model):
    prospect = models.ForeignKey(Prospect, on_delete=models.CASCADE, related_name='consents')
    basis = models.CharField(max_length=200)
    evidence = models.TextField()
    recorded_by = models.ForeignKey(AdminUser, on_delete=models.PROTECT)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


class Suppression(models.Model):
    e164 = models.CharField(max_length=16, unique=True)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class CallCampaign(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='call_campaigns')
    status = models.CharField(max_length=30, default='draft')
    compliance_approved = models.BooleanField(default=False)
    configuration = models.JSONField(default=dict)


class CallAttempt(models.Model):
    call_campaign = models.ForeignKey(CallCampaign, on_delete=models.CASCADE)
    prospect = models.ForeignKey(Prospect, on_delete=models.PROTECT)
    sid = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=30, default='queued')
    duration = models.PositiveIntegerField(default=0)
    amd = models.CharField(max_length=30, default='unknown')
    rang_at = models.DateTimeField(null=True)
    answered_at = models.DateTimeField(null=True)
    amd_checked_at = models.DateTimeField(null=True)
    amd_requested = models.BooleanField(default=False)
    error_code = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(default=timezone.now, null=True)
    updated_at = models.DateTimeField(auto_now=True)


class WebhookEvent(models.Model):
    fingerprint = models.CharField(max_length=64, unique=True)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class ExportJob(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    author = models.ForeignKey(AdminUser, on_delete=models.PROTECT)
    format = models.CharField(max_length=4, default='csv')
    filters = models.JSONField(default=dict)
    columns = models.JSONField(default=list)
    status = models.CharField(max_length=20, default='pending')
    file = models.FileField(upload_to='exports/%Y/%m/', blank=True)
    expires_at = models.DateTimeField()
    error = models.TextField(blank=True)


class AuditEvent(models.Model):
    actor = models.ForeignKey(AdminUser, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class PlatformSettings(models.Model):
    lookup_cache_hours = models.PositiveIntegerField(default=168)
    lookup_rate = models.PositiveIntegerField(default=5)
    export_hours = models.PositiveIntegerField(default=24)
    import_retention_days = models.PositiveIntegerField(default=90)
    currency = models.CharField(max_length=3, default='CAD')


class TaskDelivery(models.Model):
    kind = models.CharField(max_length=20)
    object_id = models.PositiveBigIntegerField()
    status = models.CharField(max_length=20, default='pending', db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    error = models.CharField(max_length=120, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['kind', 'object_id'], name='unique_task_delivery')
        ]


class ProspectActivity(models.Model):
    prospect = models.ForeignKey(Prospect, on_delete=models.PROTECT, related_name='activities')
    request_id = models.UUIDField(unique=True)
    fingerprint = models.CharField(max_length=64)
    author_portal_id = models.PositiveBigIntegerField()
    author_role = models.CharField(max_length=20)
    kind = models.CharField(max_length=20)
    body = models.TextField()
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class ProspectActivityShare(models.Model):
    activity = models.ForeignKey(
        ProspectActivity, on_delete=models.PROTECT, related_name='client_shares'
    )
    client_id = models.PositiveBigIntegerField()
    visible = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['activity', 'client_id'], name='unique_activity_client_share'
            )
        ]


class IsolationFollowUp(models.Model):
    absence_visit = models.OneToOneField(
        'IsolationVisit',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='absence_task',
    )
    prospect = models.ForeignKey(Prospect, on_delete=models.PROTECT, related_name='follow_ups')
    request_id = models.UUIDField(unique=True)
    fingerprint = models.CharField(max_length=64)
    created_by_id = models.PositiveBigIntegerField(null=True)
    note = models.TextField(blank=True)
    due_at = models.DateTimeField(db_index=True)
    revision = models.PositiveIntegerField(default=0)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    resolution = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class IsolationVisit(models.Model):
    process_id = models.UUIDField(default=uuid4, db_index=True, editable=False)
    previous_visit = models.OneToOneField(
        'self', on_delete=models.PROTECT, null=True, blank=True, related_name='next_visit'
    )
    publication = models.CharField(max_length=20, default='internal')
    publication_status = models.CharField(max_length=20, default='internal')
    publication_error = models.CharField(max_length=40, blank=True)
    publication_checked_at = models.DateTimeField(null=True, blank=True)
    closer_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    closer_name = models.CharField(max_length=150, blank=True)
    c2_snapshot = models.JSONField(default=dict)
    prospect = models.ForeignKey(Prospect, on_delete=models.PROTECT, related_name='visits')
    request_id = models.UUIDField(unique=True)
    fingerprint = models.CharField(max_length=64)
    client_id = models.PositiveBigIntegerField(db_index=True)
    client_name = models.CharField(max_length=150)
    setter_id = models.PositiveBigIntegerField()
    setter_name = models.CharField(max_length=150)
    booked_by_id = models.PositiveBigIntegerField()
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    timezone = models.CharField(max_length=100)
    status = models.CharField(max_length=20, default='scheduled')
    revision = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F('starts_at')),
                name='isolation_visit_positive_interval',
            )
        ]
        indexes = [models.Index(fields=['client_id', 'status', 'starts_at'])]


class IsolationReminderPolicy(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    enabled = models.BooleanField(default=True)
    delay_hours = models.PositiveIntegerField(default=24)
    revision = models.PositiveIntegerField(default=0)
    active_from = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(pk=1), name='single_isolation_reminder_policy'
            )
        ]


class IsolationNotice(models.Model):
    anchor_at = models.DateTimeField(null=True, blank=True)
    visit = models.ForeignKey(IsolationVisit, on_delete=models.PROTECT, related_name='notices')
    recipient_id = models.PositiveBigIntegerField(db_index=True)
    recipient_role = models.CharField(max_length=20)
    kind = models.CharField(max_length=30)
    event_key = models.CharField(max_length=150, unique=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class IsolationWorkingHours(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    enabled = models.BooleanField(default=False)
    windows = models.JSONField(default=list)
    revision = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(pk=1), name='single_isolation_working_hours')
        ]


class IsolationVisitCalendar(models.Model):
    client_id = models.PositiveBigIntegerField(primary_key=True)
    version = models.PositiveIntegerField(default=0)


class IsolationVisitResult(models.Model):
    visit = models.OneToOneField(IsolationVisit, on_delete=models.PROTECT, related_name='result')
    author_client_id = models.PositiveBigIntegerField(null=True, blank=True)
    author_closer_id = models.PositiveBigIntegerField(null=True, blank=True)
    closed = models.BooleanField(null=True, blank=True)
    performed = models.BooleanField()
    outcome = models.CharField(max_length=30)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class IsolationVisitSupplement(models.Model):
    visit = models.ForeignKey(IsolationVisit, on_delete=models.PROTECT, related_name='supplements')
    request_id = models.UUIDField(unique=True)
    author_client_id = models.PositiveBigIntegerField()
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class IsolationAssignmentBatch(models.Model):
    request_id = models.UUIDField(unique=True)
    actor_portal_id = models.PositiveBigIntegerField()
    fingerprint = models.CharField(max_length=64)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
