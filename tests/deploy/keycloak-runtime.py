"""Exercise the candidate Keycloak image in isolated CI with synthetic identities and SMTP.

Requires CI=true, Docker, and aiosmtpd==1.4.6. All containers, data and messages are
temporary; no production service or real mail relay is contacted.
"""
import base64
import hashlib
import html
from html.parser import HTMLParser
from http.cookiejar import CookieJar, DefaultCookiePolicy
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.request import build_opener, HTTPRedirectHandler, HTTPCookieProcessor, Request
import uuid

ROOT = Path(__file__).resolve().parents[2]
BASE = 'http://127.0.0.1:18081/auth'
CALLBACK = 'http://127.0.0.1:18765/'
PASSWORD = 'Synthetic-Investigación-2026!'
NEW_PASSWORD = 'Synthetic-Research-Updated-2026!'
ADMIN_PASSWORD = 'Synthetic-Admin-2026!'
POSTGRES_IMAGE = ('postgres:14.24-alpine@sha256:'
                  '4ea9e5ed06591da7ea23eb65465e8d3187fe79f4d5ec3ae976d29a33b013e77a')


def require(condition, message):
    """Keep failure output free of tokens, password hashes and mail links."""
    if not condition:
        raise AssertionError(message)


class Page(HTMLParser):
    """Read native login forms and preserve their hidden anti-CSRF fields."""
    def __init__(self, text, url, status):
        super().__init__(convert_charrefs=True)
        self.url, self.status = url, status
        self.forms, self.links = {}, []
        self.current = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.current = {'action': urljoin(self.url, attrs.get('action', '')),
                            'fields': {}}
            self.forms[attrs.get('id', str(len(self.forms)))] = self.current
        elif tag == 'input' and self.current is not None and attrs.get('name'):
            if attrs.get('type') not in ('submit', 'button', 'checkbox'):
                self.current['fields'][attrs['name']] = attrs.get('value', '')
        elif tag == 'a' and attrs.get('href'):
            self.links.append(urljoin(self.url, attrs['href']))

    def handle_endtag(self, tag):
        if tag == 'form':
            self.current = None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LoopbackCookiePolicy(DefaultCookiePolicy):
    """Match browsers' secure-context exception for this loopback-only CI server.

    Keycloak marks loopback cookies Secure even over HTTP. Python's CookieJar does
    not implement that browser exception, so it otherwise drops the login cookie.
    Production HTTPS and remote HTTP retain the normal cookie policy.
    """
    def return_ok_secure(self, cookie, request):
        if request.type == 'http' and urlparse(request.get_full_url()).hostname == '127.0.0.1':
            return True
        return super().return_ok_secure(cookie, request)


class Browser:
    def __init__(self):
        self.opener = build_opener(
            HTTPCookieProcessor(CookieJar(policy=LoopbackCookiePolicy())), NoRedirect())

    def request(self, url, fields=None, headers=None):
        data = urlencode(fields).encode() if fields is not None else None
        for _ in range(12):
            request = Request(url, data=data, headers=headers or {})
            try:
                response = self.opener.open(request, timeout=20)
            except HTTPError as error:
                response = error
            with response:
                status = response.code
                body = response.read().decode('utf-8')
                location = response.headers.get('Location')
            if status in (301, 302, 303, 307, 308) and location:
                url = urljoin(url, location)
                if not url.startswith(BASE + '/'):
                    return Page('', url, status)
                data = None
                continue
            return Page(body, url, status)
        raise AssertionError('Authentication redirected too many times.')

    def submit(self, page, form_id, values):
        require(form_id in page.forms, 'Expected native form ' + form_id)
        form = page.forms[form_id]
        return self.request(form['action'], {**form['fields'], **values})

    def json(self, url, fields=None, bearer=None, json_content=None):
        headers = {'Authorization': 'Bearer ' + bearer} if bearer else {}
        headers['Accept'] = 'application/json'
        data = urlencode(fields).encode() if fields is not None else None
        if json_content is not None:
            data = json.dumps(json_content).encode()
            headers['Content-Type'] = 'application/json'
        try:
            with self.opener.open(Request(url, data=data, headers=headers), timeout=20) as response:
                return response.code, json.load(response)
        except HTTPError as error:
            with error:
                body = error.read().decode('utf-8')
                try:
                    return error.code, json.loads(body)
                except json.JSONDecodeError:
                    return error.code, {}


