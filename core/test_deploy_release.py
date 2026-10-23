"""Exercise CD control flow with fake Git/Docker/HTTPS; no server or provider touched."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest import TestCase, skipUnless

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which('bash') if os.name != 'nt' else 'C:/Program Files/Git/bin/bash.exe'
SHA = 'a' * 40
OLD = 'b' * 40


def shell_path(path):
    value = str(path).replace('\\', '/')
    if len(value) > 1 and value[1] == ':':
        return '/' + value[0].lower() + value[2:]
    return value


@skipUnless(BASH and Path(BASH).exists(), 'Bash required for deployment script tests')
class DeployReleaseTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'crm'
        self.bin = self.root / 'bin'
        (self.repo / '.git').mkdir(parents=True)
        (self.repo / 'scripts').mkdir()
        self.bin.mkdir()
        (self.repo / '.env').write_text('CALLVERIFY_DOMAIN=crm.example.com\nPRIVATE=synthetic\n')
        self.write(
            self.repo / 'scripts' / 'deploy.sh', 'echo deployed >> "$LOG"\nexit "${FAIL_DEPLOY:-0}"'
        )
        self.write(self.bin / 'flock', 'exit "${LOCKED:-0}"')
        self.write(self.bin / 'sleep', 'exit 0')
        self.write(
            self.bin / 'git',
            """
echo "git $*" >> "$LOG"
case "$1" in
 status) printf '%s' "${DIRTY:-}" ;;
 rev-parse) if [[ "$2" == HEAD ]]; then echo "$OLD"; else echo "$LATEST"; fi ;;
esac
""",
        )
        self.write(
            self.bin / 'docker',
            """
echo "docker $*" >> "$LOG"
if [[ "${CONSUME_INPUT:-0}" == 1 && " $* " == *" exec "* && " $* " != *pg_restore* ]]; then
  cat >/dev/null
fi
case " $* " in
 *" ps "*) if [[ "${NOT_RUNNING:-0}" != 1 ]]; then echo synthetic-container; fi ;;
 *pg_dump*) if [[ "${FAIL_BACKUP:-0}" == 1 ]]; then exit 1; fi; echo synthetic-dump ;;
 *pg_restore*) cat >/dev/null ;;
 *" tar "*) tar -czf - --files-from /dev/null ;;
esac
""",
        )
        self.write(
            self.bin / 'curl',
            """
echo "curl $*" >> "$LOG"
if [[ "${FAIL_HEALTH:-0}" == 1 ]]; then exit 1; fi
if [[ " $* " == *" -w "* ]]; then printf 401; fi
""",
        )
        self.log = self.root / 'operations.log'

    def write(self, path, body):
        path.write_text(
            '#!/usr/bin/env bash\nset -euo pipefail\n' + body + '\n', encoding='utf-8', newline='\n'
        )
        path.chmod(0o700)

    def run_release(self, deploy_sha=SHA, deploy_path=None, via_stdin=False, **changes):
        env = {**os.environ, 'LOG': shell_path(self.log), 'OLD': OLD, 'LATEST': SHA, **changes}
        result = subprocess.run(
            [
                BASH,
                '-c',
                'export PATH="$1:$PATH"; exec bash -s -- "$3" "$4"'
                if via_stdin
                else 'export PATH="$1:$PATH"; exec bash "$2" "$3" "$4"',
                '--',
                shell_path(self.bin),
                shell_path(ROOT / 'scripts' / 'deploy-release.sh'),
                deploy_sha,
                shell_path(self.repo) if deploy_path is None else deploy_path,
            ],
            env=env,
            input=(ROOT / 'scripts' / 'deploy-release.sh').read_text() if via_stdin else None,
            capture_output=True,
            text=True,
            timeout=30,
        )
        log = self.log.read_text() if self.log.exists() else ''
        return result, log

    def test_script_transmitted_over_ssh_stdin_reaches_verification_despite_interactive_children(
        self,
    ):
        self.write(
            self.repo / 'scripts' / 'deploy.sh',
            'cat >/dev/null\necho deployed >> "$LOG"',
        )
        result, log = self.run_release(via_stdin=True, CONSUME_INPUT='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('deployed', log)
        self.assertIn('https://crm.example.com/api/isolation/work-queue/', log)
        self.assertTrue((self.repo / '.git/crm-last-successful-deploy').is_file())
        self.assertEqual((self.repo / '.git/crm-last-successful-deploy').read_text().strip(), SHA)

    def test_success_backs_up_before_checkout_and_records_verified_sha(self):
        result, log = self.run_release()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(log.index('pg_dump'), log.index('git checkout'))
        self.assertLess(log.index('git checkout'), log.index('deployed'))
        self.assertIn('https://crm.example.com/api/assurance/contacts/', log)
        self.assertEqual((self.repo / '.git/crm-last-successful-deploy').read_text().strip(), SHA)
        backup = next((self.repo / '.backups').iterdir())
        self.assertEqual(len(list(backup.glob('*.dump'))), 3)
        self.assertTrue((backup / 'media.tar.gz').is_file())
        self.assertEqual((backup / 'previous-commit').read_text().strip(), OLD)
        self.assertNotIn('PRIVATE=synthetic', result.stdout + result.stderr)

    def test_dirty_or_superseded_commits_do_not_deploy(self):
        for values in ({'DIRTY': ' M tracked.py'}, {'LATEST': 'c' * 40}):
            with self.subTest(values=values):
                result, log = self.run_release(**values)
                self.assertNotIn('deployed', log)
                self.assertNotIn('git checkout', log)
                self.assertFalse((self.repo / '.backups').exists())
                self.assertEqual(result.returncode, 1 if 'DIRTY' in values else 0)

    def test_failed_backup_prevents_checkout_and_migration(self):
        result, log = self.run_release(FAIL_BACKUP='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('git checkout', log)
        self.assertNotIn('deployed', log)

    def test_failed_migration_or_health_never_records_success(self):
        for failure in ('FAIL_DEPLOY', 'FAIL_HEALTH'):
            with self.subTest(failure=failure):
                result, _ = self.run_release(**{failure: '1'})
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.repo / '.git/crm-last-successful-deploy').exists())
                self.assertTrue((self.repo / '.backups').exists())

    def test_uninitialized_installation_requires_first_manual_deploy(self):
        result, log = self.run_release(NOT_RUNNING='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('deployed', log)
        self.assertFalse((self.repo / '.backups').exists())

    def test_same_checkout_after_failed_deploy_is_retried_until_verified(self):
        result, log = self.run_release(OLD=SHA)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('deployed', log)
        self.log.unlink()
        result, log = self.run_release(OLD=SHA)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('deployed', log)

    def test_invalid_arguments_and_existing_lock_prevent_any_deploy(self):
        for values in (
            {'deploy_sha': 'main;echo unsafe'},
            {'deploy_path': '/'},
            {'deploy_path': '/opt/crm/../other'},
            {'LOCKED': '1'},
        ):
            with self.subTest(values=values):
                result, log = self.run_release(**values)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('git fetch', log)
                self.assertNotIn('deployed', log)

    def test_shell_scripts_parse_and_backups_are_excluded_from_build(self):
        for name in ('deploy.sh', 'deploy-release.sh'):
            result = subprocess.run(
                [BASH, '-n', shell_path(ROOT / 'scripts' / name)], capture_output=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('.backups', (ROOT / '.dockerignore').read_text().splitlines())
