"""Release artifacts and private configuration, without a Docker daemon."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('release', ROOT / 'scripts/terminology/release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
COMMIT = 'a' * 40


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.manifest = dict(source_commit=COMMIT, workflow_run=release.RUN_URL+'123',
                             images={app: 'ghcr.io/sihsalus/terminology-'+app+'@sha256:'+'b'*64
                                     for app in release.APPS}, storage='rustfs/rustfs@sha256:'+'c'*64)
        self.env = self.root / '.env'
        self.env.write_text("# keep\nTERMINOLOGY_EMAIL_HOST_PASSWORD='synthetic $LITERAL `uname`'\n"
                            "TERMINOLOGY_SOURCE_SHA=old\nexport TERMINOLOGY_SOURCE_SHA=duplicate\n")
        self.env.chmod(0o600)
        self.original = self.env.read_bytes()
        self.candidate = self.root / '.env.candidate'
        self.model = {'services': {service: {'image': self.reference(app)}
                                  for service, app in release.SERVICES.items()}}
        for app, ref in self.manifest['images'].items():
            directory = self.root / ('terminology-'+app+'-'+COMMIT)
            directory.mkdir()
            (directory/'image-ref.txt').write_text(ref+'\n')
            self.report(directory/'security.json', ref)
        (self.root/'terminology-service-security').mkdir()
        self.report(self.root/'terminology-service-security/storage.json', self.manifest['storage'])

    def reference(self, app):
        return self.manifest['storage'] if app == 'storage' else self.manifest['images'][app]

    def report(self, path, ref, vulnerabilities=None):
        path.write_text(json.dumps(dict(SchemaVersion=2, ArtifactType='container_image', ArtifactName=ref,
                                       Results=[dict(Vulnerabilities=vulnerabilities or [])])))

    def test_collects_same_run_scans_and_digests(self):
        result = release.collect(self.root, COMMIT, '123')
        self.assertEqual(result['images'], self.manifest['images'])
        self.assertEqual(result['storage_scan'], result['workflow_run'])

    def test_rejects_findings_in_each_of_seven_images(self):
        for file in list(self.root.glob('*/security.json')) + list(self.root.glob('*/storage.json')):
            original = file.read_text()
            data = json.loads(original)
            data['Results'][0]['Vulnerabilities'] = [{'Severity': 'HIGH'}]
            file.write_text(json.dumps(data))
            with self.subTest(file=file), self.assertRaisesRegex(ValueError, 'findings'):
                release.collect(self.root, COMMIT, '123')
            file.write_text(original)

    def test_missing_or_mismatched_scan_is_rejected(self):
        file = self.root / ('terminology-api-'+COMMIT) / 'security.json'
        self.report(file, self.manifest['images']['web'])
        with self.assertRaisesRegex(ValueError, 'mismatched'):
            release.collect(self.root, COMMIT, '123')
        file.unlink()
        with self.assertRaises(FileNotFoundError):
            release.collect(self.root, COMMIT, '123')

    def test_wrong_commit_artifacts_are_not_reused(self):
        with self.assertRaises(FileNotFoundError):
            release.collect(self.root, 'd'*40, '123')

    def test_rejects_mutable_foreign_or_incomplete_manifest(self):
        for value in ('ghcr.io/sihsalus/terminology-api:latest', 'evil.invalid/api@sha256:'+'b'*64):
            manifest = copy.deepcopy(self.manifest)
            manifest['images']['api'] = value
            with self.assertRaises(ValueError):
                release.validate(manifest)
        manifest['images'].pop('api')
        with self.assertRaises(ValueError):
            release.validate(manifest)

    def test_manifest_requires_keycloak_even_when_sso_is_disabled(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['images'].pop('keycloak')
        with self.assertRaisesRegex(ValueError, 'six runtime images'):
            release.validate(manifest)

    def prepare(self):
        with patch.object(release.subprocess, 'check_output', return_value=COMMIT+'\n'), \
             patch.object(release, 'compose', return_value=json.dumps(self.model)):
            release.prepare(self.manifest, self.env, self.candidate)

    def test_prepare_preserves_secrets_and_installed_file(self):
        self.prepare()
        self.assertEqual(self.env.read_bytes(), self.original)
        candidate = self.candidate.read_text()
        self.assertIn("# keep\nTERMINOLOGY_EMAIL_HOST_PASSWORD='synthetic $LITERAL `uname`'\n", candidate)
        self.assertEqual(candidate.count('TERMINOLOGY_SOURCE_SHA='), 1)
        self.assertIn('TERMINOLOGY_SOURCE_SHA='+COMMIT, candidate)
        self.assertEqual(self.candidate.stat().st_mode & 0o777, 0o600)
        self.assertIn('TERMINOLOGY_KEYCLOAK_IMAGE='+self.manifest['images']['keycloak'], candidate)

    def test_prepare_validates_optional_keycloak_profile(self):
        with patch.object(release.subprocess, 'check_output', return_value=COMMIT+'\n'), \
             patch.object(release, 'compose', return_value=json.dumps(self.model)) as compose:
            release.prepare(self.manifest, self.env, self.candidate)
        compose.assert_called_once_with(self.candidate, '--profile', 'keycloak', 'config', '--format', 'json')

    def test_prepare_never_overwrites_existing_candidate(self):
        self.candidate.write_text('existing')
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual(self.candidate.read_text(), 'existing')

    def test_prepare_rejects_wrong_checkout(self):
        with patch.object(release.subprocess, 'check_output', return_value='d'*40), \
             self.assertRaisesRegex(ValueError, 'source commit'):
            release.prepare(self.manifest, self.env, self.candidate)
        self.assertFalse(self.candidate.exists())

    def test_prepare_rejects_override_and_cleans_failed_candidate(self):
        for service in ('storage', 'api', 'keycloak'):
            original = self.model['services'][service]['image']
            self.model['services'][service]['image'] = 'wrong'
            with self.subTest(service=service), self.assertRaises(ValueError):
                self.prepare()
            self.assertFalse(self.candidate.exists())
            self.assertEqual(self.env.read_bytes(), self.original)
            self.model['services'][service]['image'] = original

    def test_rejects_public_and_symlink_env(self):
        self.env.chmod(0o644)
        with self.assertRaises(ValueError):
            self.prepare()
        self.env.chmod(0o600)
        link = self.root/'link'
        link.symlink_to(self.env)
        with self.assertRaises(ValueError):
            release.private_env(link)

    def containers(self, oidc=False):
        return [dict(Config=dict(Image=self.reference(app), Labels={
                    'com.docker.compose.service': service, 'org.opencontainers.image.revision': COMMIT}),
                     State=dict(Running=True, OOMKilled=False, Health=dict(Status='healthy')),
                     RestartCount=0) for service, app in release.SERVICES.items()
                if service != 'keycloak' or oidc]

    def verify(self, items):
        check_output = subprocess.check_output

        def inspect(args, **kwargs):
            if args[:2] == ['docker', 'inspect']:
                return json.dumps(items)
            return check_output(args, **kwargs)

        with patch.object(release, 'compose', return_value='\n'.join(str(i) for i in range(len(items)))), \
             patch.object(release.subprocess, 'check_output', side_effect=inspect):
            return release.verify(self.manifest, self.env)

    def test_verify_nine_healthy_services(self):
        self.assertEqual(len(self.verify(self.containers())['services']), 9)

    def enable_oidc(self):
        """Model the explicit activation flag using an unrelated synthetic host."""
        self.env.write_text(self.original.decode() + "TERMINOLOGY_OIDC_SERVER_URL='https://identity.example.org'\n")

    def test_verify_ten_healthy_services_with_oidc(self):
        self.enable_oidc()
        services = self.verify(self.containers(oidc=True))['services']
        self.assertEqual(len(services), 10)
        self.assertEqual(services['keycloak']['health'], 'healthy')

    def test_oidc_requires_provider_and_disabled_oidc_rejects_stale_provider(self):
        with self.assertRaisesRegex(ValueError, 'Expected 9'):
            self.verify(self.containers(oidc=True))
        self.enable_oidc()
        with self.assertRaisesRegex(ValueError, 'Expected 10'):
            self.verify(self.containers())

    def test_keycloak_health_revision_and_digest_are_required(self):
        self.enable_oidc()
        for section, name, value in (
                ('State', 'Health', {}), ('State', 'Health', {'Status': 'unhealthy'}),
                ('State', 'Running', False), ('State', 'OOMKilled', True),
                ('Config', 'Image', 'wrong'),
        ):
            items = self.containers(oidc=True)
            provider = next(item for item in items if item['Config']['Labels']['com.docker.compose.service'] == 'keycloak')
            provider[section][name] = value
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                self.verify(items)
        items = self.containers(oidc=True)
        provider = next(item for item in items if item['Config']['Labels']['com.docker.compose.service'] == 'keycloak')
        provider['Config']['Labels']['org.opencontainers.image.revision'] = 'd'*40
        with self.assertRaisesRegex(ValueError, 'source revision'):
            self.verify(items)

    def test_oidc_reader_supports_legacy_empty_quoted_and_exported_values(self):
        for suffix, expected in (
                ('', False), ('TERMINOLOGY_OIDC_SERVER_URL=\n', False),
                ("TERMINOLOGY_OIDC_SERVER_URL=''\n", False),
                ('export TERMINOLOGY_OIDC_SERVER_URL="" # disabled\n', False),
                ("TERMINOLOGY_OIDC_SERVER_URL='# literal'\n", True),
                ('TERMINOLOGY_OIDC_SERVER_URL="# literal"\n', True),
                ('TERMINOLOGY_OIDC_SERVER_URL=#literal\n', True),
                ("export TERMINOLOGY_OIDC_SERVER_URL='https://identity.example.org' # own realm\n", True),
                ('TERMINOLOGY_OIDC_SERVER_URL=https://identity.example.org\n'
                 'TERMINOLOGY_OIDC_SERVER_URL= # disabled\n', False),
        ):
            with self.subTest(suffix=suffix):
                self.env.write_text(self.original.decode() + suffix)
                self.assertIs(release.oidc_enabled(self.env), expected)

    def test_oidc_reader_does_not_execute_shell_substitutions(self):
        marker = self.root / 'must-not-exist'
        self.env.write_text(self.original.decode() + f'TERMINOLOGY_OIDC_SERVER_URL=$(touch {marker})\n')
        self.assertTrue(release.oidc_enabled(self.env))
        self.assertFalse(marker.exists())

    def test_verify_detects_missing_service_and_runtime_drift(self):
        with self.assertRaises(ValueError):
            self.verify(self.containers()[:-1])
        for section, name, value in [('Config', 'Image', 'wrong'), ('State', 'Running', False),
                                      ('State', 'OOMKilled', True), ('State', 'Health', {}),
                                      ('State', 'Health', {'Status': 'unhealthy'})]:
            items = self.containers()
            items[0][section][name] = value
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                self.verify(items)
        items = self.containers()
        items[0]['RestartCount'] = 1
        with self.assertRaises(ValueError):
            self.verify(items)
        items = self.containers()
        items[0]['Config']['Labels']['org.opencontainers.image.revision'] = 'd'*40
        with self.assertRaises(ValueError):
            self.verify(items)


if __name__ == '__main__':
    unittest.main()
