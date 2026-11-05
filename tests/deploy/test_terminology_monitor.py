"""Failure and notification regression checks, using synthetic data only."""
import importlib.util
import json
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("monitor", ROOT / "scripts/terminology/monitor.py")
monitor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(monitor)


class MonitorTest(unittest.TestCase):
    def test_http_200_with_broken_or_missing_dependency_fails(self):
        for body in ({"DatabaseBackend": "unavailable"}, {}):
            with self.subTest(body=body), self.assertRaises(monitor.ProbeFailure):
                monitor.validate_health(json.dumps(body), ("DatabaseBackend",))

    def test_optional_flower_does_not_hide_actual_dependency_failure(self):
        body = {"DatabaseBackend": "working", "Flower": "unavailable"}
        monitor.validate_health(json.dumps(body), ("DatabaseBackend",))
        body["DatabaseBackend"] = "unavailable"
        with self.assertRaises(monitor.ProbeFailure):
            monitor.validate_health(json.dumps(body), ("DatabaseBackend",))

    def test_oidc_wrong_issuer_and_missing_signing_keys_fail(self):
        base = "https://example.org"
        issuer = base + "/auth/realms/ocl"
        with patch.object(monitor, "fetch", return_value=b'{"issuer":"https://other.example"}'):
            with self.assertRaises(monitor.ProbeFailure):
                monitor.oidc_check(base)
        metadata = {"issuer": issuer, "jwks_uri": issuer + "/protocol/openid-connect/certs"}
        with patch.object(monitor, "fetch", side_effect=[json.dumps(metadata), '{"keys":[]}']):
            with self.assertRaises(monitor.ProbeFailure):
                monitor.oidc_check(base)

    def test_transient_failure_recovers_without_incident(self):
        check = MagicMock(side_effect=[TimeoutError(), None])
        with patch.object(monitor.time, "sleep"):
            result = monitor.retry("web", check)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["check"], "web")
            self.assertGreaterEqual(result["duration_ms"], 0)
        self.assertEqual(check.call_count, 2)

    def test_retries_are_bounded_and_server_messages_redacted(self):
        check = MagicMock(side_effect=RuntimeError("private-secret@example.test"))
        with patch.object(monitor.time, "sleep"):
            result = monitor.retry("smtp", check)
        self.assertEqual(check.call_count, 3)
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("private-secret", json.dumps(result))
        self.assertEqual(result["error"], "RuntimeError")

    def test_redirect_is_never_followed_with_authorization(self):
        self.assertIsNone(monitor.NoRedirect().redirect_request(
            None, None, 302, "", {}, "http://untrusted.example"))
        check = MagicMock(side_effect=HTTPError("https://example.org", 302, "private", {}, None))
        with patch.object(monitor.time, "sleep"):
            self.assertEqual(monitor.retry("endpoint", check)["error"], "HTTP 302")

    def test_notifications_initial_outage_recovery_and_retry(self):
        for current, previous, notice, expected in (
            ("success", None, None, True),
            ("failure", "success", "success", True),
            ("failure", "failure", "success", False),
            ("success", "failure", "success", True),
            ("success", "success", "success", False),
            ("failure", "failure", "failure", True),
            ("success", "success", "failure", True),
            ("failure", None, "success", True),
        ):
            with self.subTest(current=current, previous=previous, notice=notice):
                self.assertEqual(monitor.needs_notice(current, previous, notice), expected)

    @patch.dict(os.environ, {"GITHUB_RUN_ID": "12", "GITHUB_REF_NAME": "main"})
    def test_history_uses_latest_completed_run_before_current(self):
        runs = {"workflow_runs": [{"id": 11}, {"id": 10}, {"id": 12}, {"id": 13}]}
        jobs = {"jobs": [{"name": "Probe service", "conclusion": "failure"},
                         {"name": "Notify group", "conclusion": "success"}]}
        with patch.object(monitor, "github", side_effect=[runs, jobs]) as api:
            self.assertEqual(monitor.previous_result(), ("failure", "success"))
            self.assertEqual(api.call_args.args[0], "/actions/runs/11/jobs?per_page=100")

    def test_smtp_probe_does_not_send_mail(self):
        with patch.object(monitor, "smtp_connection") as connection:
            monitor.smtp_check()
            connection.return_value.__enter__.return_value.send_message.assert_not_called()
            connection.return_value.__enter__.return_value.sendmail.assert_not_called()

    @patch.dict(os.environ, {
        "TERMINOLOGY_EMAIL_HOST_USER": "sender@example.org",
        "TERMINOLOGY_MONITOR_RECIPIENT": "group@example.org",
        "TERMINOLOGY_HOST": "example.org",
        "GITHUB_REPOSITORY": "example/repo", "GITHUB_RUN_ID": "12",
    })
    def test_notice_goes_only_to_requested_group(self):
        message = monitor.notice_message("failure")
        self.assertEqual(message["To"], "group@example.org")
        self.assertIsNone(message["Cc"])
        self.assertIsNone(message["Bcc"])
        self.assertIn("/actions/runs/12", message.get_content())
        self.assertNotIn("axel", message.get_content().lower())

    @patch.dict(os.environ, {"PROBE_RESULT": "failure"})
    def test_failed_notice_is_not_reported_as_success(self):
        with patch.object(monitor, "previous_result", return_value=("success", "success")), \
                patch.object(monitor, "notice_message", return_value=MagicMock()), \
                patch.object(monitor, "smtp_connection") as connection:
            connection.return_value.__enter__.return_value.send_message.return_value = {
                "group@example.org": (550, b"Rejected")}
            with self.assertRaises(RuntimeError):
                monitor.notify()


    def test_report_is_exported_for_failed_job_and_human_summary(self):
        report = {"checks": [{"check": "redis", "status": "failed",
                              "duration_ms": 21400, "error": "HTTP 503"}]}
        with tempfile.TemporaryDirectory() as directory:
            output, summary = Path(directory) / "output", Path(directory) / "summary"
            with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output), "GITHUB_STEP_SUMMARY": str(summary)}), \
                    patch("builtins.print"):
                monitor.publish_report(report)
            key, payload = output.read_text().strip().split("=", 1)
            self.assertEqual(key, "report")
            self.assertEqual(json.loads(payload), report)
            self.assertIn("redis: FALLO (21400 ms): HTTP 503", summary.read_text())

    @patch.dict(os.environ, {
        "TERMINOLOGY_EMAIL_HOST_USER": "sender@example.org",
        "TERMINOLOGY_MONITOR_RECIPIENT": "group@example.org",
        "TERMINOLOGY_HOST": "example.org",
        "GITHUB_REPOSITORY": "example/repo", "GITHUB_RUN_ID": "12",
        "PROBE_REPORT": '{"checks":[{"check":"redis","status":"failed","duration_ms":21400,"error":"HTTP 503"}]}',
    })
    def test_incident_email_names_failed_component_and_duration(self):
        message = monitor.notice_message("failure")
        self.assertIn("INCIDENCIA", str(message["Subject"]))
        self.assertIn("redis: FALLO (21400 ms): HTTP 503", message.get_content())

    @patch.dict(os.environ, {
        "TERMINOLOGY_EMAIL_HOST_USER": "sender@example.org",
        "TERMINOLOGY_MONITOR_RECIPIENT": "group@example.org",
        "TERMINOLOGY_HOST": "example.org",
        "GITHUB_REPOSITORY": "example/repo", "GITHUB_RUN_ID": "12",
        "PROBE_REPORT": "incomplete report",
    })
    def test_incomplete_probe_report_does_not_prevent_incident_email(self):
        message = monitor.notice_message("failure")
        self.assertIn("INCIDENCIA", str(message["Subject"]))
        self.assertIn("No se pudo leer el detalle", message.get_content())
        self.assertIn("/actions/runs/12", message.get_content())


if __name__ == "__main__":
    unittest.main()
