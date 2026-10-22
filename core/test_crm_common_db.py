from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import os
from pathlib import Path
import secrets
import subprocess
import sys
from unittest import TestCase, skipUnless
from unittest.mock import MagicMock, patch

from django.core.exceptions import ImproperlyConfigured
import psycopg
from psycopg import sql
from packages.database import configure_schema
from scripts import crm_common_db as common


class CommonDatabaseConfigurationTests(TestCase):
    def test_explicit_schema_only_for_matching_postgres_service(self):
        with patch.dict(os.environ, {'CRM_DB_SCHEMA': ''}):
            database = {'ENGINE': 'django.db.backends.sqlite3'}
            configure_schema(database, 'portal')
            self.assertNotIn('OPTIONS', database)
        for schema in ('public', 'assurance', 'portal,public', 'portal;DROP SCHEMA portal'):
            with patch.dict(os.environ, {'CRM_DB_SCHEMA': schema}):
                with self.assertRaises(ImproperlyConfigured):
                    configure_schema({'ENGINE': 'django.db.backends.postgresql'}, 'portal')
        with patch.dict(os.environ, {'CRM_DB_SCHEMA': 'portal'}):
            with self.assertRaises(ImproperlyConfigured):
                configure_schema({'ENGINE': 'django.db.backends.sqlite3'}, 'portal')
            database = {'ENGINE': 'django.db.backends.postgresql'}
            configure_schema(database, 'portal')
            self.assertEqual(database['OPTIONS']['options'], '-c search_path=portal')

    def test_existing_database_or_role_refused_without_ddl(self):
        for results in ([(1,)], [None, (1,)]):
            admin = MagicMock()
            admin.autocommit = True
            admin.execute.return_value.fetchone.side_effect = results
            with self.assertRaises(common.BackupError):
                common.provision(admin, 'amx_rehearsal_abc123')
            self.assertEqual(admin.execute.call_count, len(results))
        admin = MagicMock()
        with self.assertRaises(common.BackupError):
            common.provision(admin, 'existing_production')
        admin.execute.assert_not_called()

    def test_cli_invalid_name_or_nonprivate_output_never_connects_or_prints_secrets(self):
        for name, output in [
            ('prod', 'private-media/unused.json'),
            ('amx_rehearsal_abc123', 'credentials.json'),
        ]:
            with (
                patch.object(common.psycopg, 'connect') as connect,
                redirect_stdout(StringIO()) as out,
                redirect_stderr(StringIO()) as err,
            ):
                self.assertEqual(
                    common.main(['--name', name, '--output', output, '--disposable']), 1
                )
                connect.assert_not_called()
                self.assertNotIn('password', out.getvalue() + err.getvalue())

    def test_service_environment_separates_schema_and_identity(self):
        manifest = {
            'disposable': True,
            'database': 'amx_rehearsal_abc123',
            'services': {
                service: {'user': service, 'password': 'synthetic'} for service in common.SERVICES
            },
        }
        for service in common.SERVICES:
            env = common.service_environment(manifest, service, host='localhost', port=55439)
            self.assertEqual(env['CRM_DB_SCHEMA'], service)
            prefix = common.PREFIXES[service]
            self.assertEqual(env[prefix + '_PASSWORD'], 'synthetic')
            self.assertEqual(
                env[prefix + ('_DB' if service == 'isolation' else '_NAME')], manifest['database']
            )


@skipUnless(
    os.getenv('CRM_COMMON_PG_TEST') == '1', 'Explicit disposable PostgreSQL acceptance only'
)
class CommonDatabaseAcceptance(TestCase):
    def test_three_migrated_services_in_one_database_and_cross_schema_denials(self):
        name = 'amx_rehearsal_' + secrets.token_hex(6)
        manifest = None
        with psycopg.connect(dbname='postgres', autocommit=True) as admin:
            try:
                manifest = common.provision(admin, name)
                for service in common.SERVICES:
                    env = {
                        **os.environ,
                        **common.service_environment(
                            manifest, service, host=admin.info.host, port=admin.info.port
                        ),
                    }
                    # A fresh database per run; never migrate any currently deployed service.
                    result = subprocess.run(
                        [
                            sys.executable,
                            'manage.py',
                            'migrate',
                            '--noinput',
                            '--settings=' + common.SETTINGS[service],
                        ],
                        cwd=Path(__file__).resolve().parents[1],
                        env=env,
                        capture_output=True,
                        timeout=90,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
                    credentials = manifest['services'][service]
                    with psycopg.connect(
                        host=admin.info.host,
                        port=admin.info.port,
                        dbname=name,
                        user=credentials['user'],
                        password=credentials['password'],
                        autocommit=True,
                    ) as db:
                        self.assertEqual(
                            db.execute('SELECT current_database(), current_schema()').fetchone(),
                            (name, service),
                        )
                        self.assertGreater(
                            db.execute('SELECT COUNT(*) FROM django_migrations').fetchone()[0], 0
                        )
                        db.execute(
                            'CREATE TABLE rehearsal_probe(id BIGSERIAL PRIMARY KEY, value TEXT)'
                        )
                        self.assertEqual(
                            db.execute(
                                "INSERT INTO rehearsal_probe(value) VALUES ('synthetic') RETURNING id"
                            ).fetchone()[0],
                            1,
                        )
                        for other in common.SERVICES:
                            if other == service:
                                continue
                            for statement in (
                                'SELECT * FROM {}.django_migrations',
                                'CREATE TABLE {}.forbidden(id int)',
                                "INSERT INTO {}.django_migrations(app,name,applied) VALUES ('x','x',now())",
                            ):
                                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                                    db.execute(sql.SQL(statement).format(sql.Identifier(other)))
                        for statement in (
                            'CREATE TABLE public.forbidden(id int)',
                            'CREATE TEMP TABLE forbidden(id int)',
                            'CREATE DATABASE forbidden',
                            'CREATE ROLE forbidden',
                        ):
                            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                                db.execute(statement)
                        db.execute('DROP TABLE rehearsal_probe')
                # All three migration histories coexist, none in public.
                with psycopg.connect(
                    **{
                        **admin.info.get_parameters(),
                        'password': admin.info.password,
                        'dbname': name,
                    }
                ) as db:
                    self.assertEqual(
                        {
                            row[0]
                            for row in db.execute(
                                "SELECT schemaname FROM pg_tables WHERE tablename='django_migrations'"
                            )
                        },
                        set(common.SERVICES),
                    )
                    self.assertFalse(
                        db.execute("SELECT 1 FROM pg_tables WHERE schemaname='public'").fetchone()
                    )
                with self.assertRaises(common.BackupError):
                    common.provision(admin, name)
            finally:
                if manifest:
                    admin.execute(
                        sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name))
                    )
                    for entry in manifest['services'].values():
                        admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(entry['user'])))
