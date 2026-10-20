"""Export existing Django identities into a private, first-start Keycloak realm.

Run inside the API image with the public realm template mounted read-only:
    python - --template /tmp/ocl-realm.json < keycloak-realm.py > private/ocl-realm.json
The caller must quiesce account writes and protect stdout with mode 600.
This reads accounts and hashes; it never changes credentials, grants roles, or sends email.
"""
import argparse
import copy
from email.errors import HeaderParseError
from email.headerregistry import Address
from email.utils import parseaddr
import json
import os
from pathlib import Path
import sys


def build_realm(template, rows, credential_converter):
    """Validate every identity before returning a realm with preserved password hashes."""
    if template.get('realm') != 'ocl' or template.get('users'):
        raise ValueError('Expected an empty ocl realm template.')
    result = copy.deepcopy(template)
    # The deployment opens registration only after the API and web cutover succeeds.
    result['registrationAllowed'] = False
    users = []
    usernames = set()
    emails = set()
    for row in rows:
        identity = f"account id {row['id']}"
        username = row['username']
        email = row['email']
        # Keycloak normalizes local usernames to lowercase. Never silently rename an OCL identity.
        if not isinstance(username, str) or not username or username != username.strip().lower():
            raise ValueError(f'Noncanonical username for {identity}; explicit migration review required.')
        if username.casefold() in usernames:
            raise ValueError(f'Username collision for {identity}.')
        if not isinstance(email, str) or not email.strip() or email != email.strip():
            raise ValueError(f'Missing or noncanonical email for {identity}.')
        if email.casefold() in emails:
            raise ValueError(f'Email collision for {identity}.')
        try:
            credential = credential_converter(row['password'], temporary=False)
        except (TypeError, ValueError, KeyError):
            raise ValueError(f'Unsupported password hash for {identity}.') from None
        if not isinstance(credential, dict) or credential.get('type') != 'password':
            raise ValueError(f'Unsupported password hash for {identity}.')
        usernames.add(username.casefold())
        emails.add(email.casefold())
        users.append({
            'username': username,
            'email': email,
            'firstName': row['first_name'] or '',
            'lastName': row['last_name'] or '',
            'enabled': row['is_active'],
            'emailVerified': row['verified'],
            'credentials': [credential],
            'requiredActions': [],
        })
    result['users'] = users
    return result


def main(argv=None):
    """Write a complete first-start realm, leaving diagnostics and hashes out of logs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', required=True, type=Path)
    args = parser.parse_args(argv)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    # Django and the application are imported only when the export command actually runs.
    import django  # pylint: disable=import-outside-toplevel
    django.setup()
    from django.conf import settings  # pylint: disable=import-outside-toplevel
    from core.services.auth.openid import OpenIDAuthService  # pylint: disable=import-outside-toplevel
    from core.users.models import UserProfile  # pylint: disable=import-outside-toplevel

    template = json.loads(args.template.read_text(encoding='utf-8'))
    # One SELECT provides a coherent account snapshot while the maintenance caller stops writes.
    rows = list(UserProfile.objects.order_by('id').values(
        'id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'verified', 'password'))
    result = build_realm(template, rows, OpenIDAuthService.credential_representation_from_hash)
    sender = settings.DEFAULT_FROM_EMAIL
    name, address = parseaddr(sender)
    try:
        mailbox = Address(addr_spec=address)
    except (ValueError, HeaderParseError):
        raise ValueError('Invalid SMTP sender address.') from None
    if not mailbox.username or not mailbox.domain or any(char in sender for char in '\r\n'):
        raise ValueError('Invalid SMTP sender address.')
    result['smtpServer'].update({'from': address, 'fromDisplayName': name or 'SIHSALUS Terminología'})
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    sys.stdout.write(payload + '\n')


if __name__ == '__main__':
    try:
        main()
    except ValueError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
