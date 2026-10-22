"""Read-only SQLite preparation audit. Never merges databases or exports business rows."""

import argparse
from contextlib import ExitStack, closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

try:
    from scripts.crm_backup import (
        snapshot,
        plain_path,
        exclusive_write,
        BackupError,
        require,
        SERVICES,
    )
except ModuleNotFoundError:
    from crm_backup import snapshot, plain_path, exclusive_write, BackupError, require, SERVICES

# Every non-FK portal identity reference is enumerated; additions must be classified.
IDENTITIES = {
    'portal': {'identity_assurancemailrelay': ['recipient_id']},
    'assurance': {
        'assurance_advisorassignment': ['setter_id', 'advisor_id'],
        'assurance_advisorschedule': ['advisor_id'],
        'assurance_appointment': ['setter_id', 'advisor_id', 'booked_by_id'],
        'assurance_appointmentincident': ['author_id'],
        'assurance_appointmentreport': ['author_id'],
        'assurance_businessaudit': ['actor_id'],
        'assurance_contact': ['assigned_advisor_id', 'created_by_id', 'lease_owner_id'],
        'assurance_contactcalloutcome': ['setter_id'],
        'assurance_contactdocument': ['author_id'],
        'assurance_contactimport': ['created_by_id'],
        'assurance_contactnote': ['author_id'],
        'assurance_followuptask': ['setter_id', 'closed_by_id'],
        'assurance_reminderevent': ['recipient_id'],
        'assurance_tasknotificationread': ['user_id'],
    },
    'isolation': {
        'core_campaign': ['portal_owner_id'],
        'core_isolationassignmentbatch': ['actor_portal_id'],
        'core_isolationfollowup': ['created_by_id', 'closed_by_id'],
        'core_isolationvisit': ['client_id', 'setter_id', 'booked_by_id', 'closer_id'],
        'core_isolationvisitcalendar': ['client_id'],
        'core_isolationvisitresult': ['author_client_id', 'author_closer_id'],
        'core_isolationvisitsupplement': ['author_client_id'],
        'core_prospect': ['assigned_setter_id'],
        'core_prospectactivity': ['author_portal_id'],
        'core_prospectactivityshare': ['client_id'],
    },
}

EXCLUSIONS = {
    'portal': {
        'identity_assurancemailcursor.after_id': 'Curseur historique, pas une identité.',
        'identity_assurancemailrelay.event_id': 'Événement Assurance polymorphe selon stream : contrôle métier ultérieur.',
        'identity_calendarsync.remote_id': 'Identifiant distant opaque.',
        'identity_calendarsync.source_id': 'Source calendrier selon espace, vérifiée séparément.',
        'identity_phonecallattempt.contact_id': 'Fiche selon espace, vérifiée séparément.',
    },
    'assurance': {
        'assurance_businessaudit.object_id': 'Référence audit polymorphe : contrôle métier ultérieur.'
    },
    'isolation': {
        'core_auditevent.object_id': 'Référence audit polymorphe : contrôle métier ultérieur.',
        'core_taskdelivery.object_id': 'Référence de livraison polymorphe : contrôle métier ultérieur.',
        'django_admin_log.object_id': 'Référence administrative polymorphe : contrôle métier ultérieur.',
    },
}

REQUIRED = {
    'portal': {
        'auth_user',
        'identity_membership',
        'identity_calendarconnection',
        'identity_calendarsync',
        'identity_phonecallattempt',
    },
    'assurance': {'assurance_contact', 'assurance_appointment'},
    'isolation': {'core_adminuser', 'core_prospect', 'core_isolationvisit'},
}
LATEST = {
    'portal': ('identity', '0015_phonecallattempt_workspace'),
    'assurance': ('assurance', '0026_appointment_reschedule_count_and_more'),
    'isolation': ('core', '0017_isolationfollowup'),
}


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def inventory(db, counts):
    result = {}
    for table, count in counts.items():
        columns = db.execute('PRAGMA table_info(' + quote(table) + ')').fetchall()
        foreign = db.execute('PRAGMA foreign_key_list(' + quote(table) + ')').fetchall()
        indexes = []
        for row in db.execute('PRAGMA index_list(' + quote(table) + ')').fetchall():
            indexes.append(
                {
                    'unique': bool(row[2]),
                    'partial': bool(row[4]),
                    'columns': db.execute('PRAGMA index_info(' + quote(row[1]) + ')').fetchall(),
                }
            )
        definition = {
            'columns': columns,
            'foreign_keys': foreign,
            'indexes': indexes,
            'sql': db.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()[0],
        }
        encoded = json.dumps(definition, sort_keys=True, default=str).encode()
        result[table] = {
            'rows': count,
            'columns': [row[1] for row in columns],
            'foreign_key_columns': [row[3] for row in foreign],
            'schema_sha256': hashlib.sha256(encoded).hexdigest(),
        }
    return result


