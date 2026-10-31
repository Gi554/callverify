"""Administrative dossier exports reuse the list's exact scope and filters."""

from datetime import timezone as datetime_timezone
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from packages.exports import kind, bounded, response, NUMBERISH
from packages.client_folders import summary, dossier_rows, serialize_rows

LABELS = {
    'scheduled': 'Planifié',
    'rescheduled': 'Reprogrammé',
    'performed': 'Rendez-vous tenu',
    'absent': 'Absent',
    'not_performed': 'Non tenu — autre motif',
    'report_due': 'Compte rendu attendu',
    'cancelled': 'Annulé',
    'appointment_booked': 'Rendez-vous pris',
    'voicemail': 'Répondeur',
    'invalid_number': 'Numéro invalide déclaré',
    'disconnected': 'Appel coupé',
    'not_interested': 'Pas intéressé',
    'callback': 'Rappel demandé',
    'unreachable': 'Injoignable',
    'open': 'À faire',
    'overdue': 'En retard',
    'closed': 'Terminé',
}
METRICS = {
    'prospects': 'Prospects distincts confiés (historique inclus)',
    'appointments': 'Rendez-vous attribués (annulations incluses)',
    'sales': 'Ventes ou contrats conclus sur rendez-vous tenus non annulés',
    'call_results': 'Résultats d’appel déclarés (pas des conversations connectées)',
    'tasks': 'Tâches et rappels (tous statuts)',
    'open_tasks': 'Tâches ouvertes',
    'overdue_tasks': 'Tâches ouvertes en retard',
}
RULE = (
    'Rendez-vous limités au client ; prospects, résultats d’appel et tâches : historique '
    'complet des fiches, avant réaffectation inclus. Ne pas sommer les prospects entre clients. '
    'Une présence confirmée non annulée consomme l’objectif ; une absence ne le consomme pas. '
    'Objectif administratif et quota restant non inclus dans cet export métier.'
)
FIELDS = {
    'prospects': [
        ('id', 'Réf. fiche'),
        ('name', 'Prospect'),
        ('phone', 'Téléphone fourni'),
        ('status', 'Statut commercial'),
    ],
    'appointments': [
        ('id', 'Réf. rendez-vous'),
        ('contact_id', 'Réf. fiche'),
        ('name', 'Prospect'),
        ('starts_at', 'Début (UTC ISO 8601)'),
        ('ends_at', 'Fin (UTC ISO 8601)'),
        ('timezone', 'Fuseau du rendez-vous'),
        ('status', 'Statut du rendez-vous'),
        ('setter_id', 'Setter ID'),
        ('setter_name', 'Setter'),
        ('booked_by_id', 'Auteur réservation ID'),
        ('closer_name', 'Closer'),
        ('report_by_id', 'Auteur compte rendu ID'),
        ('reported_at', 'Compte rendu le (UTC ISO 8601)'),
        ('performed', 'Présence déclarée dans le compte rendu'),
        ('sale_concluded', 'Vente ou contrat déclaré dans le compte rendu'),
        ('note', 'Note du compte rendu'),
    ],
    'calls': [
        ('id', 'Réf. résultat'),
        ('contact_id', 'Réf. fiche'),
        ('name', 'Prospect'),
        ('created_at', 'Déclaré le (UTC ISO 8601)'),
        ('actor_id', 'Auteur ID'),
        ('status', 'Résultat déclaré'),
        ('note', 'Note'),
    ],
    'tasks': [
        ('id', 'Réf. tâche'),
        ('contact_id', 'Réf. fiche'),
        ('name', 'Prospect'),
        ('created_at', 'Créée le (UTC ISO 8601)'),
        ('due_at', 'Échéance (UTC ISO 8601)'),
        ('actor_id', 'Responsable / créateur ID'),
        ('status', 'État de la tâche'),
        ('note', 'Note / motif'),
        ('resolution', 'Résolution'),
        ('closed_by_id', 'Clôturée par ID'),
    ],
}


