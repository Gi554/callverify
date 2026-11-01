"""Independent business payroll ledgers: immutable receipts, explicit corrections, no bank transfer."""

import hashlib
import json
from datetime import timedelta
from decimal import Decimal
from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from packages.quebec_period import ZONE, period

ZERO = Decimal('0')


def money(value):
    return format(value or ZERO, '.2f')


def today():
    return timezone.now().astimezone(ZONE).date()


def term_output(row):
    return {
        'id': row.pk,
        'agent_id': row.agent_id,
        'starts_on': row.starts_on,
        'ends_on': row.ends_on,
        'cadence': row.cadence,
        'target': row.target,
        'attendance_cad': money(row.attendance_cad),
        'bonus_cad': money(row.bonus_cad),
        'conditions': row.conditions,
        'revision': row.revision,
        'editable': row.starts_on > today(),
    }


def active_term(store, agent):
    return store.Terms.objects.filter(
        agent_id=agent, starts_on__lte=today(), ends_on__gte=today()
    ).first()


def lock(store, agent):
    store.Account.objects.get_or_create(agent_id=agent)
    store.Account.objects.filter(agent_id=agent).update(revision=F('revision'))
    return store.Account.objects.get(agent_id=agent)


def reconcile(
    store, agent, actor=None, reason='Mise à jour des résultats rémunérables', record_increase=False
):
    with transaction.atomic():
        account = lock(store, agent)
        generated = store.earned(agent)['amount']
        if account.generated_cad != generated:
            before = account.generated_cad
            if generated < before or record_increase:
                store.Adjustment.objects.create(
                    agent_id=agent,
                    before_cad=before,
                    after_cad=generated,
                    delta_cad=generated - before,
                    actor_id=actor,
                    reason=reason,
                )
                store.audit(
                    actor,
                    agent,
                    'adjustment_created',
                    {'before': money(before), 'after': money(generated), 'reason': reason},
                )
            account.generated_cad = generated
            account.revision += 1
            account.save(update_fields=['generated_cad', 'revision'])
        return account


def scope(request, agent=None):
    if request.user.role not in ('administrator', 'setter'):
        raise PermissionDenied('Accès rémunération non autorisé.')
    if agent is not None and request.user.role != 'administrator' and request.user.pk != agent:
        raise PermissionDenied('Votre rémunération uniquement.')


def balance(store, agent, params, names=None):
    start, end, lower, upper = period(params)
    earned = store.earned(agent)
    selected = store.earned(agent, lower, upper)
    paid = (
        store.Payment.objects.filter(agent_id=agent).aggregate(total=Sum('amount_cad'))['total']
        or ZERO
    )
    net = earned['amount'] - paid
    term = active_term(store, agent)
    goal = None
    if term:
        first, last = term.starts_on, term.ends_on
        if term.cadence == 'week':
            day = today()
            first = max(first, day - timedelta(days=day.weekday()))
            last = min(last, day + timedelta(days=6 - day.weekday()))
        _, _, goal_lower, goal_upper = period({'from': str(first), 'to': str(last)})
        completed = store.earned(agent, goal_lower, goal_upper)['attendance']
        goal = {
            **term_output(term),
            'from': first,
            'to': last,
            'completed': completed,
            'remaining': max(0, term.target - completed),
        }
    account = store.Account.objects.filter(agent_id=agent).first()
    return {
        'agent_id': agent,
        'agent_name': (names if names is not None else store.roster()).get(
            agent, f'Agent #{agent}'
        ),
        'currency': 'CAD',
        'from': start,
        'to': end,
        'timezone': 'America/Toronto',
        'period': {
            **{k: v for k, v in selected.items() if k != 'amount'},
            'amount_cad': money(selected['amount']),
        },
        'generated_cad': money(earned['amount']),
        'attendance_amount_cad': earned.get('attendance_amount_cad', money(earned['amount'])),
        'sale_bonus_cad': earned.get('sale_bonus_cad', '0.00'),
        'paid_cad': money(paid),
        'balance_cad': money(net),
        'to_pay_cad': money(max(ZERO, net)),
        'to_regularize_cad': money(max(ZERO, -net)),
        'revision': account.revision if account else 0,
        'goal': goal,
        'unpriced': earned['unpriced'],
        'adjustment_pending': bool(account and account.generated_cad != earned['amount']),
        'definition': 'Gains et règlements cumulés dans cet espace uniquement ; les indicateurs de période suivent la date du rendez-vous au Québec. Les règlements sont enregistrés hors Orvia, sans virement.',
    }