class Mailbox:
    def __init__(self):
        self.messages = []

    async def handle_DATA(self, _server, _session, envelope):  # noqa: N802
        self.messages.append((tuple(envelope.rcpt_tos), envelope.content))
        return '250 Message accepted by synthetic test sink'

    def link(self, recipient, after):
        from email import policy
        from email.parser import BytesParser
        deadline = time.monotonic() + 15
        matched_messages, link_paths = 0, set()
        while time.monotonic() < deadline:
            matched_messages = 0
            for recipients, content in self.messages[after:]:
                if recipient not in recipients:
                    continue
                matched_messages += 1
                message = BytesParser(policy=policy.default).parsebytes(content)
                for part in message.walk():
                    if part.get_content_type() not in ('text/plain', 'text/html'):
                        continue
                    for candidate in re.findall(r'https?://[^\s<>"]+', html.unescape(part.get_content())):
                        link_paths.add(urlparse(candidate).path)
                        if '/login-actions/action-token?' in candidate:
                            require(candidate.startswith(BASE + '/'), 'Mail action must target isolated CI.')
                            return candidate.rstrip(').')
            time.sleep(0.1)
        raise AssertionError('Expected synthetic verification/reset mail action missing: '
                             f'messages={len(self.messages[after:])}, matching={matched_messages}, '
                             f'link_paths={sorted(link_paths)}')


def authorization(browser, register=False, action=None):
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    endpoint = 'registrations' if register else 'auth'
    url = BASE + '/realms/ocl/protocol/openid-connect/' + endpoint + '?' + urlencode({
        'client_id': 'ocl-web', 'redirect_uri': CALLBACK, 'response_type': 'code',
        'scope': 'openid profile email', 'state': secrets.token_urlsafe(16),
        'nonce': secrets.token_urlsafe(16), 'code_challenge': challenge,
        'code_challenge_method': 'S256',
        **({'kc_action': action} if action else {}),
    })
    return browser.request(url), verifier


def login(username, password, allowed=True):
    browser = Browser()
    page, verifier = authorization(browser)
    result = browser.submit(page, 'kc-form-login', {'username': username, 'password': password})
    code = parse_qs(urlparse(result.url).query).get('code', [None])[0]
    if not allowed:
        require(not code, 'Disabled account or old password unexpectedly authenticated.')
        return
    require(result.url.startswith(CALLBACK) and code, 'Imported/registered user did not finish sign-in.')
    status, token = browser.json(BASE + '/realms/ocl/protocol/openid-connect/token', {
        'grant_type': 'authorization_code', 'client_id': 'ocl-web', 'redirect_uri': CALLBACK,
        'code': code, 'code_verifier': verifier,
    })
    require(status == 200 and token.get('access_token'), 'PKCE code exchange failed.')
    status, claims = browser.json(BASE + '/realms/ocl/protocol/openid-connect/userinfo',
                                 bearer=token['access_token'])
    require(status == 200 and claims.get('preferred_username') == username, 'Username claim changed.')
    require(claims.get('email_verified') is True, 'Verified email claim missing.')
    require('groups' not in claims, 'Identity provider must not grant local OCL groups.')
    return browser, token['access_token']


def prepare_realm(path):
    """Use the real export shape with synthetic PBKDF2 values and a local SMTP sink."""
    spec = importlib.util.spec_from_file_location('keycloak_realm', ROOT / 'scripts/terminology/keycloak-realm.py')
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)
    template = json.loads((ROOT / 'images/keycloak/ocl-realm.json').read_text())
    # Only this ephemeral fixture disables SMTP authentication/TLS. Production retains both.
    template['smtpServer'] = {
        'host': 'host.docker.internal', 'port': '1025', 'from': 'noreply@example.invalid',
        'fromDisplayName': 'SIHSALUS CI', 'auth': 'false', 'starttls': 'false', 'ssl': 'false'}
    iterations, salt = 320000, 'synthetic-keycloak-import-salt'
    value = base64.b64encode(hashlib.pbkdf2_hmac(
        'sha256', PASSWORD.encode(), salt.encode(), iterations)).decode()
    credential = {
        'type': 'password', 'temporary': False,
        'credentialData': json.dumps({'algorithm': 'pbkdf2-sha256', 'hashIterations': iterations}),
        'secretData': json.dumps({'value': value, 'salt': base64.b64encode(salt.encode()).decode()}),
    }
    rows = [
        dict(id=1, username='migrated-researcher', email='migrated-researcher@pucp.edu.pe',
             first_name='', last_name='', is_active=True, verified=True, password='synthetic'),
        dict(id=2, username='legacy-admin', email='legacy-admin@example.invalid',
             first_name='', last_name='', is_active=True, verified=True, password='synthetic'),
        dict(id=3, username='disabled-researcher', email='disabled-researcher@pucp.edu.pe',
             first_name='', last_name='', is_active=False, verified=True, password='synthetic'),
    ]
    result = exporter.build_realm(template, rows, lambda _value, temporary=False: credential)
    # CI exercises registration immediately; production reconciles only after API/web readiness.
    result['registrationAllowed'] = True
    path.write_text(json.dumps(result), encoding='utf-8')
    path.chmod(0o644)  # Synthetic fixture must be readable by the container's unprivileged UID.


