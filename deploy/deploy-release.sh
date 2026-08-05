#!/usr/bin/env bash
set -euo pipefail

# Deploy the exact current origin/main commit. Run on the VPS as root.
[[ $# -eq 1 ]] || { echo "usage: $0 <main-commit-sha>" >&2; exit 64; }
SHA="$1"
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "a full 40-character SHA is required" >&2; exit 64; }
ROOT="${ROOT:-/srv/112233.es}"
REPO="$ROOT/repo"
RELEASES="$ROOT/releases"
CURRENT="$ROOT/current"
ENV_FILE="$ROOT/shared/production.env"
LOCK_FILE="$ROOT/shared/release.lock"
[[ -r "$ENV_FILE" ]] || { echo "missing $ENV_FILE" >&2; exit 65; }
[[ "$(stat -c %a "$ENV_FILE")" == "600" ]] || { echo "$ENV_FILE must have mode 600" >&2; exit 65; }
command -v flock >/dev/null || { echo "flock is required for production release serialization" >&2; exit 69; }
exec 9>"$LOCK_FILE"
chmod 600 "$LOCK_FILE"
flock -n 9 || { echo "another production deploy or rollback is already running" >&2; exit 75; }
mkdir -p "$RELEASES" "$ROOT/backups"

if [[ ! -d "$REPO/.git" ]]; then
  git clone https://github.com/antony502189-max/Ttest.git "$REPO"
fi
git -C "$REPO" fetch origin --prune --tags
main_sha="$(git -C "$REPO" rev-parse origin/main)"
[[ "$SHA" == "$main_sha" ]] || {
  echo "$SHA is not the current origin/main commit ($main_sha); use rollback-release.sh for an older release" >&2
  exit 65
}

release="$RELEASES/$SHA"
if [[ ! -e "$release/.git" ]]; then
  git -C "$REPO" worktree add --detach "$release" "$SHA"
fi
compose=(docker compose --env-file "$ENV_FILE" -f "$release/docker-compose.production.yml")
"${compose[@]}" config --quiet

old_sha="none"
old_release=""
if [[ -L "$CURRENT" ]]; then
  old_release="$(readlink -f "$CURRENT")"
  [[ -f "$old_release/docker-compose.production.yml" ]] || {
    echo "current release has no production compose file: $old_release" >&2
    exit 65
  }
  old_sha="$(basename "$old_release")"
fi

postgres_volume="ttest-production_postgres-data"
minio_volume="ttest-production_minio-data"
has_existing_postgres=0
has_existing_minio=0
docker volume inspect "$postgres_volume" >/dev/null 2>&1 && has_existing_postgres=1
docker volume inspect "$minio_volume" >/dev/null 2>&1 && has_existing_minio=1
if [[ -z "$old_release" ]] && (( has_existing_postgres || has_existing_minio )); then
  echo "persistent production volumes exist but there is no current release; refusing to touch them without a known backup runtime" >&2
  exit 65
fi

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
    restored=0
    for _ in $(seq 1 30); do
      if "${previous_compose[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=3)"; then
        restored=1
        break
      fi
      sleep 2
    done
    if (( restored )); then
      ln -sfn "$RELEASES/$old_sha" "$CURRENT"
    else
      echo "automatic rollback failed readiness; current symlink was not advanced" >&2
    fi
  else
    "${compose[@]}" stop frontend backend mail-worker external-listings-worker
  fi
  printf 'status=failed\nfailed_at=%s\nfailed_log=%s\n' "$(date -u +%FT%TZ)" "$failure_log" >> "$metadata"
  exit "$exit_code"
}
trap rollback_after_failure ERR

printf 'old_sha=%s\nnew_sha=%s\nstatus=in_progress\ntimestamp=%s\n' "$old_sha" "$SHA" "$(date -u +%FT%TZ)" > "$metadata"

backups="first_deploy:no_existing_persistent_data"
revision="none"
if [[ -n "$old_release" ]]; then
  previous_compose=(docker compose --env-file "$ENV_FILE" -f "$old_release/docker-compose.production.yml")
  "${previous_compose[@]}" config --quiet

  # Quiesce every writer before the backup and migration boundary. The ERR
  # trap restores the previous application services if any later step fails.
  "${previous_compose[@]}" stop frontend backend mail-worker external-listings-worker

  previous_dependencies=()
  (( has_existing_postgres )) && previous_dependencies+=(postgres)
  if (( has_existing_minio )); then
    previous_dependencies+=(minio minio-init)
  fi
  if (( ${#previous_dependencies[@]} )); then
    "${previous_compose[@]}" up -d "${previous_dependencies[@]}"
  fi

  if (( has_existing_postgres )); then
    postgres_backup="$(COMPOSE_FILE="$old_release/docker-compose.production.yml" ENV_FILE="$ENV_FILE" BACKUP_DIR="$ROOT/backups" "$release/deploy/backup-postgres.sh")"
    backups="postgres=$postgres_backup"
    revision="$("${previous_compose[@]}" run --rm migrate alembic current 2>/dev/null || true)"
  fi
  if (( has_existing_minio )); then
    minio_backup="$(COMPOSE_FILE="$old_release/docker-compose.production.yml" ENV_FILE="$ENV_FILE" BACKUP_DIR="$ROOT/backups" "$release/deploy/backup-minio.sh")"
    if [[ "$backups" == "first_deploy:"* ]]; then backups="minio=$minio_backup"; else backups="$backups minio=$minio_backup"; fi
  fi
fi
printf 'backups=%s\nrevision_before=%s\nbackup_runtime_sha=%s\n' "$backups" "$revision" "$old_sha" >> "$metadata"

# Only after the old runtime has been quiesced and its persistent data backed
# up may the new release start dependency images or apply migrations.
"${compose[@]}" up -d postgres redis minio minio-init
"${compose[@]}" build migrate
"${compose[@]}" run --rm migrate
revision_after="$("${compose[@]}" run --rm migrate alembic current 2>/dev/null || true)"
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
