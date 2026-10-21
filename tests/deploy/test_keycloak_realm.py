"""First-start Keycloak export and declarative realm checks, without services."""
import copy
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'keycloak_realm', ROOT / 'scripts/terminology/keycloak-realm.py')
EXPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORT)


class KeycloakRealmTests(unittest.TestCase):
    def setUp(self):
        self.template = json.loads((ROOT / 'images/keycloak/ocl-realm.json').read_text())
        self.row = dict(id=3, username='researcher', email='researcher@pucp.edu.pe',
                        first_name='Ana', last_name='', is_active=True, verified=True,
                        password='synthetic-hash')
        self.credential = dict(type='password', credentialData='synthetic', secretData='synthetic',
                               temporary=False)
        self.convert = Mock(return_value=self.credential)

    def export(self, rows=None):
        return EXPORT.build_realm(self.template, rows if rows is not None else [self.row], self.convert)

    def export_main(self, sender):
        """Exercise the real entry point with synthetic Django rows and settings."""
        user_model = Mock()
        user_model.objects.order_by.return_value.values.return_value = [self.row]
        settings = SimpleNamespace(DEFAULT_FROM_EMAIL=sender)
        modules = {
            'django': Mock(), 'django.conf': SimpleNamespace(settings=settings),
            'core.users.models': SimpleNamespace(UserProfile=user_model),
            'core.services.auth.openid': SimpleNamespace(OpenIDAuthService=SimpleNamespace(
                credential_representation_from_hash=self.convert)),
        }
        output = io.StringIO()
        with patch.dict('sys.modules', modules), \
                patch.object(Path, 'read_text', return_value=json.dumps(self.template)), \
                redirect_stdout(output):
            EXPORT.main(['--template', 'synthetic-realm.json'])
        self.assertEqual(settings.DEFAULT_FROM_EMAIL, sender)
        return json.loads(output.getvalue())

    def test_export_main_normalizes_bare_and_formatted_senders(self):
        for sender, name in (('noreply@example.invalid', 'SIHSALUS Terminología'),
                             ('Equipo SIHSALUS <noreply@example.invalid>', 'Equipo SIHSALUS')):
            with self.subTest(sender=sender):
                smtp = self.export_main(sender)['smtpServer']
                self.assertEqual(smtp['from'], 'noreply@example.invalid')
                self.assertEqual(smtp['fromDisplayName'], name)
                self.assertEqual(smtp['password'], '${TERMINOLOGY_EMAIL_HOST_PASSWORD}')

    def test_export_main_rejects_invalid_senders(self):
        for sender in ('not-an-email', 'Name <>', 'a@example.invalid,b@example.invalid',
                       'Name\r\n <a@example.invalid>'):
            with self.subTest(sender=sender), self.assertRaisesRegex(ValueError, 'Invalid SMTP sender'):
                self.export_main(sender)

    def test_preserves_identity_status_and_credentials_without_roles(self):
        original = copy.deepcopy(self.template)
        result = self.export()
        user = result['users'][0]
        self.assertEqual(user['username'], 'researcher')
        self.assertEqual(user['email'], 'researcher@pucp.edu.pe')
        self.assertTrue(user['enabled'])
        self.assertTrue(user['emailVerified'])
        self.assertEqual(user['credentials'], [self.credential])
        self.assertEqual(user['requiredActions'], [])
        self.assertNotIn('groups', user)
        self.assertNotIn('realmRoles', user)
        self.assertNotIn('clientRoles', user)
        self.assertEqual(original, self.template)
        self.assertFalse(result['registrationAllowed'])
        self.convert.assert_called_once_with('synthetic-hash', temporary=False)

    def test_preserves_disabled_unverified_and_legacy_email_accounts(self):
        self.row.update(is_active=False, verified=False, email='legacy@example.invalid', first_name=None)
        user = self.export()['users'][0]
        self.assertFalse(user['enabled'])
        self.assertFalse(user['emailVerified'])
        self.assertEqual(user['email'], 'legacy@example.invalid')
        self.assertEqual(user['firstName'], '')

    def test_refuses_silent_username_normalization(self):
        for username in ('Researcher', ' researcher', '', None):
            self.row['username'] = username
            with self.subTest(username=username), self.assertRaisesRegex(ValueError, 'Noncanonical'):
                self.export()

    def test_refuses_colliding_identities(self):
        duplicate = dict(self.row, id=4, email='different@pucp.edu.pe')
        with self.assertRaisesRegex(ValueError, 'Username collision'):
            self.export([self.row, duplicate])
        duplicate.update(username='different', email='RESEARCHER@PUCP.EDU.PE')
        with self.assertRaisesRegex(ValueError, 'Email collision'):
            self.export([self.row, duplicate])

    def test_refuses_missing_or_padded_email(self):
        for email in ('', None, ' researcher@pucp.edu.pe '):
            self.row['email'] = email
            with self.subTest(email=email), self.assertRaisesRegex(ValueError, 'email'):
                self.export()

    def test_hash_errors_do_not_disclose_credentials(self):
        self.convert.side_effect = ValueError('synthetic-secret-hash')
        with self.assertRaisesRegex(ValueError, 'account id 3') as caught:
            self.export()
        self.assertNotIn('synthetic-secret', str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)

    def test_refuses_reusing_an_export_or_another_realm(self):
        for change in ({'realm': 'master'}, {'users': [{'username': 'existing'}]}):
            self.template.update(change)
            with self.assertRaisesRegex(ValueError, 'empty ocl realm'):
                self.export()

    def test_realm_enforces_confirmation_and_public_pkce_client(self):
        realm = self.template
        self.assertTrue(realm['verifyEmail'])
        self.assertTrue(realm['resetPasswordAllowed'])
        self.assertFalse(realm['editUsernameAllowed'])
        self.assertEqual(realm['registrationAllowed'], '${TERMINOLOGY_ALLOW_SELF_REGISTRATION}')
        self.assertEqual(realm['defaultLocale'], 'es')
        self.assertEqual(realm['loginTheme'], 'sihsalus')
        self.assertEqual(realm['emailTheme'], 'sihsalus')
        client = next(item for item in realm['clients'] if item['clientId'] == 'ocl-web')
        self.assertEqual(client['clientId'], 'ocl-web')
        self.assertTrue(client['publicClient'])
        self.assertTrue(client['standardFlowEnabled'])
        self.assertFalse(client['implicitFlowEnabled'])
        self.assertFalse(client['directAccessGrantsEnabled'])
        self.assertFalse(client['serviceAccountsEnabled'])
        self.assertFalse(client['fullScopeAllowed'])
        self.assertEqual(client['attributes']['pkce.code.challenge.method'], 'S256')
        self.assertEqual(client['redirectUris'], ['${TERMINOLOGY_WEB_URL}/'])
        self.assertNotIn('protocolMappers', client)
        self.assertNotIn('defaultGroups', realm)

    def test_account_self_service_cannot_change_the_ocl_identity(self):
        clients = {item['clientId']: item for item in self.template['clients']}
        self.assertFalse(clients['account']['enabled'])
        self.assertFalse(clients['account']['standardFlowEnabled'])
        self.assertNotIn('account-console', clients)
        actions = {item['alias']: item for item in self.template['requiredActions']}
        for action in ('UPDATE_PROFILE', 'UPDATE_EMAIL', 'VERIFY_PROFILE'):
            self.assertFalse(actions[action]['enabled'])
        for action in ('VERIFY_EMAIL', 'UPDATE_PASSWORD'):
            self.assertTrue(actions[action]['enabled'])

    def test_native_email_validation_rejects_domain_lookalikes(self):
        provider, = self.template['components']['org.keycloak.userprofile.UserProfileProvider']
        # Realm imports use ComponentExportRepresentation; type is the map key.
        self.assertNotIn('providerType', provider)
        profile = json.loads(provider['config']['kc.user.profile.config'][0])
        # A missing policy disables unmanaged attributes; DISABLED is not a native enum.
        self.assertIsNone(profile.get('unmanagedAttributePolicy'))
        for name in ('firstName', 'lastName'):
            attribute = next(item for item in profile['attributes'] if item['name'] == name)
            maximum = attribute['validations']['length']['max']
            self.assertEqual(maximum, 100)
            self.assertLessEqual(len('A' * 100), maximum)
            self.assertGreater(len('A' * 101), maximum)
        email = next(item for item in profile['attributes'] if item['name'] == 'email')
        self.assertIn('email', email['validations'])
        pattern = re.compile(email['validations']['pattern']['pattern'])
        for value in ('ana@pucp.edu.pe', 'ANA@PUCP.EDU.PE'):
            self.assertIsNotNone(pattern.fullmatch(value))
        for value in ('ana@sub.pucp.edu.pe', 'ana@pucp.edu.pe.evil.invalid',
                      'ana@notpucp.edu.pe', 'ana@pucpXeduXpe', 'ana@@pucp.edu.pe'):
            self.assertIsNone(pattern.fullmatch(value))
        actions = {action['alias']: action for action in self.template['requiredActions']}
        self.assertFalse(actions['VERIFY_PROFILE']['enabled'])
        self.assertTrue(actions['VERIFY_EMAIL']['enabled'])
        self.assertTrue(actions['UPDATE_PASSWORD']['enabled'])
        self.assertLess(actions['VERIFY_EMAIL']['priority'], actions['UPDATE_PASSWORD']['priority'])

    def test_smtp_credentials_remain_native_placeholders(self):
        smtp = self.template['smtpServer']
        self.assertEqual(smtp['auth'], 'true')
        self.assertEqual(smtp['starttls'], 'true')
        self.assertEqual(smtp['password'], '${TERMINOLOGY_EMAIL_HOST_PASSWORD}')
        self.assertEqual(self.export()['smtpServer'], smtp)

    def test_theme_extends_native_templates_and_is_packaged(self):
        theme = ROOT / 'images/keycloak/themes/sihsalus'
        login = (theme / 'login/theme.properties').read_text()
        self.assertIn('parent=keycloak.v2\n', login)
        self.assertIn('styles=css/styles.css css/sihsalus.css\n', login)
        self.assertIn('darkMode=false\n', login)
        self.assertEqual((theme / 'email/theme.properties').read_text(), 'parent=keycloak\nlocales=es\n')
        self.assertFalse(list(theme.rglob('*.ftl')), 'Authentication templates must remain upstream')
        self.assertIn('COPY --chown=1000:0 themes/sihsalus /opt/keycloak/themes/sihsalus',
                      (ROOT / 'images/keycloak/Dockerfile').read_text())
        css = (theme / 'login/resources/css/sihsalus.css').read_text()
        self.assertIn('--sihsalus-primary: #4836ff;', css)
        self.assertIn('radial-gradient(', css)
        self.assertNotIn('url(', css, 'Background must not fetch external assets')

    def test_email_messages_preserve_native_parameters_and_formatted_duration(self):
        path = ROOT / 'images/keycloak/themes/sihsalus/email/messages/messages_es.properties'
        messages = dict(line.split('=', 1) for line in path.read_text().splitlines()
                        if line and not line.startswith('#'))
        for prefix, parameters, duration in (
                ('emailVerification', {'0', '2', '3'}, '3'),
                ('passwordReset', {'0', '2', '3'}, '3'),
                ('executeActions', {'0', '2', '3', '4'}, '4')):
            for suffix in ('Body', 'BodyHtml'):
                message = messages[prefix + suffix]
                with self.subTest(message=prefix + suffix):
                    self.assertEqual(set(re.findall(r'\{(\d+)\}', message)), parameters)
                    self.assertIn('caduca en {' + duration + '}.', message)
                    rendered = message.replace('{' + duration + '}', '30 minutos')
                    self.assertIn('30 minutos.', rendered)
                    self.assertNotIn('minutos minutos', rendered)
                    if suffix == 'BodyHtml':
                        self.assertIn('href="{0}"', message)


if __name__ == '__main__':
    unittest.main()
