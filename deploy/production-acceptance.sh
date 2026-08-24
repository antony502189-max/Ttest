#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
BASE_DIR="${BASE_DIR:-$ROOT/shared/audit/production-acceptance}"
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
LIGHT_INTERVAL_SECONDS="${LIGHT_INTERVAL_SECONDS:-60}"
FULL_INTERVAL_SECONDS="${FULL_INTERVAL_SECONDS:-600}"
FULL_TIMEOUT_SECONDS="${FULL_TIMEOUT_SECONDS:-300}"
MAX_LOG_BYTES="${MAX_LOG_BYTES:-104857600}"

die() { echo "$*" >&2; exit 64; }
utc_now() { date -u +%FT%TZ; }
epoch_now() { date -u +%s; }
active_link() { printf '%s/active-run' "$BASE_DIR"; }
active_dir() { readlink -f "$(active_link)" 2>/dev/null || true; }
kv() { printf '%s=%s\n' "$1" "$2"; }

sanitize() {
  sed -E \
    -e 's/((PASSWORD|SECRET|TOKEN|COOKIE|AUTHORIZATION|DSN|DATABASE_URL|SMTP_[A-Z_]*|S3_[A-Z_]*|MINIO_[A-Z_]*|GOOGLE_[A-Z_]*|BACKUP_[A-Z_]*)(=|:)[[:space:]]*)[^[:space:]]+/\1[REDACTED]/Ig' \
    -e 's#(postgres(ql)?://)[^[:space:]]+#\1[REDACTED]#Ig' \
    | head -c 65536
}

