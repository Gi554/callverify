"""Assurance payroll; no shared rows with Isolation and no payment execution."""

import json
from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from packages import payroll_service as service
from . import models


class Store:
    workspace = 'assurance'
    Account = models.SetterPayrollAccount
    Terms = models.SetterPayrollTerms
    Payment = models.SetterPayrollPayment
    Adjustment = models.SetterPayrollAdjustment

    @staticmethod
    def roster():
        from .compensation import roster

        return roster()

    @staticmethod
    def validate_agent(request, agent, proof):
        if agent not in Store.roster():
            raise ValidationError('Setter Assurance connu requis.')

    @staticmethod
    def earned(agent, lower=None, upper=None):
        rows = models.Appointment.objects.filter(
            setter_id=agent, status='scheduled', report__performed=True, ends_at__lte=timezone.now()
        )
        if lower is not None:
            rows = rows.filter(starts_at__gte=lower, starts_at__lt=upper)
        amount = rows.aggregate(amount=Sum('report__unit_rate_cad'))['amount'] or Decimal('0')
        return {
            'attendance_amount_cad': service.money(amount),
            'sale_bonus_cad': '0.00',
            'attendance': rows.count(),
            'sales': 0,
            'unpriced': rows.filter(report__unit_rate_cad__isnull=True).count(),
            'amount': rows.aggregate(amount=Sum('report__unit_rate_cad'))['amount'] or Decimal('0'),
        }

    @staticmethod
    def audit(actor, agent, action, data):
        models.BusinessAudit.objects.create(
            actor_id=actor or agent,
            object_id=agent,
            action='payroll.' + action,
            metadata=json.loads(json.dumps({'setter_id': agent, **data}, default=str)),
        )


@api_view(['GET'])
def overview(request, agent=None):
    return service.overview(Store, request, agent)


@api_view(['POST'])
def terms(request, agent, pk=None):
    return service.set_terms(Store, request, agent, pk)


@api_view(['POST'])
def payment(request, agent):
    try:
        return service.record_payment(Store, request, agent)
    except ValidationError as exc:
        if request.user.role == 'administrator':
            Store.audit(
                request.user.pk, agent, 'payment_rejected', {'reason': str(exc.detail)[:1000]}
            )
        raise


def reconcile(agent, actor=None, correction=False):
    return service.reconcile(Store, agent, actor, record_increase=correction)


def active_terms(agent):
    return service.active_term(Store, agent)
