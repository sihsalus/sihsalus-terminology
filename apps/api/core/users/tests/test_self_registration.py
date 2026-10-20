"""Exercise institutional registration without a database or real email delivery."""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory
from rest_framework.validators import UniqueValidator

from core.common.tasks import send_user_verification_email
from core.middlewares.middlewares import RequireAuthenticationMiddleware
from core.users.models import UserProfile
from core.users.serializers import UserSignupSerializer
from core.users.views import UserSignup, TokenAuthenticationView, UserEmailVerificationView


@override_settings(ALLOW_SELF_REGISTRATION=True, SELF_REGISTRATION_EMAIL_DOMAINS={'pucp.edu.pe'})
class SelfRegistrationTest(SimpleTestCase):
    """Use real serializers and account state, mocking only persistence and mail."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.payload = {'username': 'synthetic-member', 'email': 'synthetic@pucp.edu.pe',
                        'password': 'synthetic-registration-8294!'}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        # Uniqueness is covered separately; no database or external services in this suite.
        self.stack.enter_context(patch.object(UniqueValidator, '__call__', return_value=None))
        self.stack.enter_context(patch('core.users.views.AuthService.is_sso_enabled', return_value=False))

    def serializer(self, **changes):
        """Build the production serializer with an anonymous requesting user."""
        return UserSignupSerializer(data={**self.payload, **changes},
                                    context={'request': SimpleNamespace(user=AnonymousUser())})

    def test_exact_domain_and_case_normalization(self):
        """Allow institutional domains regardless of domain case."""
        serializer = self.serializer(email='synthetic@PUCP.EDU.PE')
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['email'], 'synthetic@pucp.edu.pe')

    def test_reject_other_domains_subdomains_and_lookalikes(self):
        """Suffix matches and malformed addresses must never grant registration."""
        for email in ('synthetic@gmail.com', 'synthetic@pucp.edu.pe.evil.test',
                      'synthetic@evilpucp.edu.pe', 'synthetic@alumni.pucp.edu.pe',
                      'synthetic', 'synthetic@@pucp.edu.pe'):
            with self.subTest(email=email):
                serializer = self.serializer(email=email)
                self.assertFalse(serializer.is_valid())
                self.assertIn('email', serializer.errors)

    @override_settings(SELF_REGISTRATION_EMAIL_DOMAINS=set())
    def test_missing_allowlist_denies_registration(self):
        """Enabling the flag alone does not open unrestricted account creation."""
        self.assertFalse(self.serializer().is_valid())

    def test_email_uniqueness_is_case_insensitive(self):
        """Email aliases differing only by case do not create separate identities."""
        validators = self.serializer().fields['email'].validators
        self.assertEqual(next(item for item in validators if isinstance(item, UniqueValidator)).lookup, 'iexact')

    def test_password_is_required_and_preserves_spaces(self):
        """Signup must not silently alter the password later used for login."""
        serializer = self.serializer(password='  synthetic-registration-8294!  ')
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['password'], '  synthetic-registration-8294!  ')
        payload = self.payload.copy()
        del payload['password']
        missing = UserSignupSerializer(data=payload)
        self.assertFalse(missing.is_valid())
        self.assertIn('password', missing.errors)

    def test_signup_verification_and_login(self):
        """Public signup cannot inject privileges or skip verification before login."""
        with patch.object(UserProfile, 'save'), patch.object(UserProfile, 'set_checksums'), \
                patch.object(UserProfile, 'record_event'), \
                patch.object(UserProfile, 'get_token', return_value='synthetic-token') as get_token, \
                patch.object(UserProfile, 'send_verification_email') as send_mail, \
                patch.object(UserProfile.objects, 'filter') as lookup:
            lookup.return_value.exists.return_value = False
            created = []
            original = UserSignupSerializer.create

            def create(serializer, data):
                user = original(serializer, data)
                created.append(user)
                return user

            payload = {**self.payload, 'verified': True, 'is_staff': True, 'is_superuser': True,
                       'groups': ['admin'], 'orgs': ['SIHSALUS']}
            with patch.object(UserSignupSerializer, 'create', create), \
                    patch.object(UserSignupSerializer, 'to_representation', return_value={}):
                response = UserSignup.as_view()(self.factory.post('/users/signup/', payload, format='json'))
            self.assertEqual(response.status_code, 201, response.data)
            self.assertNotIn('token', response.data)
            user = created[0]
            self.assertEqual(user.first_name, '')
            # Django exposes field validation through its documented metadata API.
            user._meta.get_field('first_name').clean(user.first_name, user)  # pylint: disable=protected-access
            self.assertFalse(user.verified)
            self.assertFalse(user.is_staff)
            self.assertFalse(user.is_superuser)
            self.assertIsNotNone(user.verification_token)
            send_mail.assert_called_once()
            lookup.return_value.first.return_value = user
            get_token.reset_mock()
            response = TokenAuthenticationView.as_view()(
                self.factory.post('/users/login/', self.payload, format='json'))
            self.assertEqual(response.status_code, 401)
            get_token.assert_not_called()
            with patch.object(UserEmailVerificationView, 'get_object', return_value=user):
                verify = UserEmailVerificationView.as_view()
                response = verify(self.factory.get('/users/synthetic-member/verify/wrong/'),
                                  verification_token='wrong')
                self.assertEqual(response.status_code, 401)
                response = verify(self.factory.get('/users/synthetic-member/verify/synthetic/'),
                                  verification_token=user.verification_token)
                self.assertEqual(response.status_code, 200)
            self.assertTrue(user.verified)
            self.assertIsNone(user.verification_token)
            response = TokenAuthenticationView.as_view()(
                self.factory.post('/users/login/', self.payload, format='json'))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['token'], 'synthetic-token')

    def test_authentication_gate_allows_only_account_flow(self):
        """Email links remain reachable before the user is able to authenticate."""
        self.assertTrue(RequireAuthenticationMiddleware.is_exempt_path('/users/signup/'))
        self.assertTrue(RequireAuthenticationMiddleware.is_exempt_path('/users/synthetic/verify/token/'))
        self.assertFalse(RequireAuthenticationMiddleware.is_exempt_path('/orgs/SIHSALUS/sources/'))

    def test_denied_domain_never_creates_an_account(self):
        """Validation fails before a profile or verification message can be created."""
        with patch.object(UserSignupSerializer, 'create') as create:
            response = UserSignup.as_view()(self.factory.post('/users/signup/',
                {**self.payload, 'email': 'synthetic@gmail.com'}, format='json'))
        self.assertEqual(response.status_code, 400)
        create.assert_not_called()

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                       WEB_URL='https://terminology.example.test', TEST_MODE=False)
    def test_confirmation_email_targets_local_installation(self):
        """Render and send only to the in-memory outbox, never to an SMTP server."""
        user = UserProfile(username='synthetic', email='synthetic@pucp.edu.pe',
                           verification_token='synthetic-token')
        with patch.object(UserProfile.objects, 'filter') as lookup:
            lookup.return_value.first.return_value = user
            send_user_verification_email.run(123)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['synthetic@pucp.edu.pe'])
        self.assertIn('SIHSALUS', message.subject)
        self.assertIn('https://terminology.example.test/#/accounts/synthetic/verify/synthetic-token/', message.body)
        self.assertNotIn('app.openconceptlab.org', message.body)
