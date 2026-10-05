"""Private deployments must not log credentials or offer public account creation."""
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import PermissionDenied

from core.users.views import UserSignup


class DeploymentAccessTest(SimpleTestCase):
    """Check access gates without creating accounts or contacting external services."""

    def test_request_payload_logger_is_not_installed(self):
        """Access logs suffice; request and response bodies can contain credentials."""
        self.assertNotIn('core.middlewares.middlewares.CustomLoggerMiddleware', settings.MIDDLEWARE)
        self.assertNotIn('request_logging.middleware.LoggingMiddleware', settings.MIDDLEWARE)

    @override_settings(ALLOW_SELF_REGISTRATION=False)
    def test_signup_disabled_before_processing(self):
        """Reject both registration redirects and creation before parsing user data."""
        with patch('core.users.views.AuthService.is_sso_enabled') as sso, \
                patch.object(UserSignup, 'get_serializer') as serializer:
            for method in (UserSignup().get, UserSignup().post):
                with self.assertRaises(PermissionDenied):
                    method(SimpleNamespace())
            sso.assert_not_called()
            serializer.assert_not_called()

    @override_settings(ALLOW_SELF_REGISTRATION=True)
    @patch('core.users.views.AuthService.is_sso_enabled', return_value=False)
    def test_enabled_signup_keeps_existing_get_behavior(self, sso):
        """Administrators may explicitly enable the upstream registration flow."""
        self.assertEqual(UserSignup.get(SimpleNamespace()).status_code, 405)
        sso.assert_called_once_with()
