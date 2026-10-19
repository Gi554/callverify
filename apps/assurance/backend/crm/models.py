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
    custom_values=models.JSONField(default=dict)
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
    revision=models.PositiveIntegerField(default=0)
    lease_owner_id=models.PositiveBigIntegerField(null=True,blank=True)
    lease_token=models.UUIDField(null=True,blank=True)
    lease_expires_at=models.DateTimeField(null=True,blank=True)

class AdvisorAssignment(models.Model):
    setter_id=models.PositiveBigIntegerField()
    setter_name=models.CharField(max_length=150)
    advisor_id=models.PositiveBigIntegerField()
    advisor_name=models.CharField(max_length=150)
    active=models.BooleanField(default=True)
    revision=models.PositiveIntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=['setter_id','advisor_id'],name='unique_assurance_assignment')]

class BusinessAudit(models.Model):
    actor_id=models.PositiveBigIntegerField()
    action=models.CharField(max_length=80)
    object_id=models.PositiveBigIntegerField()
    metadata=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)

class AdvisorSchedule(models.Model):
    # Serializes slot changes for the same advisor across all of their setters.
    advisor_id=models.PositiveBigIntegerField(primary_key=True)
    version=models.PositiveIntegerField(default=0)

class Appointment(models.Model):
    request_id=models.UUIDField(unique=True)
    fingerprint=models.CharField(max_length=64)
    contact=models.ForeignKey(Contact,on_delete=models.PROTECT,related_name='appointments')
    assignment=models.ForeignKey(AdvisorAssignment,on_delete=models.PROTECT,related_name='appointments')
    setter_id=models.PositiveBigIntegerField()
    setter_name=models.CharField(max_length=150)
    advisor_id=models.PositiveBigIntegerField(db_index=True)
    advisor_name=models.CharField(max_length=150)
    booked_by_id=models.PositiveBigIntegerField()
    starts_at=models.DateTimeField()
    ends_at=models.DateTimeField()
    timezone=models.CharField(max_length=100)
    status=models.CharField(max_length=20,default='scheduled',choices=[('scheduled','Planifié'),('cancelled','Annulé')])
    revision=models.PositiveIntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(ends_at__gt=models.F('starts_at')),name='appointment_positive_interval')]
        indexes=[models.Index(fields=['advisor_id','status','starts_at']),models.Index(fields=['setter_id','starts_at'])]

class AppointmentReport(models.Model):
    appointment=models.OneToOneField(Appointment,on_delete=models.PROTECT,related_name='report')
    performed=models.BooleanField()
    problem=models.BooleanField(default=False)
    note=models.TextField(blank=True)
    author_id=models.PositiveBigIntegerField()
    created_at=models.DateTimeField(auto_now_add=True)

class FollowUpTask(models.Model):
    policy_revision=models.PositiveIntegerField(default=0)
    revision=models.PositiveIntegerField(default=0)
    appointment=models.OneToOneField(Appointment,on_delete=models.PROTECT,related_name='follow_up')
    setter_id=models.PositiveBigIntegerField(db_index=True)
    reason=models.TextField()
    priority=models.CharField(max_length=20,default='normal')
    due_at=models.DateTimeField()
    closed_at=models.DateTimeField(null=True,blank=True)
    closed_by_id=models.PositiveBigIntegerField(null=True,blank=True)
    resolution=models.TextField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True)

class TaskNotification(models.Model):
    task=models.ForeignKey(FollowUpTask,on_delete=models.PROTECT,related_name='notifications')
    event_key=models.CharField(max_length=100,unique=True)
    kind=models.CharField(max_length=30)
    created_at=models.DateTimeField(auto_now_add=True)

class TaskNotificationRead(models.Model):
    notification=models.ForeignKey(TaskNotification,on_delete=models.CASCADE,related_name='receipts')
    user_id=models.PositiveBigIntegerField()
    read_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['notification','user_id'],name='unique_task_notification_read')]

