#!/usr/bin/env python3
"""Collect CI evidence, prepare a private environment, and inspect a running release."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
APPS = ('api', 'web', 'postgres', 'redis', 'elasticsearch')
SERVICES = dict(api='api', worker='api', importer='api', scheduler='api', web='web',
                db='postgres', redis='redis', es='elasticsearch', storage='storage')
RUN_URL = 'https://github.com/sihsalus/sihsalus-terminology/actions/runs/'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def image_ref(value, repository):
    require(isinstance(value, str) and re.fullmatch(re.escape(repository) + r'@sha256:[0-9a-f]{64}', value),
            'Expected an immutable image in ' + repository)
    return value


def validate(manifest):
    require(re.fullmatch(r'[0-9a-f]{40}', manifest['source_commit']), 'Invalid source commit')
    require(re.fullmatch(re.escape(RUN_URL) + r'[1-9][0-9]*', manifest['workflow_run']), 'Invalid workflow run')
    require(set(manifest['images']) == set(APPS), 'Expected all five runtime images')
    for app in APPS:
        image_ref(manifest['images'][app], 'ghcr.io/sihsalus/terminology-' + app)
    image_ref(manifest['storage'], 'rustfs/rustfs')
    return manifest


def scan(path, reference):
    report = json.loads(path.read_text())
    require(report.get('SchemaVersion') == 2 and report.get('ArtifactType') == 'container_image'
            and report.get('ArtifactName') == reference and report.get('Results'),
            'Missing or mismatched image scan: ' + path.name)
    require(not any(v['Severity'] in ('HIGH', 'CRITICAL')
                    for result in report['Results'] for v in (result.get('Vulnerabilities') or [])),
            'Image scan contains HIGH/CRITICAL findings')


def collect(artifacts, commit, run):
    images = {}
    for app in APPS:
        directory = artifacts / ('terminology-' + app + '-' + commit)
        images[app] = (directory / 'image-ref.txt').read_text().strip()
        scan(directory / 'security.json', images[app])
    storage_report = artifacts / 'terminology-service-security/storage.json'
    storage = json.loads(storage_report.read_text())['ArtifactName']
    scan(storage_report, storage)
    return validate(dict(source_commit=commit, workflow_run=RUN_URL + run,
                         images=images, storage=storage, storage_scan=RUN_URL + run,
                         runtime_security='HIGH/CRITICAL: 0 findings across all five images'))


def compose(env, *args):
    return subprocess.check_output(['docker', 'compose', '--env-file', str(env), '-f',
                                    str(ROOT / 'docker-compose.terminology.yml'), *args],
                                   cwd=ROOT, text=True, stderr=subprocess.PIPE, timeout=60)


def private_env(path):
    require(not path.is_symlink() and path.is_file() and path.stat().st_mode & 0o777 == 0o600,
            'Environment must be a regular file with mode 600')


def prepare(manifest, env, output):
    private_env(env)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    require(commit == manifest['source_commit'], 'Install the release source commit before preparing it')
    settings = {'TERMINOLOGY_SOURCE_SHA': manifest['source_commit']}
    settings.update({'TERMINOLOGY_' + app.upper() + '_IMAGE': manifest['images'][app] for app in APPS})
    lines = []
    for line in env.read_text().splitlines():
        match = re.match(r'\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=', line)
        if not match or match[1] not in settings:
            lines.append(line)
    lines.extend(key + '=' + value for key, value in settings.items())
    # Exclusive creation protects the installed environment and earlier candidates.
    with open(output, 'x', opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
        stream.write('\n'.join(lines) + '\n')
    try:
        model = json.loads(compose(output, 'config', '--format', 'json'))
        require(model['services']['storage']['image'] == manifest['storage'], 'Storage differs from the scanned release')
        for service, app in SERVICES.items():
            reference = manifest['storage'] if app == 'storage' else manifest['images'][app]
            require(model['services'][service]['image'] == reference,
                    'Compose image override differs from the release: ' + service)
    except Exception:
        output.unlink()
        raise


def verify(manifest, env):
    private_env(env)
    ids = compose(env, 'ps', '--all', '-q').splitlines()
    require(len(ids) == len(SERVICES), 'Expected nine runtime containers; inspect Compose status')
    items = json.loads(subprocess.check_output(['docker', 'inspect', *ids], text=True, timeout=30))
    result = {}
    for item in items:
        service = item['Config']['Labels']['com.docker.compose.service']
        require(service in SERVICES and service not in result, 'Unexpected or duplicate runtime service')
        app = SERVICES[service]
        reference = manifest['storage'] if app == 'storage' else manifest['images'][app]
        require(item['Config']['Image'] == reference, 'Running image differs: ' + service)
        if app != 'storage':
            require(item['Config']['Labels'].get('org.opencontainers.image.revision') == manifest['source_commit'],
                    'Running source revision differs: ' + service)
        state = item['State']
        require(state['Running'] and not state['OOMKilled'] and item['RestartCount'] == 0,
                'Stopped, restarted or OOM-killed service: ' + service)
        health = state.get('Health', {}).get('Status')
        require(health == 'healthy' if service in ('api', 'web', 'db', 'redis', 'es') else health in (None, 'healthy'),
                'Missing or unhealthy healthcheck: ' + service)
        result[service] = {'image': reference, 'health': health or 'running (no healthcheck)'}
    return dict(source_commit=manifest['source_commit'], services=result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('manifest', help='CI only: collect successful jobs from one run')
    build.add_argument('artifacts', type=Path)
    build.add_argument('--commit', required=True)
    build.add_argument('--run', required=True)
    for name in ('prepare', 'verify'):
        command = commands.add_parser(name)
        command.add_argument('manifest', type=Path)
        command.add_argument('env', type=Path)
        if name == 'prepare':
            command.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.command == 'manifest':
        print(json.dumps(collect(args.artifacts, args.commit, args.run), indent=2))
    else:
        manifest = validate(json.loads(args.manifest.read_text()))
        if args.command == 'prepare':
            prepare(manifest, args.env.absolute(), args.output.absolute())
            print('Private candidate prepared; installed configuration and services are unchanged.')
        else:
            print(json.dumps(verify(manifest, args.env), indent=2))


if __name__ == '__main__':
    os.umask(0o077)
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        # Compose errors may contain interpolated secrets; never echo process output.
        print('Release stopped: ' + (str(error) if isinstance(error, ValueError) else type(error).__name__), file=sys.stderr)
        sys.exit(1)