env_value() {
  local key="$1" fallback="${2:-}" line value
  line="$(grep -m1 -E "^${key}=" "$ENV_FILE" || true)"
  if [[ -z "$line" ]]; then printf '%s' "$fallback"; return; fi
  value="${line#*=}"
  if [[ ${#value} -ge 2 && "$value" == \"*\" && "$value" == *\" ]]; then
    value="${value:1:${#value}-2}"
  elif [[ ${#value} -ge 2 && "$value" == \'*\' && "$value" == *\' ]]; then
    value="${value:1:${#value}-2}"
  fi
  printf '%s' "$value"
}

write_status() {
  local dir="$1" state="$2" detail="${3:-}"
  { kv STATE "$state"; kv UPDATED "$(utc_now)"; [[ -n "$detail" ]] && kv DETAIL "$detail"; } > "$dir/status"
}
value_from_status() { sed -n "s/^$2=//p" "$1/status" 2>/dev/null | tail -n 1; }
metadata_value() { sed -n "s/^$2=//p" "$1/metadata.txt" 2>/dev/null | tail -n 1; }

format_duration() {
  local total="$1" h m s
  (( total < 0 )) && total=0
  h=$((total / 3600)); m=$(((total % 3600) / 60)); s=$((total % 60))
  printf '%02d:%02d:%02d' "$h" "$m" "$s"
}

resource_pressure() {
  local cpu load available total free_pct disk_free
  cpu="$(nproc)"; load="$(awk '{print $1}' /proc/loadavg)"
  available="$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)"; total="$(awk '/MemTotal:/ {print $2}' /proc/meminfo)"
  disk_free="$(df -P "$ROOT" | awk 'NR==2 {gsub(/%/, "", $5); print 100-$5}')"
  free_pct=$(( available * 100 / total ))
  awk -v load="$load" -v cpu="$cpu" -v ram="$free_pct" -v disk="$disk_free" 'BEGIN { exit !(load >= cpu || ram < 15 || disk < 10) }'
}

light_check() {
  local dir="$1" domain sha http backend worker services load ram disk health line
  domain="$(env_value APP_DOMAIN)"; [[ "$domain" =~ ^[A-Za-z0-9.-]+$ ]] || domain="invalid"
  sha="$(git -C "$ROOT/current" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)"
  http="$(timeout 5 curl --silent --output /dev/null --write-out '%{http_code}' "https://$domain/" || true)"
  backend="$(timeout 15 docker compose --env-file "$ENV_FILE" -f "$ROOT/current/docker-compose.production.yml" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=3)" >/dev/null 2>&1 && echo OK || echo FAIL)"
  worker="$(timeout 15 docker compose --env-file "$ENV_FILE" -f "$ROOT/current/docker-compose.production.yml" exec -T external-listings-worker python -m app.workers.external_listings --healthcheck >/dev/null 2>&1 && echo OK || echo FAIL)"
  services="$(timeout 10 docker compose --env-file "$ENV_FILE" -f "$ROOT/current/docker-compose.production.yml" ps --status running -q | wc -l | tr -d ' ')"
  load="$(awk '{print $1}' /proc/loadavg)"
  ram="$(( 100 - $(awk '/MemAvailable:/ {a=$2} /MemTotal:/ {t=$2} END {print int(a*100/t)}' /proc/meminfo) ))"
  disk="$(df -P "$ROOT" | awk 'NR==2 {print $5}')"
  health=OK
  [[ "$http" =~ ^[23][0-9][0-9]$ ]] || health=FAIL
  [[ "$backend" == OK && "$worker" == OK && "$services" -ge 7 ]] || health=FAIL
  line="$(printf '%s | HEALTH=%s | HTTP=%s | BACKEND=%s | WORKER=%s | SERVICES=%s | DISK=%s | RAM=%s%% | LOAD=%s | SHA=%s' "$(utc_now)" "$health" "${http:-000}" "$backend" "$worker" "$services" "$disk" "$ram" "$load" "$sha")"
  printf '%s\n' "$line" >> "$dir/live.log"
  [[ "$health" == OK ]] || printf '%s\n' "$line" >> "$dir/errors.log"
  [[ "$health" == OK ]]
}

capture_import_snapshot() {
  local postgres_user postgres_db compose worker_row run_id
  postgres_user="$(env_value POSTGRES_USER ttest)"; postgres_db="$(env_value POSTGRES_DB ttest)"
  compose=(docker compose --env-file "$ENV_FILE" -f "$ROOT/current/docker-compose.production.yml")
  worker_row="$(timeout 30 "${compose[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 -U "$postgres_user" -d "$postgres_db" -At -F '|' -c "
    SELECT COALESCE(health, ''), COALESCE(heartbeat_at::text, ''), COALESCE(last_started_at::text, ''), COALESCE(last_finished_at::text, ''), COALESCE(last_success_at::text, ''), COALESCE(last_run_id, '')
    FROM external_worker_state WHERE id = 1;
  ")" || return 1
  [[ -n "$worker_row" ]] || return 1
  printf 'IMPORT_WORKER|%s\n' "$worker_row"; run_id="${worker_row##*|}"; [[ -n "$run_id" ]] || return 1
  timeout 30 "${compose[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 -v run_id="$run_id" -U "$postgres_user" -d "$postgres_db" -At -F '|' -c "
    SELECT 'IMPORT_SOURCE', source_name, result, COALESCE(discovery_complete::text, ''), COALESCE(discovery_pages::text, ''), COALESCE(jsonb_array_length(discovery_failed_pages), 0)::text,
           COALESCE(counters->>'discovered_urls', '0'), COALESCE(counters->>'fetched_details', '0'), COALESCE(counters->>'accepted_rooms', '0')
    FROM external_import_runs WHERE run_id = :'run_id' ORDER BY source_name;
  "
}

full_check() {
  local dir="$1" sequence="$2" sample tmp rc snapshot_rc sha result monitor_line
  sample="$(printf '%s/samples/%04d-%s.log' "$dir" "$sequence" "$(date -u +%Y%m%dT%H%M%SZ)")"; tmp="$(mktemp)"
  sha="$(git -C "$ROOT/current" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)"
  exec 9>"$BASE_DIR/full-check.lock"
  if ! flock -n 9; then
    { kv TIMESTAMP "$(utc_now)"; kv RELEASE_SHA "$sha"; kv RESULT SKIPPED_PREVIOUS_CHECK_RUNNING; } > "$sample"
    printf '%s | RESULT=SKIPPED_PREVIOUS_CHECK_RUNNING\n' "$(utc_now)" >> "$dir/monitor.log"; rm -f "$tmp"; return 0
  fi
  if resource_pressure || ! tail -n 1 "$dir/live.log" | grep -q 'HEALTH=OK'; then
    { kv TIMESTAMP "$(utc_now)"; kv RELEASE_SHA "$sha"; kv RESULT SKIPPED_RESOURCE_PRESSURE; } > "$sample"
    printf '%s | RESULT=SKIPPED_RESOURCE_PRESSURE\n' "$(utc_now)" >> "$dir/monitor.log"
    rm -f "$tmp"; flock -u 9; exec 9>&-; return 0
  fi
  set +e
  if command -v ionice >/dev/null; then
    nice -n 10 ionice -c2 -n7 timeout --foreground "$FULL_TIMEOUT_SECONDS" bash "$ROOT/current/deploy/production-monitor-check.sh" >"$tmp" 2>&1
  else
    nice -n 10 timeout --foreground "$FULL_TIMEOUT_SECONDS" bash "$ROOT/current/deploy/production-monitor-check.sh" >"$tmp" 2>&1
  fi
  rc=$?; set -e
  case "$rc" in 0) result=PASS ;; 2) result=WARNING ;; 75) result=MAINTENANCE ;; *) result=FAIL ;; esac
  {
    kv TIMESTAMP "$(utc_now)"; kv RELEASE_SHA "$sha"; kv MONITOR_RETURN_CODE "$rc"; kv RESULT "$result"; sanitize < "$tmp"
    printf '\nIMPORT_SNAPSHOT_BEGIN\n'; set +e; capture_import_snapshot | sanitize; snapshot_rc=${PIPESTATUS[0]}; set -e
    kv IMPORT_SNAPSHOT_RETURN_CODE "$snapshot_rc"; printf 'IMPORT_SNAPSHOT_END\n'
  } > "$sample"
  rm -f "$tmp"
  snapshot_rc="$(sed -n 's/^IMPORT_SNAPSHOT_RETURN_CODE=//p' "$sample" | tail -n 1)"
  if [[ "$result" != MAINTENANCE && "$snapshot_rc" != 0 ]]; then result=FAIL; sed -i 's/^RESULT=.*/RESULT=FAIL/' "$sample"; fi
  monitor_line="$(printf '%s | RESULT=%s | MONITOR_RC=%s | SNAPSHOT_RC=%s | SHA=%s' "$(utc_now)" "$result" "$rc" "$snapshot_rc" "$sha")"
  printf '%s\n' "$monitor_line" >> "$dir/monitor.log"
  [[ "$result" == PASS || "$result" == WARNING || "$result" == MAINTENANCE ]] || printf '%s\n' "$monitor_line" >> "$dir/errors.log"
  flock -u 9; exec 9>&-; [[ "$result" != FAIL ]]
}

make_report() {
  local dir="$1" lifecycle="${2:-UNKNOWN}" start expected expected_epoch sha current final total_full full_pass full_warn full_fail skipped_pressure skipped_running maintenance snapshot_fail http_fail backend_fail worker_fail disk_warn import_fail threshold_fail first_failure last_failure duration cpu ram report_epoch completed
  start="$(metadata_value "$dir" START_TIME)"; expected="$(metadata_value "$dir" EXPECTED_END_TIME)"; expected_epoch="$(metadata_value "$dir" END_EPOCH)"
  sha="$(metadata_value "$dir" RELEASE_SHA)"; duration="$(metadata_value "$dir" DURATION_HOURS)"; cpu="$(metadata_value "$dir" CPU_COUNT)"; ram="$(metadata_value "$dir" TOTAL_RAM)"
  current="$(git -C "$ROOT/current" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)"; report_epoch="$(epoch_now)"; completed=NO
  [[ "$lifecycle" == FINISHED && "$expected_epoch" =~ ^[0-9]+$ && "$report_epoch" -ge "$expected_epoch" ]] && completed=YES
  total_full="$(find "$dir/samples" -maxdepth 1 -type f -name '*.log' | wc -l | tr -d ' ')"
  full_pass="$(grep -rl '^RESULT=PASS$' "$dir/samples" 2>/dev/null | wc -l | tr -d ' ' || true)"; full_warn="$(grep -rl '^RESULT=WARNING$' "$dir/samples" 2>/dev/null | wc -l | tr -d ' ' || true)"; full_fail="$(grep -rl '^RESULT=FAIL$' "$dir/samples" 2>/dev/null | wc -l | tr -d ' ' || true)"
  skipped_pressure="$(grep -rl '^RESULT=SKIPPED_RESOURCE_PRESSURE$' "$dir/samples" 2>/dev/null | wc -l | tr -d ' ' || true)"; skipped_running="$(grep -rl '^RESULT=SKIPPED_PREVIOUS_CHECK_RUNNING$' "$dir/samples" 2>/dev/null | wc -l | tr -d ' ' || true)"; maintenance="$(grep -rl '^RESULT=MAINTENANCE$' "$dir/samples" 2>/dev/null | wc -l | tr -d ' ' || true)"
  snapshot_fail="$(grep -rl '^IMPORT_SNAPSHOT_RETURN_CODE=[^0]' "$dir/samples" 2>/dev/null | wc -l | tr -d ' ' || true)"
  http_fail="$(grep -Ec 'HTTP=(000|4[0-9][0-9]|5[0-9][0-9])' "$dir/live.log" 2>/dev/null || true)"; backend_fail="$(grep -c 'BACKEND=FAIL' "$dir/live.log" 2>/dev/null || true)"; worker_fail="$(grep -c 'WORKER=FAIL' "$dir/live.log" 2>/dev/null || true)"
  disk_warn="$(grep -Rci 'disk usage\|/var/lib/docker=.*%\|/srv/112233.es/.*=%' "$dir/samples" 2>/dev/null || true)"; import_fail="$(grep -Rh '^IMPORT_SOURCE|' "$dir/samples" 2>/dev/null | awk -F'|' '$3 != "success" {n++} END {print n+0}')"; threshold_fail="$(grep -Rci 'healthy sources.*required\|healthy-source threshold' "$dir/samples" 2>/dev/null || true)"
  first_failure="$(grep 'HEALTH=FAIL' "$dir/live.log" 2>/dev/null | head -n1 || true)"; last_failure="$(grep 'HEALTH=FAIL' "$dir/live.log" 2>/dev/null | tail -n1 || true)"

  final=FAIL
  if [[ "$completed" == YES && "$full_fail" == 0 && "$snapshot_fail" == 0 && "$http_fail" == 0 && "$backend_fail" == 0 && "$worker_fail" == 0 && "$current" == "$sha" ]]; then
    final=PASS
    if [[ "$full_warn" != 0 || "$skipped_pressure" != 0 || "$skipped_running" != 0 || "$maintenance" != 0 ]]; then final=PASS_WITH_WARNINGS; fi
  fi
  {
    printf '# Production acceptance report\n\n'
    kv START "$start"; kv END "$(utc_now)"; kv EXPECTED_END "$expected"; kv DURATION_HOURS "$duration"; kv LIFECYCLE_STATE "$lifecycle"; kv RUN_COMPLETED "$completed"
    kv RELEASE_SHA "$sha"; kv RELEASE_CHANGED "$([[ "$current" == "$sha" ]] && echo NO || echo YES)"; kv CPU_COUNT "$cpu"; kv TOTAL_RAM "$ram"; kv LIGHT_INTERVAL "$LIGHT_INTERVAL_SECONDS"; kv FULL_INTERVAL "$FULL_INTERVAL_SECONDS"
    kv TOTAL_LIGHT_CHECKS "$(wc -l < "$dir/live.log" 2>/dev/null || echo 0)"; kv TOTAL_FULL_CHECKS "$total_full"; kv PASSED_FULL_CHECKS "$full_pass"; kv WARNING_FULL_CHECKS "$full_warn"; kv FAILED_FULL_CHECKS "$full_fail"
    kv SKIPPED_RESOURCE_PRESSURE "$skipped_pressure"; kv SKIPPED_PREVIOUS_CHECK_RUNNING "$skipped_running"; kv MAINTENANCE_SAMPLES "$maintenance"; kv IMPORT_SNAPSHOT_FAILURES "$snapshot_fail"
    kv HTTP_FAILURES "$http_fail"; kv BACKEND_FAILURES "$backend_fail"; kv WORKER_FAILURES "$worker_fail"; kv DISK_WARNINGS "$disk_warn"; kv IMPORT_NON_SUCCESS_SOURCE_ROWS "$import_fail"; kv THRESHOLD_FAILURES "$threshold_fail"
    kv FIRST_FAILURE "${first_failure:-NONE}"; kv LAST_FAILURE "${last_failure:-NONE}"; kv FINAL_STATUS "$final"
  } > "$dir/final-report.md"
}

run_monitor() {
  local dir="$1" duration_seconds="$2" start end next_light next_full sequence=0 exit_state=FINISHED current_log_bytes
  start="$(epoch_now)"; end=$((start + duration_seconds)); next_light="$start"; next_full="$start"
  trap 'exit_state=STOPPED; exit 0' TERM INT
  trap 'make_report "$dir" "$exit_state"; write_status "$dir" "$exit_state"' EXIT
  write_status "$dir" RUNNING
  while (( $(epoch_now) < end )); do
    current_log_bytes="$(stat -c%s "$dir/live.log" "$dir/monitor.log" "$dir/errors.log" | awk '{t += $1} END {print t}')"
    if (( current_log_bytes >= MAX_LOG_BYTES )); then exit_state=FAILED; printf '%s | HEALTH=FAIL | REASON=LOG_LIMIT\n' "$(utc_now)" >> "$dir/live.log"; break; fi
    if (( $(epoch_now) >= next_light )); then light_check "$dir" || true; next_light=$((next_light + LIGHT_INTERVAL_SECONDS)); fi
    if (( $(epoch_now) >= next_full )); then sequence=$((sequence + 1)); full_check "$dir" "$sequence" || true; next_full=$((next_full + FULL_INTERVAL_SECONDS)); fi
    sleep 1
  done
}

start() {
  local requested="$1" hours seconds run_id dir unit cpu ram swap disk_total disk_free load sha start_epoch end_epoch
  if [[ "$requested" == burn-in ]]; then hours="0.1667"; seconds=600; else hours="$requested"; [[ "$hours" =~ ^[1-9][0-9]*$ ]] || die "duration hours must be a positive integer"; seconds=$((hours * 3600)); fi
  [[ -r "$ENV_FILE" ]] || die "production environment file is not readable"; command -v systemd-run >/dev/null || die "systemd-run is required"; command -v flock >/dev/null || die "flock is required"
  mkdir -p "$BASE_DIR"; chmod 700 "$BASE_DIR"
  [[ ! -e "$(active_link)" || "$(value_from_status "$(active_dir)" STATE)" != RUNNING ]] || die "an acceptance run is already active"
  run_id="production-acceptance-$(date -u +%Y%m%d-%H%M%S)"; dir="$BASE_DIR/$run_id"; mkdir -p "$dir/samples"; chmod 700 "$dir" "$dir/samples"
  cpu="$(nproc)"; ram="$(free -h | awk '/^Mem:/ {print $2}')"; swap="$(free -h | awk '/^Swap:/ {print $2}')"; disk_total="$(df -h "$ROOT" | awk 'NR==2 {print $2}')"; disk_free="$(df -h "$ROOT" | awk 'NR==2 {print $4}')"; load="$(awk '{print $1}' /proc/loadavg)"
  sha="$(git -C "$ROOT/current" rev-parse --short=12 HEAD)"; start_epoch="$(epoch_now)"; end_epoch=$((start_epoch + seconds))
  {
    kv RUN_ID "$run_id"; kv START_TIME "$(utc_now)"; kv START_EPOCH "$start_epoch"; kv EXPECTED_END_TIME "$(date -u -d "@$end_epoch" +%FT%TZ)"; kv END_EPOCH "$end_epoch"; kv DURATION_HOURS "$hours"
    kv LIGHT_INTERVAL_SECONDS "$LIGHT_INTERVAL_SECONDS"; kv FULL_INTERVAL_SECONDS "$FULL_INTERVAL_SECONDS"; kv RELEASE_SHA "$sha"; kv RELEASE_PATH "$(readlink -f "$ROOT/current")"; kv HOSTNAME "$(hostname)"; kv CPU_COUNT "$cpu"; kv TOTAL_RAM "$ram"; kv SWAP "$swap"; kv DISK_TOTAL "$disk_total"; kv DISK_FREE_AT_START "$disk_free"; kv BASELINE_LOAD "$load"
  } > "$dir/metadata.txt"
  : > "$dir/live.log"; : > "$dir/monitor.log"; : > "$dir/errors.log"; chmod 600 "$dir"/*.txt "$dir"/*.log; ln -sfn "$dir" "$(active_link)"
  unit="ttest-production-acceptance-${run_id#production-acceptance-}"
  systemd-run --quiet --unit="$unit" --property=Type=exec --property=Nice=10 --property=IOSchedulingClass=best-effort --property=IOSchedulingPriority=7 --property=CPUWeight=1 --property=IOWeight=1 \
    --setenv="ROOT=$ROOT" --setenv="ENV_FILE=$ENV_FILE" --setenv="BASE_DIR=$BASE_DIR" --setenv="LIGHT_INTERVAL_SECONDS=$LIGHT_INTERVAL_SECONDS" --setenv="FULL_INTERVAL_SECONDS=$FULL_INTERVAL_SECONDS" --setenv="FULL_TIMEOUT_SECONDS=$FULL_TIMEOUT_SECONDS" --setenv="MAX_LOG_BYTES=$MAX_LOG_BYTES" \
    /bin/bash "$SCRIPT_PATH" _run "$dir" "$seconds"
  printf 'RUN_ID=%s\nUNIT=%s\nEVIDENCE_DIR=%s\n' "$run_id" "$unit" "$dir"
}

status() {
  local dir unit unit_state now start_epoch end_epoch elapsed remaining
  dir="$(active_dir)"; [[ -n "$dir" && -d "$dir" ]] || die "no acceptance run exists"; unit="ttest-production-acceptance-${dir##*production-acceptance-}"; unit_state="$(systemctl is-active "$unit" 2>/dev/null || true)"
  now="$(epoch_now)"; start_epoch="$(metadata_value "$dir" START_EPOCH)"; end_epoch="$(metadata_value "$dir" END_EPOCH)"; elapsed=$((now - start_epoch)); remaining=$((end_epoch - now)); (( remaining < 0 )) && remaining=0
  cat "$dir/status"; printf 'RUN_ID=%s\nUNIT=%s\nUNIT_STATE=%s\nELAPSED=%s\nREMAINING=%s\nEVIDENCE_DIR=%s\n' "$(basename "$dir")" "$unit" "${unit_state:-unknown}" "$(format_duration "$elapsed")" "$(format_duration "$remaining")" "$dir"
  tail -n 1 "$dir/live.log" 2>/dev/null || true; tail -n 1 "$dir/monitor.log" 2>/dev/null || true
}

follow() { local dir; dir="$(active_dir)"; [[ -n "$dir" ]] || die "no acceptance run exists"; tail -F "$dir/live.log"; }
stop() { local dir unit; dir="$(active_dir)"; [[ -n "$dir" ]] || die "no acceptance run exists"; unit="ttest-production-acceptance-${dir##*production-acceptance-}"; systemctl stop "$unit"; }
report() {
  local dir state
  dir="$(active_dir)"; [[ -n "$dir" ]] || die "no acceptance run exists"
  if [[ ! -f "$dir/final-report.md" ]]; then state="$(value_from_status "$dir" STATE)"; [[ "$state" != RUNNING ]] || die "acceptance run is still active; use status or follow"; make_report "$dir" "$state"; fi
  cat "$dir/final-report.md"
}

case "${1:-}" in
  start) start "${2:-24}" ;;
  burn-in) start burn-in ;;
  status) status ;;
  follow) follow ;;
  stop) stop ;;
  report) report ;;
  _run) run_monitor "$2" "$3" ;;
  *) die "usage: $0 {start [hours]|burn-in|status|follow|stop|report}" ;;
esac
