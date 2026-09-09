#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER="$ROOT_DIR/deploy/production-monitor-run.sh"
TEST_DIR="$(mktemp -d)"
cleanup() { rm -rf "$TEST_DIR"; }
trap cleanup EXIT

mkdir -p "$TEST_DIR/root/shared" "$TEST_DIR/bin"
cat > "$TEST_DIR/root/shared/production.env" <<'ENV'
MONITOR_ALERTS_REQUIRED=1
MONITOR_ALERT_REPEAT_SECONDS=999999
MONITOR_ALERT_WEBHOOK_URL=https://alerts.example.invalid/hook
MONITOR_ALERT_WEBHOOK_FORMAT=slack
ENV
chmod 600 "$TEST_DIR/root/shared/production.env"

cat > "$TEST_DIR/checker.sh" <<'EOF_CHECKER'
#!/usr/bin/env bash
monitor_mode="$(cat "$FAKE_MONITOR_MODE")"
case "$monitor_mode" in
  critical|critical-heartbeat-*)
    heartbeat_age="${monitor_mode##*-}"
    if [[ "$heartbeat_age" =~ ^[0-9]+$ ]]; then
      echo "CRITICAL: services=healthy, worker=healthy, heartbeat_age=${heartbeat_age}s, healthy_sources=4/3, cycle_age=100s, run_id=run-one"
    else
      echo 'CRITICAL: synthetic database failure'
    fi
    exit 1
    ;;
  critical-cycle-*)
    cycle_age="${monitor_mode##*-}"
    echo "CRITICAL: services=healthy, worker=healthy, heartbeat_age=100s, healthy_sources=4/3, cycle_age=${cycle_age}s, run_id=run-one"
    exit 1
    ;;
  critical-identity-*)
    identity="${monitor_mode##*-}"
    echo "CRITICAL: synthetic database failure identity=${identity}"
    exit 1
    ;;
  critical)
    echo 'CRITICAL: synthetic database failure'
    exit 1
    ;;
  warning)
    echo 'WARNING: synthetic degraded source'
    exit 2
    ;;
  ok)
    echo 'OK: synthetic recovery'
    exit 0
    ;;
  *)
    exit 99
    ;;
esac
EOF_CHECKER
chmod +x "$TEST_DIR/checker.sh"

cat > "$TEST_DIR/bin/curl" <<'EOF_CURL'
#!/usr/bin/env bash
printf 'call\n' >> "$FAKE_CURL_LOG"
if [[ "${FAKE_CURL_FAIL:-0}" == "1" ]]; then
  exit 22
fi
exit 0
EOF_CURL
chmod +x "$TEST_DIR/bin/curl"

mode_file="$TEST_DIR/mode"
curl_log="$TEST_DIR/curl.log"
state_file="$TEST_DIR/monitor.state"
printf 'critical-heartbeat-301\n' > "$mode_file"

run_expect() {
  local expected="$1"
  set +e
  env \
    PATH="$TEST_DIR/bin:$PATH" \
    ROOT="$TEST_DIR/root" \
    ENV_FILE="$TEST_DIR/root/shared/production.env" \
    MONITOR_CHECKER="$TEST_DIR/checker.sh" \
    MONITOR_STATE_FILE="$state_file" \
    FAKE_MONITOR_MODE="$mode_file" \
    FAKE_CURL_LOG="$curl_log" \
    FAKE_CURL_FAIL="${FAKE_CURL_FAIL:-0}" \
    bash "$RUNNER" >/dev/null 2>&1
  rc=$?
  set -e
  [[ "$rc" -eq "$expected" ]] || { echo "expected rc=$expected, got $rc" >&2; exit 1; }
}

run_expect 1
[[ "$(wc -l < "$curl_log")" -eq 1 ]] || { echo 'first critical alert was not delivered exactly once' >&2; exit 1; }

# A) A heartbeat age change is the same incident inside the repeat window.
printf 'critical-heartbeat-302\n' > "$mode_file"
run_expect 1
[[ "$(wc -l < "$curl_log")" -eq 1 ]] || { echo 'heartbeat age change bypassed deduplication' >&2; exit 1; }

# B) A cycle age change is the same incident when its durable condition is unchanged.
printf 'critical-cycle-7201\n' > "$mode_file"
run_expect 1
[[ "$(wc -l < "$curl_log")" -eq 1 ]] || { echo 'cycle age change bypassed deduplication' >&2; exit 1; }

# C) Expiring the configured repeat interval intentionally re-pages the incident.
sed -i 's/^MONITOR_ALERT_REPEAT_SECONDS=.*/MONITOR_ALERT_REPEAT_SECONDS=0/' "$TEST_DIR/root/shared/production.env"
run_expect 1
[[ "$(wc -l < "$curl_log")" -eq 2 ]] || { echo 'repeat interval did not re-alert the open incident' >&2; exit 1; }
sed -i 's/^MONITOR_ALERT_REPEAT_SECONDS=.*/MONITOR_ALERT_REPEAT_SECONDS=999999/' "$TEST_DIR/root/shared/production.env"

# D) A severity transition is a new alert.
printf 'warning\n' > "$mode_file"
run_expect 2
[[ "$(wc -l < "$curl_log")" -eq 3 ]] || { echo 'severity transition did not alert' >&2; exit 1; }

# E) A durable condition change is a new alert even when severity is stable.
printf 'critical-identity-one\n' > "$mode_file"
run_expect 1
[[ "$(wc -l < "$curl_log")" -eq 4 ]] || { echo 'critical severity transition did not alert' >&2; exit 1; }
printf 'critical-identity-two\n' > "$mode_file"
run_expect 1
[[ "$(wc -l < "$curl_log")" -eq 5 ]] || { echo 'new incident identity did not alert' >&2; exit 1; }

# F) An incident recovery alerts once.
printf 'ok\n' > "$mode_file"
run_expect 0
[[ "$(wc -l < "$curl_log")" -eq 6 ]] || { echo 'recovery notification was not delivered' >&2; exit 1; }

# Required alerting must fail closed when the configured destination rejects
# delivery. A warning would normally exit 2; delivery failure escalates to 1.
printf 'warning\n' > "$mode_file"
FAKE_CURL_FAIL=1 run_expect 1
[[ "$(wc -l < "$curl_log")" -eq 7 ]] || { echo 'failed delivery was not attempted' >&2; exit 1; }
grep -Fq 'status=ok' "$state_file" || { echo 'failed incident delivery advanced state' >&2; exit 1; }

# Failed delivery must not consume the incident transition. The next healthy
# destination gets another attempt even though the checker output is unchanged.
run_expect 2
[[ "$(wc -l < "$curl_log")" -eq 8 ]] || { echo 'failed incident delivery was not retried' >&2; exit 1; }

# The same rule is essential for recovery: a failed recovery notification must
# remain pending until one destination accepts it.
printf 'ok\n' > "$mode_file"
FAKE_CURL_FAIL=1 run_expect 1
[[ "$(wc -l < "$curl_log")" -eq 9 ]] || { echo 'failed recovery delivery was not attempted' >&2; exit 1; }
grep -Fq 'status=warning' "$state_file" || { echo 'failed recovery delivery advanced state' >&2; exit 1; }
run_expect 0
[[ "$(wc -l < "$curl_log")" -eq 10 ]] || { echo 'failed recovery delivery was not retried' >&2; exit 1; }

echo 'production monitor alert regression harness: PASS'
