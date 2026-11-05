#!/usr/bin/env python3
"""External read-only probes and transition emails. No application admin credentials."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
import json
import os
import smtplib
import socket
import ssl
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

WORKFLOW = "monitor.yml"
QUEUES = ("default", "indexing", "concurrent", "bulk_import_root",
          "bulk_import_0", "bulk_import_1", "bulk_import_2", "bulk_import_3")


class ProbeFailure(Exception):
    """A safe, locally generated diagnostic."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url, headers=None):
    request = Request(url, headers={"User-Agent": "SIHSALUS-Availability/1.0", **(headers or {})})
    with build_opener(NoRedirect()).open(request, timeout=20) as response:
        if response.status != 200:
            raise ProbeFailure("Unexpected HTTP status")
        body = response.read(1024 * 1024 + 1)
        if len(body) > 1024 * 1024:
            raise ProbeFailure("Response too large")
        return body


def validate_health(body, required):
    data = json.loads(body)
    failed = [key for key in required if data.get(key) != "working"]
    if failed:
        raise ProbeFailure("Unhealthy or missing components: " + ", ".join(failed))


def web_check(base):
    body = fetch(base + "/")
    if b'id="root"' not in body or b"<html" not in body.lower():
        raise ProbeFailure("Application entry point missing")


def oidc_check(base):
    issuer = base + "/auth/realms/ocl"
    data = json.loads(fetch(issuer + "/.well-known/openid-configuration"))
    if data.get("issuer") != issuer:
        raise ProbeFailure("Unexpected OIDC issuer")
    if data.get("jwks_uri") != issuer + "/protocol/openid-connect/certs":
        raise ProbeFailure("Unexpected signing-key endpoint")
    if not json.loads(fetch(data["jwks_uri"])).get("keys"):
        raise ProbeFailure("OIDC signing keys missing")


def tls_check(host):
    with socket.create_connection((host, 443), timeout=20) as raw:
        with ssl.create_default_context().wrap_socket(raw, server_hostname=host) as conn:
            expires = ssl.cert_time_to_seconds(conn.getpeercert()["notAfter"])
    if expires - time.time() < 14 * 86400:
        raise ProbeFailure("TLS certificate expires in less than 14 days")


def smtp_connection():
    client = smtplib.SMTP(os.environ["TERMINOLOGY_EMAIL_HOST"],
                          int(os.environ.get("TERMINOLOGY_EMAIL_PORT", "587")), timeout=20)
    try:
        client.ehlo()
        client.starttls(context=ssl.create_default_context())
        client.ehlo()
        client.login(os.environ["TERMINOLOGY_EMAIL_HOST_USER"],
                     os.environ["TERMINOLOGY_EMAIL_HOST_PASSWORD"])
        return client
    except Exception:
        client.close()
        raise


def smtp_check():
    with smtp_connection():
        pass  # Authentication only: never send a periodic test message.


def retry(name, check):
    for attempt in range(3):
        try:
            check()
            return {"check": name, "status": "ok"}
        except Exception as error:  # Remote bodies and SMTP replies may contain private data.
            diagnostic = ("HTTP " + str(error.code) if isinstance(error, HTTPError)
                          else type(error).__name__)
            if isinstance(error, ProbeFailure):
                diagnostic = str(error)
            if isinstance(error, HTTPError):
                error.close()
            if attempt < 2:
                time.sleep(10)
    return {"check": name, "status": "failed", "error": diagnostic}


