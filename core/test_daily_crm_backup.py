from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from cryptography.fernet import Fernet
from scripts import daily_crm_backup as backup


class DailyBackupTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / '.git').mkdir()
        (self.root / '.env').write_text('SECRET=private', encoding='utf-8')
        self.encryption = Fernet(Fernet.generate_key())

    def test_capture_encrypts_each_component_and_manifest_and_refuses_tampering(self):
        def source(args):
            return b'PGDMP synthetic dump' if 'pg_dump' in args[-1] else b'synthetic private media'

        with patch.object(backup, 'bounded', side_effect=source):
            folder = backup.capture(self.root, self.encryption)
        self.assertTrue((folder / 'complete').exists())
        for file in folder.glob('*.enc'):
            self.assertNotIn(b'private', file.read_bytes())
            self.assertNotIn(b'PGDMP', file.read_bytes())
        manifest = backup.read_archive(folder, self.encryption)
        self.assertEqual(
            set(manifest['components']),
            {'db.dump', 'portal-db.dump', 'assurance-db.dump', 'media.tar.gz', 'config.env'},
        )
        self.assertEqual(
            backup.component(folder, 'config.env', manifest, self.encryption), b'SECRET=private'
        )
        (folder / 'config.env.enc').write_bytes(b'corrupted')
        with self.assertRaises(Exception):
            backup.component(folder, 'config.env', manifest, self.encryption)

    def test_restore_only_creates_and_removes_its_own_networkless_container(self):
        from io import BytesIO
        import tarfile

        stream = BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz'):
            pass

        def source(args):
            return b'PGDMP synthetic dump' if 'pg_dump' in args[-1] else stream.getvalue()

        with patch.object(backup, 'bounded', side_effect=source):
            folder = backup.capture(self.root, self.encryption)
        commands = []
        container = 'a' * 64

        def run(args, data=None, timeout=180):
            commands.append(args)
            if args[:2] == ['docker', 'inspect']:
                return b'sha256:' + b'b' * 64
            if args[:2] == ['docker', 'run']:
                return container.encode()
            if 'psql' in args and '-Atc' in args:
                return b'12'
            return b'source-container'

        with (
            patch.object(backup, 'run', side_effect=run),
            patch.object(backup.subprocess, 'run') as process,
        ):
            process.return_value.returncode = 0
            result = backup.verify_restore(folder, self.encryption)
        self.assertTrue(result['production_unchanged'])
        self.assertEqual(len(result['postgres']), 3)
        creation = next(c for c in commands if c[:2] == ['docker', 'run'])
        self.assertIn('--network', creation)
        self.assertEqual(creation[creation.index('--network') + 1], 'none')
        self.assertNotIn('-p', creation)
        self.assertNotIn('-v', creation)
        self.assertEqual(process.call_args.args[0], ['docker', 'rm', '-f', '-v', container])
        self.assertTrue(all('pg_restore' not in c or container in c for c in commands))

    def test_partial_archive_is_never_considered_complete(self):
        with patch.object(backup, 'bounded', side_effect=backup.BackupError('failed')):
            with self.assertRaises(backup.BackupError):
                backup.capture(self.root, self.encryption)
        folder = next((self.root / '.daily-backups').iterdir())
        self.assertFalse((folder / 'complete').exists())
        with self.assertRaises(backup.BackupError):
            backup.read_archive(folder, self.encryption)

    def test_cron_install_preserves_other_jobs_and_replaces_only_its_own_marker(self):
        from types import SimpleNamespace

        previous = SimpleNamespace(
            returncode=0,
            stdout=b'0 3 * * * unrelated-command\n15 4 * * * old # orvia-encrypted-daily-backup\n',
        )
        with (
            patch.object(backup.subprocess, 'run', return_value=previous),
            patch.object(backup, 'run', return_value=b'') as run,
        ):
            result = backup.install_cron(PurePosixPath('/opt/amx-crm'))
        self.assertTrue(result['scheduled'])
        entry = run.call_args.args[1].decode()
        self.assertIn('unrelated-command', entry)
        self.assertEqual(entry.count('# orvia-encrypted-daily-backup'), 1)
        self.assertIn('--verify-restore', entry)
        self.assertNotIn('old #', entry)
