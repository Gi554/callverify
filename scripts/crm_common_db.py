"""Create a new disposable common PostgreSQL database, never reuse an existing one."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import sys

import psycopg
from psycopg import sql

try:
    from scripts.crm_backup import exclusive_write, plain_path, require, BackupError
except ModuleNotFoundError:
    from crm_backup import exclusive_write, plain_path, require, BackupError

SERVICES = ('portal', 'assurance', 'isolation')
PREFIXES = {'portal': 'PORTAL_DB', 'assurance': 'ASSURANCE_DB', 'isolation': 'POSTGRES'}
SETTINGS = {'portal': 'portal.backend.settings', 'assurance': 'apps.assurance.backend.settings',
            'isolation': 'config.settings'}


def provision(admin, name):
    require(bool(re.fullmatch(r'amx_rehearsal_[a-z0-9]{6,20}', name)), 'Disposable database name required.')
    require(admin.autocommit, 'Autocommit admin connection required.')
    roles = {service: name + '_' + service for service in SERVICES}
    passwords = {service: secrets.token_urlsafe(32) for service in SERVICES}
    # Refuse before changing anything, including roles with the same prefix.
    require(not admin.execute('SELECT 1 FROM pg_database WHERE datname=%s', (name,)).fetchone(), 'Database exists.')
    require(not admin.execute('SELECT 1 FROM pg_roles WHERE rolname=ANY(%s)', (list(roles.values()),)).fetchone(), 'Role exists.')
    created_roles = []
    created_database = False
    try:
        for service, role in roles.items():
            admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}')
                          .format(sql.Identifier(role), sql.Literal(passwords[service])))
            created_roles.append(role)
        admin.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0 ENCODING {}').format(sql.Identifier(name), sql.Literal('UTF8')))
        created_database = True
        admin.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(name)))
        with psycopg.connect(**{**admin.info.get_parameters(), 'password': admin.info.password, 'dbname': name}, autocommit=True) as target:
            target.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
            for service, role in roles.items():
                target.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(name), sql.Identifier(role)))
                target.execute(sql.SQL('CREATE SCHEMA {} AUTHORIZATION {}').format(sql.Identifier(service), sql.Identifier(role)))
                target.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM PUBLIC').format(sql.Identifier(service)))
                target.execute(sql.SQL('ALTER ROLE {} IN DATABASE {} SET search_path TO {}')
                               .format(sql.Identifier(role), sql.Identifier(name), sql.Identifier(service)))
    except BaseException:
        # Cleanup only objects created by THIS invocation, never existing databases.
        if created_database:
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
        for role in reversed(created_roles):
            admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
        raise
    return {'version': 1, 'disposable': True, 'database': name, 'services': {
        service: {'schema': service, 'user': roles[service], 'password': passwords[service]}
        for service in SERVICES}}


def service_environment(manifest, service, *, host, port):
    require(manifest.get('disposable') is True and service in SERVICES, 'Disposable manifest required.')
    prefix = PREFIXES[service]
    entry = manifest['services'][service]
    return {'DEBUG': 'true', 'CRM_DB_SCHEMA': service,
            prefix + '_HOST': host, prefix + '_PORT': str(port),
            prefix + ('_DB' if service == 'isolation' else '_NAME'): manifest['database'],
            prefix + '_USER': entry['user'], prefix + '_PASSWORD': entry['password']}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Provision a NEW disposable PostgreSQL rehearsal target.')
    parser.add_argument('--name', required=True)
    parser.add_argument('--output', type=Path, required=True, help='New private credentials file, outside Git.')
    parser.add_argument('--disposable', action='store_true', required=True)
    args = parser.parse_args(argv)
    try:
        output = plain_path(args.output)
        require(output.is_relative_to(plain_path(Path(__file__).resolve().parents[1] / 'private-media')), 'Private output directory required.')
        require(not output.exists(), 'Destination exists.')
        require(bool(re.fullmatch(r'amx_rehearsal_[a-z0-9]{6,20}', args.name)), 'Disposable database name required.')
        # PG* environment is used only by the operator connection, not logged.
        with psycopg.connect(autocommit=True, connect_timeout=5) as admin:
            require(admin.info.host in ('localhost', '127.0.0.1', '::1'), 'Local rehearsal server required.')
            manifest = provision(admin, args.name)
            manifest['host'] = admin.info.host
            manifest['port'] = admin.info.port
        exclusive_write(output, json.dumps(manifest, indent=2).encode())
        print('Disposable target created: one database, three schemas. Credentials written privately. No source imported.')
        return 0
    except (BackupError, psycopg.Error, OSError, ValueError):
        print('Target creation failed. Existing databases are never reused; inspect the new target before retrying.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
