"""Encrypted online snapshots and isolated PostgreSQL restore checks on the VPS.

Each pg_dump is consistent independently; this is not a cross-service transaction.
No backup purge, production restore or provider command is performed here.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from uuid import uuid4
from cryptography.fernet import Fernet

MAX_BYTES = 256 * 1024 * 1024
SERVICES = ('db', 'portal-db', 'assurance-db')
COMPOSE = [
    'docker',
    'compose',
    '-f',
    'compose.yaml',
    '-f',
    'infra/compose.crm.yaml',
    '-f',
    'compose.production.yaml',
]


class BackupError(ValueError):
    pass


def run(args, data=None, timeout=180):
    result = subprocess.run(
        args, input=data, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout
    )
    if result.returncode:
        raise BackupError('Commande de sauvegarde/restauration en échec.')
    return result.stdout


def bounded(args):
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    timer = threading.Timer(180, process.kill)
    timer.start()
    try:
        data = process.stdout.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise BackupError('Composant supérieur à 256 Mio ; adaptation de sauvegarde requise.')
        if process.wait(timeout=10):
            raise BackupError('Capture indisponible.')
        return data
    finally:
        timer.cancel()
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()


def write(path, data):
    with path.open('xb') as stream:
        os.chmod(path, 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def cipher(root):
    key = root / '.git' / 'crm-daily-backup.key'
    if key.is_symlink():
        raise BackupError('Lien de clé refusé.')
    if not key.exists():
        write(key, Fernet.generate_key())
    if os.name == 'posix' and key.stat().st_mode & 0o077:
        raise BackupError('Clé privée : permissions 600 requises.')
    return Fernet(key.read_bytes().strip())


def validate_root(value):
    root = Path(value).absolute()
    if (
        root.is_symlink()
        or '..' in root.parts
        or not (root / '.git').is_dir()
        or not (root / '.env').is_file()
    ):
        raise BackupError('Racine CRM explicite requise.')
    return root.resolve()


def ensure_package_root(root):
    """Make package imports work when cron executes this file by absolute path."""
    path = str(Path(root).resolve())
    if path not in sys.path:
        sys.path.insert(0, path)


def capture(root, encryption):
    target = root / '.daily-backups'
    if target.is_symlink():
        raise BackupError('Lien de sauvegarde refusé.')
    target.mkdir(mode=0o700, exist_ok=True)
    if os.name == 'posix' and target.stat().st_mode & 0o077:
        raise BackupError('Dossier de sauvegarde privé requis.')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:12]
    folder = target / stamp
    folder.mkdir(mode=0o700)
    metadata = {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'mode': 'online-independent-snapshots',
        'components': {},
    }
    for service in SERVICES:
        data = bounded(
            COMPOSE
            + [
                'exec',
                '-T',
                service,
                'sh',
                '-c',
                'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-acl',
            ]
        )
        if not data.startswith(b'PGDMP'):
            raise BackupError('Archive PostgreSQL invalide.')
        name = service + '.dump'
        write(folder / (name + '.enc'), encryption.encrypt(data))
        metadata['components'][name] = {
            'size': len(data),
            'sha256': hashlib.sha256(data).hexdigest(),
        }
    for name, data in [
        (
            'media.tar.gz',
            bounded(
                COMPOSE + ['exec', '-T', 'api', 'tar', '-czf', '-', '-C', '/app/private-media', '.']
            ),
        ),
        ('config.env', (root / '.env').read_bytes()),
    ]:
        write(folder / (name + '.enc'), encryption.encrypt(data))
        metadata['components'][name] = {
            'size': len(data),
            'sha256': hashlib.sha256(data).hexdigest(),
        }
    write(
        folder / 'manifest.enc', encryption.encrypt(json.dumps(metadata, sort_keys=True).encode())
    )
    # Only this marker identifies a completed archive; failed partial captures are never selected.
    write(folder / 'complete', b'1\n')
    write(
        root / '.git' / ('crm-backup-last-' + stamp + '.json'),
        json.dumps({'backup': stamp, 'state': 'captured', 'at': metadata['created_at']}).encode(),
    )
    return folder


def read_archive(folder, encryption):
    if folder.is_symlink() or not (folder / 'complete').is_file():
        raise BackupError('Sauvegarde complète requise.')
    manifest = folder / 'manifest.enc'
    if manifest.stat().st_size > 1000000:
        raise BackupError('Manifeste trop volumineux.')
    metadata = json.loads(encryption.decrypt(manifest.read_bytes()))
    expected = {service + '.dump' for service in SERVICES} | {'media.tar.gz', 'config.env'}
    if set(metadata['components']) != expected:
        raise BackupError('Composants inattendus.')
    return metadata


def component(folder, name, metadata, encryption):
    path = folder / (name + '.enc')
    if path.is_symlink() or path.stat().st_size > MAX_BYTES * 2:
        raise BackupError('Archive non valide.')
    data = encryption.decrypt(path.read_bytes())
    item = metadata['components'][name]
    if len(data) != item['size'] or hashlib.sha256(data).hexdigest() != item['sha256']:
        raise BackupError('Intégrité invalide.')
    return data


def verify_restore(folder, encryption):
    metadata = read_archive(folder, encryption)
    source_id = run(COMPOSE + ['ps', '-q', 'db']).decode().strip()
    image = run(['docker', 'inspect', '--format', '{{.Image}}', source_id]).decode().strip()
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', image):
        raise BackupError('Image PostgreSQL non reconnue.')
    container = None
    try:
        container = (
            run(
                [
                    'docker',
                    'run',
                    '--rm',
                    '-d',
                    '--network',
                    'none',
                    '--label',
                    'orvia.restore-check=true',
                    '--name',
                    'orvia-restore-' + uuid4().hex,
                    '-e',
                    'POSTGRES_HOST_AUTH_METHOD=trust',
                    image,
                ]
            )
            .decode()
            .strip()
        )
        if not re.fullmatch(r'[a-f0-9]{64}', container):
            raise BackupError('Conteneur de contrôle invalide.')
        for _ in range(60):
            ready = subprocess.run(
                ['docker', 'exec', container, 'pg_isready', '-U', 'postgres'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise BackupError('Base de contrôle indisponible.')
        results = []
        for index, service in enumerate(SERVICES):
            database = 'crm_restore_' + str(index)
            run(['docker', 'exec', container, 'createdb', '-U', 'postgres', database])
            data = component(folder, service + '.dump', metadata, encryption)
            run(
                [
                    'docker',
                    'exec',
                    '-i',
                    container,
                    'pg_restore',
                    '-U',
                    'postgres',
                    '-d',
                    database,
                    '--no-owner',
                    '--no-acl',
                    '--exit-on-error',
                    '--single-transaction',
                ],
                data,
            )
            tables = int(
                run(
                    [
                        'docker',
                        'exec',
                        container,
                        'psql',
                        '-U',
                        'postgres',
                        '-d',
                        database,
                        '-Atc',
                        "SELECT count(*) FROM pg_tables WHERE schemaname='public'",
                    ]
                )
                .decode()
                .strip()
            )
            migrations = int(
                run(
                    [
                        'docker',
                        'exec',
                        container,
                        'psql',
                        '-U',
                        'postgres',
                        '-d',
                        database,
                        '-Atc',
                        'SELECT count(*) FROM django_migrations',
                    ]
                )
                .decode()
                .strip()
            )
            if tables < 1 or migrations < 1:
                raise BackupError('Schéma restauré incomplet.')
            # Count every restored public table inside the isolated database.
            sql = "DO $$ DECLARE r record; n bigint; BEGIN FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='public' LOOP EXECUTE format('SELECT count(*) FROM public.%I',r.tablename) INTO n; END LOOP; END $$;"
            run(
                [
                    'docker',
                    'exec',
                    container,
                    'psql',
                    '-U',
                    'postgres',
                    '-d',
                    database,
                    '-v',
                    'ON_ERROR_STOP=1',
                    '-c',
                    sql,
                ]
            )
            results.append(
                {'service': service, 'tables': tables, 'migrations': migrations, 'restored': True}
            )
        # Verify private files and encrypted config without extracting or printing them.
        import tarfile
        from io import BytesIO

        with tarfile.open(
            fileobj=BytesIO(component(folder, 'media.tar.gz', metadata, encryption)), mode='r:gz'
        ) as archive:
            media_entries = len(archive.getmembers())
        if not component(folder, 'config.env', metadata, encryption):
            raise BackupError('Configuration vide.')
        result = {
            'verified_at': datetime.now(timezone.utc).isoformat(),
            'postgres': results,
            'media_entries': media_entries,
            'network': 'none',
            'production_unchanged': True,
        }
        write(folder / ('restore-check-' + uuid4().hex[:8] + '.json'), json.dumps(result).encode())
        return result
    finally:
        if container and re.fullmatch(r'[a-f0-9]{64}', container):
            # Only the newly created isolated container may be removed; never source services.
            subprocess.run(
                ['docker', 'rm', '-f', '-v', container],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def install_cron(root):
    if not re.fullmatch(r'/[a-zA-Z0-9_/-]+', str(root)):
        raise BackupError('Chemin de planification simple requis.')
    marker = '# orvia-encrypted-daily-backup'
    previous = subprocess.run(['crontab', '-l'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if previous.returncode not in (0, 1):
        raise BackupError('Crontab indisponible.')
    lines = [line for line in previous.stdout.decode().splitlines() if marker not in line]
    entry = f'15 4 * * * /usr/bin/python3 {root}/scripts/daily_crm_backup.py --root {root} --verify-restore >> {root}/.git/crm-daily-backup.log 2>&1 {marker}'
    lines.append(entry)
    run(['crontab', '-'], ('\n'.join(lines) + '\n').encode())
    return {
        'scheduled': True,
        'hour_server': '04:15',
        'encrypted': True,
        'restore_check': 'daily',
        'other_cron_entries_preserved': True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--verify-restore', action='store_true')
    parser.add_argument('--archive')
    parser.add_argument('--install-cron', action='store_true')
    parser.add_argument('--require-offsite', action='store_true')
    args = parser.parse_args()
    root = validate_root(args.root)
    os.chdir(root)
    ensure_package_root(root)
    if args.install_cron:
        if args.archive or args.verify_restore:
            raise BackupError('Installation de cron seule requise.')
        print(json.dumps(install_cron(root)))
        return
    import fcntl

    with (root / '.git' / 'crm-deploy.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        encryption = cipher(root)
        if args.archive:
            folder = Path(args.archive).resolve()
            if folder.parent != root / '.daily-backups':
                raise BackupError('Archive hors du dossier de sauvegarde refusée.')
        else:
            folder = capture(root, encryption)
        verified = verify_restore(folder, encryption) if args.verify_restore else None
        from scripts.crm_offsite_backup import read_config, upload_archive

        remote_config = read_config(root / '.git' / 'crm-backup-s3.env')
        if args.require_offsite and not remote_config:
            raise BackupError('Destination hors site non configurée.')
        remote = None
        if remote_config:
            if not verified:
                raise BackupError('La vérification de restauration est obligatoire avant l’upload.')
            remote = upload_archive(
                folder, encryption, remote_config, restore_verified=bool(verified)
            )
        print(
            json.dumps(
                {
                    'backup': folder.name,
                    'encrypted': True,
                    'state': 'restore_verified' if verified else 'captured',
                    'verification': verified,
                    'offsite': remote or {'configured': False, 'uploaded': False},
                }
            )
        )


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(
            'Sauvegarde CRM en échec : vérifier les services, droits, volumes et espace disque.',
            file=__import__('sys').stderr,
        )
        raise SystemExit(1)
