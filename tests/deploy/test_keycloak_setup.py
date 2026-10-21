"""Provisioning/reconciliation checks with mocked PostgreSQL and HTTP clients."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'keycloak_setup', ROOT / 'scripts/terminology/keycloak-setup.py')
SETUP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SETUP)


class KeycloakSetupTests(unittest.TestCase):
    def setUp(self):
        environment = {
            'DB_HOST': 'db', 'DB_USER': 'postgres', 'DB_PASSWORD': 'synthetic-admin',
            'TERMINOLOGY_KEYCLOAK_DB_PASSWORD': 'synthetic-service',
            'TERMINOLOGY_KEYCLOAK_ADMIN_USERNAME': 'synthetic-admin',
            'TERMINOLOGY_KEYCLOAK_ADMIN_PASSWORD': 'synthetic-password',
            'ALLOW_SELF_REGISTRATION': 'true', 'EMAIL_HOST': 'smtp.example.invalid',
            'EMAIL_PORT': '587', 'DEFAULT_FROM_EMAIL': 'noreply@example.invalid',
            'EMAIL_HOST_USER': 'sender@example.invalid', 'EMAIL_HOST_PASSWORD': 'synthetic-smtp',
        }
        self.environment = patch.dict(os.environ, environment, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.admin, self.authentication, self.service = (MagicMock() for _ in range(3))
        self.cursor = self.admin.cursor.return_value.__enter__.return_value
        self.cursor.fetchone.side_effect = [None, None]
        self.service_cursor = self.service.cursor.return_value.__enter__.return_value
        self.service_cursor.fetchone.side_effect = [(None,)]
        self.connect = patch.object(SETUP, 'connect', side_effect=[
            self.admin, self.authentication, self.service])
        self.connection = self.connect.start()
        self.addCleanup(self.connect.stop)

    def provision(self, require_existing=False):
        output = io.StringIO()
        with redirect_stdout(output):
            SETUP.prepare_database(require_existing=require_existing)
        return json.loads(output.getvalue())

    def statements(self):
        return [call.args[0] for call in self.cursor.execute.call_args_list]

    def test_first_run_creates_bounded_role_database_and_schema_protection(self):
        self.assertEqual(self.provision(), {'realm_initialized': False})
        statements = self.statements()
        creation = next(call for call in self.cursor.execute.call_args_list
                        if call.args[0].startswith('CREATE ROLE'))
        self.assertEqual(creation.args[1], ('synthetic-service',))
        self.assertNotIn('synthetic-service', creation.args[0])
        self.assertIn('NOSUPERUSER', creation.args[0])
        self.assertIn('NOCREATEROLE', creation.args[0])
        self.assertIn('NOBYPASSRLS', creation.args[0])
        self.assertIn('CREATE DATABASE keycloak OWNER keycloak', statements)
        self.assertIn('REVOKE ALL ON DATABASE keycloak FROM PUBLIC', statements)
        self.assertIn('REVOKE CREATE ON SCHEMA public FROM PUBLIC', statements)
        self.assertTrue(self.admin.autocommit)
        self.admin.close.assert_called_once()
        self.authentication.close.assert_called_once()
        self.service.close.assert_called_once()

    def test_existing_database_does_not_rotate_credentials_or_reimport_realm(self):
        self.cursor.fetchone.side_effect = [
            (False, False, False, False, False, True, False), ('keycloak',)]
        self.service_cursor.fetchone.side_effect = [('realm',), (True,)]
        self.assertEqual(self.provision(), {'realm_initialized': True})
        self.assertFalse(any(statement.startswith(('CREATE ROLE', 'ALTER ROLE', 'CREATE DATABASE'))
                             for statement in self.statements()))

    def test_existing_sso_never_recreates_a_missing_role_or_database(self):
        cases = ([None], [(False, False, False, False, False, True, False), None])
        for results in cases:
            self.cursor.reset_mock()
            self.cursor.fetchone.side_effect = results
            with self.subTest(results=results), self.assertRaisesRegex(ValueError, 'restore its backup'):
                self.provision(require_existing=True)
            self.assertFalse(any(statement.startswith(('CREATE', 'ALTER', 'REVOKE'))
                                 for statement in self.statements()))
            self.connection.reset_mock()
            self.connection.side_effect = [self.admin, self.authentication, self.service]

    def test_existing_sso_requires_its_realm_before_any_ddl(self):
        self.cursor.fetchone.side_effect = [
            (False, False, False, False, False, True, False), ('keycloak',)]
        self.service_cursor.fetchone.side_effect = [('realm',), (False,)]
        with self.assertRaisesRegex(ValueError, 'ocl realm'):
            self.provision(require_existing=True)
        self.assertFalse(any(statement.startswith(('CREATE', 'ALTER', 'REVOKE'))
                             for statement in self.statements()))

    def test_existing_sso_with_intact_realm_is_accepted(self):
        self.cursor.fetchone.side_effect = [
            (False, False, False, False, False, True, False), ('keycloak',)]
        self.service_cursor.fetchone.side_effect = [('realm',), (True,)]
        self.assertEqual(self.provision(require_existing=True), {'realm_initialized': True})

    def test_unrelated_database_owner_is_rejected_before_authentication_or_ddl(self):
        self.cursor.fetchone.side_effect = [
            (False, False, False, False, False, True, False), ('another-owner',)]
        with self.assertRaisesRegex(ValueError, 'unexpected owner'):
            self.provision()
        self.assertEqual(self.connection.call_count, 1)
        self.assertFalse(any(statement.startswith(('CREATE', 'REVOKE')) for statement in self.statements()))
        self.admin.close.assert_called_once()

    def test_existing_privileges_or_memberships_are_rejected(self):
        for index in (0, 1, 2, 3, 4, 5, 6):
            role = [False, False, False, False, False, True, False]
            role[index] = not role[index]
            self.cursor.fetchone.side_effect = [tuple(role)]
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'unexpected privileges'):
                self.provision()
            self.connection.reset_mock()
            self.connection.side_effect = [self.admin, self.authentication, self.service]

    def test_wrong_service_password_cannot_change_existing_schema(self):
        self.cursor.fetchone.side_effect = [
            (False, False, False, False, False, True, False), ('keycloak',)]
        self.connection.side_effect = [self.admin, RuntimeError('authentication failed')]
        with self.assertRaisesRegex(RuntimeError, 'authentication failed'):
            self.provision()
        self.assertFalse(any(statement.startswith(('CREATE', 'REVOKE')) for statement in self.statements()))

    def test_uninitialized_schema_is_reported_without_writing_service_database(self):
        self.cursor.fetchone.side_effect = [
            (False, False, False, False, False, True, False), ('keycloak',)]
        self.service_cursor.fetchone.side_effect = [('realm',), (False,)]
        self.assertFalse(self.provision()['realm_initialized'])
        self.assertTrue(all(call.args[0].startswith('SELECT')
                            for call in self.service_cursor.execute.call_args_list))

    def reconciliation(self, realm=None):
        requests = MagicMock()
        requests.post.return_value.json.return_value = {'access_token': 'synthetic-token'}
        requests.get.return_value.json.return_value = realm or {'sslRequired': 'external', 'verifyEmail': True}
        return requests

    def test_reconciliation_updates_only_reviewed_settings_without_disclosing_secrets(self):
        requests = self.reconciliation()
        output = io.StringIO()
        with patch.dict('sys.modules', {'requests': requests}), redirect_stdout(output):
            SETUP.reconcile_realm()
        payload = requests.put.call_args.kwargs['json']
        self.assertEqual(set(payload), {
            'registrationAllowed', 'resetPasswordAllowed', 'verifyEmail', 'smtpServer',
            'loginTheme', 'emailTheme'})
        self.assertEqual(payload['loginTheme'], 'sihsalus')
        self.assertEqual(payload['emailTheme'], 'sihsalus')
        self.assertTrue(payload['registrationAllowed'])
        self.assertEqual(payload['smtpServer']['starttls'], 'true')
        self.assertEqual(payload['smtpServer']['auth'], 'true')
        self.assertEqual(payload['smtpServer']['password'], 'synthetic-smtp')
        self.assertEqual(payload['smtpServer']['from'], 'noreply@example.invalid')
        self.assertEqual(payload['smtpServer']['fromDisplayName'], 'SIHSALUS Terminología')
        self.assertNotIn('synthetic', output.getvalue())
        self.assertEqual(requests.put.call_args.kwargs['timeout'], 20)

    def test_reconciliation_can_close_registration_without_disabling_verification(self):
        os.environ['ALLOW_SELF_REGISTRATION'] = 'false'
        requests = self.reconciliation()
        with patch.dict('sys.modules', {'requests': requests}), redirect_stdout(io.StringIO()):
            SETUP.reconcile_realm()
        payload = requests.put.call_args.kwargs['json']
        self.assertFalse(payload['registrationAllowed'])
        self.assertTrue(payload['verifyEmail'])

    def test_reconciliation_separates_a_formatted_sender(self):
        os.environ['DEFAULT_FROM_EMAIL'] = 'Equipo SIHSALUS <noreply@example.invalid>'
        requests = self.reconciliation()
        with patch.dict('sys.modules', {'requests': requests}), redirect_stdout(io.StringIO()):
            SETUP.reconcile_realm()
        smtp = requests.put.call_args.kwargs['json']['smtpServer']
        self.assertEqual(smtp['from'], 'noreply@example.invalid')
        self.assertEqual(smtp['fromDisplayName'], 'Equipo SIHSALUS')
        self.assertEqual(os.environ['DEFAULT_FROM_EMAIL'], 'Equipo SIHSALUS <noreply@example.invalid>')

    def test_reconciliation_rejects_invalid_sender_before_http(self):
        for sender in ('not-an-email', 'Name <>', 'a@example.invalid,b@example.invalid',
                       'Name\r\n <a@example.invalid>'):
            requests = self.reconciliation()
            with self.subTest(sender=sender), patch.dict(os.environ, DEFAULT_FROM_EMAIL=sender), \
                    patch.dict('sys.modules', {'requests': requests}):
                with self.assertRaisesRegex(ValueError, 'Invalid SMTP sender'):
                    SETUP.reconcile_realm()
            requests.post.assert_not_called()
            requests.put.assert_not_called()

    def test_missing_smtp_or_invalid_flags_fail_before_http(self):
        for key, invalid in (('EMAIL_HOST_PASSWORD', ''), ('ALLOW_SELF_REGISTRATION', 'TRUE'),
                             ('EMAIL_PORT', '0'), ('EMAIL_PORT', '65536')):
            requests = self.reconciliation()
            with patch.dict(os.environ, {key: invalid}), patch.dict('sys.modules', {'requests': requests}):
                with self.subTest(key=key, invalid=invalid), self.assertRaises(ValueError):
                    SETUP.reconcile_realm()
            requests.post.assert_not_called()
            requests.put.assert_not_called()

    def test_reconciliation_does_not_override_unexpected_security_configuration(self):
        for realm in ({'sslRequired': 'none', 'verifyEmail': True},
                      {'sslRequired': 'external', 'verifyEmail': False},
                      {'sslRequired': 'external', 'verifyEmail': 'false'}):
            requests = self.reconciliation(realm)
            with patch.dict('sys.modules', {'requests': requests}), self.assertRaises(ValueError):
                SETUP.reconcile_realm()
            requests.put.assert_not_called()


if __name__ == '__main__':
    unittest.main()
