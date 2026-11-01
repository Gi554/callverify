"""Read-only, workspace-local administrative audit journal."""

from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.response import Response
from .quebec_period import period

PRIVATE = (
    'password',
    'secret',
    'token',
    'proof',
    'authorization',
    'cookie',
    'fingerprint',
    'credential',
    'payload',
    'api_key',
)


def safe(value, depth=0):
    if depth > 12:
        return '[profondeur limitée]'
    if isinstance(value, dict):
        return {
            k: (
                '[masqué]'
                if any(word in str(k).lower() for word in PRIVATE)
                else safe(v, depth + 1)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [safe(v, depth + 1) for v in value]
    return value


def positive(value, label):
    try:
        number = int(value)
        if not 1 <= number <= 9223372036854775807:
            raise ValueError()
        return number
    except (TypeError, ValueError):
        raise ValidationError(label + ' invalide.') from None


def journal(request, rows, workspace, pk=None):
    if request.user.role != 'administrator':
        raise PermissionDenied('Journal réservé à l’administration de cet espace.')
    start, end, lower, upper = period(request.query_params)
    rows = rows.filter(created_at__gte=lower, created_at__lt=upper)
    params = request.query_params
    if params.get('action'):
        action = params['action']
        if len(action) > 100:
            raise ValidationError('Type d’action invalide.')
        rows = rows.filter(action=action)
    if params.get('object_id'):
        obj = params['object_id']
        if len(obj) > 100:
            raise ValidationError('Référence invalide.')
        rows = rows.filter(
            object_id=obj if workspace == 'isolation' else positive(obj, 'Référence')
        )
    if params.get('actor_id'):
        actor = positive(params['actor_id'], 'Auteur')
        rows = (
            rows.filter(metadata__actor_portal_id=actor)
            if workspace == 'isolation'
            else rows.filter(actor_id=actor)
        )
    rows = rows.order_by('-created_at', '-pk')

    def output(row):
        actor = row.metadata.get('actor_portal_id') if workspace == 'isolation' else row.actor_id
        return {
            'id': row.pk,
            'created_at': row.created_at,
            'action': row.action,
            'object_id': row.object_id,
            'actor_id': actor,
            'actor_label': f'Compte #{actor}' if actor else 'Système / auteur non enregistré',
            'metadata': safe(row.metadata),
        }

    if pk is not None:
        row = rows.filter(pk=pk).first()
        if row is None:
            raise NotFound('Événement introuvable dans cette période et cet espace.')
        result = Response(output(row))
    else:
        page = positive(params.get('page', '1'), 'Page')
        if page > 1000000:
            raise ValidationError('Page invalide.')
        # Include all event types of this space, without exposing another database.
        actions = list(rows.order_by('action').values_list('action', flat=True).distinct()[:200])
        result = Response(
            {
                'results': [output(row) for row in rows[(page - 1) * 25 : page * 25]],
                'count': rows.count(),
                'page': page,
                'page_size': 25,
                'actions': actions,
                'from': start,
                'to': end,
                'timezone': 'America/Toronto',
            }
        )
    result['Cache-Control'] = 'no-store'
    return result
