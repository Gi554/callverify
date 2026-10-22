from datetime import datetime, timezone
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch

import phonenumbers
import psycopg
from psycopg import sql
from scripts import crm_demo as demo
from scripts import crm_demo_seed as seed


class SyntheticDataTests(TestCase):
    def test_numbers_cannot_be_mistaken_for_assigned_subscribers_and_ids_repeat(self):
        for index in (1, 5000, 20000):
            number = phonenumbers.parse(seed.phone(index), None)
            self.assertFalse(phonenumbers.is_valid_number(number))
        self.assertNotEqual(seed.phone(1), seed.phone(2))
        self.assertEqual(seed.identifier(42, 'assurance', 'task', 1), seed.identifier(42, 'assurance', 'task', 1))
        self.assertNotEqual(seed.identifier(42, 'assurance', 'task', 1), seed.identifier(42, 'isolation', 'task', 1))

    def test_slots_do_not_overlap_across_dst_and_tasks_have_multiple_states(self):
        now = datetime(2026, 11, 1, 16, tzinfo=timezone.utc)
        slots = [seed.slot(i, 1250, now).astimezone(timezone.utc) for i in range(1250)]
        self.assertEqual(len(set(slots)), 1250)
        self.assertTrue(all((after - before).total_seconds() >= 1800 for before, after in zip(slots, slots[1:])))
        dates = [seed.task_dates(i, now) for i in range(40)]
        self.assertTrue(any(due < now and closed is None for due, closed in dates))
        self.assertTrue(any(due > now and closed is None for due, closed in dates))
        self.assertTrue(any(closed is not None for _, closed in dates))

    def test_runtime_does_not_inherit_live_credentials_or_database(self):
        manifest = {'disposable': True, 'database': 'amx_rehearsal_abc123', 'host': '127.0.0.1', 'port': 55439,
            'services': {'portal': {'user': 'demo', 'password': 'synthetic'}}, 'demo': {'runtime_keys': {}}}
        with patch.dict(os.environ, {'NEWT_CALLS_ENABLED': 'true', 'NEWT_PASSWORD': 'REAL-SECRET', 'TWILIO_AUTH_TOKEN': 'REAL-SECRET',
            'SMTP_PASSWORD': 'REAL-SECRET', 'DATABASE_URL': 'REAL-DB', 'PORTAL_DB_PASSWORD': 'REAL-SECRET'}):
            env = demo.clean_environment(manifest, 'portal', Path('private-media/context.json'))
        self.assertNotIn('NEWT_PASSWORD', env); self.assertNotIn('NEWT_CALLS_ENABLED', env)
        self.assertNotIn('REAL-SECRET', str(env)); self.assertNotIn('DATABASE_URL', env)
        self.assertEqual(env['PORTAL_DB_PASSWORD'], 'synthetic')
        self.assertEqual(env['PORTAL_EMAIL_BACKEND'], 'django.core.mail.backends.locmem.EmailBackend')
        self.assertEqual(env['LOOKUP_ENABLED'], 'false')
        manifest['demo']['runtime_keys']['NEWT_CALLS_ENABLED'] = 'true'
        with self.assertRaises(demo.BackupError):
            demo.clean_environment(manifest, 'portal', Path('private-media/context.json'))

    def test_volume_and_nonprivate_destination_fail_before_connection(self):
        with patch.object(demo.psycopg, 'connect') as connect:
            with self.assertRaises(demo.BackupError): demo.create_demo(Path('demo.json'))
            for count in (0, 39, 20001):
                with self.assertRaises(demo.BackupError): demo.create_demo(Path('private-media/unused-demo.json'), count)
            connect.assert_not_called()