def probe(skip_smtp=False):
    web_host = os.environ["TERMINOLOGY_HOST"]
    api_host = os.environ["TERMINOLOGY_API_HOST"]
    for host in (web_host, api_host):
        if urlsplit("https://" + host).netloc != host or "/" in host or "@" in host:
            raise ProbeFailure("Expected a bare hostname")
    web, api = "https://" + web_host, "https://" + api_host
    checks = [
        ("web", lambda: web_check(web)),
        ("api-database-search-workers", lambda: validate_health(
            fetch(api + "/healthcheck/?format=json"),
            ("DatabaseBackend", "ElasticSearch", *("celery@" + q for q in QUEUES)))),
        ("redis", lambda: validate_health(fetch(api + "/healthcheck/redis/?format=json"), ("Redis",))),
        ("login-oidc", lambda: oidc_check(web)),
        ("web-certificate", lambda: tls_check(web_host)),
        ("api-certificate", lambda: tls_check(api_host)),
    ]
    if not skip_smtp:
        checks.append(("smtp-authentication", smtp_check))
    with ThreadPoolExecutor(max_workers=len(checks)) as pool:
        results = list(pool.map(lambda item: retry(*item), checks))
    print(json.dumps({"time": datetime.now(timezone.utc).isoformat(),
                      "smtp_checked": not skip_smtp, "checks": results}, indent=2))
    return 1 if any(result["status"] != "ok" for result in results) else 0


def github(path):
    return json.loads(fetch("https://api.github.com/repos/" + os.environ["GITHUB_REPOSITORY"] + path,
                            {"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                             "Accept": "application/vnd.github+json",
                             "X-GitHub-Api-Version": "2022-11-28"}))


def previous_result():
    query = urlencode({"status": "completed", "branch": os.environ["GITHUB_REF_NAME"], "per_page": 20})
    runs = github("/actions/workflows/" + WORKFLOW + "/runs?" + query)["workflow_runs"]
    current = int(os.environ["GITHUB_RUN_ID"])
    runs = [run for run in runs if run["id"] < current]
    if not runs:
        return None, None
    previous = max(runs, key=lambda run: run["id"])
    jobs = github("/actions/runs/" + str(previous["id"]) + "/jobs?per_page=100")["jobs"]
    states = {job["name"]: job["conclusion"] for job in jobs}
    return states.get("Probe service"), states.get("Notify group")


def needs_notice(current, previous, previous_notice):
    return previous is None or current != previous or previous_notice != "success"


def notice_message(current):
    state = "RECUPERADO / CORRECTO" if current == "success" else "INCIDENCIA"
    message = EmailMessage()
    message["From"] = "SIHSALUS Terminología <" + os.environ["TERMINOLOGY_EMAIL_HOST_USER"] + ">"
    message["To"] = os.environ["TERMINOLOGY_MONITOR_RECIPIENT"]
    message["Subject"] = "[SIHSALUS Terminología] " + state
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain=os.environ["TERMINOLOGY_EMAIL_HOST_USER"].split("@")[-1])
    run_url = ("https://github.com/" + os.environ["GITHUB_REPOSITORY"] +
               "/actions/runs/" + os.environ["GITHUB_RUN_ID"])
    message.set_content(
        "Estado del monitoreo: " + state + "\n\n"
        "Portal: https://" + os.environ["TERMINOLOGY_HOST"] + "/\n"
        "Comprobaciones: web, API, base de datos, búsqueda, workers, Redis, "
        "inicio de sesión, certificados y autenticación SMTP.\n"
        "Detalle de esta ejecución: " + run_url + "\n\n"
        "Un resultado correcto no acredita la entrega en bandeja de entrada "
        "ni valida una importación clínica.\n"
        "Aviso automático solicitado para este grupo; no contiene datos de usuarios.\n")
    return message


def notify():
    current = os.environ["PROBE_RESULT"]
    if current not in ("success", "failure", "cancelled", "skipped"):
        raise ProbeFailure("Unexpected probe job result")
    previous, previous_notice = previous_result()
    if not needs_notice(current, previous, previous_notice):
        print("No state transition; no email sent.")
        return
    with smtp_connection() as client:
        refused = client.send_message(notice_message(current))
        if refused:
            raise RuntimeError("Alert recipient refused")
    print("Transition email accepted by SMTP for the configured group.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("probe", "notify"))
    parser.add_argument("--skip-smtp", action="store_true", help="Local HTTPS-only diagnostic; not used by the schedule")
    args = parser.parse_args()
    if args.command == "probe":
        return probe(args.skip_smtp)
    notify()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print("Monitor failed: " + type(error).__name__, file=sys.stderr)
        sys.exit(1)
