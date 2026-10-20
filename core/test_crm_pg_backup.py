from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase,skipUnless
from unittest.mock import patch
import os
import secrets
import psycopg
from psycopg import sql
from cryptography.fernet import Fernet
from scripts import crm_pg_backup as backup

class PgBackupTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.key=self.root/'key';self.key.write_bytes(Fernet.generate_key());self.archive=self.root/'backup.enc'
    def create(self):
        with patch.object(backup,'counts',return_value=[['public','documents',1]]),patch.object(backup,'dump',return_value=b'PGDMP synthetic bytes'):
            return backup.create('assurance','amx_assurance',self.key,self.archive,quiesced=True)
    def test_encrypted_roundtrip_integrity_and_no_overwrite(self):
        result=self.create();manifest,data=backup.unpack(self.archive,self.key)
        self.assertEqual(backup.summary(manifest),result);self.assertEqual(data,b'PGDMP synthetic bytes')
        self.assertNotIn(b'synthetic',self.archive.read_bytes())
        with self.assertRaises(backup.BackupError):self.create()
        original=self.archive.read_bytes();self.archive.write_bytes(original[:-5]+b'wrong')
        with self.assertRaises(backup.BackupError):backup.unpack(self.archive,self.key)
    def test_maintenance_and_changed_counts_refused(self):
        with self.assertRaises(backup.BackupError):backup.create('portal','amx_portal',self.key,self.archive)
        with patch.object(backup,'counts',side_effect=[[['public','x',1]],[['public','x',2]]]),patch.object(backup,'dump',return_value=b'PGDMP test'):
            with self.assertRaises(backup.BackupError):backup.create('portal','amx_portal',self.key,self.archive,quiesced=True)
        self.assertFalse(self.archive.exists())
    def test_target_and_trust_required_before_any_database_connection(self):
        self.create()
        with patch.object(backup.psycopg,'connect') as connect:
            for target,trusted in [('production',True),('crm_restore_test',False),('crm_restore_bad;drop',True)]:
                with self.assertRaises(backup.BackupError):backup.restore(self.archive,self.key,target,trusted=trusted)
            connect.assert_not_called()
    def test_existing_target_never_restored_or_dropped(self):
        self.create()
        with patch.object(backup.psycopg,'connect') as connect,patch.object(backup.subprocess,'run') as run:
            connect.return_value.__enter__.return_value.execute.return_value.fetchone.return_value=(1,)
            with self.assertRaises(backup.BackupError):backup.restore(self.archive,self.key,'crm_restore_existing',trusted=True)
            self.assertEqual(connect.return_value.__enter__.return_value.execute.call_count,1);run.assert_not_called()
    def test_dump_failure_and_wrong_key_do_not_create_output(self):
        with patch.object(backup,'counts',return_value=[['public','x',1]]),patch.object(backup,'dump',side_effect=backup.BackupError('failed')):
            with self.assertRaises(backup.BackupError):backup.create('isolation','amx_isolation',self.key,self.archive,quiesced=True)
        self.assertFalse(self.archive.exists());self.create();self.key.write_bytes(Fernet.generate_key())
        with self.assertRaises(backup.BackupError):backup.unpack(self.archive,self.key)

@skipUnless(os.getenv('CRM_BACKUP_PG_TEST')=='1','Explicit disposable PostgreSQL acceptance only')
class PgBackupAcceptance(TestCase):
    def test_real_dump_restore_binary_relations_sequences_and_source_preserved(self):
        source='crm_backup_test_'+secrets.token_hex(6);target='crm_restore_'+secrets.token_hex(6)
        try:
            with psycopg.connect(dbname='postgres',autocommit=True) as admin:
                admin.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(source)))
            with psycopg.connect(dbname=source) as db:
                db.execute('CREATE TABLE contacts(id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL)')
                db.execute('CREATE TABLE documents(id BIGSERIAL PRIMARY KEY, contact_id BIGINT REFERENCES contacts(id), content BYTEA NOT NULL)')
                db.execute("INSERT INTO contacts(name) VALUES ('Synthetic backup')")
                db.execute('INSERT INTO documents(contact_id,content) VALUES (1,%s)',(b'%PDF-synthetic',))
            with TemporaryDirectory() as folder:
                key=Path(folder)/'key';key.write_bytes(Fernet.generate_key());archive=Path(folder)/'pg.enc'
                result=backup.create('assurance',source,key,archive,quiesced=True)
                self.assertEqual(result['tables'],2)
                restored=backup.restore(archive,key,target,trusted=True)
                self.assertTrue(restored['restored']);self.assertEqual(backup.counts(source),backup.counts(target))
                with psycopg.connect(dbname=target) as db:
                    self.assertEqual(db.execute('SELECT content FROM documents WHERE contact_id=1').fetchone()[0],b'%PDF-synthetic')
                    self.assertEqual(db.execute("INSERT INTO contacts(name) VALUES ('After restore') RETURNING id").fetchone()[0],2)
                with self.assertRaises(backup.BackupError):backup.restore(archive,key,target,trusted=True)
                self.assertEqual(backup.counts(source),[['public','contacts',1],['public','documents',1]])
        finally:
            # Only randomly named databases created for this opt-in CI test may be removed.
            with psycopg.connect(dbname='postgres',autocommit=True) as admin:
                for name in (target,source):
                    self.assertTrue(name.startswith(('crm_backup_test_','crm_restore_')))
                    admin.execute(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(name)))
