"""Backup/restore acceptance uses only temporary SQLite databases and files."""
from contextlib import closing
from contextlib import redirect_stdout,redirect_stderr
from io import BytesIO
from io import StringIO
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile,ZIP_DEFLATED
from cryptography.fernet import Fernet
from scripts import crm_backup as backup

class LocalBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.media=self.root/'private-media';self.media.mkdir()
        (self.media/'imports').mkdir();(self.media/'imports'/'original.csv').write_bytes(b'name;phone\nsynthetic;test\n')
        self.key=self.root/'key';self.secret=Fernet.generate_key();self.key.write_bytes(self.secret)
        self.archive=self.root/'backup.enc';self.target=self.root/'restored'
        self.sources={name:self.root/(name+'.sqlite3') for name in backup.SERVICES}
        for name,path in self.sources.items():
            with closing(sqlite3.connect(path)) as db:
                db.execute('CREATE TABLE documents (id INTEGER PRIMARY KEY, content BLOB)')
                db.execute('INSERT INTO documents(content) VALUES (?)',(b'private document '+name.encode(),));db.commit()
    def create(self,**kwargs):
        return backup.create(self.sources,self.media,self.key,self.archive,quiesced=True,**kwargs)
    def rewrite(self,edit):
        payload=Fernet(self.secret).decrypt(self.archive.read_bytes())
        with ZipFile(BytesIO(payload)) as archive:entries={name:archive.read(name) for name in archive.namelist()}
        edit(entries);stream=BytesIO()
        with ZipFile(stream,'w',ZIP_DEFLATED) as archive:
            for name,data in entries.items():archive.writestr(name,data)
        self.archive.write_bytes(Fernet(self.secret).encrypt(stream.getvalue()))
    def test_encrypted_roundtrip_all_databases_binary_documents_and_media(self):
        result=self.create();self.assertEqual(result['databases'],3)
        self.assertNotIn(b'private document',self.archive.read_bytes())
        self.assertNotIn(b'original.csv',self.archive.read_bytes())
        verified=backup.summary(backup.unpack(self.archive,self.key)[0]);self.assertEqual(result,verified)
        self.assertEqual(backup.restore(self.archive,self.key,self.target),result)
        for service in backup.SERVICES:
            with closing(sqlite3.connect(self.target/'databases'/(service+'.sqlite3'))) as db:
                self.assertEqual(db.execute('SELECT content FROM documents').fetchone()[0],b'private document '+service.encode())
        self.assertEqual((self.target/'media'/'imports'/'original.csv').read_bytes(),(self.media/'imports'/'original.csv').read_bytes())
    def test_wal_commits_are_preserved(self):
        with closing(sqlite3.connect(self.sources['assurance'])) as db:
            db.execute('PRAGMA journal_mode=WAL');db.execute('INSERT INTO documents(content) VALUES (?)',(b'committed WAL document',));db.commit()
            self.create();backup.restore(self.archive,self.key,self.target)
        with closing(sqlite3.connect(self.target/'databases'/'assurance.sqlite3')) as restored:
            self.assertEqual(restored.execute('SELECT COUNT(*) FROM documents').fetchone()[0],2)
    def test_no_overwrite_and_no_source_mutation(self):
        before={name:path.read_bytes() for name,path in self.sources.items()}
        self.create();original=self.archive.read_bytes()
        with self.assertRaises(backup.BackupError):self.create()
        self.assertEqual(self.archive.read_bytes(),original)
        self.target.mkdir();(self.target/'preserve').write_text('existing')
        with self.assertRaises(backup.BackupError):backup.restore(self.archive,self.key,self.target)
        self.assertEqual((self.target/'preserve').read_text(),'existing')
        self.assertEqual(before,{name:path.read_bytes() for name,path in self.sources.items()})
    def test_wrong_key_or_tampering_leaves_no_restore_directory(self):
        self.create();other=self.root/'wrong-key';other.write_bytes(Fernet.generate_key())
        with self.assertRaises(backup.BackupError):backup.restore(self.archive,other,self.target)
        data=bytearray(self.archive.read_bytes());data[len(data)//2]^=1;self.archive.write_bytes(data)
        with self.assertRaises(backup.BackupError):backup.restore(self.archive,self.key,self.target)
        self.assertFalse(self.target.exists())
    def test_manifest_hash_count_and_traversal_refused_before_writes(self):
        self.create()
        def edit_hash(entries):
            manifest=json.loads(entries['manifest.json']);manifest['files']['media/imports/original.csv']['sha256']='0'*64;entries['manifest.json']=json.dumps(manifest).encode()
        self.rewrite(edit_hash)
        with self.assertRaises(backup.BackupError):backup.restore(self.archive,self.key,self.target)
        self.assertFalse(self.target.exists());self.archive.unlink();self.create()
        def edit_count(entries):
            manifest=json.loads(entries['manifest.json']);manifest['databases']['portal']['documents']=999;entries['manifest.json']=json.dumps(manifest).encode()
        self.rewrite(edit_count)
        with self.assertRaises(backup.BackupError):backup.restore(self.archive,self.key,self.target)
        self.assertFalse(self.target.exists());self.archive.unlink();self.create()
        self.rewrite(lambda entries:entries.update({'../escape':b'unsafe'}))
        with self.assertRaises(backup.BackupError):backup.restore(self.archive,self.key,self.target)
        self.assertFalse(self.target.exists());self.assertFalse((self.root/'escape').exists())
    def test_limits_missing_sources_maintenance_and_key_exclusion(self):
        with self.assertRaises(backup.BackupError):backup.create(self.sources,self.media,self.key,self.archive)
        with patch.object(backup,'MAX_BYTES',10):
            with self.assertRaises(backup.BackupError):self.create()
        with self.assertRaises(backup.BackupError):backup.create(self.sources,self.media,self.key,self.media/'copy',quiesced=True)
        inside=self.media/'key';inside.write_bytes(self.secret)
        with self.assertRaises(backup.BackupError):backup.create(self.sources,self.media,inside,self.archive,quiesced=True)
        self.sources['portal'].unlink()
        with self.assertRaises(backup.BackupError):self.create()
        self.assertFalse(self.archive.exists())
    def test_symlink_or_junction_rejected(self):
        link=self.media/'link'
        try:link.symlink_to(self.key)
        except OSError:self.skipTest('Symlink creation unavailable without Windows developer mode')
        with self.assertRaises(backup.BackupError):self.create()
    def test_restore_disk_failure_cleans_only_new_directory(self):
        self.create()
        with patch.object(backup,'exclusive_write',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):backup.restore(self.archive,self.key,self.target)
        self.assertFalse(self.target.exists());self.assertTrue(self.archive.exists())

    def test_cli_keygen_create_verify_restore_and_refuse_existing_key(self):
        key=self.root/'generated-key';output=StringIO();errors=StringIO()
        with redirect_stdout(output),redirect_stderr(errors):
            self.assertEqual(backup.main(['keygen','--key-file',str(key)]),0)
            original=key.read_bytes()
            self.assertEqual(backup.main(['keygen','--key-file',str(key)]),1)
            self.assertEqual(key.read_bytes(),original)
            args=['create','--key-file',str(key),'--media',str(self.media),'--output',str(self.archive),'--quiesced']
            for name,path in self.sources.items():args.extend(['--'+name,str(path)])
            self.assertEqual(backup.main(args),0)
            self.assertEqual(backup.main(['verify','--key-file',str(key),'--archive',str(self.archive)]),0)
            self.assertEqual(backup.main(['restore','--key-file',str(key),'--archive',str(self.archive),'--target',str(self.target)]),0)
        self.assertNotIn(original.decode(),output.getvalue()+errors.getvalue())

    def test_nonportable_names_and_missing_database_archive_refused(self):
        for name in ('media/../escape','media/CON.txt','media/name:stream','media/trailing.','/absolute','media\\escape'):
            with self.assertRaises(backup.BackupError):backup.safe_name(name)
        self.create()
        self.rewrite(lambda entries:entries.pop('databases/portal.sqlite3'))
        with self.assertRaises(backup.BackupError):backup.restore(self.archive,self.key,self.target)
        self.assertFalse(self.target.exists())
