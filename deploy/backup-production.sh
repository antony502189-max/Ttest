#!/usr/bin/env bash
set -euo pipefail

# Run both encrypted persistent-data backups. Neither child script deletes data.
ROOT="${ROOT:-/srv/112233.es}"
"$ROOT/current/deploy/backup-postgres.sh"
"$ROOT/current/deploy/backup-minio.sh"
