from contextlib import closing,redirect_stdout,redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import sqlite3
import unittest
from scripts import crm_db_audit as audit


class DatabasePreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.sources={key:self.root/(key+'.sqlite3') for key in audit.SERVICES}
        self.report=self.root/'report.json'
        for service,path in self.sources.items():
            tables=audit.REQUIRED[service]|set(audit.IDENTITIES[service])|{'django_migrations','django_content_type'}
            with closing(sqlite3.connect(path)) as db:
                for table in tables:
                    columns=set(audit.IDENTITIES[service].get(table,[]))
                    if table=='django_migrations':columns|={'app','name'}
                    if table=='auth_user':columns|={'username','password'}
                    if table=='identity_membership':columns|={'workspace','role','user_id'}
                    if table=='identity_calendarconnection':columns|={'workspace'}
                    if table=='identity_calendarsync':columns|={'source_id','connection_id','remote_id'}
                    if table=='identity_phonecallattempt':columns|={'workspace','contact_id','request_id','user_id'}
                    definition=['id INTEGER PRIMARY KEY']
                    for column in sorted(columns):
                        if column=='id':continue
                        kind='INTEGER' if column.endswith('_id') and column not in ('remote_id','request_id') else 'TEXT'
                        extra=' REFERENCES auth_user(id)' if service=='portal' and column=='user_id' else ''
                        if table=='identity_calendarsync' and column=='connection_id':extra=' REFERENCES identity_calendarconnection(id)'
                        definition.append(audit.quote(column)+' '+kind+extra)
                    db.execute('CREATE TABLE '+audit.quote(table)+' ('+','.join(definition)+')')
                db.execute('INSERT INTO django_migrations(app,name) VALUES (?,?)',audit.LATEST[service])
                if service=='portal':
                    db.execute("INSERT INTO auth_user(id,username,password) VALUES (1,'PRIVATE PERSON','PRIVATE PASSWORD')")
                db.commit()

    def execute(self,service,sql,params=()):
        with closing(sqlite3.connect(self.sources[service])) as db:db.execute(sql,params);db.commit()
    def hashes(self):return {key:hashlib.sha256(path.read_bytes()).hexdigest() for key,path in self.sources.items()}
    def command(self,*extra):
        args=[item for key,path in self.sources.items() for item in ('--'+key,str(path))]+['--output',str(self.report),*extra]
        with redirect_stdout(StringIO()) as out,redirect_stderr(StringIO()) as err:code=audit.main(args)
        return code,out.getvalue(),err.getvalue()

    def test_aggregate_report_detects_collisions_never_exports_identity_or_changes_sources(self):
        self.execute('assurance','INSERT INTO assurance_contact(created_by_id) VALUES (1)')
        before=self.hashes();result=audit.audit(self.sources)
        self.assertEqual(result['audit_status'],'no_issues_in_checked_scope')
        self.assertFalse(result['migration_ready']);self.assertFalse(result['quiesced_declared'])
        self.assertEqual(result['target']['database_count'],1)
        shared={row['table'] for row in result['shared_tables']}
        self.assertIn('django_migrations',shared);self.assertIn('django_content_type',shared)
        self.assertNotIn('PRIVATE',json.dumps(result));self.assertNotIn('username',str(result['identity_checks']))
        self.assertEqual(self.hashes(),before)

    def test_missing_central_identity_is_a_counted_blocker_without_exposing_id(self):
        self.execute('isolation','INSERT INTO core_isolationvisit(closer_id) VALUES (9834567)')
        result=audit.audit(self.sources)
        entry=next(row for row in result['identity_checks'] if row['table']=='core_isolationvisit' and row['column']=='closer_id')
        self.assertEqual(entry['missing_identity_rows'],1)
        self.assertNotIn('9834567',json.dumps(result))
        self.assertTrue(any(row['kind']=='missing_portal_identity' for row in result['blockers']))
        code,output,error=self.command();self.assertEqual(code,2);self.assertTrue(self.report.is_file())
        self.assertIn('issues_found',output);self.assertEqual(error,'')

    def test_polymorphic_phone_and_calendar_sources_use_their_workspace(self):
        self.execute('assurance','INSERT INTO assurance_contact(id) VALUES (10)')
        self.execute('assurance','INSERT INTO assurance_appointment(id) VALUES (20)')
        self.execute('portal',"INSERT INTO identity_phonecallattempt(workspace,contact_id,user_id) VALUES ('assurance',10,1)")
        self.execute('portal',"INSERT INTO identity_calendarconnection(id,workspace) VALUES (1,'assurance')")
        self.execute('portal','INSERT INTO identity_calendarsync(connection_id,source_id) VALUES (1,20)')
        result=audit.audit(self.sources)
        self.assertTrue(all(row['missing_source_rows']==0 for row in result['source_checks']))
        self.execute('portal',"UPDATE identity_phonecallattempt SET workspace='isolation'")
        self.execute('portal','UPDATE identity_calendarsync SET source_id=21')
        result=audit.audit(self.sources)
        self.assertTrue(all(row['missing_source_rows']==1 for row in result['source_checks']))

    def test_new_unclassified_reference_or_missing_migration_blocks(self):
        self.execute('isolation','ALTER TABLE core_prospect ADD COLUMN new_owner_id INTEGER')
        self.execute('assurance','DELETE FROM django_migrations')
        result=audit.audit(self.sources)
        self.assertTrue(any(row['kind']=='unclassified_reference' and row['column']=='new_owner_id' for row in result['blockers']))
        self.assertTrue(any(row['kind']=='missing_expected_migration' for row in result['blockers']))

    def test_wal_commits_are_included_without_copying_main_database_alone(self):
        with closing(sqlite3.connect(self.sources['assurance'])) as db:
            db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA wal_autocheckpoint=0')
            db.execute('INSERT INTO assurance_contact(created_by_id) VALUES (1)');db.commit()
            result=audit.audit(self.sources)
            self.assertEqual(result['sources']['assurance']['tables']['assurance_contact']['rows'],1)

    def test_cli_requires_distinct_sources_and_never_overwrites_sources_or_existing_reports(self):
        before=self.hashes();self.report.write_text('PRESERVE')
        self.assertEqual(self.command()[0],1);self.assertEqual(self.report.read_text(),'PRESERVE')
        self.report=self.sources['portal'];self.assertEqual(self.command()[0],1)
        self.assertEqual(self.hashes(),before)
        with self.assertRaises(audit.BackupError):audit.audit({**self.sources,'assurance':self.sources['portal']})

    def test_quiesced_clean_report_is_still_not_migration_authorization(self):
        code,out,err=self.command('--quiesced');self.assertEqual(code,0,(out,err))
        result=json.loads(self.report.read_text(encoding='utf-8'))
        self.assertTrue(result['quiesced_declared']);self.assertFalse(result['migration_ready'])
        self.assertFalse(result['blockers']);self.assertIn('migration_ready',out)

    def test_missing_source_or_foreign_key_corruption_fails_without_report_or_raw_values(self):
        self.execute('portal',"INSERT INTO identity_phonecallattempt(workspace,contact_id,user_id) VALUES ('assurance',1,9834567)")
        code,out,err=self.command();self.assertEqual(code,1)
        self.assertFalse(self.report.exists());self.assertNotIn('9834567',err+out)
        self.sources['portal']=self.root/'missing.sqlite3'
        self.assertEqual(self.command()[0],1);self.assertFalse(self.sources['portal'].exists())
