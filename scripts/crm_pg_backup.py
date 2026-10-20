"""One PostgreSQL database per encrypted archive; explicit isolated restore only."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import re
import subprocess
import sys
from threading import Timer
import psycopg
from psycopg import sql
from cryptography.fernet import InvalidToken

try:
    from scripts.crm_backup import BackupError,require,cipher,exclusive_write,plain_path,SERVICES,MAX_BYTES
except ModuleNotFoundError:
    from crm_backup import BackupError,require,cipher,exclusive_write,plain_path,SERVICES,MAX_BYTES

MAGIC=b'AMXPG1\n'

def database_name(name):
    require(bool(re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]{0,62}',name)), 'Nom PostgreSQL simple requis (63 caractères maximum).')
    return name

def counts(name):
    with psycopg.connect(dbname=database_name(name),connect_timeout=10,options='-c statement_timeout=60000') as db:
        db.execute('SET TRANSACTION READ ONLY')
        tables=db.execute("SELECT schemaname,tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2").fetchall()
        require(bool(tables),'Base vide : aucune table à sauvegarder.')
        return [[schema,table,db.execute(sql.SQL('SELECT COUNT(*) FROM {}.{}').format(sql.Identifier(schema),sql.Identifier(table))).fetchone()[0]] for schema,table in tables]

def dump(name):
    # libpq uses PGHOST/PGPORT/PGUSER/PGPASSFILE/PGSSL* from the private process environment.
    # No shell, credential argument, plaintext dump file or stderr content in logs.
    process=subprocess.Popen(['pg_dump','--format=custom','--no-password','--lock-wait-timeout=10000','--dbname',database_name(name)],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    timer=Timer(120,process.kill);timer.start()
    try:
        data=process.stdout.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES:process.kill();raise BackupError('Dump supérieur à la limite de 256 Mio.')
        code=process.wait(timeout=10)
        require(code==0 and data.startswith(b'PGDMP'),'pg_dump a échoué ou a expiré ; aucune archive créée.')
        return data
    finally:
        timer.cancel()
        if process.poll() is None:process.kill()
        process.wait();process.stdout.close()

def create(service,source,key_file,output,*,quiesced=False):
    require(quiesced,'Arrêtez les écritures et confirmez --quiesced.')
    require(service in SERVICES,'Service inconnu.')
    source=database_name(source);output=plain_path(output)
    require(not output.exists() and output!=plain_path(key_file),'Archive existante ou chemin de clé incompatible.')
    encryption=cipher(key_file)
    before=counts(source);data=dump(source)
    require(before==counts(source),'Comptages modifiés pendant le dump ; rétablissez la maintenance.')
    manifest={'version':1,'engine':'postgresql','service':service,'source':source,
              'created_at':datetime.now(timezone.utc).isoformat(),'tables':before,
              'size':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    encoded=json.dumps(manifest).encode()
    require(len(encoded)<=1024*1024,'Manifeste trop volumineux.')
    exclusive_write(output,encryption.encrypt(MAGIC+len(encoded).to_bytes(4,'big')+encoded+data))
    return summary(manifest)

def unpack(archive,key_file):
    path=plain_path(archive)
    require(path.is_file() and path.stat().st_size<=MAX_BYTES*2,'Archive absente ou trop volumineuse.')
    try:raw=cipher(key_file).decrypt(path.read_bytes())
    except InvalidToken as error:raise BackupError('Archive altérée ou clé incorrecte.') from error
    require(raw.startswith(MAGIC) and len(raw)>=len(MAGIC)+4,'Format PostgreSQL incorrect.')
    length=int.from_bytes(raw[len(MAGIC):len(MAGIC)+4],'big')
    require(0<length<=1024*1024,'Manifeste invalide.')
    try:manifest=json.loads(raw[len(MAGIC)+4:len(MAGIC)+4+length])
    except (ValueError,UnicodeError) as error:raise BackupError('Manifeste illisible.') from error
    data=raw[len(MAGIC)+4+length:]
    require(isinstance(manifest,dict) and manifest.get('version')==1 and manifest.get('engine')=='postgresql' and manifest.get('service') in SERVICES,'Manifeste incompatible.')
    database_name(manifest.get('source',''))
    tables=manifest.get('tables')
    require(isinstance(tables,list) and bool(tables) and all(isinstance(row,list) and len(row)==3 and all(isinstance(v,str) and v for v in row[:2]) and type(row[2]) is int and row[2]>=0 for row in tables),'Comptages invalides.')
    require(len(data)<=MAX_BYTES and data.startswith(b'PGDMP') and manifest.get('size')==len(data) and manifest.get('sha256')==hashlib.sha256(data).hexdigest(),'Dump tronqué ou empreinte incorrecte.')
    return manifest,data

def summary(manifest):
    return {key:manifest[key] for key in ('version','service','created_at','size')}|{'tables':len(manifest['tables'])}

def restore(archive,key_file,target,*,trusted=False):
    require(trusted,'Confirmez --trusted-source : un dump peut exécuter du SQL de sa source.')
    target=database_name(target)
    require(target.startswith('crm_restore_'),'La cible doit commencer par crm_restore_ et être neuve.')
    manifest,data=unpack(archive,key_file)
    require(target!=manifest['source'],'La base source ne peut pas être la cible.')
    with psycopg.connect(dbname='postgres',autocommit=True,connect_timeout=10) as admin:
        require(not admin.execute('SELECT 1 FROM pg_database WHERE datname=%s',(target,)).fetchone(),'Base cible existante : aucun écrasement.')
        # No DROP, --clean or --create in pg_restore; CREATE DATABASE itself is exclusive.
        admin.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(target)))
        admin.execute(sql.SQL('REVOKE CONNECT, TEMPORARY ON DATABASE {} FROM PUBLIC').format(sql.Identifier(target)))
    try:
        result=subprocess.run(['pg_restore','--no-password','--no-owner','--no-acl','--exit-on-error','--single-transaction','--dbname',target],input=data,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=120,check=False)
        require(result.returncode==0,'pg_restore a échoué ; cible conservée pour diagnostic, aucun service à démarrer.')
        require(counts(target)==manifest['tables'],'Comptages restaurés différents ; ne pas utiliser cette cible.')
    except BaseException:
        # Deliberately never drops a database, even one just created by this command.
        raise
    return summary(manifest)|{'target':target,'restored':True}

def main(argv=None):
    parser=argparse.ArgumentParser(description='Sauvegarde PostgreSQL unitaire chiffrée et restauration isolée.')
    commands=parser.add_subparsers(dest='command',required=True)
    create_parser=commands.add_parser('create');create_parser.add_argument('--service',choices=SERVICES,required=True)
    create_parser.add_argument('--source',required=True);create_parser.add_argument('--output',required=True);create_parser.add_argument('--quiesced',action='store_true')
    verify_parser=commands.add_parser('verify')
    restore_parser=commands.add_parser('restore');restore_parser.add_argument('--target',required=True);restore_parser.add_argument('--trusted-source',action='store_true')
    for item in (create_parser,verify_parser,restore_parser):item.add_argument('--key-file',required=True)
    for item in (verify_parser,restore_parser):item.add_argument('--archive',required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=='create':result=create(args.service,args.source,args.key_file,args.output,quiesced=args.quiesced)
        elif args.command=='verify':result=summary(unpack(args.archive,args.key_file)[0])
        else:result=restore(args.archive,args.key_file,args.target,trusted=args.trusted_source)
    except (BackupError,OSError,psycopg.Error,subprocess.SubprocessError):
        print('Opération refusée ou échouée. Vérifiez configuration, maintenance, clé et cible ; ne démarrez pas les services sur une restauration non validée.',file=sys.stderr)
        return 1
    print(json.dumps(result));return 0

if __name__=='__main__':sys.exit(main())