class AppointmentIncident(models.Model):
    appointment=models.ForeignKey(Appointment,on_delete=models.PROTECT,related_name='incidents')
    request_id=models.UUIDField(unique=True)
    author_id=models.PositiveBigIntegerField()
    note=models.TextField()
    created_at=models.DateTimeField(auto_now_add=True)

class FollowUpPolicy(models.Model):
    id=models.PositiveSmallIntegerField(primary_key=True,default=1,editable=False)
    initial_hours=models.PositiveIntegerField(default=24)
    reopen_hours=models.PositiveIntegerField(default=24)
    default_priority=models.CharField(max_length=20,default='normal')
    revision=models.PositiveIntegerField(default=0)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(pk=1),name='single_follow_up_policy')]

class ContactNote(models.Model):
    contact=models.ForeignKey(Contact,on_delete=models.PROTECT,related_name='notes')
    request_id=models.UUIDField(unique=True)
    author_id=models.PositiveBigIntegerField()
    channel=models.CharField(max_length=20,choices=[('internal','Interne'),('advisor','Conseiller')])
    body=models.TextField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        indexes=[models.Index(fields=['contact','channel','author_id'])]

class ContactFieldSchema(models.Model):
    id=models.PositiveSmallIntegerField(primary_key=True,default=1,editable=False)
    fields=models.JSONField(default=list)
    revision=models.PositiveIntegerField(default=0)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(pk=1),name='single_contact_field_schema')]

class ContactDocument(models.Model):
    contact=models.ForeignKey(Contact,on_delete=models.PROTECT,related_name='documents')
    request_id=models.UUIDField(unique=True)
    author_id=models.PositiveBigIntegerField()
    channel=models.CharField(max_length=20,choices=[('internal','Interne'),('advisor','Conseiller')])
    filename=models.CharField(max_length=180)
    content_type=models.CharField(max_length=50)
    size=models.PositiveIntegerField()
    sha256=models.CharField(max_length=64)
    content=models.BinaryField()
    created_at=models.DateTimeField(auto_now_add=True)

class ContactPipeline(models.Model):
    id=models.PositiveSmallIntegerField(primary_key=True,default=1,editable=False)
    stages=models.JSONField(default=list)
    revision=models.PositiveIntegerField(default=0)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(pk=1),name='single_contact_pipeline')]

class ReminderPolicy(models.Model):
    id=models.PositiveSmallIntegerField(primary_key=True,default=1)
    tasks_enabled=models.BooleanField(default=True)
    reports_enabled=models.BooleanField(default=True)
    task_interval_hours=models.PositiveIntegerField(default=24)
    report_grace_hours=models.PositiveIntegerField(default=24)
    report_interval_hours=models.PositiveIntegerField(default=24)
    escalations_enabled=models.BooleanField(default=False)
    task_escalation_hours=models.PositiveIntegerField(default=72)
    report_escalation_hours=models.PositiveIntegerField(default=72)
    escalation_interval_hours=models.PositiveIntegerField(default=24)
    revision=models.PositiveIntegerField(default=0)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(pk=1),name='single_reminder_policy')]

class ReminderEvent(models.Model):
    event_key=models.CharField(max_length=64,unique=True)
    kind=models.CharField(max_length=30)
    appointment=models.ForeignKey(Appointment,on_delete=models.PROTECT,related_name='reminders')
    task=models.ForeignKey(FollowUpTask,on_delete=models.PROTECT,null=True,related_name='reminders')
    recipient_id=models.PositiveBigIntegerField()
    recipient_role=models.CharField(max_length=20)
    anchor_at=models.DateTimeField()
    policy_revision=models.PositiveIntegerField()
    valid_until=models.DateTimeField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=(models.Q(kind='task_overdue',task__isnull=False,recipient_role='setter')|models.Q(kind='report_missing',task__isnull=True,recipient_role='advisor')|
            models.Q(kind='task_escalation',task__isnull=False,recipient_role='administrator',recipient_id=0)|models.Q(kind='report_escalation',task__isnull=True,recipient_role='administrator',recipient_id=0)),name='reminder_kind_target')]
        indexes=[models.Index(fields=['recipient_id','recipient_role','valid_until'],name='reminder_active_recipient')]