def audit(databases, *, quiesced=False):
    require(set(databases) == set(SERVICES), 'Les trois bases sources sont requises.')
    paths = {key: plain_path(path) for key, path in databases.items()}
    require(len(set(paths.values())) == 3, 'Trois fichiers sources distincts sont requis.')
    result = {
        'version': 1,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'local_sqlite_preflight',
        'quiesced_declared': bool(quiesced),
        'migration_ready': False,
        'target': {
            'engine': 'postgresql',
            'database_count': 1,
            'schemas': list(SERVICES),
            'identity_authority': 'portal',
        },
        'sources': {},
        'identity_checks': [],
        'source_checks': [],
        'shared_tables': [],
        'blockers': [],
        'limits': [
            'Instantanés cohérents séparément ; aucune transaction commune aux trois sources.',
            'Aucun compte n’est fusionné sur la base de son nom ou de son ID numérique.',
            'JSON/audits polymorphes, fichiers, secrets de chiffrement, clés et séquences PostgreSQL restent à vérifier.',
            'Aucun contrôle de droits PostgreSQL ni répétition de migration/restauration : pas de feu vert de bascule.',
        ],
    }
    if not quiesced:
        result['limits'].append(
            'Services non déclarés arrêtés : reprendre l’audit sur un arrêt coordonné avant migration.'
        )
    with ExitStack() as stack:
        connections = {}
        for service, path in paths.items():
            data, counts = snapshot(path)
            db = stack.enter_context(closing(sqlite3.connect(':memory:')))
            db.deserialize(data)
            db.execute('PRAGMA trusted_schema=OFF')
            db.execute('PRAGMA query_only=ON')
            connections[service] = db
            tables = inventory(db, counts)
            result['sources'][service] = {
                'tables': tables,
                'table_count': len(tables),
                'row_count': sum(counts.values()),
            }
            missing = (REQUIRED[service] | set(IDENTITIES[service]) | {'django_migrations'}) - set(
                tables
            )
            if missing:
                result['blockers'].append(
                    {'kind': 'missing_tables', 'service': service, 'tables': sorted(missing)}
                )
            migrations = (
                set(db.execute('SELECT app,name FROM django_migrations'))
                if 'django_migrations' in tables
                else set()
            )
            if LATEST[service] not in migrations:
                result['blockers'].append(
                    {
                        'kind': 'missing_expected_migration',
                        'service': service,
                        'migration': LATEST[service],
                    }
                )
            for table, info in tables.items():
                for column in info['columns']:
                    if (
                        not column.endswith('_id')
                        or column in info['foreign_key_columns']
                        or column == 'request_id'
                    ):
                        continue
                    if column in IDENTITIES[service].get(table, []):
                        continue
                    if table + '.' + column in EXCLUSIONS[service]:
                        continue
                    result['blockers'].append(
                        {
                            'kind': 'unclassified_reference',
                            'service': service,
                            'table': table,
                            'column': column,
                        }
                    )
                absent = set(IDENTITIES[service].get(table, [])) - set(info['columns'])
                if absent:
                    result['blockers'].append(
                        {
                            'kind': 'missing_reference_columns',
                            'service': service,
                            'table': table,
                            'columns': sorted(absent),
                        }
                    )
        users = set()
        if 'auth_user' in result['sources']['portal']['tables']:
            users = {row[0] for row in connections['portal'].execute('SELECT id FROM auth_user')}
        for service, checks in IDENTITIES.items():
            db = connections[service]
            tables = result['sources'][service]['tables']
            for table, columns in checks.items():
                if table not in tables:
                    continue
                for column in columns:
                    if column not in tables[table]['columns']:
                        continue
                    referenced = 0
                    missing = 0
                    for (value,) in db.execute(
                        'SELECT '
                        + quote(column)
                        + ' FROM '
                        + quote(table)
                        + ' WHERE '
                        + quote(column)
                        + ' IS NOT NULL'
                    ):
                        referenced += 1
                        if value not in users:
                            missing += 1
                    entry = {
                        'service': service,
                        'table': table,
                        'column': column,
                        'referenced_rows': referenced,
                        'missing_identity_rows': missing,
                    }
                    result['identity_checks'].append(entry)
                    if missing:
                        result['blockers'].append({'kind': 'missing_portal_identity', **entry})
        # Two external service references whose destination depends on the portal workspace.
        portal = connections['portal']
        checks = [
            (
                'identity_phonecallattempt',
                'contact_id',
                'SELECT workspace,contact_id FROM identity_phonecallattempt',
                {'assurance': 'assurance_contact', 'isolation': 'core_prospect'},
            ),
            (
                'identity_calendarsync',
                'source_id',
                'SELECT c.workspace,s.source_id FROM identity_calendarsync s JOIN identity_calendarconnection c ON c.id=s.connection_id',
                {'assurance': 'assurance_appointment', 'isolation': 'core_isolationvisit'},
            ),
        ]
        for table, column, sql, targets in checks:
            if table not in result['sources']['portal']['tables'] or (
                table == 'identity_calendarsync'
                and 'identity_calendarconnection' not in result['sources']['portal']['tables']
            ):
                continue
            destinations = {
                space: {
                    row[0] for row in connections[space].execute('SELECT id FROM ' + quote(target))
                }
                for space, target in targets.items()
                if target in result['sources'][space]['tables']
            }
            total = missing = 0
            for workspace, source in portal.execute(sql):
                total += 1
                if workspace not in destinations or source not in destinations[workspace]:
                    missing += 1
            entry = {
                'service': 'portal',
                'table': table,
                'column': column,
                'referenced_rows': total,
                'missing_source_rows': missing,
            }
            result['source_checks'].append(entry)
            if missing:
                result['blockers'].append({'kind': 'missing_business_source', **entry})
        tables = {table for source in result['sources'].values() for table in source['tables']}
        for table in sorted(tables):
            owners = [
                service for service in SERVICES if table in result['sources'][service]['tables']
            ]
            if len(owners) > 1:
                result['shared_tables'].append(
                    {
                        'table': table,
                        'services': owners,
                        'same_definition': len(
                            {
                                result['sources'][service]['tables'][table]['schema_sha256']
                                for service in owners
                            }
                        )
                        == 1,
                        'action': 'Conserver chaque copie dans son schéma ; ne pas fusionner les lignes.',
                    }
                )
    result['excluded_references'] = EXCLUSIONS
    result['audit_status'] = 'issues_found' if result['blockers'] else 'no_issues_in_checked_scope'
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Audit SQLite CRM en lecture seule ; aucune fusion ni bascule.'
    )
    for service in SERVICES:
        parser.add_argument('--' + service, required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument(
        '--quiesced',
        action='store_true',
        help='Déclaration opérateur d’un arrêt coordonné déjà effectué ; le script n’arrête rien.',
    )
    args = parser.parse_args(argv)
    try:
        sources = {key: getattr(args, key) for key in SERVICES}
        target = plain_path(args.output)
        require(
            target not in {plain_path(path) for path in sources.values()},
            'Le rapport ne peut pas remplacer une source.',
        )
        require(
            not target.exists(), 'Le rapport existe déjà : choisissez une nouvelle destination.'
        )
        result = audit(sources, quiesced=args.quiesced)
        exclusive_write(target, json.dumps(result, ensure_ascii=False, indent=2).encode())
        print(
            json.dumps(
                {
                    'audit_status': result['audit_status'],
                    'blocker_count': len(result['blockers']),
                    'migration_ready': False,
                }
            )
        )
        return 2 if result['blockers'] else 0
    except (BackupError, sqlite3.Error, OSError, ValueError):
        print(
            'Audit impossible : sources, schéma, intégrité ou destination invalides. Aucune base modifiée.',
            file=sys.stderr,
        )
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