def verify(mailbox):
    admin = Browser()
    status, token = admin.json(BASE + '/realms/master/protocol/openid-connect/token', {
        'grant_type': 'password', 'client_id': 'admin-cli',
        'username': 'ci-admin', 'password': ADMIN_PASSWORD,
    })
    require(status == 200 and token.get('access_token'), 'CI bootstrap administrator unavailable.')

    def users(username):
        status, result = admin.json(BASE + '/admin/realms/ocl/users?' + urlencode({
            'username': username, 'exact': 'true'}), bearer=token['access_token'])
        require(status == 200 and isinstance(result, list), 'Cannot inspect synthetic account.')
        return result

    login('migrated-researcher', PASSWORD)
    login('legacy-admin', PASSWORD)
    login('disabled-researcher', PASSWORD, allowed=False)
    print('PASS: PBKDF2 import, legacy account and disabled-account behavior; PKCE and claims.')

    for index, address in enumerate(('invalid@notpucp.edu.pe', 'invalid@sub.pucp.edu.pe',
                                     'invalid@pucp.edu.pe.evil.invalid')):
        browser = Browser()
        page, _ = authorization(browser, register=True)
        browser.submit(page, 'kc-register-form', {
            'username': 'rejected-' + str(index), 'email': address,
            'firstName': 'Synthetic', 'lastName': 'Researcher',
        })
        require(not users('rejected-' + str(index)), 'Non-PUCP registration was accepted.')
    require(not mailbox.messages, 'Rejected registrations unexpectedly sent email.')
    print('PASS: native user-profile domain validation rejects lookalike and subdomain addresses.')

    for field in ('firstName', 'lastName'):
        rejected = 'long-' + field.lower()
        browser = Browser()
        page, _ = authorization(browser, register=True)
        browser.submit(page, 'kc-register-form', {
            'username': rejected, 'email': rejected + '@pucp.edu.pe',
            'firstName': 'Synthetic', 'lastName': 'Researcher', field: 'A' * 101,
        })
        require(not users(rejected), 'Name exceeding the OCL field limit was accepted.')
    require(not mailbox.messages, 'Rejected name lengths unexpectedly sent email.')

    username, address = 'registered-researcher', 'registered-researcher@pucp.edu.pe'
    browser = Browser()
    page, _ = authorization(browser, register=True)
    require('password' not in page.forms.get('kc-register-form', {}).get('fields', {}),
            'Native registration must verify email before setting a password.')
    result = browser.submit(page, 'kc-register-form', {
        'username': username, 'email': address, 'firstName': 'Synthetic', 'lastName': 'Researcher',
    })
    created = users(username)
    print('Registration challenge:', {'status': result.status, 'path': urlparse(result.url).path,
                                     'forms': sorted(result.forms), 'messages': len(mailbox.messages),
                                     'requiredActions': created[0].get('requiredActions') if created else None})
    require(len(created) == 1 and created[0]['emailVerified'] is False,
            'New account must await email verification.')
    require(not parse_qs(urlparse(result.url).query).get('code'), 'Unverified registration issued a code.')
    page = browser.request(mailbox.link(address, 0))
    require(users(username)[0]['emailVerified'] is True, 'Verification link did not confirm email.')
    result = browser.submit(page, 'kc-passwd-update-form', {
        'password-new': PASSWORD, 'password-confirm': PASSWORD,
    })
    require(result.url.startswith(CALLBACK) and parse_qs(urlparse(result.url).query).get('code'),
            'Confirmed registration did not finish password setup and sign-in.')
    browser, access_token = login(username, PASSWORD)
    print('PASS: native registration sends a captured confirmation mail and permits verified login.')

    status, _ = browser.json(BASE + '/realms/ocl/account/', bearer=access_token, json_content={
        'username': username, 'email': 'changed-researcher@pucp.edu.pe',
        'firstName': 'Synthetic', 'lastName': 'Researcher',
    })
    require(status in (401, 403, 404), 'Account REST API allowed self-service profile editing.')
    for action in ('UPDATE_PROFILE', 'UPDATE_EMAIL'):
        result, _ = authorization(browser, action=action)
        require(not any('email' in form['fields'] for form in result.forms.values()),
                'Disabled identity action exposed an email editing form.')
        require(users(username)[0]['email'] == address, 'Identity action changed the verified email.')
    print('PASS: account REST and application-initiated actions cannot change the OCL identity.')

    before = len(mailbox.messages)
    browser = Browser()
    page, _ = authorization(browser)
    reset_link = next((link for link in page.links if '/login-actions/reset-credentials' in link), None)
    require(reset_link, 'Native forgotten-password link missing.')
    page = browser.request(reset_link)
    browser.submit(page, 'kc-reset-password-form', {'username': username})
    page = browser.request(mailbox.link(address, before))
    browser.submit(page, 'kc-passwd-update-form', {
        'password-new': NEW_PASSWORD, 'password-confirm': NEW_PASSWORD,
    })
    login(username, NEW_PASSWORD)
    login(username, PASSWORD, allowed=False)
    print('PASS: native password recovery sends captured mail and replaces the synthetic password.')


