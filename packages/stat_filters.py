"""Administrative filters shared as code only; querysets stay in their own CRM."""

from django.db.models import Max
from rest_framework.exceptions import PermissionDenied, ValidationError


def selections(params, role, allowed):
    values = {}
    for key in allowed:
        raw = params.get(key, '')
        if not raw:
            continue
        if role != 'administrator':
            raise PermissionDenied('Filtres d’équipe réservés à l’administration.')
        if (
            not isinstance(raw, str)
            or not raw.isdecimal()
            or not 0 < int(raw) <= 9223372036854775807
        ):
            raise ValidationError({key: 'Identifiant positif requis.'})
        values[key] = int(raw)
    return values


def options(rows, id_field, name_field):
    latest = (
        rows.order_by()
        .values(id_field)
        .exclude(**{id_field: None})
        .annotate(last=Max('pk'))
        .order_by(id_field)[:500]
    )
    ids = [item['last'] for item in latest]
    values = rows.filter(pk__in=ids).values_list(id_field, name_field)
    return [
        {'id': pk, 'name': name or f'#{pk}'}
        for pk, name in sorted(values, key=lambda item: str(item[1]).casefold())
    ]


def merged(*groups):
    """One option per identifier across several sources; the first source names it."""
    seen = {}
    for group in groups:
        for row in group:
            seen.setdefault(row['id'], row)
    return sorted(seen.values(), key=lambda row: str(row['name']).casefold())
