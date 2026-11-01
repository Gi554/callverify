"""Shared model definitions; each business app stores its own independent ledger."""

import uuid
from django.db import models


class Account(models.Model):
    agent_id = models.PositiveBigIntegerField(primary_key=True)
    revision = models.PositiveIntegerField(default=0)
    generated_cad = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    class Meta:
        abstract = True


class Terms(models.Model):
    agent_id = models.PositiveBigIntegerField(db_index=True)
    starts_on = models.DateField()
    ends_on = models.DateField()
    cadence = models.CharField(max_length=12, choices=[('week', 'Semaine'), ('mandate', 'Mandat')])
    target = models.PositiveIntegerField()
    attendance_cad = models.DecimalField(max_digits=10, decimal_places=2)
    bonus_cad = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    conditions = models.CharField(max_length=2000, blank=True)
    revision = models.PositiveIntegerField(default=0)
    actor_id = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_on__gte=models.F('starts_on')),
                name='%(app_label)s_%(class)s_dates',
            ),
            models.CheckConstraint(
                condition=models.Q(attendance_cad__gte=0, bonus_cad__gte=0),
                name='%(app_label)s_%(class)s_nonneg',
            ),
        ]


class Payment(models.Model):
    agent_id = models.PositiveBigIntegerField(db_index=True)
    request_id = models.UUIDField(default=uuid.uuid4, unique=True)
    fingerprint = models.CharField(max_length=64)
    amount_cad = models.DecimalField(max_digits=14, decimal_places=2)
    paid_on = models.DateField()
    reference = models.CharField(max_length=150)
    reference_key = models.CharField(max_length=64, unique=True)
    note = models.CharField(max_length=1000, blank=True)
    actor_id = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_cad__gt=0), name='%(app_label)s_%(class)s_positive'
            )
        ]


class Adjustment(models.Model):
    agent_id = models.PositiveBigIntegerField(db_index=True)
    before_cad = models.DecimalField(max_digits=16, decimal_places=2)
    after_cad = models.DecimalField(max_digits=16, decimal_places=2)
    delta_cad = models.DecimalField(max_digits=16, decimal_places=2)
    actor_id = models.PositiveBigIntegerField(null=True)
    reason = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
