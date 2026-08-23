#!/usr/bin/env bash
# Autonomous, low-overhead production acceptance monitoring.  Runtime evidence
# is intentionally kept outside Git under shared/audit.
set -euo pipefail
umask 077

ROOT="${ROOT:-/srv/112233.es}"
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
  # Never persist likely credentials if an underlying command logs one.
  sed -E \
    -e 's/((PASSWORD|SECRET|TOKEN|COOKIE|AUTHORIZATION|DSN|DATABASE_URL|SMTP_[A-Z_]*|S3_[A-Z_]*|MINIO_[A-Z_]*|GOOGLE_[A-Z_]*|BACKUP_[A-Z_]*)(=|:)[[:space:]]*)[^[:space:]]+/\1[REDACTED]/Ig' \
    -e 's#(postgres(ql)?://)[^[:space:]]+#\1[REDACTED]#Ig' \
    | head -c 65536
}

write_status() {
  local dir="$1" state="$2" detail="${3:-}"
  {
    kv STATE "$state"
    kv UPDATED "$(utc_now)"
    [[ -n "$detail" ]] && kv DETAIL "$detail"
  } > "$dir/status"
}

value_from_status() { sed -n "s/^$2=//p" "$1/status" 2>/dev/null | tail -n 1; }

resource_state() {
  local cpu load available total free_pct disk_free
  cpu="$(nproc)"
  load="$(awk '{print $1}' /proc/loadavg)"
  available="$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)"
  total="$(awk '/MemTotal:/ {print $2}' /proc/meminfo)"
  disk_free="$(df -P "$ROOT" | awk 'NR==2 {print 100-$5}')"
  free_pct=$(( available * 100 / total ))
  awk -v load="$load" -v cpu="$cpu" -v ram="$free_pct" -v disk="$disk_free" 'BEGIN { exit !(load >= cpu || ram < 15 || disk < 10) }'
}

light_check() {
  local dir="$1" domain sha http backend worker services load ram disk health
  domain="$(sed -n 's/^APP_DOMAIN=//p' "$ROOT/shared/production.env" | tail -n 1)"
  sha="$(git -C "$ROOT/current" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)"
  http="$(timeout 5 curl --silent --output /dev/null --write-out '%{http_code}' "https://$domain/" || true)"
  backend="$(timeout 15 docker compose --env-file "$ROOT/shared/production.env" -f "$ROOT/current/docker-compose.production.yml" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=3)" >/dev/null 2>&1 && echo OK || echo FAIL)"
  worker="$(timeout 15 docker compose --env-file "$ROOT/shared/production.env" -f "$ROOT/current/docker-compose.production.yml" exec -T external-listings-worker python -m app.workers.external_listings --healthcheck >/dev/null 2>&1 && echo OK || echo FAIL)"
  services="$(timeout 10 docker compose --env-file "$ROOT/shared/production.env" -f "$ROOT/current/docker-compose.production.yml" ps --status running -q | wc -l)"
  load="$(awk '{print $1}' /proc/loadavg)"
  ram="$(( 100 - $(awk '/MemAvailable:/ {available=$2} /MemTotal:/ {total=$2} END {print int(available*100/total)}' /proc/meminfo) ))"
  disk="$(df -P "$ROOT" | awk 'NR==2 {print $5}')"
  health=OK
  [[ "$http" =~ ^[23][0-9][0-9]$ ]] || health=FAIL
  [[ "$backend" == OK && "$worker" == OK && "$services" -ge 7 ]] || health=FAIL
  printf '%s | HEALTH=%s | HTTP=%s | BACKEND=%s | WORKER=%s | SERVICES=%s | DISK=%s | RAM=%s%% | LOAD=%s | SHA=%s\n' \
    "$(utc_now)" "$health" "${http:-000}" "$backend" "$worker" "$services" "$disk" "$ram" "$load" "$sha" >> "$dir/live.log"
  [[ "$health" == OK ]]
}

