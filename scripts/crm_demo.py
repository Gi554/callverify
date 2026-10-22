"""Prepare/serve a separate synthetic CRM. Never loads .env or copies live data."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time

import psycopg

try:
    from scripts.crm_common_db import provision, service_environment, SERVICES, SETTINGS
    from scripts.crm_backup import plain_path, exclusive_write, require, BackupError
except ModuleNotFoundError:
    from crm_common_db import provision, service_environment, SERVICES, SETTINGS
    from crm_backup import plain_path, exclusive_write, require, BackupError

ROOT = Path(__file__).resolve().parents[1]
PORTS = {'portal': 8190, 'assurance': 8191, 'isolation': 8100}
RUNTIME_KEYS = (
    'SECRET_KEY',
    'PORTAL_SECRET_KEY',
    'ASSURANCE_SECRET_KEY',
    'ASSURANCE_ACCESS_KEY',
    'ISOLATION_ACCESS_KEY',
)


def private_path(path):
    path = plain_path(path)
    require(
        path.is_relative_to(plain_path(ROOT / 'private-media')), 'Private demo folder required.'
    )
    return path


def clean_environment(manifest, service, context):
    # Allowlist: never inherit production/provider credentials or DB selection.
    allowed = {
        'SYSTEMROOT',
        'WINDIR',
        'PATH',
        'PATHEXT',
        'TEMP',
        'TMP',
        'USERPROFILE',
        'HOME',
        'LOCALAPPDATA',
        'APPDATA',
        'COMSPEC',
    }
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env.update(service_environment(manifest, service, host=manifest['host'], port=manifest['port']))
    keys = manifest['demo']['runtime_keys']
    require(set(keys).issubset(RUNTIME_KEYS), 'Only demo signing keys may be configured.')
    env.update(keys)
    env.update(
        {
            'DJANGO_SETTINGS_MODULE': SETTINGS[service],
            'CRM_DEMO_MODE': 'true',
            'CRM_DEMO_CONTEXT': str(context),
            'PYTHONIOENCODING': 'utf-8',
            'ALLOWED_HOSTS': 'localhost,127.0.0.1,testserver',
            'CORS_ALLOWED_ORIGINS': 'http://localhost:5174,http://127.0.0.1:5174',
            'PORTAL_INTERNAL_URL': 'http://127.0.0.1:8190',
            'ASSURANCE_INTERNAL_URL': 'http://127.0.0.1:8191',
            'ISOLATION_INTERNAL_URL': 'http://127.0.0.1:8100',
            'PORTAL_PUBLIC_URL': 'http://localhost:5174',
            'LOOKUP_ENABLED': 'false',
            'CELERY_EAGER': 'false',
            'PORTAL_EMAIL_BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
        }
    )
    return env


def validate_manifest(manifest):
    require(
        manifest.get('disposable') is True and manifest.get('demo', {}).get('synthetic') is True,
        'Synthetic manifest required.',
    )
    require(
        manifest.get('host') in ('localhost', '127.0.0.1', '::1'), 'Local demo server required.'
    )
    import re

    require(
        bool(re.fullmatch(r'amx_rehearsal_[a-z0-9]{6,20}', manifest.get('database', ''))),
        'Demo database required.',
    )
    for service in SERVICES:
        entry = manifest['services'][service]
        require(
            entry['schema'] == service and entry['user'] == manifest['database'] + '_' + service,
            'Demo role mismatch.',
        )


def run_worker(manifest, service, path, args):
    result = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        env=clean_environment(manifest, service, path),
        capture_output=True,
        encoding='utf-8',
        timeout=180,
    )
    if result.returncode:
        # Log remains inside the new private demo folder; never print credentials.
        (path.parent / (service + '-failure.log')).write_text(
            result.stdout + result.stderr, encoding='utf-8'
        )
        raise BackupError('Demo preparation failed; inspect the private failure log.')
    return result.stdout


def create_demo(output, count=5000, seed=20261022):
    output = private_path(output)
    require(not output.exists(), 'Demo manifest already exists; no reseeding or reset allowed.')
    require(40 <= count <= 20000, 'Choose 40 to 20000 prospects per workspace.')
    require(
        output.parent.is_dir() and not any(output.parent.iterdir()),
        'New empty private demo folder required.',
    )
    with psycopg.connect(dbname='postgres', autocommit=True, connect_timeout=5) as admin:
        require(admin.info.host in ('localhost', '127.0.0.1', '::1'), 'Local demo server required.')
        manifest = provision(admin, 'amx_rehearsal_' + secrets.token_hex(6))
        manifest.update(host=admin.info.host, port=admin.info.port)
    manifest['demo'] = {
        'synthetic': True,
        'state': 'preparing',
        'contacts_per_space': count,
        'seed': seed,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'password': secrets.token_urlsafe(20),
        'runtime_keys': {key: secrets.token_urlsafe(32) for key in RUNTIME_KEYS},
    }
    validate_manifest(manifest)

    def save():
        output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    exclusive_write(output, json.dumps(manifest, ensure_ascii=False, indent=2).encode())
    try:
        for service in SERVICES:
            run_worker(
                manifest,
                service,
                output,
                ['manage.py', 'migrate', '--noinput', '--settings=' + SETTINGS[service]],
            )
            result = json.loads(
                run_worker(manifest, service, output, ['-m', 'scripts.crm_demo_seed'])
            )
            if service == 'portal':
                manifest['demo']['users'] = result.pop('users')
            manifest['demo'].setdefault('counts', {})[service] = result
            save()
        manifest['demo']['state'] = 'ready'
        save()
        access = (
            'CRM AMX — RECETTE FICTIVE UNIQUEMENT\nhttp://localhost:5174/crm\n\nMot de passe commun aux comptes de recette : '
            + manifest['demo']['password']
            + '\n\n'
        )
        access += '\n'.join(
            user['username']
            + ' : '
            + ', '.join(space + '/' + role for space, role in user['memberships'])
            for user in manifest['demo']['users']
        )
        access += '\n\nAucun téléphone, courriel ou calendrier réel connecté. Ne pas réutiliser ces comptes en production.\n'
        exclusive_write(output.parent / 'ACCES.txt', access.encode('utf-8'))
    except BaseException:
        manifest['demo']['state'] = 'failed'
        save()
        raise
    return manifest


def serve(path, node):
    path = private_path(path)
    manifest = json.loads(path.read_text(encoding='utf-8'))
    validate_manifest(manifest)
    require(manifest['demo'].get('state') == 'ready', 'Demo seed must be complete.')
    require(Path(node).is_file(), 'Node executable required.')
    # Fail if any port is busy, never stop another project to make room.
    for port in [5174, *PORTS.values()]:
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    processes = []
    streams = []
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        for service in SERVICES:
            stream = (path.parent / (service + '-server.log')).open('ab')
            streams.append(stream)
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        'manage.py',
                        'runserver',
                        '127.0.0.1:' + str(PORTS[service]),
                        '--noreload',
                    ],
                    cwd=ROOT,
                    env=clean_environment(manifest, service, path),
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    creationflags=flags,
                )
            )
        stream = (path.parent / 'frontend-server.log').open('ab')
        streams.append(stream)
        processes.append(
            subprocess.Popen(
                [node, 'node_modules/vite/bin/vite.js', '--config', 'vite.demo.config.ts'],
                cwd=ROOT / 'frontend',
                env=clean_environment(manifest, 'portal', path),
                stdout=stream,
                stderr=subprocess.STDOUT,
                creationflags=flags,
            )
        )
        print(
            'Synthetic CRM: http://localhost:5174/crm — credentials in the private ACCES.txt. Ctrl+C stops this demo only.',
            flush=True,
        )
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        raise BackupError('A demo service stopped. Inspect the private logs.')
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for stream in streams:
            stream.close()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Create or serve a separate synthetic CRM; no .env or live data.'
    )
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create')
    create.add_argument('--output', required=True, type=Path)
    create.add_argument('--contacts-per-space', type=int, default=5000)
    create.add_argument('--seed', type=int, default=20261022)
    start = sub.add_parser('serve')
    start.add_argument('--manifest', required=True, type=Path)
    start.add_argument('--node', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'create':
            result = create_demo(args.output, args.contacts_per_space, args.seed)
            print(
                json.dumps(
                    {
                        'synthetic': True,
                        'state': result['demo']['state'],
                        'counts': result['demo']['counts'],
                    },
                    ensure_ascii=False,
                )
            )
        else:
            serve(args.manifest, args.node)
        return 0
    except KeyboardInterrupt:
        return 0
    except (BackupError, psycopg.Error, OSError, ValueError, KeyError, subprocess.SubprocessError):
        print(
            'Demo operation failed. Inspect the private target/logs; existing sources were not changed.',
            file=sys.stderr,
        )
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
