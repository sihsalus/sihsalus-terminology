import logging

from celery_once.backends import Redis
from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import ValidationError
from django.db.models import Q
from django_redis import get_redis_connection
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from pydash import get
from redis import Sentinel
from rest_framework.exceptions import AuthenticationFailed

from core.common.exceptions import DeactivatedAccountLoginRefused

logger = logging.getLogger('oclapi')


class QueueOnceRedisSentinelBackend(Redis):
    def __init__(self, backend_settings):
        # pylint: disable=super-init-not-called
        self._sentinel = Sentinel(backend_settings['sentinels'])
        self._sentinel_master = backend_settings['sentinels_master']
        self.blocking_timeout = backend_settings.get("blocking_timeout", 1)
        self.blocking = backend_settings.get("blocking", False)

    @property
    def redis(self):
        return self._sentinel.master_for(self._sentinel_master)


class QueueOnceRedisBackend(Redis):
    """
    Calls get_redis_connection from django_redis so that it re-uses django redis cache config.
    """
    def __init__(self, backend_settings):
        # pylint: disable=super-init-not-called
        self.blocking_timeout = backend_settings.get("blocking_timeout", 1)
        self.blocking = backend_settings.get("blocking", False)

    @property
    def redis(self):
        return get_redis_connection('default')


class OCLOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """
    1. overrides Default OIDCAuthenticationBackend
    2. creates/updates user from OID to django on successful auth
    """
    def verify_claims(self, claims):
        """Require a valid username and a verified email before resolving an identity."""
        if not super().verify_claims(claims) or claims.get('email_verified') is not True:
            return False
        username, email = claims.get('preferred_username'), claims.get('email')
        if not isinstance(username, str) or not isinstance(email, str) or not email.strip():
            return False
        try:
            self.UserModel._meta.get_field('username').clean(username, None)  # pylint: disable=protected-access
            self.UserModel._meta.get_field('email').clean(email, None)  # pylint: disable=protected-access
        except ValidationError:
            return False
        return True

    def create_user(self, claims):
        """Provision verified institutional users without granting local privileges."""
        from core.users.models import UserProfile
        if not self.verify_claims(claims):
            raise AuthenticationFailed('A verified identity is required.')
        email = claims['email']
        if email.rsplit('@', 1)[-1].lower() not in settings.SELF_REGISTRATION_EMAIL_DOMAINS:
            raise AuthenticationFailed('Use an email address from an allowed institution.')
        user = UserProfile.objects.create_user(
            claims['preferred_username'],
            email=email,
            first_name=claims.get('given_name') or '',
            last_name=claims.get('family_name') or '',
            verified=True,
            company=claims.get('company', None),
            location=claims.get('location', None)
        )
        if user.id:
            user.set_checksums()
        user.record_joined_ocl_event()
        return user

    def update_user(self, user, claims):
        """Refresh profile names while Django retains identity and authorization data."""
        user.first_name = claims.get('given_name') or user.first_name
        user.last_name = claims.get('family_name') or user.last_name
        user.company = claims.get('company', None) or user.company
        user.location = claims.get('location', None) or user.location
        user.verified = True

        if user.is_dirty():
            user.save()
            user.set_checksums()

        return user

    def authenticate(self, request, **kwargs):
        """Discard saved tokens when a browser sign-in cannot resolve its identity."""
        try:
            user = super().authenticate(request, **kwargs)
        except AuthenticationFailed:
            user = None
        if user is None and request is not None:
            for key in ('oidc_access_token', 'oidc_id_token'):
                request.session.pop(key, None)
        return user

    def filter_users_by_claims(self, claims):
        """
        Link an exact username only when its verified email also matches. Reject
        collisions instead of creating another identity or attaching by email alone.
        Disabled accounts and local permissions remain under administrator control.
        """
        from core.users.models import UserProfile

        if not self.verify_claims(claims):
            raise AuthenticationFailed('A verified identity is required.')
        username = claims['preferred_username']
        # Evaluate once so collision checks and profile updates refer to the same rows.
        users = UserProfile.objects.filter(Q(username__iexact=username) | Q(email__iexact=claims['email']))
        user = users[0] if users else None
        if user and not user.is_active:
            raise DeactivatedAccountLoginRefused()
        if user and (len(users) != 1 or user.username != username or not self.has_verified_email_of(user, claims)):
            logger.warning('OIDC sign-in refused because the local identity does not match the verified claims')
            raise AuthenticationFailed('This identity does not match the existing local account.')
        return users

    @staticmethod
    def has_verified_email_of(user, claims):
        """Compare emails without accepting truthy strings as verification evidence."""
        email = claims.get('email')
        if claims.get('email_verified') is not True or not isinstance(email, str) or not email.strip():
            return False
        return email.strip().lower() == (user.email or '').strip().lower()


class OCLAuthenticationBackend(ModelBackend):
    """
    1. authentication backend defined in settings.AUTHENTICATION_BACKENDS.
    2. switches between Django/OID Auth Backends based on type of request
    3. switches to django auth if a valid django token is used in request
    """

    def get_auth_backend(self, request=None):
        if get(self, '_authentication_backend'):
            return get(self, '_authentication_backend')

        from core.services.auth.core import AuthService
        if AuthService.is_valid_django_token(request) or get(settings, 'TEST_MODE', False):
            klass = ModelBackend
        else:
            klass = AuthService.get().authentication_backend_class

        self._authentication_backend = klass()

        return self._authentication_backend

    def authenticate(self, request, username=None, password=None, **kwargs):
        return self.get_auth_backend(request).authenticate(
            request=request, username=username, password=password, **kwargs)

    def get_user(self, user_id):
        return self.get_auth_backend().get_user(user_id=user_id)