full_check() {
  local dir="$1" sequence="$2" sample tmp rc sha result
  sample="$(printf '%s/samples/%04d-%s.log' "$dir" "$sequence" "$(date -u +%Y%m%dT%H%M%SZ)")"
  tmp="$(mktemp)"
  sha="$(git -C "$ROOT/current" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)"
  # Keep the lock for the whole check.  FD 9 is inherited only by this shell.
  exec 9>"$BASE_DIR/full-check.lock"
  if ! flock -n 9; then
    { kv TIMESTAMP "$(utc_now)"; kv RELEASE_SHA "$sha"; kv RESULT SKIPPED_PREVIOUS_CHECK_RUNNING; } > "$sample"
    rm -f "$tmp"
    return 0
  fi
  if resource_state || ! tail -n 1 "$dir/live.log" | grep -q 'HEALTH=OK'; then
    { kv TIMESTAMP "$(utc_now)"; kv RELEASE_SHA "$sha"; kv RESULT SKIPPED_RESOURCE_PRESSURE; } > "$sample"
    rm -f "$tmp"
    flock -u 9
    exec 9>&-
    return 0
  fi
  set +e
  if command -v ionice >/dev/null; then
    nice -n 10 ionice -c2 -n7 timeout --foreground "$FULL_TIMEOUT_SECONDS" bash "$ROOT/current/deploy/production-monitor-check.sh" >"$tmp" 2>&1
  else
    nice -n 10 timeout --foreground "$FULL_TIMEOUT_SECONDS" bash "$ROOT/current/deploy/production-monitor-check.sh" >"$tmp" 2>&1
  fi
  rc=$?
  set -e
  result=PASS
  (( rc == 0 )) || result=FAIL
  {
    kv TIMESTAMP "$(utc_now)"
    kv RELEASE_SHA "$sha"
    kv RETURN_CODE "$rc"
    kv RESULT "$result"
    sanitize < "$tmp"
  } > "$sample"
  rm -f "$tmp"
  flock -u 9
  exec 9>&-
  (( rc == 0 ))
}