def response(data):
    result = Response(data)
    result['Cache-Control'] = 'no-store'
    return result


def overview(store, request, agent=None):
    scope(request, agent)
    names = store.roster()
    if agent is not None:
        if agent not in names and agent != request.user.pk:
            raise ValidationError('Agent connu de cet espace requis.')
        data = balance(store, agent, request.query_params)
        data['terms'] = [
            term_output(row)
            for row in store.Terms.objects.filter(agent_id=agent).order_by('-starts_on')[:100]
        ]
        for kind, model, fields in (
            (
                'payments',
                store.Payment,
                ('id', 'amount_cad', 'paid_on', 'reference', 'note', 'actor_id', 'created_at'),
            ),
            (
                'adjustments',
                store.Adjustment,
                ('id', 'before_cad', 'after_cad', 'delta_cad', 'actor_id', 'reason', 'created_at'),
            ),
        ):
            try:
                page = int(request.query_params.get(kind + '_page', '1'))
                if not 1 <= page <= 1000000:
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValidationError('Page d’historique invalide.')
            qs = model.objects.filter(agent_id=agent).order_by('-created_at', '-pk')
            count = qs.count()
            data[kind] = list(qs.values(*fields)[(page - 1) * 25 : page * 25])
            data[kind + '_page'] = page
            data[kind + '_count'] = count
        return response(data)
    ids = [request.user.pk] if request.user.role == 'setter' else sorted(names)
    if len(ids) > 500:
        raise ValidationError('Annuaire limité à 500 agents.')
    return response(
        {
            'results': [balance(store, pk, request.query_params, names) for pk in ids],
            'count': len(ids),
            'currency': 'CAD',
        }
    )


class TermInput(serializers.Serializer):
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()
    cadence = serializers.ChoiceField(choices=['week', 'mandate'])
    target = serializers.IntegerField(min_value=0, max_value=100000)
    attendance_cad = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=ZERO)
    bonus_cad = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=ZERO, default=ZERO
    )
    conditions = serializers.CharField(max_length=2000, allow_blank=True, default='')
    reason = serializers.CharField(max_length=1000)
    revision = serializers.IntegerField(min_value=0)
    proof = serializers.CharField(max_length=8192, required=False)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés.')
        if (
            data['starts_on'] < today()
            or not 0 <= (data['ends_on'] - data['starts_on']).days <= 365
        ):
            raise ValidationError('Période future ou débutant aujourd’hui, de 366 jours maximum.')
        return data


