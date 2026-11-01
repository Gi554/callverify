"""Isolation payroll; data and permissions stay in the Isolation database."""

import json
from decimal import Decimal
from django.db.models import Sum
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from packages import payroll_service as service
from .isolation_work import WorkAuthentication
from . import models


class Store:
    workspace = 'isolation'
    Account = models.IsolationPayrollAccount
    Terms = models.IsolationPayrollTerms
    Payment = models.IsolationPayrollPayment
    Adjustment = models.IsolationPayrollAdjustment

    @staticmethod
    def roster():
        names = dict(models.IsolationSetterRate.objects.values_list('setter_id', 'setter_name'))
        names.update(
            dict(
                models.IsolationVisit.objects.order_by('pk').values_list('setter_id', 'setter_name')
            )
        )
        return names

    @staticmethod
    def validate_agent(request, agent, proof):
        from .isolation_compensation import rate_claims

        claims = rate_claims(proof, request.user)
        if claims['setter']['id'] != agent:
            raise ValidationError('Attestation d’agent incompatible.')
        models.IsolationSetterRate.objects.get_or_create(
            setter_id=agent,
            client_id=claims['client']['id'],
            defaults={
                'setter_name': claims['setter']['name'],
                'client_name': claims['client']['name'],
            },
        )

    @staticmethod
    def earned(agent, lower=None, upper=None):
        from .isolation_compensation import credited

        total = Decimal('0')
        result = {
            'attendance': 0,
            'sales': 0,
            'unpriced': 0,
            'attendance_amount_cad': '0.00',
            'sale_bonus_cad': '0.00',
        }
        for component, label, field in [
            ('attendance', 'attendance', 'attendance_unit_cad'),
            ('sale', 'sales', 'sale_unit_cad'),
        ]:
            rows = credited(component).filter(setter_id=agent)
            if lower is not None:
                rows = rows.filter(starts_at__gte=lower, starts_at__lt=upper)
            result[label] = rows.count()
            result['unpriced'] += rows.filter(**{'result__' + field + '__isnull': True}).count()
            amount = rows.aggregate(amount=Sum('result__' + field))['amount'] or Decimal('0')
            result['attendance_amount_cad' if component == 'attendance' else 'sale_bonus_cad'] = (
                service.money(amount)
            )
            total += amount
        return {**result, 'amount': total}

    @staticmethod
    def audit(actor, agent, action, data):
        models.AuditEvent.objects.create(
            action='isolation.payroll.' + action,
            object_id=str(agent),
            metadata={
                'actor_portal_id': actor,
                'setter_id': agent,
                **json.loads(json.dumps(data, default=str)),
            },
        )


@api_view(['GET'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
def overview(request, agent=None):
    return service.overview(Store, request, agent)


@api_view(['POST'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
def terms(request, agent, pk=None):
    return service.set_terms(Store, request, agent, pk)


@api_view(['POST'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
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