def docker(*args, check=True):
    """Run only named disposable CI resources; never print command credentials."""
    return subprocess.run(['docker', *args], check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def main():
    require(os.environ.get('CI') == 'true', 'This integration test runs only in CI.')
    from aiosmtpd.controller import Controller

    suffix = uuid.uuid4().hex[:10]
    network, database, server = (name + suffix for name in ('kc-ci-net-', 'kc-ci-db-', 'kc-ci-'))
    mailbox = Mailbox()
    smtp = Controller(mailbox, hostname='0.0.0.0', port=1025, ready_timeout=5)
    with tempfile.TemporaryDirectory(prefix='keycloak-ci-') as temporary:
        realm_file = Path(temporary) / 'ocl-realm.json'
        prepare_realm(realm_file)
        try:
            smtp.start()
            docker('network', 'create', network)
            docker('run', '-d', '--name', database, '--network', network, '--network-alias', 'db',
                   '-e', 'POSTGRES_DB=keycloak', '-e', 'POSTGRES_USER=keycloak',
                   '-e', 'POSTGRES_PASSWORD=synthetic-db-password', POSTGRES_IMAGE)
            for _ in range(60):
                if docker('exec', database, 'pg_isready', '-U', 'keycloak', check=False).returncode == 0:
                    break
                time.sleep(1)
            else:
                raise AssertionError('Isolated PostgreSQL did not start.')
            docker('run', '-d', '--name', server, '--network', network,
                   '--add-host', 'host.docker.internal:host-gateway', '--memory', '1g', '--cpus', '0.75',
                   '--read-only', '--tmpfs', '/tmp:uid=1000,gid=0,size=64m',
                   '--tmpfs', '/opt/keycloak/data:uid=1000,gid=0,size=64m',
                   '-p', '127.0.0.1:18081:8080',
                   '--mount', f'type=bind,src={realm_file},dst=/opt/keycloak/data/import/ocl-realm.json,readonly',
                   '-e', 'KC_DB_URL=jdbc:postgresql://db:5432/keycloak',
                   '-e', 'KC_DB_USERNAME=keycloak', '-e', 'KC_DB_PASSWORD=synthetic-db-password',
                   '-e', 'KC_DB_POOL_MAX_SIZE=5', '-e', 'KC_DB_POOL_MIN_SIZE=1',
                   '-e', 'KC_DB_POOL_INITIAL_SIZE=1',
                   '-e', 'KC_HOSTNAME=' + BASE, '-e', 'KC_HTTP_RELATIVE_PATH=/auth',
                   '-e', 'KC_HTTP_ENABLED=true', '-e', 'KC_BOOTSTRAP_ADMIN_USERNAME=ci-admin',
                   '-e', 'KC_BOOTSTRAP_ADMIN_PASSWORD=' + ADMIN_PASSWORD,
                   '-e', 'JAVA_OPTS_KC_HEAP=-Xms128m -Xmx512m',
                   '-e', 'TERMINOLOGY_WEB_URL=' + CALLBACK.rstrip('/'),
                   '-e', 'TERMINOLOGY_ALLOW_SELF_REGISTRATION=true',
                   os.environ.get('KEYCLOAK_TEST_IMAGE', 'terminology-keycloak:ci'),
                   'start', '--optimized', '--import-realm')
            for _ in range(120):
                state = json.loads(docker('inspect', '--format', '{{json .State}}', server).stdout)
                require(state['Running'], 'Candidate Keycloak stopped during initialization.')
                if state.get('Health', {}).get('Status') == 'healthy':
                    break
                time.sleep(2)
            else:
                raise AssertionError('Candidate Keycloak did not become healthy within four minutes.')
            verify(mailbox)
            require(docker('inspect', '--format', '{{.State.OOMKilled}}', server).stdout.strip() == 'false',
                    'Candidate exceeded its 1 GiB memory limit.')
        except Exception:
            # Synthetic setup has no private data. Avoid HTTP request/response or mail bodies in output.
            logs = docker('logs', '--tail', '80', server, check=False)
            print(logs.stdout + logs.stderr)
            state = docker('inspect', '--format', '{{json .State}}', server, check=False)
            print(state.stdout or state.stderr)
            raise
        finally:
            smtp.stop()
            docker('rm', '-f', '-v', server, database, check=False)
            docker('network', 'rm', network, check=False)


if __name__ == '__main__':
    main()
