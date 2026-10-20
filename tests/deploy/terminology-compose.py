"""Render the dedicated stack without a Docker daemon or real credentials."""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class TerminologyComposition(unittest.TestCase):
    """A terminology deployment must not start clinical services or exhaust its host."""

    def render(self, maintenance=False, registration='false', keycloak=False):
        env = dict(os.environ, TERMINOLOGY_HOST="terminology.example.org")
        env["TERMINOLOGY_ALLOW_SELF_REGISTRATION"] = registration
        env["TERMINOLOGY_OIDC_SERVER_URL"] = "https://terminology.example.org/auth" if keycloak else ""
        env["TERMINOLOGY_OIDC_CLIENT_ID"] = "ocl-web" if keycloak else ""
        env["TERMINOLOGY_API_HOST"] = "api.terminology.example.org"
        for key in ("DB_PASSWORD", "SECRET_KEY", "ADMIN_PASSWORD", "ADMIN_TOKEN",
                    "STORAGE_ACCESS_KEY", "STORAGE_SECRET_KEY", "KEYCLOAK_DB_PASSWORD", "KEYCLOAK_ADMIN_PASSWORD"):
            env["TERMINOLOGY_" + key] = "synthetic-render-only"
        for app in ("API", "WEB", "POSTGRES", "REDIS", "ELASTICSEARCH", "KEYCLOAK"):
            env["TERMINOLOGY_" + app + "_IMAGE"] = (
                "ghcr.io/sihsalus/terminology-" + app.lower() + "@sha256:" + "a" * 64)
        command = ["docker", "compose", "-f", "docker-compose.terminology.yml"]
        if keycloak:
            command += ["--profile", "keycloak"]
        if maintenance:
            command += ["--profile", "maintenance"]
        result = subprocess.run(command + ["config", "--format", "json"], cwd=ROOT, env=env,
                                capture_output=True, text=True, check=True, timeout=30)
        return json.loads(result.stdout)["services"]

    def test_runtime_budget_and_isolation(self):
        services = self.render()
        self.assertEqual(set(services), {"api", "web", "db", "redis", "es", "storage",
                                        "worker", "importer", "scheduler"})
        self.assertLessEqual(sum(int(s["mem_limit"]) for s in services.values()), 5 * 1024**3)
        for name, service in services.items():
            self.assertNotIn("build", service, name)
            self.assertEqual(service["cgroup_parent"], "sihsalus-terminology.slice")
            self.assertIn("@sha256:", service["image"])
            for port in service.get("ports", []):
                self.assertEqual(port["host_ip"], "127.0.0.1", name)
        self.assertEqual(services["redis"]["command"][-1], "noeviction")
        self.assertEqual(services["web"]["environment"]["API_URL"], "https://api.terminology.example.org")
        self.assertIn("bulk_import_root", ",".join(services["importer"]["command"]))
        self.assertIn("concurrent", ",".join(services["worker"]["command"]))
        self.assertEqual(services["worker"]["command"][0], "celery")
        self.assertEqual(services["worker"]["command"][-1], "2")
        self.assertEqual(services["importer"]["command"][0], "celery")
        self.assertEqual(services["importer"]["command"][-1], "1")
        for name in ("api", "worker", "importer", "scheduler"):
            self.assertNotIn("API_SUPERUSER_PASSWORD", services[name]["environment"])
            self.assertEqual(services[name]["environment"]["ALLOW_SELF_REGISTRATION"], "false")
            self.assertEqual(services[name]["environment"]["ENABLE_THROTTLING"], "true")

    def test_registration_flag_reaches_web_and_all_api_processes(self):
        services = self.render(maintenance=True, registration='true')
        for name in ('api', 'worker', 'importer', 'scheduler', 'bootstrap', 'web'):
            self.assertEqual(services[name]['environment']['ALLOW_SELF_REGISTRATION'], 'true')
            if name != 'web':
                self.assertEqual(services[name]['environment']['SELF_REGISTRATION_EMAIL_DOMAINS'], 'pucp.edu.pe')

    def test_sso_is_optional_private_and_within_six_gib(self):
        services = self.render(keycloak=True)
        self.assertEqual(len(services), 10)
        self.assertLessEqual(sum(int(s["mem_limit"]) for s in services.values()), 6 * 1024**3)
        identity = services['keycloak']
        self.assertEqual(identity['profiles'], ['keycloak'])
        self.assertTrue(identity['read_only'])
        self.assertEqual(identity['environment']['KC_DB_POOL_MAX_SIZE'], '5')
        self.assertEqual(identity['ports'][0]['host_ip'], '127.0.0.1')
        self.assertEqual(identity['ports'][0]['published'], '8081')
        self.assertEqual(identity['volumes'][0]['target'], '/opt/keycloak/data/import')
        self.assertTrue(identity['volumes'][0]['read_only'])
        self.assertFalse(identity['volumes'][0]['bind']['create_host_path'])
        self.assertEqual(services['api']['environment']['OIDC_SERVER_URL'], 'https://terminology.example.org/auth')
        self.assertEqual(services['web']['environment']['OIDC_RP_CLIENT_ID'], 'ocl-web')
        self.assertEqual(services['web']['environment']['LOGIN_REDIRECT_URL'], 'https://terminology.example.org/')
        for name in ('api', 'worker', 'importer', 'scheduler', 'web'):
            self.assertNotIn('KC_BOOTSTRAP_ADMIN_PASSWORD', services[name]['environment'])
            self.assertNotIn('TERMINOLOGY_KEYCLOAK_ADMIN_PASSWORD', services[name]['environment'])

    def test_bootstrap_is_explicit_and_bounded(self):
        services = self.render(maintenance=True)
        self.assertEqual(services["bootstrap"]["profiles"], ["maintenance"])
        self.assertEqual(services["bootstrap"]["restart"], "no")
        self.assertLessEqual(int(services["bootstrap"]["mem_limit"]), 768 * 1024**2)


if __name__ == "__main__":
    unittest.main()
