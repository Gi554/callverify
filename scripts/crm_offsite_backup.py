"""Upload only verified, client-encrypted CRM snapshots to private S3 storage."""

import hashlib
import json
import os
import re
import stat
from pathlib import Path

from scripts.daily_crm_backup import BackupError, SERVICES, component, read_archive

CONFIG_KEYS = {
    'CRM_BACKUP_S3_BUCKET',
    'CRM_BACKUP_S3_REGION',
    'CRM_BACKUP_S3_ENDPOINT_URL',
    'CRM_BACKUP_S3_PREFIX',
    'CRM_BACKUP_S3_ACCESS_KEY_ID',
    'CRM_BACKUP_S3_SECRET_ACCESS_KEY',
}
ARCHIVE_NAME = re.compile(r'^\d{8}T\d{6}Z-[a-f0-9]{12}$')
RESTORE_CHECK = re.compile(r'^restore-check-[a-f0-9]{8}\.json$')
BUCKET_NAME = re.compile(r'^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$')


def _env_value(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def read_config(env_file):
    """Read the dedicated private credential file, never the shared Compose .env."""
    path = Path(env_file)
    if path.is_symlink():
        raise BackupError('Fichier de configuration S3 non sûr.')
    if not path.exists():
        return None
    if os.name == 'posix' and path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise BackupError('Permissions du fichier de configuration S3 trop ouvertes.')
    values = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        match = re.match(r'^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$', line)
        if match and match.group(1) in CONFIG_KEYS:
            values[match.group(1)] = _env_value(match.group(2))
    if not values.get('CRM_BACKUP_S3_BUCKET'):
        if any(value for key, value in values.items() if key != 'CRM_BACKUP_S3_BUCKET'):
            raise BackupError('Configuration S3 incomplète.')
        return None

    bucket = values['CRM_BACKUP_S3_BUCKET']
    access = values.get('CRM_BACKUP_S3_ACCESS_KEY_ID', '')
    secret = values.get('CRM_BACKUP_S3_SECRET_ACCESS_KEY', '')
    prefix = values.get('CRM_BACKUP_S3_PREFIX', 'orvia-crm-backups').strip('/')
    endpoint = values.get('CRM_BACKUP_S3_ENDPOINT_URL', '')
    region = values.get('CRM_BACKUP_S3_REGION', 'ca-central-1')
    if not BUCKET_NAME.fullmatch(bucket) or '..' in bucket:
        raise BackupError('Nom de bucket S3 invalide.')
    if not access or not secret:
        raise BackupError('Identifiants S3 dédiés manquants.')
    if (
        not prefix
        or not re.fullmatch(r'[A-Za-z0-9/_-]+', prefix)
        or '..' in prefix
        or '//' in prefix
    ):
        raise BackupError('Préfixe de stockage S3 invalide.')
    if endpoint and not re.fullmatch(r'https://[^\s/]+(?:/[^\s]*)?', endpoint):
        raise BackupError('Endpoint S3 HTTPS invalide.')
    if not re.fullmatch(r'[a-zA-Z0-9-]{2,40}', region):
        raise BackupError('Région S3 invalide.')
    return {
        'bucket': bucket,
        'region': region,
        'endpoint': endpoint or None,
        'prefix': prefix,
        'access_key': access,
        'secret_key': secret,
    }


def _client(config):
    import boto3
    from botocore.config import Config

    return boto3.client(
        's3',
        region_name=config['region'],
        endpoint_url=config['endpoint'],
        aws_access_key_id=config['access_key'],
        aws_secret_access_key=config['secret_key'],
        config=Config(
            connect_timeout=10,
            read_timeout=60,
            retries={'max_attempts': 3, 'mode': 'standard'},
            s3={'addressing_style': 'path'},
        ),
    )


def _sha256_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def upload_archive(folder, encryption, config, *, restore_verified=False, client=None):
    """Upload an archive only after local restore verification; mark it complete last."""
    folder = Path(folder)
    if folder.is_symlink() or not ARCHIVE_NAME.fullmatch(folder.name):
        raise BackupError('Nom d’archive distante invalide.')
    if not restore_verified:
        raise BackupError('La restauration isolée doit être vérifiée avant l’upload.')
    manifest = read_archive(folder, encryption)
    expected = {'manifest.enc'} | {name + '.enc' for name in manifest['components']}
    files = list(folder.iterdir())
    if any(path.is_symlink() or not path.is_file() for path in files):
        raise BackupError('Fichier inattendu ou lien symbolique dans la sauvegarde.')
    names = {path.name for path in files}
    extras = names - expected - {'complete'}
    if (
        not expected.issubset(names)
        or 'complete' not in names
        or any(not RESTORE_CHECK.fullmatch(name) for name in extras)
    ):
        raise BackupError('Contenu d’archive incomplet ou inattendu.')
    checks = [path for path in files if RESTORE_CHECK.fullmatch(path.name)]
    if not checks:
        raise BackupError('Preuve de restauration isolée absente.')
    try:
        proof = json.loads(max(checks, key=lambda path: path.stat().st_mtime).read_text('utf-8'))
    except (OSError, ValueError):
        raise BackupError('Preuve de restauration isolée invalide.') from None
    rows = proof.get('postgres') if isinstance(proof, dict) else None
    if not isinstance(rows, list) or any(not isinstance(item, dict) for item in rows):
        raise BackupError('Preuve de restauration isolée invalide.')
    restored = {item.get('service') for item in rows if item.get('restored') is True}
    if (
        proof.get('network') != 'none'
        or proof.get('production_unchanged') is not True
        or restored != set(SERVICES)
    ):
        raise BackupError('Preuve de restauration isolée invalide.')
    if (folder / 'complete').read_bytes() != b'1\n':
        raise BackupError('Marqueur de sauvegarde complète invalide.')

    client = client or _client(config)
    root = f"{config['prefix'].rstrip('/')}/{folder.name}/"
    total_bytes = 0
    for name in sorted(expected):
        path = folder / name
        if name != 'manifest.enc':
            component(folder, name[:-4], manifest, encryption)
        digest = _sha256_file(path)
        size = path.stat().st_size
        key = root + name
        client.upload_file(
            str(path),
            config['bucket'],
            key,
            ExtraArgs={
                'Metadata': {'sha256': digest, 'archive': folder.name},
            },
        )
        remote = client.head_object(Bucket=config['bucket'], Key=key)
        if (
            remote.get('ContentLength') != size
            or remote.get('Metadata', {}).get('sha256') != digest
            or remote.get('Metadata', {}).get('archive') != folder.name
        ):
            raise BackupError('Vérification de l’objet distant échouée.')
        body = client.get_object(Bucket=config['bucket'], Key=key)['Body']
        remote_hash = hashlib.sha256()
        remote_size = 0
        try:
            for chunk in body.iter_chunks(chunk_size=1024 * 1024):
                remote_hash.update(chunk)
                remote_size += len(chunk)
        finally:
            body.close()
        if remote_size != size or remote_hash.hexdigest() != digest:
            raise BackupError('Intégrité de la copie distante invalide.')
        total_bytes += size

    marker_key = root + 'complete'
    client.put_object(
        Bucket=config['bucket'],
        Key=marker_key,
        Body=b'1\n',
        Metadata={'archive': folder.name, 'objects': str(len(expected))},
    )
    marker = client.head_object(Bucket=config['bucket'], Key=marker_key)
    if (
        marker.get('ContentLength') != 2
        or marker.get('Metadata', {}).get('archive') != folder.name
        or marker.get('Metadata', {}).get('objects') != str(len(expected))
    ):
        raise BackupError('Marqueur distant non confirmé.')
    return {
        'uploaded': True,
        'objects_verified': len(expected),
        'bytes_verified': total_bytes,
        'completion_marker': True,
        'client_side_encryption': True,
        'server_side_encryption': 'provider_policy_required',
    }
