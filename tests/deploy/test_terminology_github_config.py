"""Receiver tests with real dotenv files and a simulated deployment."""
import contextlib
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('sync_config', SOURCE / 'scripts/terminology/sync-github-config.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
COMMIT = 'a' * 40


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / '.env.terminology-state'
        self.state.mkdir(mode=0o700)
        (self.root / 'scripts/deploy').mkdir(parents=True)
        shutil.copy2(SOURCE / 'scripts/deploy/env.sh', self.root / 'scripts/deploy/env.sh')
        self.settings = {key: 'synthetic-value' for key in module.CONFIG_KEYS}
        self.settings.update(module.OPTIONAL_SSO_DEFAULTS)
        self.settings.update(TERMINOLOGY_MACHINE_ID='a'*32, TERMINOLOGY_BACKUP_KEEP='14',
                             TERMINOLOGY_EMAIL_PORT='587', TERMINOLOGY_ADMIN_EMAIL='',
                             TERMINOLOGY_ALLOW_SELF_REGISTRATION='false',
                             TERMINOLOGY_EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend')
        # Omit retention to exercise its default.
        self.original = '# preserve comment\nUNMANAGED_IMAGE=image@sha256:abc\n' + ''.join(
            key + "='" + value + "'\n" for key, value in self.settings.items()
            if key != 'TERMINOLOGY_BACKUP_KEEP')
        self.env = self.root / '.env.terminology'
        self.active = self.state / 'active.env'
        for path in (self.env, self.active):
            path.write_text(self.original)
            path.chmod(0o600)
        self.payload = dict(commit=COMMIT, mode='apply', settings=self.settings.copy())
        self.calls = []
        self.compose_failure = False
        self.deploy_failure = False
        self.dirty = False
        self.machine = 'a'*32
        real_read = Path.read_text

        def check_output(args, **kwargs):
            if args[:2] == ['git', 'rev-parse']:
                return COMMIT + '\n'
            if args[:2] == ['git', 'status']:
                return ' M tracked\n' if self.dirty else ''
            return subprocess.check_output(args, **kwargs)

        def read_text(path, *args, **kwargs):
            if str(path) == '/etc/machine-id':
                return self.machine
            return real_read(path, *args, **kwargs)

        def run(args, **kwargs):
            self.calls.append(args)
            if args[0] == 'docker':
                if self.compose_failure:
                    raise subprocess.CalledProcessError(1, args)
            elif args[:2] == ['bash', 'scripts/deploy/deploy-terminology.sh']:
                self.assertEqual(args[3], 'update')
                if not self.deploy_failure:
                    shutil.copy2(self.env, self.active)
                return subprocess.CompletedProcess(args, 1 if self.deploy_failure else 0)
            else:
                self.fail('Unexpected command')
            return subprocess.CompletedProcess(args, 0)

        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(module, 'ROOT', self.root))
        commands = stack.enter_context(patch.object(module, 'subprocess'))
        commands.check_output.side_effect = check_output
        commands.run.side_effect = run
        commands.STDOUT = subprocess.STDOUT
        stack.enter_context(patch.object(Path, 'read_text', read_text))
        stack.enter_context(patch.dict(os.environ, SSH_ORIGINAL_COMMAND='terminology-config'))
        previous = os.umask(0o077)
        self.addCleanup(os.umask, previous)

    def receive(self):
        output = io.StringIO()
        stream = io.TextIOWrapper(io.BytesIO(json.dumps(self.payload).encode()))
        with patch.object(module.sys, 'stdin', stream), contextlib.redirect_stdout(output):
            module.receive()
        self.output = output.getvalue()
        return json.loads(self.output)

    def unchanged(self):
        self.assertEqual(self.env.read_text(), self.original)
        self.assertEqual(self.active.read_text(), self.original)
        self.assertFalse(self.calls)

    def existing_sso(self):
        """Model an already reviewed SSO deployment, without running any service."""
        self.settings.update(
            TERMINOLOGY_OIDC_SERVER_URL='https://synthetic-value/auth',
            TERMINOLOGY_OIDC_CLIENT_ID='ocl-web',
            TERMINOLOGY_KEYCLOAK_DB_PASSWORD='synthetic-keycloak-database',
            TERMINOLOGY_KEYCLOAK_ADMIN_PASSWORD='synthetic-keycloak-admin',
        )
        self.original = ''.join(key + "='" + value + "'\n" for key, value in self.settings.items())
        for path in (self.env, self.active):
            path.write_text(self.original)
        self.payload['settings'] = self.settings.copy()

    def test_legacy_configuration_and_payload_keep_local_authentication(self):
        for key in module.OPTIONAL_SSO_DEFAULTS:
            del self.payload['settings'][key]
        self.original = ''.join(
            line + '\n' for line in self.original.splitlines()
            if not any(line.startswith(key + '=') for key in module.OPTIONAL_SSO_DEFAULTS))
        for path in (self.env, self.active):
            path.write_text(self.original)
        self.assertEqual(self.receive()['status'], 'unchanged')
        self.unchanged()
        for key, value in module.OPTIONAL_SSO_DEFAULTS.items():
            self.assertEqual(module.read_configuration(self.env)[key], value)

    def test_blank_optional_admin_username_uses_default(self):
        self.payload['settings']['TERMINOLOGY_KEYCLOAK_ADMIN_USERNAME'] = ''
        self.assertEqual(self.receive()['status'], 'unchanged')
        self.unchanged()

    def test_rejects_sso_activation_through_configuration_sync(self):
        self.payload['settings'].update(
            TERMINOLOGY_OIDC_SERVER_URL='https://synthetic-value/auth',
            TERMINOLOGY_OIDC_CLIENT_ID='ocl-web',
            TERMINOLOGY_KEYCLOAK_DB_PASSWORD='synthetic-keycloak-database',
            TERMINOLOGY_KEYCLOAK_ADMIN_PASSWORD='synthetic-keycloak-admin',
        )
        with self.assertRaisesRegex(module.ConfigurationError, 'coordinated'):
            self.receive()
        self.unchanged()

    def test_existing_sso_noop_preserves_configuration(self):
        self.existing_sso()
        self.assertEqual(self.receive()['status'], 'unchanged')
        self.unchanged()

    def test_existing_sso_allows_smtp_rotation_with_profile(self):
        self.existing_sso()
        self.payload['settings']['TERMINOLOGY_EMAIL_HOST_PASSWORD'] = 'rotated-synthetic-smtp'
        result = self.receive()
        self.assertEqual(result['changed_keys'], ['TERMINOLOGY_EMAIL_HOST_PASSWORD'])
        self.assertEqual(result['status'], 'applied')
        self.assertEqual(self.calls[0][-4:], ['--profile', 'keycloak', 'config', '--quiet'])
        self.assertNotIn('rotated-synthetic-smtp', self.output)

    def test_existing_sso_registration_uses_existing_smtp(self):
        self.existing_sso()
        self.payload['settings']['TERMINOLOGY_ALLOW_SELF_REGISTRATION'] = 'true'
        result = self.receive()
        self.assertEqual(result['changed_keys'], ['TERMINOLOGY_ALLOW_SELF_REGISTRATION'])
        self.assertEqual(result['status'], 'applied')

    def test_rejects_sso_disable_and_admin_rename(self):
        self.existing_sso()
        cases = [dict(TERMINOLOGY_OIDC_SERVER_URL='', TERMINOLOGY_OIDC_CLIENT_ID=''),
                 dict(TERMINOLOGY_KEYCLOAK_ADMIN_USERNAME='another-admin')]
        for changed in cases:
            with self.subTest(keys=list(changed)):
                self.payload['settings'] = dict(self.settings, **changed)
                with self.assertRaisesRegex(module.ConfigurationError, 'coordinated'):
                    self.receive()
                self.unchanged()

    def test_sso_rejects_noncanonical_url_or_client(self):
        self.existing_sso()
        cases = [dict(TERMINOLOGY_OIDC_SERVER_URL=''), dict(TERMINOLOGY_OIDC_CLIENT_ID=''),
                 dict(TERMINOLOGY_OIDC_SERVER_URL='http://synthetic-value/auth'),
                 dict(TERMINOLOGY_OIDC_SERVER_URL='https://different-host/auth'),
                 dict(TERMINOLOGY_OIDC_SERVER_URL='https://synthetic-value/auth/'),
                 dict(TERMINOLOGY_OIDC_CLIENT_ID='another-client')]
        for changed in cases:
            with self.subTest(keys=list(changed)):
                self.payload['settings'] = dict(self.settings, **changed)
                with self.assertRaisesRegex(module.ConfigurationError, 'Invalid local Keycloak'):
                    self.receive()
                self.unchanged()

    def test_sso_requires_credentials(self):
        self.existing_sso()
        for key in ('TERMINOLOGY_KEYCLOAK_DB_PASSWORD', 'TERMINOLOGY_KEYCLOAK_ADMIN_PASSWORD'):
            with self.subTest(key=key):
                self.payload['settings'] = dict(self.settings, **{key: ''})
                with self.assertRaisesRegex(module.ConfigurationError, 'Missing configuration: ' + key):
                    self.receive()
                self.unchanged()

    def test_sso_requires_smtp_even_when_registration_is_closed(self):
        self.existing_sso()
        self.payload['settings']['TERMINOLOGY_EMAIL_BACKEND'] = 'django.core.mail.backends.dummy.EmailBackend'
        with self.assertRaisesRegex(module.ConfigurationError, 'Keycloak requires SMTP'):
            self.receive()
        self.unchanged()

    def test_sso_credential_rotations_require_coordinated_change(self):
        self.existing_sso()
        for key in ('TERMINOLOGY_KEYCLOAK_DB_PASSWORD', 'TERMINOLOGY_KEYCLOAK_ADMIN_PASSWORD'):
            with self.subTest(key=key):
                self.payload['settings'] = dict(self.settings, **{key: 'rotated-synthetic-secret'})
                with self.assertRaisesRegex(module.ConfigurationError, 'coordinated'):
                    self.receive()
                self.unchanged()

    def test_keycloak_image_is_managed_by_release_not_config_sync(self):
        self.assertNotIn('TERMINOLOGY_KEYCLOAK_IMAGE', module.CONFIG_KEYS)
        self.payload['settings']['TERMINOLOGY_KEYCLOAK_IMAGE'] = 'unreviewed-image'
        with self.assertRaisesRegex(module.ConfigurationError, 'configuration keys'):
            self.receive()
        self.unchanged()

    def test_registration_requires_smtp(self):
        self.payload['settings']['TERMINOLOGY_ALLOW_SELF_REGISTRATION'] = 'true'
        self.payload['settings']['TERMINOLOGY_EMAIL_BACKEND'] = 'django.core.mail.backends.dummy.EmailBackend'
        with self.assertRaisesRegex(module.ConfigurationError, 'requires SMTP'):
            self.receive()
        self.unchanged()

    def test_registration_flag_is_strict(self):
        self.payload['settings']['TERMINOLOGY_ALLOW_SELF_REGISTRATION'] = 'yes'
        with self.assertRaisesRegex(module.ConfigurationError, 'Invalid self-registration'):
            self.receive()
        self.unchanged()

    def test_registration_can_be_enabled_with_smtp(self):
        self.payload['settings']['TERMINOLOGY_ALLOW_SELF_REGISTRATION'] = 'true'
        result = self.receive()
        self.assertEqual(result['changed_keys'], ['TERMINOLOGY_ALLOW_SELF_REGISTRATION'])
        self.assertEqual(result['status'], 'applied')

    def test_noop_preserves_bytes_and_does_not_deploy(self):
        self.assertEqual(self.receive()['status'], 'unchanged')
        self.unchanged()

    def test_check_reports_names_without_changing_files(self):
        self.payload['mode'] = 'check'
        self.payload['settings']['TERMINOLOGY_EMAIL_HOST_PASSWORD'] = 'new-synthetic-password'
        result = self.receive()
        self.assertEqual(result['settings_matched'], len(module.CONFIG_KEYS) - 1)
        self.assertEqual(result['changed_keys'], ['TERMINOLOGY_EMAIL_HOST_PASSWORD'])
        self.assertNotIn('new-synthetic-password', self.output)
        self.unchanged()

    def test_apply_roundtrips_literals_preserves_unmanaged_and_journal(self):
        password = 'synthetic $HOME ${UNDEFINED} `uname` "double" \\slash #end'
        self.payload['settings']['TERMINOLOGY_EMAIL_HOST_PASSWORD'] = password
        result = self.receive()
        self.assertEqual(result['status'], 'applied')
        self.assertEqual(module.read_configuration(self.env), self.payload['settings'])
        self.assertIn('# preserve comment\nUNMANAGED_IMAGE=image@sha256:abc\n', self.env.read_text())
        journal = self.state / result['journal']
        self.assertEqual((journal / 'previous.env').read_text(), self.original)
        self.assertEqual(self.env.read_bytes(), self.active.read_bytes())
        self.assertEqual((journal / 'exit').read_text(), '0\n')
        for file in [self.env, journal/'previous.env', journal/'target.env', journal/'deploy.log']:
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(journal.stat().st_mode & 0o777, 0o700)
        self.assertNotIn(password, self.output)
        self.assertEqual(len(self.calls), 2)

    def test_compose_failure_preserves_active_configuration(self):
        self.payload['settings']['TERMINOLOGY_BACKUP_KEEP'] = '15'
        self.compose_failure = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.receive()
        self.assertEqual(self.env.read_text(), self.original)
        self.assertEqual(self.active.read_text(), self.original)
        self.assertEqual(len(self.calls), 1)

    def test_failed_deploy_keeps_recovery_and_blocks_retry(self):
        self.payload['settings']['TERMINOLOGY_BACKUP_KEEP'] = '15'
        self.deploy_failure = True
        with self.assertRaisesRegex(module.ConfigurationError, 'private recovery journal'):
            self.receive()
        self.assertEqual(self.active.read_text(), self.original)
        journal = next(self.state.glob('github-config-*'))
        self.assertEqual((journal/'previous.env').read_text(), self.original)
        self.assertEqual((journal/'exit').read_text(), '1\n')
        with self.assertRaisesRegex(module.ConfigurationError, 'pending deployment'):
            self.receive()
        self.assertEqual(len(self.calls), 2)

    def test_rejects_persisted_credential_rotations(self):
        for key in set(module.CREDENTIAL_SETTING_NAMES) - {'TERMINOLOGY_EMAIL_HOST_PASSWORD'}:
            with self.subTest(key=key):
                self.payload['settings'] = dict(self.settings, **{key:'changed'})
                with self.assertRaisesRegex(module.ConfigurationError, 'coordinated'):
                    self.receive()
                self.unchanged()

    def test_rejects_bad_scalar_and_missing_values(self):
        for value in ['has\nnewline', 'has\rreturn', 'has\0null', "has'quote", '', None, 123]:
            with self.subTest(value=repr(value)):
                self.payload['settings']['TERMINOLOGY_EMAIL_HOST_PASSWORD'] = value
                with self.assertRaises(module.ConfigurationError):
                    self.receive()
                self.unchanged()

    def test_rejects_unknown_keys(self):
        self.payload['settings']['UNKNOWN'] = 'synthetic'
        with self.assertRaisesRegex(module.ConfigurationError, 'configuration keys'):
            self.receive()
        self.unchanged()

    def test_rejects_invalid_numeric_and_backend_settings(self):
        cases = [('BACKUP_KEEP','1'), ('BACKUP_KEEP','x'), ('EMAIL_PORT','0'),
                 ('EMAIL_PORT','65536'), ('EMAIL_PORT','smtp'), ('EMAIL_BACKEND','unapproved')]
        for suffix, value in cases:
            with self.subTest(setting=suffix, value=value):
                self.payload['settings'] = dict(self.settings, **{'TERMINOLOGY_'+suffix:value})
                with self.assertRaises(module.ConfigurationError):
                    self.receive()
                self.unchanged()

    def test_rejects_wrong_commit(self):
        self.payload['commit'] = 'b'*40
        with self.assertRaisesRegex(module.ConfigurationError, 'operations commit'):
            self.receive()
        self.unchanged()

    def test_rejects_dirty_checkout(self):
        self.dirty = True
        with self.assertRaisesRegex(module.ConfigurationError, 'clean'):
            self.receive()
        self.unchanged()

    def test_rejects_wrong_host(self):
        self.machine = 'b'*32
        with self.assertRaisesRegex(module.ConfigurationError, 'host identity'):
            self.receive()
        self.unchanged()

    def test_rejects_nonprivate_configuration(self):
        self.env.chmod(0o644)
        with self.assertRaisesRegex(module.ConfigurationError, 'mode 600'):
            self.receive()
        self.unchanged()

    def test_rejects_shell_command(self):
        with patch.dict(os.environ, SSH_ORIGINAL_COMMAND='id'):
            with self.assertRaisesRegex(module.ConfigurationError, 'Unsupported SSH command'):
                self.receive()
        self.unchanged()

    def test_rejects_concurrent_synchronization(self):
        with (self.state/'github-config.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                self.receive()
        self.unchanged()


class SecretGenerationTests(unittest.TestCase):
    def test_generates_distinct_private_keycloak_credentials_without_enabling_sso(self):
        """Exercise only the local secret generator; no Docker or network calls."""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'synthetic.env'
            subprocess.run(['bash', str(SOURCE / 'scripts/security/secrets_generate.sh'), str(output)],
                           check=True, capture_output=True, text=True)
            settings = module.read_configuration(output)
            database = settings['TERMINOLOGY_KEYCLOAK_DB_PASSWORD']
            admin = settings['TERMINOLOGY_KEYCLOAK_ADMIN_PASSWORD']
            self.assertRegex(database, r'^[a-f0-9]{48}$')
            self.assertRegex(admin, r'^[a-f0-9]{48}$')
            self.assertNotEqual(database, admin)
            self.assertEqual(settings['TERMINOLOGY_OIDC_SERVER_URL'], '')
            self.assertEqual(settings['TERMINOLOGY_OIDC_CLIENT_ID'], '')
            self.assertEqual(settings['TERMINOLOGY_KEYCLOAK_ADMIN_USERNAME'], 'sihsalus-admin')
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main(verbosity=2)