make_report() {
  local dir="$1" start end expected sha current final full_pass full_fail skipped_pressure skipped_running http_fail backend_fail worker_fail first_failure last_failure duration cpu ram
  start="$(sed -n 's/^START_TIME=//p' "$dir/metadata.txt" | tail -n1)"
  expected="$(sed -n 's/^EXPECTED_END_TIME=//p' "$dir/metadata.txt" | tail -n1)"
  sha="$(sed -n 's/^RELEASE_SHA=//p' "$dir/metadata.txt" | tail -n1)"
  current="$(git -C "$ROOT/current" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)"
  duration="$(sed -n 's/^DURATION_HOURS=//p' "$dir/metadata.txt" | tail -n1)"
  cpu="$(sed -n 's/^CPU_COUNT=//p' "$dir/metadata.txt" | tail -n1)"
  ram="$(sed -n 's/^TOTAL_RAM=//p' "$dir/metadata.txt" | tail -n1)"
  end="$(utc_now)"
  full_pass="$(grep -rl '^RESULT=PASS$' "$dir/samples" 2>/dev/null | wc -l | tr -d ' ' || true)"
  full_fail="$(grep -rl '^RESULT=FAIL$' "$dir/samples" 2>/dev/null | wc -l | tr -d ' ' || true)"
  skipped_pressure="$(grep -rl '^RESULT=SKIPPED_RESOURCE_PRESSURE$' "$dir/samples" 2>/dev/null | wc -l | tr -d ' ' || true)"
  skipped_running="$(grep -rl '^RESULT=SKIPPED_PREVIOUS_CHECK_RUNNING$' "$dir/samples" 2>/dev/null | wc -l | tr -d ' ' || true)"
  http_fail="$(grep -c 'HTTP=\(000\|4\|5\)' "$dir/live.log" 2>/dev/null || true)"
  backend_fail="$(grep -c 'BACKEND=FAIL' "$dir/live.log" 2>/dev/null || true)"
  worker_fail="$(grep -c 'WORKER=FAIL' "$dir/live.log" 2>/dev/null || true)"
  first_failure="$(grep 'HEALTH=FAIL' "$dir/live.log" 2>/dev/null | head -n1 || true)"
  last_failure="$(grep 'HEALTH=FAIL' "$dir/live.log" 2>/dev/null | tail -n1 || true)"
  final=PASS
  [[ "$full_fail" == 0 && "$http_fail" == 0 && "$backend_fail" == 0 && "$worker_fail" == 0 && "$current" == "$sha" ]] || final=FAIL
  [[ "$final" == PASS && ( "$skipped_pressure" != 0 || "$skipped_running" != 0 ) ]] && final=PASS_WITH_WARNINGS
  {
    printf '# Production acceptance report\n\n'
    kv START "$start"; kv END "$end"; kv EXPECTED_END "$expected"; kv DURATION_HOURS "$duration"; kv RELEASE_SHA "$sha"; kv RELEASE_CHANGED "$([[ "$current" == "$sha" ]] && echo NO || echo YES)"; kv CPU_COUNT "$cpu"; kv TOTAL_RAM "$ram"
    kv LIGHT_INTERVAL "$LIGHT_INTERVAL_SECONDS"; kv FULL_INTERVAL "$FULL_INTERVAL_SECONDS"
    kv TOTAL_LIGHT_CHECKS "$(wc -l < "$dir/live.log" 2>/dev/null || echo 0)"; kv PASSED_FULL_CHECKS "$full_pass"; kv FAILED_FULL_CHECKS "$full_fail"
    kv SKIPPED_RESOURCE_PRESSURE "$skipped_pressure"; kv SKIPPED_PREVIOUS_CHECK_RUNNING "$skipped_running"; kv HTTP_FAILURES "$http_fail"; kv BACKEND_FAILURES "$backend_fail"; kv WORKER_FAILURES "$worker_fail"; kv FIRST_FAILURE "${first_failure:-NONE}"; kv LAST_FAILURE "${last_failure:-NONE}"; kv FINAL_STATUS "$final"
  } > "$dir/final-report.md"
}

run_monitor() {
  local dir="$1" duration_seconds="$2" start end next_light next_full sequence=0 exit_state=FINISHED current_log_bytes
  start="$(epoch_now)"; end=$((start + duration_seconds)); next_light="$start"; next_full="$start"
  trap 'exit_state=STOPPED; exit 0' TERM INT
  trap 'make_report "$dir"; write_status "$dir" "$exit_state"' EXIT
  write_status "$dir" RUNNING
  while (( $(epoch_now) < end )); do
    # Sample output is capped at 64 KiB and there can be at most six samples
    # per hour, so inspecting the fixed log files is enough to enforce the
    # run-level limit without recursively scanning the evidence directory.
    current_log_bytes="$(stat -c%s "$dir/live.log" "$dir/monitor.log" "$dir/errors.log" | awk '{total += $1} END {print total}')"
    if (( current_log_bytes >= MAX_LOG_BYTES )); then
      exit_state=FAILED; printf '%s | HEALTH=FAIL | REASON=LOG_LIMIT\n' "$(utc_now)" >> "$dir/live.log"; break
    fi
    if (( $(epoch_now) >= next_light )); then light_check "$dir" || true; next_light=$((next_light + LIGHT_INTERVAL_SECONDS)); fi
    if (( $(epoch_now) >= next_full )); then sequence=$((sequence + 1)); full_check "$dir" "$sequence" || true; next_full=$((next_full + FULL_INTERVAL_SECONDS)); fi
    sleep 1
  done
}

