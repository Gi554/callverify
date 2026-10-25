from django.conf import settings
from django.db import models

ROLES = {
    'assurance': {'administrator', 'setter', 'advisor'},
    'isolation': {'administrator', 'setter', 'client', 'closer'},
}


class PhoneCallAttempt(models.Model):
    request_id = models.UUIDField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    workspace = models.CharField(max_length=20, default='assurance')
    contact_id = models.PositiveBigIntegerField()
    contact_label = models.CharField(max_length=120, blank=True, default='')
    extension = models.CharField(max_length=10)
    fingerprint = models.CharField(max_length=64)
    state = models.CharField(max_length=20, default='dispatching')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Keyed digest of the dialed number: matches the NEWT 511 journal without storing it.
    destination_digest = models.CharField(max_length=64, blank=True, default='')
    journal_status = models.CharField(max_length=20, default='pending')
    journal_started_at = models.DateTimeField(null=True, blank=True)
    journal_duration = models.PositiveIntegerField(null=True, blank=True)
    journal_checked_at = models.DateTimeField(null=True, blank=True)


class Membership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='workspace_memberships'
    )
    workspace = models.CharField(max_length=20, choices=[(key, key) for key in ROLES])
    role = models.CharField(max_length=30)
    active = models.BooleanField(default=True)
    # Assurance advisors only: total prospects (booked appointments) owed to their client.
    prospect_quota = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'workspace'], name='unique_workspace_membership'
            ),
            models.UniqueConstraint(
                fields=['workspace'],
                condition=models.Q(workspace='isolation', role='client'),
                name='single_isolation_client',
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.role not in ROLES.get(self.workspace, set()):
            raise ValidationError('Rôle incompatible avec cet espace')


class AccessAudit(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=60)
    workspace = models.CharField(max_length=20, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SessionGeneration(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True
    )
    generation = models.PositiveBigIntegerField(default=0)


class CalendarConnection(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    workspace = models.CharField(max_length=20)
    provider = models.CharField(max_length=20, blank=True)
    payload = models.TextField(blank=True)
    connected = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True)
    revision = models.PositiveIntegerField(default=0)
    auto_sync = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'workspace'], name='unique_owner_workspace_calendar'
            )
        ]


class CalendarAuthorization(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    workspace = models.CharField(max_length=20)
    provider = models.CharField(max_length=20)
    state_hash = models.CharField(max_length=64, unique=True)
    session_hash = models.CharField(max_length=64)
    verifier = models.TextField()
    revision = models.PositiveIntegerField()
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)


class CalendlyConnection(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    payload = models.TextField(blank=True)
    connected = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True)
    checked_at = models.DateTimeField(null=True)
    revision = models.PositiveIntegerField(default=0)


class CalendlyAuthorization(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    state_hash = models.CharField(max_length=64, unique=True)
    session_hash = models.CharField(max_length=64)
    verifier = models.TextField()
    revision = models.PositiveIntegerField()
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)


class CalendarSync(models.Model):
    import uuid

    connection = models.ForeignKey(
        CalendarConnection, on_delete=models.PROTECT, related_name='events'
    )
    source_id = models.PositiveBigIntegerField()
    key = models.UUIDField(default=uuid.uuid4, unique=True)
    provider = models.CharField(max_length=20)
    remote_id = models.CharField(max_length=2048, blank=True)
    source_revision = models.IntegerField(default=-1)
    fingerprint = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, default='pending')
    error_code = models.CharField(max_length=40, blank=True)
    checked_at = models.DateTimeField(null=True)
    create_attempted = models.BooleanField(default=False)
    expected_start = models.DateTimeField(null=True)
    expected_end = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['connection', 'source_id'], name='unique_calendar_sync_source'
            )
        ]


class Invitation(models.Model):
    import uuid

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField()
    workspace = models.CharField(max_length=20)
    role = models.CharField(max_length=30)
    prospect_quota = models.PositiveIntegerField(null=True, blank=True)
    issuer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    token_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True)
    revoked_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower('username'), name='invitation_username_ci'
            ),
            models.UniqueConstraint(models.functions.Lower('email'), name='invitation_email_ci'),
        ]


class PortalMail(models.Model):
    import uuid

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    workspace = models.CharField(max_length=20, blank=True)
    payload = models.TextField()
    status = models.CharField(max_length=12, default='pending')
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField()
    lease_until = models.DateTimeField(null=True)
    claim = models.UUIDField(null=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        indexes = [models.Index(fields=['status', 'next_attempt_at'], name='portal_mail_due')]


class AssuranceMailRelay(models.Model):
    stream = models.CharField(max_length=20, default='incidents')
    event_id = models.PositiveBigIntegerField()
    recipient_id = models.PositiveBigIntegerField()
    mail = models.OneToOneField(PortalMail, null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['stream', 'event_id', 'recipient_id'],
                name='unique_assurance_mail_stream_event_recipient',
            )
        ]


class AssuranceMailCursor(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    after_id = models.PositiveBigIntegerField(default=0)


class PhoneExtension(models.Model):
    # One PBX for this deployment; same user may use the same post in both workspaces.
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    extension = models.CharField(max_length=10, unique=True, null=True)
    revision = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class PhoneDirectoryGate(models.Model):
    # Serialize provider directory reads across API workers, no cached personnel data.
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    revision = models.PositiveIntegerField(default=0)


class CallRules(models.Model):
    """Single row: the hours during which a call may be placed, in one time zone."""

    id = models.PositiveSmallIntegerField(primary_key=True)
    enforce_hours = models.BooleanField(default=True)
    timezone = models.CharField(max_length=60, default='America/Montreal')
    weekday_start = models.TimeField(default='09:30')
    weekday_end = models.TimeField(default='21:30')
    weekend_start = models.TimeField(default='10:00')
    weekend_end = models.TimeField(default='18:00')
    revision = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class CallExclusion(models.Model):
    """Do-not-call list: a refused number is never dialed, whoever the caller is."""

    number = models.CharField(max_length=11, unique=True)
    reason = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+'
    )
