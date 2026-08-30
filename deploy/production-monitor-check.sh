#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/current/docker-compose.production.yml}"
LOCK_FILE="${LOCK_FILE:-$ROOT/shared/release.lock}"
DISK_WARNING_PERCENT="${DISK_WARNING_PERCENT:-70}"
DISK_CRITICAL_PERCENT="${DISK_CRITICAL_PERCENT:-85}"

maintenance() {
  echo "MAINTENANCE: release operation lock is held"
  exit 75
}

release_in_progress() {
  local lock_fd
  [[ -e "$LOCK_FILE" ]] || return 1
  exec {lock_fd}<"$LOCK_FILE" || return 1
  if flock -n "$lock_fd"; then
    flock -u "$lock_fd"
    exec {lock_fd}<&-
    return 1
  fi
  exec {lock_fd}<&-
  return 0
}

critical() {
  release_in_progress && maintenance
  printf 'CRITICAL: %s\n' "$*" >&2
  exit 1
}

env_value() {
  local key="$1"
  local fallback="${2:-}"
  local line value
  line="$(grep -m1 -E "^${key}=" "$ENV_FILE" || true)"
  if [[ -z "$line" ]]; then
    printf '%s' "$fallback"
    return
  fi
  value="${line#*=}"
  if [[ ${#value} -ge 2 && "$value" == \"*\" && "$value" == *\" ]]; then
    value="${value:1:${#value}-2}"
  elif [[ ${#value} -ge 2 && "$value" == \'*\' && "$value" == *\' ]]; then
    value="${value:1:${#value}-2}"
  fi
  printf '%s' "$value"
}

require_uint() {
  local name="$1"
  local value="$2"
  [[ "$value" =~ ^[0-9]+$ ]] || critical "$name must be an unsigned integer"
}

require_bool() {
  local name="$1"
  local value="$2"
  [[ "$value" == "0" || "$value" == "1" ]] || critical "$name must be 0 or 1"
}

[[ -r "$ENV_FILE" ]] || critical "production env is not readable: $ENV_FILE"
[[ -r "$COMPOSE_FILE" ]] || critical "production compose file is not readable: $COMPOSE_FILE"

require_uint DISK_WARNING_PERCENT "$DISK_WARNING_PERCENT"
require_uint DISK_CRITICAL_PERCENT "$DISK_CRITICAL_PERCENT"
(( DISK_WARNING_PERCENT < DISK_CRITICAL_PERCENT )) || critical "disk warning threshold must be below critical threshold"
(( DISK_CRITICAL_PERCENT <= 100 )) || critical "disk critical threshold must be <= 100"

command -v flock >/dev/null || critical "flock is required for release-lock inspection"

# Never hold the release lock for the duration of a monitoring run. A monitor
# must not make a real deploy/rollback/backup/restore fail its non-blocking
# exclusive lock acquisition. Re-check on critical paths and before verdict to
# suppress transient failures if a release operation starts concurrently.
release_in_progress && maintenance

compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

check_service() {
  local service="$1"
  local require_health="$2"
  local container_id runtime state health
  container_id="$("${compose[@]}" ps -q "$service")"
  [[ -n "$container_id" ]] || critical "$service container is missing"
  runtime="$(docker inspect --format '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id")"
  IFS='|' read -r state health <<<"$runtime"
  [[ "$state" == "running" ]] || critical "$service state is $state"
  if [[ "$require_health" == "1" && "$health" != "healthy" ]]; then
    critical "$service health is $health"
  fi
}

# Verify the whole serving/data path, not only the importer. Frontend currently
# has no container healthcheck, so its running state is the fail-closed signal;
# all other long-lived production services must report healthy.
for service in postgres redis minio backend mail-worker external-listings-worker; do
  check_service "$service" 1
done
check_service frontend 0

worker_id="$("${compose[@]}" ps -q external-listings-worker)"
worker_runtime="$(docker inspect --format '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$worker_id")"
IFS='|' read -r worker_state worker_health <<<"$worker_runtime"

postgres_user="$(env_value POSTGRES_USER ttest)"
postgres_db="$(env_value POSTGRES_DB ttest)"
stale_after="$(env_value EXTERNAL_WORKER_STALE_AFTER_SECONDS 300)"
import_interval="$(env_value EXTERNAL_IMPORT_INTERVAL_SECONDS 7200)"
required_sources="$(env_value EXTERNAL_IMPORT_MIN_HEALTHY_SOURCES 3)"
configured_sources="$(env_value EXTERNAL_IMPORT_SOURCES 'fotocasa,pisocompartido,pisos,alquilerdocentecanarias,flatio')"

require_uint EXTERNAL_WORKER_STALE_AFTER_SECONDS "$stale_after"
require_uint EXTERNAL_IMPORT_INTERVAL_SECONDS "$import_interval"
require_uint EXTERNAL_IMPORT_MIN_HEALTHY_SOURCES "$required_sources"
(( import_interval > 0 )) || critical "EXTERNAL_IMPORT_INTERVAL_SECONDS must be positive"

configured_count=0
IFS=',' read -ra source_names <<<"$configured_sources"
for source_name in "${source_names[@]}"; do
  source_name="${source_name#"${source_name%%[![:space:]]*}"}"
  source_name="${source_name%"${source_name##*[![:space:]]}"}"
  [[ -n "$source_name" ]] && ((configured_count += 1))
done
(( configured_count > 0 )) || critical "EXTERNAL_IMPORT_SOURCES does not contain any source"
(( required_sources <= configured_count )) || critical "healthy-source threshold exceeds configured source count"

state_row="$(
  "${compose[@]}" exec -T postgres psql \
    -v ON_ERROR_STOP=1 \
    -U "$postgres_user" \
    -d "$postgres_db" \
    -At -F '|' \
    -c "
      SELECT
        health,
        COALESCE(FLOOR(EXTRACT(EPOCH FROM (now() - heartbeat_at)))::bigint, -1),
        COALESCE(FLOOR(EXTRACT(EPOCH FROM (now() - last_success_at)))::bigint, -1)
      FROM external_worker_state
      WHERE id = 1;
    "
)"
[[ -n "$state_row" ]] || critical "external worker state row is missing"

IFS='|' read -r db_health heartbeat_age last_success_age <<<"$state_row"
require_uint heartbeat_age "${heartbeat_age#-}"
require_uint last_success_age "${last_success_age#-}"
if (( heartbeat_age < 0 )); then
  critical "external worker heartbeat is missing"
fi
if (( heartbeat_age > stale_after )); then
  critical "external worker heartbeat is stale (${heartbeat_age}s > ${stale_after}s)"
fi
case "$db_health" in
  healthy|running) ;;
  *) critical "external worker database health is $db_health" ;;
esac

cycle_row="$(
  "${compose[@]}" exec -T postgres psql \
    -v ON_ERROR_STOP=1 \
    -U "$postgres_user" \
    -d "$postgres_db" \
    -At -F '|' \
    -c "
      WITH completed_cycles AS (
        SELECT
          run_id,
          MAX(finished_at) AS finished_at,
          COUNT(DISTINCT source_name) AS source_runs,
          COUNT(DISTINCT source_name) FILTER (
            WHERE result = 'success'
              AND discovery_complete IS TRUE
              AND COALESCE((counters->>'discovered_urls')::int, 0) > 0
              AND COALESCE((counters->>'fetched_details')::int, 0) > 0
              AND COALESCE((counters->>'accepted_rooms')::int, 0) > 0
          ) AS healthy_sources
        FROM external_import_runs
        WHERE finished_at IS NOT NULL
        GROUP BY run_id
        HAVING COUNT(DISTINCT source_name) >= ${configured_count}
      )
      SELECT
        run_id,
        healthy_sources,
        GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (now() - finished_at)))::bigint)
      FROM completed_cycles
      ORDER BY finished_at DESC
      LIMIT 1;
    "
)"
[[ -n "$cycle_row" ]] || critical "no complete external import cycle is available"