start() {
  local requested="$1" hours seconds run_id dir unit cpu ram swap disk load sha
  if [[ "$requested" == burn-in ]]; then
    hours="0.1667"; seconds=600
  else
    hours="$requested"
    [[ "$hours" =~ ^[1-9][0-9]*$ ]] || die "duration hours must be a positive integer"
    seconds=$((hours * 3600))
  fi
  command -v systemd-run >/dev/null || die "systemd-run is required"
  mkdir -p "$BASE_DIR"
  [[ ! -e "$(active_link)" || "$(value_from_status "$(active_dir)" STATE)" != RUNNING ]] || die "an acceptance run is already active"
  run_id="production-acceptance-$(date -u +%Y%m%d-%H%M%S)"
  dir="$BASE_DIR/$run_id"; mkdir -p "$dir/samples"; chmod 700 "$dir" "$dir/samples"
  cpu="$(nproc)"; ram="$(free -h | awk '/^Mem:/ {print $2}')"; swap="$(free -h | awk '/^Swap:/ {print $2}')"; disk="$(df -h "$ROOT" | awk 'NR==2 {print $4}')"; load="$(awk '{print $1}' /proc/loadavg)"; sha="$(git -C "$ROOT/current" rev-parse --short=12 HEAD)"
  { kv RUN_ID "$run_id"; kv START_TIME "$(utc_now)"; kv EXPECTED_END_TIME "$(date -u -d "+$seconds seconds" +%FT%TZ)"; kv DURATION_HOURS "$hours"; kv LIGHT_INTERVAL_SECONDS "$LIGHT_INTERVAL_SECONDS"; kv FULL_INTERVAL_SECONDS "$FULL_INTERVAL_SECONDS"; kv RELEASE_SHA "$sha"; kv RELEASE_PATH "$(readlink -f "$ROOT/current")"; kv HOSTNAME "$(hostname)"; kv CPU_COUNT "$cpu"; kv TOTAL_RAM "$ram"; kv SWAP "$swap"; kv DISK_FREE_AT_START "$disk"; kv BASELINE_LOAD "$load"; } > "$dir/metadata.txt"
  : > "$dir/live.log"; : > "$dir/monitor.log"; : > "$dir/errors.log"; chmod 600 "$dir"/*.txt "$dir"/*.log
  ln -sfn "$dir" "$(active_link)"
  unit="ttest-production-acceptance-${run_id#production-acceptance-}"
  systemd-run --quiet --unit="$unit" --property=Type=exec --property=Nice=10 --property=IOSchedulingClass=best-effort --property=IOSchedulingPriority=7 --property=CPUWeight=1 --property=IOWeight=1 /bin/bash "$SCRIPT_PATH" _run "$dir" "$seconds"
  printf 'RUN_ID=%s\nUNIT=%s\nEVIDENCE_DIR=%s\n' "$run_id" "$unit" "$dir"
}

status() { local dir unit unit_state; dir="$(active_dir)"; [[ -n "$dir" && -d "$dir" ]] || die "no acceptance run exists"; unit="ttest-production-acceptance-${dir##*production-acceptance-}"; unit_state="$(systemctl is-active "$unit" 2>/dev/null || true)"; cat "$dir/status"; printf 'RUN_ID=%s\nUNIT=%s\nUNIT_STATE=%s\nEVIDENCE_DIR=%s\n' "$(basename "$dir")" "$unit" "${unit_state:-unknown}" "$dir"; }
follow() { local dir; dir="$(active_dir)"; [[ -n "$dir" ]] || die "no acceptance run exists"; tail -F "$dir/live.log"; }
stop() { local dir unit; dir="$(active_dir)"; [[ -n "$dir" ]] || die "no acceptance run exists"; unit="ttest-production-acceptance-${dir##*production-acceptance-}"; systemctl stop "$unit"; }
report() { local dir; dir="$(active_dir)"; [[ -n "$dir" ]] || die "no acceptance run exists"; [[ -f "$dir/final-report.md" ]] || make_report "$dir"; cat "$dir/final-report.md"; }

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
