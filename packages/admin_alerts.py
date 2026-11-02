"""Live administrative checks, acknowledged independently of business state."""

import hashlib
import json
from datetime import timedelta
from django.db import models, transaction
from django.db.models import Count, Q
from django.db.models.functions import Trim
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.response import Response

KINDS = {
    'missing_results': 'Résultats à renseigner',
    'overdue_tasks': 'Rappels en retard',
    'upcoming_tasks': 'Rappels dans les prochaines 24 h',
    'new_meetings': 'Rendez-vous créés depuis 7 jours',
    'duplicate_meetings': 'Rendez-vous potentiellement en double',
    'duplicate_prospects': 'Numéros potentiellement en double',
    'missing_ownership': 'Rendez-vous sans responsable',
}


def fingerprint(kind, identity, state):
    return hashlib.sha256(
        json.dumps([kind, identity, state], sort_keys=True, default=str).encode()
    ).hexdigest()


def row(kind, identity, title, state, **extra):
    return {
        'kind': kind,
        'id': str(identity),
        'title': title,
        'signature': fingerprint(kind, identity, state),
        **extra,
    }


def source(store, kind):
    now = timezone.now()
    meetings = store.Meeting.objects.filter(status='scheduled').select_related(store.contact_field)
    if kind == 'missing_results':
        return meetings.filter(ends_at__lte=now).filter(
            Q(**{store.result + '__isnull': True})
            | Q(
                **{
                    store.result + '__performed': True,
                    store.result + '__' + store.closed_field + '__isnull': True,
                }
            )
        )
    if kind == 'missing_ownership':
        return meetings.filter(Q(setter_id=0) | Q(**{store.target + '_id': 0}))
    if kind == 'new_meetings':
        return meetings.filter(created_at__gte=now - timedelta(days=7))
    if kind in ('overdue_tasks', 'upcoming_tasks'):
        tasks = store.Task.objects.filter(closed_at__isnull=True).select_related(
            *store.task_relations
        )
        return (
            tasks.filter(due_at__lt=now)
            if kind == 'overdue_tasks'
            else tasks.filter(due_at__gte=now, due_at__lte=now + timedelta(hours=24))
        )
    if kind == 'duplicate_meetings':
        return (
            meetings.values(store.contact_field + '_id', 'starts_at')
            .annotate(total=Count('pk'), first_id=models.Min('pk'))
            .filter(total__gt=1)
            .order_by('first_id')
        )
    if kind == 'duplicate_prospects':
        return (
            store.Contact.objects.annotate(match_phone=Trim(store.phone))
            .exclude(match_phone='')
            .values('match_phone')
            .annotate(total=Count('pk'), first_id=models.Min('pk'))
            .filter(total__gt=1)
            .order_by('first_id')
        )
    raise ValidationError('Type d’alerte inconnu.')


def count(rows):
    return len(rows) if isinstance(rows, list) else rows.count()


def serialize(store, kind, item):
    if kind == 'duplicate_prospects':
        return row(
            kind,
            item['first_id'],
            f"{item['total']} fiches pour le même numéro",
            item,
            reference=item['first_id'],
            details={
                'Téléphone': item['match_phone'],
                'Nombre': item['total'],
                'Critère': 'Numéro exact après retrait des espaces en début et fin. Vérification humaine requise.',
            },
        )
    if kind == 'duplicate_meetings':
        return row(
            kind,
            item['first_id'],
            f"{item['total']} rendez-vous au même début pour la même fiche",
            item,
            reference=item[store.contact_field + '_id'],
            starts_at=item['starts_at'],
            details={
                'Nombre': item['total'],
                'Critère': 'Même fiche, même début, statut planifié. Aucun regroupement automatique.',
            },
        )
    if kind in ('overdue_tasks', 'upcoming_tasks'):
        return row(
            kind,
            item.pk,
            'Rappel à effectuer',
            [item.revision, item.due_at],
            reference=item.pk,
            due_at=item.due_at,
            details={'Rappel': item.pk, 'Version du suivi': item.revision},
        )
    return row(
        kind,
        item.pk,
        f'{getattr(item, store.contact_field).name} · Rendez-vous #{item.pk}',
        item.revision,
        reference=item.pk,
        starts_at=item.starts_at,
        details={
            'Compte setter': item.setter_id,
            ('Compte client' if store.target == 'client' else 'Compte conseiller'): getattr(
                item, store.target + '_id'
            ),
            'Version du dossier': item.revision,
        },
    )


def scope(request):
    if request.user.role != 'administrator':
        raise PermissionDenied('Centre réservé à l’administration de cet espace.')


class ReviewInput(serializers.Serializer):
    kind = serializers.ChoiceField(choices=list(KINDS))
    id = serializers.CharField(max_length=100)
    signature = serializers.RegexField(r'^[a-f0-9]{64}$')
    note = serializers.CharField(max_length=1000)


def center(store, request):
    scope(request)
    if request.method == 'POST':
        data = ReviewInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        kind = values['kind']
        if not values['id'].isdigit() or len(values['id']) > 18:
            raise ValidationError('Référence invalide.')
        rows = source(store, kind)
        if kind in ('duplicate_meetings', 'duplicate_prospects'):
            item = rows.filter(first_id=values['id']).first()
            found = serialize(store, kind, item) if item else None
        else:
            if not values['id'].isdigit() or len(values['id']) > 18:
                raise ValidationError('Référence invalide.')
            item = rows.filter(pk=values['id']).first()
            found = serialize(store, kind, item) if item else None
        if not found:
            raise NotFound('Cette alerte n’est plus active.')
        if found['signature'] != values['signature']:
            raise ValidationError('L’alerte a changé ; actualisez avant de la prendre en charge.')
        with transaction.atomic():
            review, created = store.Review.objects.get_or_create(
                signature=values['signature'],
                defaults={'kind': kind, 'actor_id': request.user.pk, 'note': values['note']},
            )
            if created:
                store.Payroll.audit(
                    request.user.pk,
                    int(found['reference']),
                    'alert_reviewed',
                    {'kind': kind, 'reference': found['reference'], 'note': values['note']},
                )
        return Response(
            {'acknowledged': True, 'actor_id': review.actor_id, 'created_at': review.created_at}
        )
    kind = request.query_params.get('kind', 'missing_results')
    if kind not in KINDS:
        raise ValidationError('Type d’alerte inconnu.')
    try:
        page = int(request.query_params.get('page', '1'))
        if not 1 <= page <= 1000000:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValidationError('Page invalide.') from None
    sources = {key: source(store, key) for key in KINDS}
    rows = sources[kind]
    if not isinstance(rows, list) and kind not in ('duplicate_meetings', 'duplicate_prospects'):
        rows = rows.order_by('-pk')
    results = [serialize(store, kind, r) for r in rows[(page - 1) * 25 : page * 25]]
    reviews = {
        r.signature: r
        for r in store.Review.objects.filter(signature__in=[r['signature'] for r in results])
    }
    for item in results:
        review = reviews.get(item['signature'])
        item['review'] = (
            {'actor_id': review.actor_id, 'note': review.note, 'created_at': review.created_at}
            if review
            else None
        )
    response = Response(
        {
            'kinds': [
                {'kind': k, 'label': label, 'count': count(sources[k])}
                for k, label in KINDS.items()
            ],
            'results': results,
            'count': count(rows),
            'page': page,
            'kind': kind,
            'checked_at': timezone.now(),
            'timezone': 'America/Toronto',
        }
    )
    response['Cache-Control'] = 'no-store'
    return response
