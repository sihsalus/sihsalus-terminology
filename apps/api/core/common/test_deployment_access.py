"""Private deployments must not log credentials or offer public account creation."""
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import PermissionDenied

from core.users.views import UserSignup
from core.middlewares.middlewares import RequireAuthenticationMiddleware


class DeploymentAccessTest(SimpleTestCase):
    """Check access gates without creating accounts or contacting external services."""

    def test_request_payload_logger_is_not_installed(self):
        """Access logs suffice; request and response bodies can contain credentials."""
        self.assertNotIn('core.middlewares.middlewares.CustomLoggerMiddleware', settings.MIDDLEWARE)
        self.assertNotIn('request_logging.middleware.LoggingMiddleware', settings.MIDDLEWARE)

    @override_settings(APPROVED_ANONYMOUS_CLIENTS=set(), APPROVED_ANONYMOUS_API_KEYS=set(),
                       APPROVED_ANONYMOUS_IPS=set())
    def test_health_checker_header_does_not_bypass_authentication(self):
        """Health endpoints remain available without trusting a client-supplied agent header."""
        middleware = RequireAuthenticationMiddleware(lambda request: None)
        request = SimpleNamespace(method='GET', path='/orgs/SIHSALUS/',
                                  META={'HTTP_USER_AGENT': 'ELB-HealthChecker/2.0'})
        with patch.object(middleware, 'get_authenticated_user', return_value=AnonymousUser()):
            self.assertFalse(middleware.is_request_allowed(request))
            request.path = '/healthcheck/'
            self.assertTrue(middleware.is_request_allowed(request))

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
