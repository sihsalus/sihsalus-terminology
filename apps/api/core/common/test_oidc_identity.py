"""Check OIDC linking and authorization with synthetic identities and no services."""
from unittest.mock import Mock, patch

from django.core.exceptions import SuspiciousOperation
from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from core.common.backends import OCLOIDCAuthenticationBackend
from core.common.exceptions import DeactivatedAccountLoginRefused
from core.users.models import UserProfile
from core.users.views import UserPasswordResetView


@override_settings(SELF_REGISTRATION_EMAIL_DOMAINS={'pucp.edu.pe'})
class OIDCIdentityTest(SimpleTestCase):
    """Use the production backend and model while mocking persistence only."""

    def setUp(self):
        self.backend = OCLOIDCAuthenticationBackend()
        self.claims = {
            'sub': 'synthetic-keycloak-subject',
            'preferred_username': 'synthetic-member',
            'email': 'synthetic@pucp.edu.pe',
            'email_verified': True,
            'given_name': 'Synthetic',
            'family_name': 'Member',
        }
        self.user = UserProfile(id=37, username='synthetic-member', email='synthetic@pucp.edu.pe')

    def test_require_verified_valid_identity_claims(self):
        """Unverified, malformed or missing identifiers cannot authenticate."""
        self.assertTrue(self.backend.verify_claims(self.claims))
        for changes in (
                {'email_verified': False}, {'email_verified': 'true'}, {'email_verified': 1},
                {'email_verified': None}, {'email': ''}, {'email': None}, {'email': ['bad']},
                {'email': 'invalid'}, {'preferred_username': ''}, {'preferred_username': None},
                {'preferred_username': 'contains spaces'}, {'preferred_username': ['invalid']},
        ):
            with self.subTest(changes=changes):
                self.assertFalse(self.backend.verify_claims({**self.claims, **changes}))

    @patch.object(UserProfile.objects, 'filter')
    def test_exact_username_and_verified_email_link_same_local_account(self, lookup):
        """Case normalization applies to email but never renames the local account."""
        self.user.email = 'Synthetic@PUCP.EDU.PE'
        lookup.return_value = [self.user]
        self.assertEqual(self.backend.filter_users_by_claims(self.claims), [self.user])
        lookup.assert_called_once()

    @patch.object(UserProfile.objects, 'filter')
    def test_existing_administrator_may_keep_noninstitutional_email(self, lookup):
        """The institution allowlist applies to provisioning, not existing accounts."""
        self.user.email = 'synthetic-admin@example.org'
        self.user.is_superuser = self.user.is_staff = True
        lookup.return_value = [self.user]
        claims = {**self.claims, 'email': self.user.email}
        self.assertEqual(self.backend.filter_users_by_claims(claims), [self.user])

    @patch.object(UserProfile.objects, 'filter')
    def test_reject_account_collisions_without_mutating_or_creating(self, lookup):
        """Same username, case variants, and email reuse must not take over an account."""
        for username, email in (
                ('synthetic-member', 'another@pucp.edu.pe'),
                ('Synthetic-Member', 'synthetic@pucp.edu.pe'),
                ('another-member', 'synthetic@pucp.edu.pe'),
        ):
            with self.subTest(username=username, email=email):
                other = UserProfile(id=41, username=username, email=email)
                lookup.return_value = [other]
                with patch.object(other, 'save') as save, patch.object(other, 'undelete') as undelete:
                    with self.assertRaises(AuthenticationFailed):
                        self.backend.filter_users_by_claims(self.claims)
                save.assert_not_called()
                undelete.assert_not_called()

    @patch.object(UserProfile.objects, 'filter')
    def test_multiple_matching_rows_are_ambiguous(self, lookup):
        """Duplicate emails fail closed even when one username matches exactly."""
        lookup.return_value = [self.user, UserProfile(id=42, username='another', email=self.user.email)]
        with self.assertRaises(AuthenticationFailed):
            self.backend.filter_users_by_claims(self.claims)

    @patch.object(UserProfile.objects, 'filter')
    def test_disabled_account_stays_disabled_after_verified_sign_in(self, lookup):
        """Only local administration can reactivate an account or its resources."""
        self.user.is_active = False
        lookup.return_value = [self.user]
        with patch.object(self.user, 'undelete') as undelete, patch.object(self.user, 'save') as save:
            with self.assertRaises(DeactivatedAccountLoginRefused):
                self.backend.filter_users_by_claims(self.claims)
        undelete.assert_not_called()
        save.assert_not_called()
        self.assertFalse(self.user.is_active)

    @patch.object(UserProfile.objects, 'filter')
    def test_unverified_claims_never_query_or_update_local_identity(self, lookup):
        """Possession of a username without verified email is insufficient."""
        with self.assertRaises(AuthenticationFailed):
            self.backend.filter_users_by_claims({**self.claims, 'email_verified': False})
        lookup.assert_not_called()

    def test_login_preserves_admin_groups_memberships_password_and_email(self):
        """OIDC group claims never grant or remove local authorization."""
        self.user.is_staff = self.user.is_superuser = True
        self.user.password = 'synthetic-existing-password-hash'
        self.user.email = 'Synthetic@pucp.edu.pe'
        with patch.object(self.user, 'set_groups') as groups, patch.object(self.user, 'save'), \
                patch.object(self.user, 'set_checksums'), \
                patch.object(type(self.user.organizations), 'set') as organizations:
            for groups_claim in (None, [], ['SuperAdmin'], ['Staff'], ['unknown']):
                claims = {**self.claims}
                if groups_claim is not None:
                    claims['groups'] = groups_claim
                self.assertIs(self.backend.update_user(self.user, claims), self.user)
                self.assertTrue(self.user.is_staff)
                self.assertTrue(self.user.is_superuser)
                self.assertEqual(self.user.password, 'synthetic-existing-password-hash')
                self.assertEqual(self.user.email, 'Synthetic@pucp.edu.pe')
            groups.assert_not_called()
            organizations.assert_not_called()

    def test_unprivileged_user_cannot_gain_roles_from_claims(self):
        """Provider groups have no authority over Django staff and superuser flags."""
        with patch.object(self.user, 'set_groups') as groups, patch.object(self.user, 'save'), \
                patch.object(self.user, 'set_checksums'):
            self.backend.update_user(self.user, {**self.claims, 'groups': ['SuperAdmin', 'Staff']})
        groups.assert_not_called()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)

    @patch.object(UserProfile.objects, 'create_user')
    def test_provision_verified_institutional_user_without_roles(self, create):
        """New identities receive neither passwords nor permissions from token claims."""
        user = create.return_value
        claims = {**self.claims, 'groups': ['SuperAdmin'], 'is_staff': True, 'is_superuser': True,
                  'password': 'must-not-be-used'}
        self.assertIs(self.backend.create_user(claims), user)
        create.assert_called_once_with(
            'synthetic-member', email='synthetic@pucp.edu.pe', first_name='Synthetic',
            last_name='Member', verified=True, company=None, location=None)
        user.set_groups.assert_not_called()
        user.record_joined_ocl_event.assert_called_once()

    @patch.object(UserProfile.objects, 'create_user')
    def test_optional_profile_names_are_empty_strings(self, create):
        """Keycloak may omit optional names, but Django character fields reject NULL."""
        self.backend.create_user({**self.claims, 'given_name': None, 'family_name': None})
        self.assertEqual(create.call_args.kwargs['first_name'], '')
        self.assertEqual(create.call_args.kwargs['last_name'], '')

    @patch.object(UserProfile.objects, 'create_user')
    def test_new_accounts_require_exact_institutional_domain(self, create):
        """Keycloak policy cannot be bypassed with verified outside or lookalike emails."""
        for email in ('synthetic@example.org', 'synthetic@pucp.edu.pe.attacker.test',
                      'synthetic@sub.pucp.edu.pe', 'synthetic@notpucp.edu.pe'):
            with self.subTest(email=email), self.assertRaises(AuthenticationFailed):
                self.backend.create_user({**self.claims, 'email': email})
        create.assert_not_called()

    @override_settings(SELF_REGISTRATION_EMAIL_DOMAINS=set())
    @patch.object(UserProfile.objects, 'create_user')
    def test_empty_allowlist_keeps_new_accounts_closed(self, create):
        """Provisioning fails closed when deployment omitted the institutional policy."""
        with self.assertRaises(AuthenticationFailed):
            self.backend.create_user(self.claims)
        create.assert_not_called()

    @patch.object(OCLOIDCAuthenticationBackend, 'get_userinfo')
    def test_full_flow_rejects_unverified_identity_before_persistence(self, userinfo):
        """Exercise the upstream get-or-create hook, not only direct helper calls."""
        userinfo.return_value = {**self.claims, 'email_verified': False}
        with patch.object(UserProfile.objects, 'filter') as lookup, \
                patch.object(UserProfile.objects, 'create_user') as create:
            with self.assertRaises(SuspiciousOperation):
                self.backend.get_or_create_user('synthetic-token', None, None)
        lookup.assert_not_called()
        create.assert_not_called()

    @patch('mozilla_django_oidc.auth.OIDCAuthenticationBackend.authenticate')
    def test_failed_browser_sign_in_removes_stored_tokens(self, authenticate):
        """No failed identity may leave a usable OIDC token in the browser session."""
        for outcome in (None, AuthenticationFailed('Identity mismatch'), DeactivatedAccountLoginRefused()):
            with self.subTest(outcome=type(outcome).__name__):
                authenticate.side_effect = outcome
                authenticate.return_value = None
                request = Mock(session={'oidc_access_token': 'synthetic-access',
                                        'oidc_id_token': 'synthetic-id', 'other': 'kept'})
                self.assertIsNone(self.backend.authenticate(request))
                self.assertEqual(request.session, {'other': 'kept'})

    @patch('core.users.views.AuthService.is_sso_enabled', return_value=True)
    def test_sso_rejects_local_password_reset_before_lookup_or_email(self, _sso):
        """Only the identity provider can issue useful password recovery links in SSO."""
        request = APIRequestFactory().post('/users/password/reset/',
                                          {'email': 'synthetic@pucp.edu.pe'}, format='json')
        with patch.object(UserProfile.objects, 'filter') as lookup, \
                patch.object(UserProfile, 'save') as save, \
                patch.object(UserProfile, 'send_reset_password_email') as send_mail:
            response = UserPasswordResetView.as_view()(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn('identity provider', str(response.data))
        lookup.assert_not_called()
        save.assert_not_called()
        send_mail.assert_not_called()

    @patch('core.users.views.AuthService.is_sso_enabled', return_value=False)
    def test_local_password_recovery_keeps_its_existing_lookup(self, _sso):
        """Installations without SSO retain their native local recovery endpoint."""
        request = APIRequestFactory().post('/users/password/reset/',
                                          {'email': 'synthetic@pucp.edu.pe'}, format='json')
        with patch.object(UserProfile.objects, 'filter') as lookup:
            lookup.return_value.first.return_value = None
            response = UserPasswordResetView.as_view()(request)
        self.assertEqual(response.status_code, 404)
        lookup.assert_called_once_with(email='synthetic@pucp.edu.pe')