IFS='|' read -r last_run_id healthy_sources cycle_age <<<"$cycle_row"
require_uint healthy_sources "$healthy_sources"
require_uint cycle_age "$cycle_age"
if (( healthy_sources < required_sources )); then
  critical "latest complete import cycle has ${healthy_sources} healthy sources; ${required_sources} required"
fi

source_degraded=0
if (( healthy_sources < configured_count )); then
  source_degraded=1
fi

# An idle healthy worker must have completed a useful full cycle recently.
# While a fresh `running` heartbeat exists, do not page merely because the
# previous cycle crossed the normal schedule interval: the current cycle may
# legitimately still be processing source details/images.
max_idle_cycle_age=$((import_interval + stale_after))
if [[ "$db_health" == "healthy" ]] && (( cycle_age > max_idle_cycle_age )); then
  critical "latest complete import cycle is stale (${cycle_age}s > ${max_idle_cycle_age}s)"
fi
if [[ "$db_health" == "healthy" ]] && (( last_success_age < 0 )); then
  critical "external worker has no recorded successful cycle"
fi

warnings=()
criticals=()
if (( source_degraded )); then
  warnings+=("external_sources=${healthy_sources}/${configured_count} useful in latest complete cycle")
fi
check_disk() {
  local path="$1"
  local usage
  [[ -e "$path" ]] || return 0
  usage="$(df -P "$path" | awk 'NR == 2 {gsub(/%/, "", $5); print $5}')"
  require_uint "disk usage for $path" "$usage"
  if (( usage >= DISK_CRITICAL_PERCENT )); then
    criticals+=("$path=${usage}%")
  elif (( usage >= DISK_WARNING_PERCENT )); then
    warnings+=("$path=${usage}%")
  fi
}

