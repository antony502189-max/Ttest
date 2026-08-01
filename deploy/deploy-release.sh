#!/usr/bin/env bash
set -euo pipefail

# Deploy a commit already reachable from origin/main. Run on the VPS as root.
[[ $# -eq 1 ]] || { echo "usage: $0 <main-commit-sha>" >&2; exit 64; }
SHA="$1"
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "a full 40-character SHA is required" >&2; exit 64; }
ROOT="${ROOT:-/srv/112233.es}"
REPO="$ROOT/repo"
RELEASES="$ROOT/releases"
CURRENT="$ROOT/current"
ENV_FILE="$ROOT/shared/production.env"
[[ -r "$ENV_FILE" ]] || { echo "missing $ENV_FILE" >&2; exit 65; }
[[ "$(stat -c %a "$ENV_FILE")" == "600" ]] || { echo "$ENV_FILE must have mode 600" >&2; exit 65; }
mkdir -p "$REPO" "$RELEASES" "$ROOT/backups"

if [[ ! -d "$REPO/.git" ]]; then
  git clone https://github.com/antony502189-max/Ttest.git "$REPO"
fi
git -C "$REPO" fetch origin --prune --tags
git -C "$REPO" merge-base --is-ancestor "$SHA" origin/main || { echo "$SHA is not reachable from origin/main" >&2; exit 65; }
release="$RELEASES/$SHA"
if [[ ! -e "$release/.git" ]]; then
  git -C "$REPO" worktree add --detach "$release" "$SHA"
fi
compose=(docker compose --env-file "$ENV_FILE" -f "$release/docker-compose.production.yml")
"${compose[@]}" config --quiet
old_sha="none"
[[ -L "$CURRENT" ]] && old_sha="$(basename "$(readlink -f "$CURRENT")")"
metadata="$ROOT/releases/$SHA.deploy-info"
failure_log="$ROOT/releases/$SHA.failed.log"

rollback_after_failure() {
  local exit_code=$?
  trap - ERR
  set +e
  "${compose[@]}" logs --no-color > "$failure_log" 2>&1
  if [[ "$old_sha" != "none" && -d "$RELEASES/$old_sha" ]]; then
    previous_compose=(docker compose --env-file "$ENV_FILE" -f "$RELEASES/$old_sha/docker-compose.production.yml")
    "${previous_compose[@]}" up -d --build backend mail-worker external-listings-worker frontend
    if "${previous_compose[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=3)"; then
      ln -sfn "$RELEASES/$old_sha" "$CURRENT"
    fi
  else
    "${compose[@]}" stop frontend backend mail-worker external-listings-worker
  fi
  printf 'status=failed\nfailed_at=%s\nfailed_log=%s\n' "$(date -u +%FT%TZ)" "$failure_log" >> "$metadata"
  exit "$exit_code"
}
trap rollback_after_failure ERR

printf 'old_sha=%s\nnew_sha=%s\nstatus=in_progress\ntimestamp=%s\n' "$old_sha" "$SHA" "$(date -u +%FT%TZ)" > "$metadata"
postgres_volume="ttest-production_postgres-data"
minio_volume="ttest-production_minio-data"
has_existing_postgres=0
has_existing_minio=0
docker volume inspect "$postgres_volume" >/dev/null 2>&1 && has_existing_postgres=1
docker volume inspect "$minio_volume" >/dev/null 2>&1 && has_existing_minio=1
"${compose[@]}" up -d postgres redis minio minio-init
backups="first_deploy:no_existing_persistent_data"
if (( has_existing_postgres )); then
  postgres_backup="$(COMPOSE_FILE="$release/docker-compose.production.yml" ENV_FILE="$ENV_FILE" BACKUP_DIR="$ROOT/backups" "$release/deploy/backup-postgres.sh")"
  backups="postgres=$postgres_backup"
fi
if (( has_existing_minio )); then
  minio_backup="$(COMPOSE_FILE="$release/docker-compose.production.yml" ENV_FILE="$ENV_FILE" BACKUP_DIR="$ROOT/backups" "$release/deploy/backup-minio.sh")"
  if [[ "$backups" == "first_deploy:"* ]]; then backups="minio=$minio_backup"; else backups="$backups minio=$minio_backup"; fi
fi
revision="$(${compose[@]} run --rm migrate alembic current 2>/dev/null || true)"
printf 'backups=%s\nrevision_before=%s\n' "$backups" "$revision" >> "$metadata"
"${compose[@]}" run --rm migrate
revision_after="$(${compose[@]} run --rm migrate alembic current 2>/dev/null || true)"
"${compose[@]}" up -d --build backend mail-worker external-listings-worker frontend
for _ in $(seq 1 30); do
  if "${compose[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=3)"; then break; fi
  sleep 2
done
"${compose[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=3)"
image_ids="$("${compose[@]}" images -q backend mail-worker external-listings-worker frontend | sort -u | paste -sd, -)"
ln -sfn "$release" "$CURRENT"
printf 'revision_after=%s\nimage_ids=%s\nstatus=success\n' "$revision_after" "$image_ids" >> "$metadata"
trap - ERR
printf 'deployed %s (previous: %s)\n' "$SHA" "$old_sha"
