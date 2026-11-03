"""Bounded business reads for snapshots. No scheduling, calls, emails or provider writes."""

from urllib.parse import urlsplit
import json
import requests
from django.conf import settings
from django.db.models import Count, Q
from packages.access.tickets import issue
from packages.quebec_period import period
from .models import PhoneCallAttempt


def business(workspace, actor, path, params):
    base = getattr(settings, workspace.upper() + '_INTERNAL_URL').rstrip('/')
    url = urlsplit(base)
    if (
        url.scheme not in ('http', 'https')
        or not url.netloc
        or url.path
        or url.query
        or url.fragment
        or url.username
        or url.password
    ):
        raise ValueError('Invalid service URL')
    prefix = '/api/assurance/' if workspace == 'assurance' else '/api/'
    with requests.get(
        base + prefix + path,
        params=params,
        headers={
            'Authorization': 'Bearer ' + issue(actor, workspace, 'administrator'),
            'X-Forwarded-Proto': 'https',
        },
        timeout=(5, 30),
        allow_redirects=False,
        stream=True,
    ) as response:
        if response.status_code != 200:
            raise ValueError('Business source unavailable')
        data = response.raw.read(2_000_001, decode_content=True)
        if len(data) > 2_000_000:
            raise ValueError('Business source too large')
        result = json.loads(data)
        if not isinstance(result, dict):
            raise ValueError('Invalid business response')
        return result


def snapshot(job):
    params = {'from': str(job.starts_on), 'to': str(job.ends_on)}
    _, _, lower, upper = period(params)
    stats_path = 'statistics/' if job.workspace == 'assurance' else 'workspace-statistics/'
    stats = business(job.workspace, job.actor_id, stats_path, params)
    if (
        str(stats.get('from')) != params['from']
        or str(stats.get('to')) != params['to']
        or stats.get('timezone') != 'America/Toronto'
    ):
        raise ValueError('Unexpected reporting window')
    programmed = 'appointments' if job.workspace == 'assurance' else 'visits'
    columns = [
        'Rendez-vous (annulations incluses)',
        'Tenus',
        'Ventes conclues',
        'Ventes non conclues',
        'Non tenus',
        'Résultats manquants',
    ]
    keys = [programmed, 'performed', 'closed', 'not_closed', 'not_performed', 'updates_due']

    def counts(row):
        if row and any(key not in row for key in keys):
            raise ValueError('Incomplete statistics metrics')
        return [row.get(k, 0) for k in keys]

    if not isinstance(stats.get('totals'), dict) or any(key not in stats['totals'] for key in keys):
        raise ValueError('Incomplete statistics totals')
    if job.kind == 'campaigns':
        campaigns = stats.get('filter_options', {}).get('campaign_id', [])
        if len(campaigns) > 50:
            raise ValueError('Campaign report limit exceeded')
        headers = ['Campagne / lot ID', 'Campagne / lot', *columns]
        rows = []
        for item in campaigns:
            filtered = business(
                job.workspace, job.actor_id, stats_path, {**params, 'campaign_id': item['id']}
            )
            rows.append([item['id'], item['name'], *counts(filtered['totals'])])
        # Imported-less appointments remain visible in the totals, not a fabricated campaign.
        rows.insert(0, ['', 'Total de l’espace, y compris sans campagne', *counts(stats['totals'])])
    else:
        groups = list(stats.get('setters', {}).get('results', []))
        page = 2
        while len(groups) < stats.get('setters', {}).get('count', 0):
            if len(groups) >= 500:
                raise ValueError('Agent report limit exceeded')
            value = business(job.workspace, job.actor_id, stats_path, {**params, 'page': page})
            part = value.get('setters', {}).get('results', [])
            if not part:
                raise ValueError('Incomplete statistics')
            groups.extend(part)
            page += 1
        groups = {r['setter_id']: r for r in groups}
        calls = (
            PhoneCallAttempt.objects.filter(
                workspace=job.workspace, created_at__gte=lower, created_at__lt=upper
            )
            .values('user_id')
            .annotate(
                attempts=Count('pk', filter=Q(state__in=['accepted', 'rejected', 'unknown'])),
                accepted=Count('pk', filter=Q(state='accepted')),
                uncertain=Count('pk', filter=Q(state='unknown')),
            )
        )
        call_counts = {r['user_id']: r for r in calls}
        ids = sorted(set(groups) | set(call_counts))
        if len(ids) > 500:
            raise ValueError('Agent report limit exceeded')
        headers = [
            'Setter ID',
            'Setter',
            *columns,
            'Tentatives Orvia',
            'Acceptés par le poste',
            'Réponses incertaines',
            'Prospects joints',
        ]
        rows = []
        for pk in ids:
            values = groups.get(pk, {})
            call = call_counts.get(pk, {})
            rows.append(
                [
                    pk,
                    values.get('setter_name') or f'Compte #{pk}',
                    *counts(values),
                    call.get('attempts', 0),
                    call.get('accepted', 0),
                    call.get('uncertain', 0),
                    'Non disponible',
                ]
            )
    return {
        'workspace': job.workspace,
        'kind': job.kind,
        'from': str(job.starts_on),
        'to': str(job.ends_on),
        'headers': headers,
        'rows': rows,
        'definition': 'Heure du Québec. Données déclaratives et instantanés successifs des services au moment de génération. Les appels acceptés ne prouvent pas la réponse du prospect. Campagnes : Assurance = lots importés ; total sans campagne conservé.',
    }