@skipUnless(os.getenv('CRM_COMMON_PG_TEST') == '1', 'Explicit disposable PostgreSQL acceptance only')
class SyntheticDataAcceptance(TestCase):
    def test_linked_seed_has_all_roles_correct_results_scoped_owners_and_no_provider_data(self):
        private = demo.ROOT / 'private-media'; private.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=private) as folder:
            path = Path(folder) / 'demo.json'; manifest = None
            try:
                manifest = demo.create_demo(path, count=120, seed=42)
                self.assertEqual(manifest['demo']['state'], 'ready')
                self.assertEqual(manifest['demo']['counts']['portal']['accounts'], 22)
                self.assertEqual(manifest['demo']['counts']['assurance']['contacts'], 120)
                self.assertEqual(manifest['demo']['counts']['isolation']['prospects'], 120)
                self.assertTrue((path.parent / 'ACCES.txt').is_file())
                password = manifest['demo']['password']
                self.assertNotIn(password, json.dumps(manifest['demo']['counts']))
                with psycopg.connect(dbname=manifest['database']) as db:
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM portal.identity_membership WHERE workspace='isolation' AND role='client'").fetchone()[0], 1)
                    for table in ('portal.identity_phonecallattempt', 'portal.identity_phoneextension', 'portal.identity_calendarconnection', 'core_lookupcheck'):
                        name = table if '.' in table else 'isolation.' + table
                        self.assertEqual(db.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(*name.split('.')))).fetchone()[0], 0)
                    self.assertEqual(db.execute('SELECT COUNT(DISTINCT assigned_setter_id) FROM isolation.core_prospect').fetchone()[0], 10)
                    self.assertEqual(db.execute('SELECT COUNT(DISTINCT closer_id) FROM isolation.core_isolationvisit').fetchone()[0], 5)
                    for service, table in [('assurance', 'assurance_appointment'), ('isolation', 'core_isolationvisit')]:
                        qualified = sql.Identifier(service, table)
                        self.assertEqual(db.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(qualified)).fetchone()[0], 30)
                        self.assertTrue(db.execute(sql.SQL("SELECT 1 FROM {} WHERE status='cancelled'").format(qualified)).fetchone())
                        self.assertTrue(db.execute(sql.SQL('SELECT 1 FROM {} WHERE starts_at > now()').format(qualified)).fetchone())
                        self.assertTrue(db.execute(sql.SQL('SELECT 1 FROM {} WHERE ends_at < now()').format(qualified)).fetchone())
                    self.assertFalse(db.execute('SELECT 1 FROM isolation.core_isolationvisitresult r JOIN isolation.core_isolationvisit v ON v.id=r.visit_id WHERE v.ends_at>now() OR v.status=\'cancelled\' OR (r.closed AND NOT r.performed)').fetchone())
                    self.assertFalse(db.execute('SELECT 1 FROM assurance.assurance_contactcalloutcome WHERE (result=\'callback\' AND task_id IS NULL) OR (result=\'appointment_booked\' AND appointment_id IS NULL)').fetchone())
                    self.assertFalse(db.execute('SELECT 1 FROM isolation.core_prospect p LEFT JOIN portal.auth_user u ON u.id=p.assigned_setter_id WHERE u.id IS NULL').fetchone())
                    self.assertTrue(db.execute("SELECT 1 FROM assurance.assurance_followuptask WHERE closed_at IS NULL AND due_at < now()").fetchone())
                    self.assertTrue(db.execute("SELECT 1 FROM isolation.core_isolationfollowup WHERE closed_at IS NOT NULL").fetchone())
                    self.assertTrue(db.execute("SELECT 1 FROM isolation.core_isolationfollowup WHERE closed_at IS NULL AND due_at > now()").fetchone())
                with self.assertRaises(demo.BackupError): demo.create_demo(path, count=120)
                result = demo.run_worker(manifest, 'assurance', path, ['manage.py', 'check'])
                self.assertIn('no issues', result)
                # Even bypassing the CLI, a second seed is refused by the ORM guards.
                with self.assertRaises(demo.BackupError): demo.run_worker(manifest, 'portal', path, ['-m', 'scripts.crm_demo_seed'])
            finally:
                if manifest:
                    with psycopg.connect(dbname='postgres', autocommit=True) as admin:
                        admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(manifest['database'])))
                        for entry in manifest['services'].values(): admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(entry['user'])))
