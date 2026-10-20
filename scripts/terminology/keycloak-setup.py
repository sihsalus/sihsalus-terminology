#!/usr/bin/env python3
"""Native PostgreSQL provisioning and Keycloak realm configuration, inside bootstrap."""
import argparse
from email.errors import HeaderParseError
from email.headerregistry import Address
from email.utils import parseaddr
import json
import os
import sys

def required(name):
    value = os.environ.get(name, '')
    if not value:
        raise ValueError('Missing setting: ' + name)
    return value


def connect(user, password, database):
    import psycopg2  # pylint: disable=import-outside-toplevel

    return psycopg2.connect(host=required('DB_HOST'), port=os.environ.get('DB_PORT', '5432'),
                            user=user, password=password, dbname=database, connect_timeout=10)


def prepare_database(require_existing=False):
    """Provision the owner/database without rotating existing credentials.

    Revoke PUBLIC's PostgreSQL 14 schema CREATE grant in the OCL database so the
    new service role cannot create objects there. The OCL postgres owner retains
    access. Existing role privileges and database ownership must match this scope.
    """
    password = required('TERMINOLOGY_KEYCLOAK_DB_PASSWORD')
    connection = connect(required('DB_USER'), required('DB_PASSWORD'), 'postgres')
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolcanlogin, "
                "EXISTS(SELECT 1 FROM pg_auth_members WHERE member = pg_roles.oid) "
                "FROM pg_roles WHERE rolname = 'keycloak'")
            role = cursor.fetchone()
            if role is None:
                if require_existing:
                    raise ValueError('Existing SSO requires the Keycloak role; restore its backup.')
                cursor.execute('CREATE ROLE keycloak LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
                               'NOREPLICATION NOBYPASSRLS PASSWORD %s', (password,))
            elif role != (False, False, False, False, False, True, False):
                raise ValueError('Existing Keycloak role has unexpected privileges or memberships.')
            cursor.execute("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = 'keycloak'")
            database = cursor.fetchone()
            if database is None and require_existing:
                raise ValueError('Existing SSO requires the Keycloak database; restore its backup.')
            if database is not None and database != ('keycloak',):
                raise ValueError('Existing Keycloak database has an unexpected owner.')
            # Authenticate before any schema change; mismatched secrets require a rotation plan.
            check = connect('keycloak', password, 'postgres')
            check.close()
            if database is None:
                cursor.execute('CREATE DATABASE keycloak OWNER keycloak')
            check = connect('keycloak', password, 'keycloak')
            try:
                with check.cursor() as realm_cursor:
                    realm_cursor.execute("SELECT to_regclass('public.realm')")
                    initialized = False
                    if realm_cursor.fetchone()[0] is not None:
                        realm_cursor.execute("SELECT EXISTS(SELECT 1 FROM realm WHERE name = 'ocl')")
                        initialized = realm_cursor.fetchone()[0]
            finally:
                check.close()
            # Django hashes become stale after an SSO password change; never rebuild an active realm from them.
            if require_existing and not initialized:
                raise ValueError('Existing SSO requires the ocl realm; restore its backup.')
            cursor.execute('REVOKE ALL ON DATABASE keycloak FROM PUBLIC')
            cursor.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
    finally:
        connection.close()
    print(json.dumps({'realm_initialized': initialized}))


def reconcile_realm():
    """Apply the reviewed SMTP/registration settings; startup import skips existing realms."""
    import requests  # pylint: disable=import-outside-toplevel

    registration = required('ALLOW_SELF_REGISTRATION')
    if registration not in ('true', 'false'):
        raise ValueError('Self-registration must be true or false.')
    sender = required('DEFAULT_FROM_EMAIL')
    name, address = parseaddr(sender)
    try:
        mailbox = Address(addr_spec=address)
    except (ValueError, HeaderParseError):
        raise ValueError('Invalid SMTP sender address.') from None
    if not mailbox.username or not mailbox.domain or any(char in sender for char in '\r\n'):
        raise ValueError('Invalid SMTP sender address.')
    smtp = {
        'host': required('EMAIL_HOST'), 'port': required('EMAIL_PORT'),
        'from': address, 'fromDisplayName': name or 'SIHSALUS Terminología',
        'auth': 'true', 'starttls': 'true', 'ssl': 'false',
        'user': required('EMAIL_HOST_USER'), 'password': required('EMAIL_HOST_PASSWORD'),
    }
    if not smtp['port'].isdigit() or not 0 < int(smtp['port']) <= 65535:
        raise ValueError('Invalid SMTP port.')
    server = 'http://keycloak:8080/auth'
    response = requests.post(server + '/realms/master/protocol/openid-connect/token', data={
        'client_id': 'admin-cli', 'grant_type': 'password',
        'username': required('TERMINOLOGY_KEYCLOAK_ADMIN_USERNAME'),
        'password': required('TERMINOLOGY_KEYCLOAK_ADMIN_PASSWORD'),
    }, timeout=20)
    response.raise_for_status()
    headers = {'Authorization': 'Bearer ' + response.json()['access_token']}
    endpoint = server + '/admin/realms/ocl'
    response = requests.get(endpoint, headers=headers, timeout=20)
    response.raise_for_status()
    realm = response.json()
    if realm.get('sslRequired') != 'external' or realm.get('verifyEmail') is not True:
        raise ValueError('Unexpected realm security configuration; review before updating it')
    response = requests.put(endpoint, headers=headers, json={
        'registrationAllowed': registration == 'true',
        'resetPasswordAllowed': True, 'verifyEmail': True, 'smtpServer': smtp,
    }, timeout=20)
    response.raise_for_status()
    print(json.dumps({'realm': 'ocl', 'smtp_configured': True,
                      'registration_enabled': registration == 'true'}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('database', 'reconcile'))
    parser.add_argument('--require-existing', action='store_true')
    args = parser.parse_args()
    if args.command == 'database':
        prepare_database(require_existing=args.require_existing)
    else:
        if args.require_existing:
            parser.error('--require-existing applies only to database preparation')
        reconcile_realm()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # SQL/HTTP exceptions may echo credentials or tokens; keep diagnostics private and bounded.
        print('Keycloak setup failed: ' + type(error).__name__, file=sys.stderr)
        sys.exit(1)
