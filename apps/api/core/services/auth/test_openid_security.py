"""Verify native password migration and bounded TLS requests without network access."""
import base64
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.test import SimpleTestCase, override_settings
from requests.exceptions import HTTPError, SSLError, Timeout

from core.services.auth.openid import OpenIDAuthService


@override_settings(OIDC_TIMEOUT=10)
class OpenIDSecurityTest(SimpleTestCase):
    """Credential material is entirely synthetic and never leaves these mocks."""

    @staticmethod
    def credential(password='synthetic-pássword-8294!'):
        """Use a short work factor for fast deterministic synthetic checks only."""
        return PBKDF2PasswordHasher().encode(password, 'synthetic-salt', iterations=1234)

    def test_native_credential_preserves_existing_password(self):
        """Keycloak can derive the same digest using the imported salt and work factor."""
        encoded = self.credential()
        result = OpenIDAuthService.credential_representation_from_hash(encoded)
        parameters = json.loads(result['credentialData'])
        secret = json.loads(result['secretData'])
        self.assertEqual(parameters, {'algorithm': 'pbkdf2-sha256', 'hashIterations': 1234})
        self.assertEqual(result['type'], 'password')
        self.assertFalse(result['temporary'])
        self.assertNotIn('value', result)
        self.assertEqual(base64.b64decode(secret['salt']), b'synthetic-salt')
        recomputed = hashlib.pbkdf2_hmac('sha256', 'synthetic-pássword-8294!'.encode(),
                                       base64.b64decode(secret['salt']), parameters['hashIterations'])
        self.assertEqual(base64.b64encode(recomputed).decode(), secret['value'])
        self.assertTrue(PBKDF2PasswordHasher().verify('synthetic-pássword-8294!', encoded))

    def test_reject_unsupported_unusable_and_malformed_hashes(self):
        """Migration must stop instead of inventing a replacement credential."""
        for encoded in (None, '!unusable', 'argon2$placeholder', 'pbkdf2_sha1$1234$salt$digest',
                        'pbkdf2_sha256$bad', 'pbkdf2_sha256$0$salt$YWJj',
                        'pbkdf2_sha256$10$$YWJj', 'pbkdf2_sha256$10$salt$invalid-base64!'):
            with self.subTest(encoded=encoded), self.assertRaises(ValueError):
                OpenIDAuthService.credential_representation_from_hash(encoded)
        for old, new in (('$1234$', '$0$'), ('$1234$', '$-1$'), ('$1234$', '$2147483648$'),
                         ('$synthetic-salt$', '$$')):
            with self.subTest(new=new), self.assertRaises(ValueError):
                OpenIDAuthService.credential_representation_from_hash(self.credential().replace(old, new))

    @patch('core.services.auth.openid.requests.post')
    def test_code_exchange_verifies_tls_and_bounds_timeout(self, post):
        """PKCE token exchange uses the verified provider connection."""
        post.return_value.json.return_value = {'access_token': 'synthetic-token'}
        result = OpenIDAuthService.exchange_code_for_token(
            'synthetic-code', 'https://terminology.example.org/#/callback', 'terminology',
            code_verifier='synthetic-verifier')
        self.assertEqual(result['access_token'], 'synthetic-token')
        self.assertIs(post.call_args.kwargs['verify'], True)
        self.assertEqual(post.call_args.kwargs['timeout'], 10)
        self.assertEqual(post.call_args.kwargs['data']['code_verifier'], 'synthetic-verifier')

    @patch('core.services.auth.openid.requests.post')
    def test_admin_authentication_verifies_tls_and_rejects_http_errors(self, post):
        """Admin credentials are never sent with certificate verification disabled."""
        post.return_value.json.return_value = {'access_token': 'synthetic-admin-token'}
        self.assertEqual(OpenIDAuthService.get_admin_token('synthetic-admin', 'synthetic-secret'),
                         'synthetic-admin-token')
        self.assertIs(post.call_args.kwargs['verify'], True)
        self.assertEqual(post.call_args.kwargs['timeout'], 10)
        post.return_value.raise_for_status.assert_called_once()
        post.return_value.raise_for_status.side_effect = HTTPError('synthetic-authentication-failure')
        with self.assertRaises(HTTPError):
            OpenIDAuthService.get_admin_token('synthetic-admin', 'synthetic-secret')

    @patch.object(OpenIDAuthService, 'get_admin_headers', return_value={'Authorization': 'Bearer synthetic-admin'})
    @patch('core.services.auth.openid.requests.post')
    def test_import_preserves_disabled_and_unverified_state(self, post, _headers):
        """Importing an account neither activates it nor verifies its email."""
        user = SimpleNamespace(is_active=False, verified=False, first_name='Synthetic', last_name='Member',
                               email='synthetic@pucp.edu.pe', username='synthetic-member', password=self.credential())
        post.return_value = Mock(status_code=201)
        self.assertTrue(OpenIDAuthService.add_user(user, 'synthetic-admin', 'synthetic-secret'))
        payload = post.call_args.kwargs['json']
        self.assertFalse(payload['enabled'])
        self.assertFalse(payload['emailVerified'])
        self.assertEqual(payload['username'], user.username)
        self.assertEqual(payload['email'], user.email)
        self.assertNotIn('groups', payload)
        self.assertNotIn('realmRoles', payload)
        self.assertFalse(payload['credentials'][0]['temporary'])
        self.assertIs(post.call_args.kwargs['verify'], True)
        self.assertEqual(post.call_args.kwargs['timeout'], 10)

    @patch('core.services.auth.openid.requests.post')
    def test_connection_errors_propagate_without_insecure_retry(self, post):
        """A failed TLS or timeout check must not trigger an unverified connection."""
        for error in (SSLError('synthetic-invalid-certificate'), Timeout('synthetic-timeout')):
            with self.subTest(error=type(error).__name__):
                post.reset_mock()
                post.side_effect = error
                with self.assertRaises(type(error)):
                    OpenIDAuthService.exchange_code_for_token('synthetic-code', 'https://example.org/', 'terminology')
                post.assert_called_once()
                self.assertIs(post.call_args.kwargs['verify'], True)