check_disk "$ROOT/releases"
check_disk "$ROOT/backups"
check_disk /var/lib/docker

if (( ${#criticals[@]} > 0 )); then
  critical "disk usage at or above ${DISK_CRITICAL_PERCENT}%: ${criticals[*]}"
fi

now_epoch="$(date -u +%s)"
require_uint current_epoch "$now_epoch"

scheduled_backups_required="$(env_value SCHEDULED_BACKUPS_REQUIRED 0)"
backup_max_age="$(env_value BACKUP_MAX_AGE_SECONDS 129600)"
require_bool SCHEDULED_BACKUPS_REQUIRED "$scheduled_backups_required"
require_uint BACKUP_MAX_AGE_SECONDS "$backup_max_age"

newest_backup_age() {
  local pattern="$1"
  local label="$2"
  local newest mtime age
  newest="$(find "$ROOT/backups" -maxdepth 1 -type f -name "$pattern" -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2-)"
  [[ -n "$newest" ]] || critical "$label backup is missing"
  [[ -f "$newest.hmac" ]] || critical "$label backup authentication file is missing: ${newest##*/}.hmac"
  mtime="$(stat -c %Y "$newest")"
  require_uint "$label backup mtime" "$mtime"
  age=$((now_epoch - mtime))
  (( age >= 0 )) || age=0
  if (( age > backup_max_age )); then
    critical "$label backup is stale (${age}s > ${backup_max_age}s)"
  fi
}

if [[ "$scheduled_backups_required" == "1" ]]; then
  newest_backup_age 'postgres-*.dump.enc' PostgreSQL
  newest_backup_age 'minio-*.tar.enc' MinIO
fi

offsite_required="$(env_value OFFSITE_BACKUP_REQUIRED 0)"
offsite_max_age="$(env_value OFFSITE_BACKUP_MAX_AGE_SECONDS 129600)"
require_bool OFFSITE_BACKUP_REQUIRED "$offsite_required"
require_uint OFFSITE_BACKUP_MAX_AGE_SECONDS "$offsite_max_age"
if [[ "$offsite_required" == "1" ]]; then
  offsite_status="$ROOT/shared/offsite-backup.status"
  [[ -r "$offsite_status" ]] || critical "off-site backup success status is missing"
  offsite_epoch="$(sed -n 's/^completed_at_epoch=//p' "$offsite_status" | tail -n 1)"
  require_uint offsite_completed_at_epoch "$offsite_epoch"
  offsite_age=$((now_epoch - offsite_epoch))
  (( offsite_age >= 0 )) || offsite_age=0
  if (( offsite_age > offsite_max_age )); then
    critical "off-site backup replication is stale (${offsite_age}s > ${offsite_max_age}s)"
  fi
fi

restore_drill_required="$(env_value OFFSITE_RESTORE_DRILL_REQUIRED 0)"
restore_drill_max_age="$(env_value OFFSITE_RESTORE_DRILL_MAX_AGE_SECONDS 3456000)"
require_bool OFFSITE_RESTORE_DRILL_REQUIRED "$restore_drill_required"
require_uint OFFSITE_RESTORE_DRILL_MAX_AGE_SECONDS "$restore_drill_max_age"
if [[ "$restore_drill_required" == "1" ]]; then
  drill_status="$ROOT/shared/offsite-restore-drill.status"
  [[ -r "$drill_status" ]] || critical "off-site restore drill status is missing"
  drill_epoch="$(sed -n 's/^completed_at_epoch=//p' "$drill_status" | tail -n 1)"
  require_uint restore_drill_completed_at_epoch "$drill_epoch"
  drill_age=$((now_epoch - drill_epoch))
  (( drill_age >= 0 )) || drill_age=0
  if (( drill_age > restore_drill_max_age )); then
    critical "off-site restore drill is stale (${drill_age}s > ${restore_drill_max_age}s)"
  fi
fi

release_in_progress && maintenance

summary="services=healthy, worker=${db_health}, heartbeat_age=${heartbeat_age}s, healthy_sources=${healthy_sources}/${required_sources}, cycle_age=${cycle_age}s, run_id=${last_run_id}"
if (( ${#warnings[@]} > 0 )); then
  printf 'WARNING: %s; %s\n' "$summary" "${warnings[*]}" >&2
  exit 2
fi

printf 'OK: %s\n' "$summary"
