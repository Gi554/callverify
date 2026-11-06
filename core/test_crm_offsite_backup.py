from io import BytesIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipIf
from unittest.mock import patch

from cryptography.fernet import Fernet

from scripts import crm_offsite_backup as offsite
from scripts import daily_crm_backup as daily


class Stream:
    def __init__(self, data):
        self.data = BytesIO(data)

    def iter_chunks(self, chunk_size):
        while chunk := self.data.read(chunk_size):
            yield chunk

    def close(self):
        self.data.close()


class FakeS3:
    def __init__(self, *, corrupt=False):
        self.objects = {}
        self.calls = []
        self.corrupt = corrupt

    def upload_file(self, filename, bucket, key, *, ExtraArgs):
        self.calls.append(('upload', key))
        self.objects[bucket, key] = (Path(filename).read_bytes(), ExtraArgs['Metadata'])

    def put_object(self, *, Bucket, Key, Body, Metadata, **kwargs):
        self.calls.append(('complete', Key))
        self.objects[Bucket, Key] = (Body, Metadata)

    def head_object(self, *, Bucket, Key):
        data, metadata = self.objects[Bucket, Key]
        return {'ContentLength': len(data), 'Metadata': metadata}

    def get_object(self, *, Bucket, Key):
        data, _ = self.objects[Bucket, Key]
        if self.corrupt:
            data = data + b'corrupt'
        return {'Body': Stream(data)}


class OffsiteBackupTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / '.git').mkdir()
        (self.root / '.env').write_text('SECRET=private\n', encoding='utf-8')
        self.encryption = Fernet(Fernet.generate_key())
        self.config = {
            'bucket': 'orvia-test-backups',
            'region': 'ca-central-1',
            'endpoint': 'https://s3.example.test',
            'prefix': 'orvia-test',
            'access_key': 'test-access-key',
            'secret_key': 'test-secret-key',
        }

    def archive(self):
        def source(args):
            return b'PGDMP synthetic dump' if 'pg_dump' in args[-1] else b'private media'

        with patch.object(daily, 'bounded', side_effect=source):
            folder = daily.capture(self.root, self.encryption)
        proof = {
            'network': 'none',
            'production_unchanged': True,
            'postgres': [{'service': service, 'restored': True} for service in daily.SERVICES],
        }
        (folder / 'restore-check-1234abcd.json').write_text(json.dumps(proof), encoding='utf-8')
        return folder

    def test_config_reads_only_dedicated_keys_and_rejects_partial_destination(self):
        env = self.root / '.git' / 'crm-backup-s3.env'
        env.write_text('S3_BUCKET=runtime-media\n', encoding='utf-8')
        if os.name == 'posix':
            os.chmod(env, 0o600)
        self.assertIsNone(offsite.read_config(env))
        env.write_text(
            'CRM_BACKUP_S3_BUCKET=orvia-test-backups\n'
            'CRM_BACKUP_S3_ACCESS_KEY_ID=test-access-key\n',
            encoding='utf-8',
        )
        with self.assertRaises(daily.BackupError):
            offsite.read_config(env)

    @skipIf(os.name != 'posix', 'Unix permissions only')
    def test_config_file_rejects_group_or_world_readable_permissions(self):
        env = self.root / '.git' / 'crm-backup-s3.env'
        env.write_text('CRM_BACKUP_S3_BUCKET=orvia-test-backups\n', encoding='utf-8')
        os.chmod(env, 0o644)
        with self.assertRaises(daily.BackupError):
            offsite.read_config(env)

    def test_only_encrypted_archives_are_uploaded_and_verified_before_completion_marker(self):
        folder = self.archive()
        client = FakeS3()
        result = offsite.upload_archive(
            folder, self.encryption, self.config, restore_verified=True, client=client
        )
        self.assertTrue(result['uploaded'])
        self.assertTrue(result['completion_marker'])
        self.assertTrue(result['client_side_encryption'])
        self.assertEqual(result['objects_verified'], 6)
        self.assertEqual(client.calls[-1][0], 'complete')
        uploaded = [key for action, key in client.calls if action == 'upload']
        self.assertEqual(len(uploaded), 6)
        self.assertTrue(all(key.startswith('orvia-test/') for key in uploaded))
        self.assertNotIn('crm-daily-backup.key', '\n'.join(key for _, key in client.calls))
        self.assertEqual(len(client.objects), 7)

    def test_remote_integrity_failure_never_writes_completion_marker(self):
        folder = self.archive()
        client = FakeS3(corrupt=True)
        with self.assertRaises(daily.BackupError):
            offsite.upload_archive(
                folder, self.encryption, self.config, restore_verified=True, client=client
            )
        self.assertFalse(any(action == 'complete' for action, _ in client.calls))

    def test_unexpected_unencrypted_file_is_never_uploaded(self):
        folder = self.archive()
        (folder / 'unexpected.txt').write_text('private', encoding='utf-8')
        client = FakeS3()
        with self.assertRaises(daily.BackupError):
            offsite.upload_archive(
                folder, self.encryption, self.config, restore_verified=True, client=client
            )
        self.assertEqual(client.calls, [])

    def test_restore_verification_is_mandatory_for_offsite_upload(self):
        folder = self.archive()
        client = FakeS3()
        with self.assertRaises(daily.BackupError):
            offsite.upload_archive(folder, self.encryption, self.config, client=client)
        self.assertEqual(client.calls, [])

    def test_archive_with_a_failed_restore_proof_is_never_uploaded(self):
        folder = self.archive()
        (folder / 'restore-check-1234abcd.json').write_text(
            json.dumps({'network': 'bridge', 'production_unchanged': False, 'postgres': []}),
            encoding='utf-8',
        )
        client = FakeS3()
        with self.assertRaises(daily.BackupError):
            offsite.upload_archive(
                folder, self.encryption, self.config, restore_verified=True, client=client
            )
        self.assertEqual(client.calls, [])
