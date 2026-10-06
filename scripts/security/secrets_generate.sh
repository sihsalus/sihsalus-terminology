#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

OUTPUT_FILE="${1:-.env.terminology}"

if [ -e "$OUTPUT_FILE" ]; then
  echo "Refusing to overwrite $OUTPUT_FILE. Move it first if you intend to rotate credentials." >&2
  exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl is required" >&2
  exit 1
fi

umask 077

secret() {
  openssl rand -hex 24
}

cat > "$OUTPUT_FILE" <<EOF
# Private terminology configuration. Complete public deployment metadata below.
TERMINOLOGY_HOST=
TERMINOLOGY_API_HOST=
TERMINOLOGY_MACHINE_ID=
TERMINOLOGY_SOURCE_SHA=
TERMINOLOGY_API_IMAGE=
TERMINOLOGY_WEB_IMAGE=
TERMINOLOGY_POSTGRES_IMAGE=
TERMINOLOGY_REDIS_IMAGE=
TERMINOLOGY_ELASTICSEARCH_IMAGE=
TERMINOLOGY_BACKUP_KEEP=14
TERMINOLOGY_EMAIL_BACKEND=django.core.mail.backends.dummy.EmailBackend
TERMINOLOGY_EMAIL_HOST=smtp.gmail.com
TERMINOLOGY_EMAIL_PORT=587
TERMINOLOGY_EMAIL_HOST_USER=
TERMINOLOGY_EMAIL_HOST_PASSWORD=
TERMINOLOGY_DEFAULT_FROM_EMAIL=
TERMINOLOGY_COMMUNITY_EMAIL=
TERMINOLOGY_REPORTS_EMAIL=
TERMINOLOGY_ADMIN_EMAIL=
TERMINOLOGY_DB_PASSWORD=$(secret)
TERMINOLOGY_SECRET_KEY=$(secret)$(secret)
TERMINOLOGY_ADMIN_PASSWORD=$(secret)
TERMINOLOGY_ADMIN_TOKEN=$(openssl rand -hex 20)
TERMINOLOGY_STORAGE_ACCESS_KEY=$(openssl rand -hex 12)
TERMINOLOGY_STORAGE_SECRET_KEY=$(secret)
EOF
chmod 600 "$OUTPUT_FILE"
printf 'Created private terminology configuration: %s\n' "$OUTPUT_FILE"
