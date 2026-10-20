"""Bounded, encrypted local SQLite backups. Never restores over a running CRM."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import sys
import time
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile
from cryptography.fernet import Fernet, InvalidToken

SERVICES = ('portal', 'assurance', 'isolation')
MAX_BYTES = 256 * 1024 * 1024
MAX_FILES = 10000

class BackupError(ValueError):
    pass

def require(condition, message):
    if not condition:raise BackupError(message)

def plain_path(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        require(not part.is_symlink() and not part.is_junction(), 'Liens symboliques et jonctions refusés.')
    return path.resolve()

def exclusive_write(path, data):
    path = plain_path(path)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise

def cipher(key_file):
    path = plain_path(key_file)
    require(path.is_file() and path.stat().st_size <= 100, 'Fichier de clé invalide.')
    try:return Fernet(path.read_bytes().strip())
    except (ValueError, TypeError) as error:raise BackupError('Clé Fernet invalide.') from error

def database_info(db):
    db.execute('PRAGMA trusted_schema=OFF')
    require(db.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'Intégrité SQLite incorrecte.')
    require(not db.execute('PRAGMA foreign_key_check').fetchall(), 'Références SQLite incohérentes.')
    tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    require(bool(tables), 'Base SQLite vide : aucune table métier.')
    return {name:db.execute('SELECT COUNT(*) FROM "'+name.replace('"', '""')+'"').fetchone()[0] for name in tables}

def snapshot(path):
    path = plain_path(path)
    require(path.is_file() and path.stat().st_size <= MAX_BYTES, 'Base source absente ou trop volumineuse.')
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=5)) as source, closing(sqlite3.connect(':memory:')) as target:
        # SQLite's backup API includes committed WAL data; no plain copy of an open database.
        started=time.monotonic()
        def progress(status, remaining, total):
            require(time.monotonic()-started < 60, 'Copie SQLite trop longue ; vérifiez l’arrêt des services.')
            require(total*source.execute('PRAGMA page_size').fetchone()[0] <= MAX_BYTES, 'Base SQLite trop volumineuse.')
        source.backup(target, pages=256, progress=progress)
        info = database_info(target)
        data = target.serialize()
        # Official sqlite3_deserialize guidance: a complete snapshot needs rollback
        # header bytes in memory, even when the source database used WAL.
        require(data.startswith(b'SQLite format 3\x00'), 'En-tête SQLite incorrect.')
        data=data[:18]+b'\x01\x01'+data[20:]
    return data, info

def safe_name(name):
    require(isinstance(name, str) and len(name) <= 1000, 'Nom d’archive invalide.')
    parts = PurePosixPath(name).parts
    require(name and not name.startswith('/') and '\\' not in name and str(PurePosixPath(name)) == name, 'Chemin d’archive invalide.')
    for part in parts:
        require(part not in ('.', '..') and not part.endswith((' ', '.')) and
                not any(ord(c)<32 or c in '<>:"|?*' for c in part), 'Chemin d’archive non portable.')
        require(part.split('.')[0].upper() not in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}, 'Nom réservé refusé.')
    return name

def create(databases, media, key_file, output, *, quiesced=False):
    require(quiesced, 'Arrêtez les services et confirmez --quiesced avant la sauvegarde.')
    require(set(databases) == set(SERVICES), 'Les trois bases sont requises.')
    media = plain_path(media);output = plain_path(output);key_file = plain_path(key_file)
    require(media.is_dir(), 'Le dossier média doit exister, même s’il est vide.')
    require(not output.is_relative_to(media) and not key_file.is_relative_to(media), 'Archive et clé doivent être hors du dossier média.')
    require(output != key_file and not output.exists(), 'La destination existe déjà ou correspond à la clé.')
    sources = {service:plain_path(path) for service,path in databases.items()}
    require(len(set(sources.values())) == 3 and all(not path.is_relative_to(media) for path in sources.values()), 'Bases distinctes, hors média, requises.')
    require(output not in sources.values() and key_file not in sources.values(), 'Destination ou clé incompatible avec une base source.')
    encryption = cipher(key_file)
    files = {};infos = {};total = 0
    def add(name, data):
        nonlocal total
        safe_name(name);total += len(data)
        require(total <= MAX_BYTES and len(files) < MAX_FILES, 'Limite locale : 256 Mio décompressés ou 10 000 fichiers dépassée.')
        files[name] = data
    for service,path in sources.items():
        data,info = snapshot(path);add(f'databases/{service}.sqlite3', data);infos[service] = info
    for folder,dirs,names in os.walk(media, followlinks=False):
        for name in dirs:plain_path(Path(folder)/name)
        for name in sorted(names):
            path = plain_path(Path(folder)/name)
            require(path.is_file(), 'Seuls les fichiers réguliers sont acceptés.')
            before = path.stat()
            require(before.st_size <= MAX_BYTES-total, 'Volume média supérieur à la limite locale.')
            with path.open('rb') as stream:data=stream.read(MAX_BYTES-total+1)
            after = path.stat()
            require((before.st_size,before.st_mtime_ns) == (after.st_size,after.st_mtime_ns) and len(data)==before.st_size, 'Fichier modifié pendant la sauvegarde.')
            add('media/'+path.relative_to(media).as_posix(), data)
    require(len({name.casefold() for name in files}) == len(files), 'Noms de fichiers incompatibles entre Windows et Linux.')
    manifest = {'version':1,'created_at':datetime.now(timezone.utc).isoformat(),'databases':infos,
                'files':{name:{'size':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in files.items()}}
    stream = BytesIO()
    manifest_bytes=json.dumps(manifest,ensure_ascii=False).encode('utf-8')
    require(len(manifest_bytes) <= 1024*1024, 'Manifeste supérieur à la limite locale de 1 Mio.')
    with ZipFile(stream, 'w', ZIP_DEFLATED) as archive:
        for name,data in files.items():archive.writestr(name,data)
        archive.writestr('manifest.json',manifest_bytes)
    require(stream.tell() <= MAX_BYTES, 'Archive supérieure à la limite locale.')
    exclusive_write(output,encryption.encrypt(stream.getvalue()))
    return summary(manifest)

def unpack(archive_file, key_file):
    path = plain_path(archive_file)
    require(path.is_file() and path.stat().st_size <= MAX_BYTES*2, 'Archive absente ou trop volumineuse.')
    try:payload = cipher(key_file).decrypt(path.read_bytes())
    except InvalidToken as error:raise BackupError('Archive altérée ou clé incorrecte ; aucune restauration.') from error
    require(len(payload) <= MAX_BYTES, 'Archive déchiffrée trop volumineuse.')
    try:
        with ZipFile(BytesIO(payload)) as archive:
            entries = archive.infolist();names = [safe_name(item.filename) for item in entries]
            require(len(names) <= MAX_FILES+1 and len(set(name.casefold() for name in names)) == len(names), 'Archive dupliquée ou trop nombreuse.')
            require(sum(item.file_size for item in entries) <= MAX_BYTES+1024*1024, 'Volume décompressé excessif.')
            require('manifest.json' in names and archive.getinfo('manifest.json').file_size <= 1024*1024, 'Manifeste absent ou trop volumineux.')
            manifest = json.loads(archive.read('manifest.json'))
            require(isinstance(manifest,dict) and manifest.get('version')==1 and set(manifest.get('databases',{}))==set(SERVICES), 'Version ou bases du manifeste incorrectes.')
            records=manifest.get('files');require(isinstance(records,dict) and set(records)==set(names)-{'manifest.json'}, 'Inventaire incohérent.')
            require({f'databases/{service}.sqlite3' for service in SERVICES}.issubset(records), 'Base manquante dans l’archive.')
            require(all(isinstance(row,dict) and type(row.get('size')) is int and row['size']>=0 for row in records.values()), 'Tailles du manifeste invalides.')
            require(sum(row['size'] for row in records.values()) <= MAX_BYTES, 'Contenu restauré supérieur à la limite locale.')
            folded={name.casefold() for name in names}
            require(all(not any(str(parent).casefold() in folded for parent in PurePosixPath(name).parents if str(parent)!='.') for name in names), 'Conflit entre un fichier et un dossier.')
            files = {}
            for name,record in records.items():
                require(name in {f'databases/{service}.sqlite3' for service in SERVICES} or name.startswith('media/'), 'Entrée non autorisée.')
                data=archive.read(name)
                require(isinstance(record,dict) and record.get('size')==len(data) and record.get('sha256')==hashlib.sha256(data).hexdigest(), 'Empreinte ou taille incorrecte.')
                files[name]=data
            for service in SERVICES:
                with closing(sqlite3.connect(':memory:')) as db:
                    db.deserialize(files[f'databases/{service}.sqlite3'])
                    require(database_info(db)==manifest['databases'][service], 'Comptages de restauration incohérents.')
    except BackupError:
        raise
    except (BadZipFile,KeyError,TypeError,ValueError,sqlite3.Error,RuntimeError,NotImplementedError,EOFError) as error:
        raise BackupError('Archive ou base invalide ; aucune restauration.') from error
    return manifest,files

def summary(manifest):
    return {'version':1,'created_at':manifest['created_at'],'databases':len(manifest['databases']),
            'files':len(manifest['files']),'bytes':sum(row['size'] for row in manifest['files'].values())}

def restore(archive_file, key_file, target):
    target = plain_path(target)
    require(not target.exists(), 'La restauration exige un nouveau dossier ; aucun écrasement possible.')
    manifest,files=unpack(archive_file,key_file)
    target.mkdir(mode=0o700)  # Exclusive creation, after all validation.
    try:
        (target/'media').mkdir(mode=0o700)
        for name,data in files.items():
            path=target.joinpath(*PurePosixPath(name).parts)
            path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            exclusive_write(path,data)
        exclusive_write(target/'manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8'))
    except BaseException:
        # Only remove the newly created restore tree, never a pre-existing directory.
        require(target.parent == plain_path(target.parent) and not target.is_symlink() and not target.is_junction(), 'Nettoyage refusé : dossier de restauration déplacé.')
        shutil.rmtree(target)
        raise
    return summary(manifest)

def main(argv=None):
    parser=argparse.ArgumentParser(description='Sauvegarde locale SQLite CRM chiffrée, sans accès réseau.')
    commands=parser.add_subparsers(dest='command',required=True)
    keygen=commands.add_parser('keygen');keygen.add_argument('--key-file',required=True)
    backup=commands.add_parser('create')
    for service in SERVICES:backup.add_argument('--'+service,required=True)
    backup.add_argument('--media',required=True);backup.add_argument('--output',required=True)
    backup.add_argument('--quiesced',action='store_true',help='Attestation : services et workers arrêtés.')
    for name in ('verify','restore'):
        command=commands.add_parser(name);command.add_argument('--archive',required=True)
        if name=='restore':command.add_argument('--target',required=True)
    for command in (backup,commands.choices['verify'],commands.choices['restore']):command.add_argument('--key-file',required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=='keygen':exclusive_write(args.key_file,Fernet.generate_key());result={'key_created':True}
        elif args.command=='create':result=create({name:getattr(args,name) for name in SERVICES},args.media,args.key_file,args.output,quiesced=args.quiesced)
        elif args.command=='verify':result=summary(unpack(args.archive,args.key_file)[0])
        else:result=restore(args.archive,args.key_file,args.target)
    except (BackupError,OSError,sqlite3.Error) as error:
        print('Opération refusée : '+str(error),file=sys.stderr);return 1
    print(json.dumps(result));return 0

if __name__=='__main__':sys.exit(main())