def set_terms(store, request, agent, pk=None):
    scope(request, agent)
    if request.user.role != 'administrator':
        raise PermissionDenied('Conditions réservées à l’administration.')
    serializer = TermInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if store.workspace == 'assurance' and data['bonus_cad'] != ZERO:
        raise ValidationError('Assurance : rémunération de présence uniquement.')
    with transaction.atomic():
        store.validate_agent(request, agent, data.get('proof'))
        account = lock(store, agent)
        qs = store.Terms.objects.filter(agent_id=agent)
        original = qs.filter(pk=pk).first() if pk else None
        if pk and not original:
            raise ValidationError('Conditions introuvables.')
        if original and (original.starts_on <= today() or original.revision != data['revision']):
            raise ValidationError(
                'Conditions déjà applicables ou modifiées : seules les périodes futures sont modifiables.'
            )
        if not original and data['revision'] != 0:
            raise ValidationError('Révision initiale attendue.')
        if (
            qs.exclude(pk=pk)
            .filter(starts_on__lte=data['ends_on'], ends_on__gte=data['starts_on'])
            .exists()
        ):
            raise ValidationError('Une autre période couvre déjà ces dates.')
        before = term_output(original) if original else None
        fields = {
            key: data[key]
            for key in (
                'starts_on',
                'ends_on',
                'cadence',
                'target',
                'attendance_cad',
                'bonus_cad',
                'conditions',
            )
        }
        if original:
            for key, value in fields.items():
                setattr(original, key, value)
            original.revision += 1
            original.actor_id = request.user.pk
            original.save()
            row = original
        else:
            row = store.Terms.objects.create(agent_id=agent, actor_id=request.user.pk, **fields)
        account.revision += 1
        account.save(update_fields=['revision'])
        store.audit(
            request.user.pk,
            agent,
            'terms_updated',
            {'before': before, 'after': term_output(row), 'reason': data['reason']},
        )
    return response(term_output(row))


class PaymentInput(serializers.Serializer):
    request_id = serializers.UUIDField()
    amount_cad = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0.01')
    )
    paid_on = serializers.DateField()
    reference = serializers.CharField(max_length=150)
    note = serializers.CharField(max_length=1000, allow_blank=True, default='')
    revision = serializers.IntegerField(min_value=0)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés.')
        if data['paid_on'] > today():
            raise ValidationError('Un paiement effectué ne peut pas être daté dans le futur.')
        return data


def record_payment(store, request, agent):
    scope(request, agent)
    if request.user.role != 'administrator':
        raise PermissionDenied('Paiements réservés à l’administration.')
    if agent not in store.roster():
        raise ValidationError('Agent connu de cet espace requis.')
    serializer = PaymentInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    canonical = {k: str(data[k]) for k in ('amount_cad', 'paid_on', 'reference', 'note')}
    canonical['agent_id'] = agent
    fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    with transaction.atomic():
        account = lock(store, agent)
        existing = store.Payment.objects.filter(request_id=data['request_id']).first()
        if existing:
            if existing.fingerprint != fingerprint:
                raise ValidationError('Identifiant d’enregistrement déjà utilisé autrement.')
            return response({'recorded': True, 'payment_id': existing.pk, 'replayed': True})
        if account.revision != data['revision']:
            raise ValidationError('Solde modifié : rechargez avant d’enregistrer.')
        statement = balance(store, agent, {})
        if data['amount_cad'] > Decimal(statement['to_pay_cad']):
            raise ValidationError('Montant supérieur au solde payable connu.')
        key = hashlib.sha256(f"{agent}:{data['reference'].strip().casefold()}".encode()).hexdigest()
        if store.Payment.objects.filter(reference_key=key).exists():
            raise ValidationError(
                'Cette référence de paiement est déjà enregistrée pour cet agent.'
            )
        account = reconcile(
            store, agent, request.user.pk, 'Rapprochement avant enregistrement de paiement'
        )
        try:
            with transaction.atomic():
                row = store.Payment.objects.create(
                    agent_id=agent,
                    fingerprint=fingerprint,
                    reference_key=key,
                    actor_id=request.user.pk,
                    **{
                        k: data[k]
                        for k in ('request_id', 'amount_cad', 'paid_on', 'reference', 'note')
                    },
                )
        except IntegrityError:
            raise ValidationError('Identifiant ou référence de paiement déjà enregistré.')
        account.revision += 1
        account.save(update_fields=['revision'])
        store.audit(
            request.user.pk,
            agent,
            'payment_recorded',
            {
                'payment_id': row.pk,
                'amount_cad': money(row.amount_cad),
                'reference': row.reference,
                'paid_on': str(row.paid_on),
                'before': statement['balance_cad'],
                'after': money(Decimal(statement['balance_cad']) - row.amount_cad),
            },
        )
        return response({'recorded': True, 'payment_id': row.pk, 'replayed': False})