def iso(value):
    return value.astimezone(datetime_timezone.utc).isoformat() if value is not None else ''


def safe(value, file):
    # Also neutralise formulas hidden after leading whitespace; keep literal phone numbers.
    if file == 'csv' and isinstance(value, str):
        if value.lstrip().startswith(('=', '+', '-', '@')) and not NUMBERISH.fullmatch(value):
            return "'" + value
    return value


def export(request, workspace, client_id):
    state_labels = {
        **LABELS,
        **(
            {
                'performed': 'Rendez-vous validé',
                'absent': 'Non honoré',
                'invalid_number': 'Numéro non attribué',
                'other': 'Autre résultat',
            }
            if workspace == 'assurance'
            else {}
        ),
    }
    if request.user.role != 'administrator':
        raise PermissionDenied('Export des dossiers réservé aux administrateurs.')
    if set(request.query_params) - {'file', 'section', 'search', 'status'}:
        raise ValidationError('Paramètres d’export inconnus ; aucune pagination autorisée.')
    file = kind(request)
    section = request.query_params.get('section', 'summary')
    if section not in ('summary', *FIELDS):
        raise ValidationError('Section d’export inconnue.')
    if section in ('calls', 'tasks') and request.query_params.get('status'):
        raise ValidationError('Ce filtre de statut est réservé aux prospects et rendez-vous.')
    now = timezone.now()
    info = summary(workspace, client_id, now)
    prefix = ['Espace', 'Client ID', 'Exporté le (UTC ISO 8601)']
    meta = [workspace, client_id, iso(now)]
    if section == 'summary':
        if request.query_params.get('search') or request.query_params.get('status'):
            raise ValidationError('La synthèse couvre le dossier entier, sans filtre de liste.')
        headers = [*prefix, 'Catégorie', 'Indicateur', 'Valeur', 'Périmètre et règle']
        indicators = [('Dossier', label, info[key]) for key, label in METRICS.items()]
        states = ['scheduled', 'performed', 'not_performed', 'report_due', 'cancelled']
        if workspace == 'assurance':
            states += ['rescheduled', 'absent']
        indicators += [
            ('Rendez-vous', state_labels[state], info['statuses'].get(state, 0)) for state in states
        ]
        indicators += [
            ('Prospects', stage['label'], stage['total']) for stage in info['prospect_statuses']
        ]
        values = [[*meta, category, label, value, RULE] for category, label, value in indicators]
    else:
        rows, context = dossier_rows(workspace, client_id, request.query_params, now)
        records = serialize_rows(bounded(rows, file), workspace, context, now)
        labels = (
            {stage['status']: stage['label'] for stage in info['prospect_statuses']}
            if section == 'prospects'
            else state_labels
        )
        headers = [*prefix, *[label for _, label in FIELDS[section]], 'Périmètre et règle']
        values = []
        for record in records:
            for key in ('starts_at', 'ends_at', 'created_at', 'due_at', 'reported_at'):
                if key in record:
                    record[key] = iso(record[key])
            record['status'] = labels.get(record['status'], record['status'])
            values.append([*meta, *[record.get(key) for key, _ in FIELDS[section]], RULE])
    result = response(
        file,
        headers,
        [[safe(value, file) for value in row] for row in values],
        f'dossier-{workspace}-{client_id}-{section}',
        'Dossier client',
    )
    # Audit only successful, bounded exports. No notes, phone numbers or search terms in metadata.
    metadata = {'client_id': client_id, 'section': section, 'file': file, 'rows': len(values)}
    if workspace == 'assurance':
        from apps.assurance.backend.crm.models import BusinessAudit

        BusinessAudit.objects.create(
            actor_id=request.user.pk,
            object_id=client_id,
            action='client_folder.exported',
            metadata=metadata,
        )
    else:
        from core.models import AuditEvent

        AuditEvent.objects.create(
            action='isolation.client_folder.exported',
            object_id=str(client_id),
            metadata={**metadata, 'actor_portal_id': request.user.pk},
        )
    return result
