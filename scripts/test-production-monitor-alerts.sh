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
case "$(cat "$FAKE_MONITOR_MODE")" in
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
printf 'critical\n' > "$mode_file"

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

# Identical incidents inside the repeat window must not page repeatedly.
run_expect 1
[[ "$(wc -l < "$curl_log")" -eq 1 ]] || { echo 'identical critical alert was not deduplicated' >&2; exit 1; }

printf 'warning\n' > "$mode_file"
run_expect 2
[[ "$(wc -l < "$curl_log")" -eq 2 ]] || { echo 'severity transition did not alert' >&2; exit 1; }

printf 'ok\n' > "$mode_file"
run_expect 0
[[ "$(wc -l < "$curl_log")" -eq 3 ]] || { echo 'recovery notification was not delivered' >&2; exit 1; }

# Required alerting must fail closed when the configured destination rejects
# delivery. A warning would normally exit 2; delivery failure escalates to 1.
printf 'warning\n' > "$mode_file"
FAKE_CURL_FAIL=1 run_expect 1
[[ "$(wc -l < "$curl_log")" -eq 4 ]] || { echo 'failed delivery was not attempted' >&2; exit 1; }

# Failed delivery must not consume the incident transition. The next healthy
# destination gets another attempt even though the checker output is unchanged.
run_expect 2
[[ "$(wc -l < "$curl_log")" -eq 5 ]] || { echo 'failed incident delivery was not retried' >&2; exit 1; }

# The same rule is essential for recovery: a failed recovery notification must
# remain pending until one destination accepts it.
printf 'ok\n' > "$mode_file"
FAKE_CURL_FAIL=1 run_expect 1
[[ "$(wc -l < "$curl_log")" -eq 6 ]] || { echo 'failed recovery delivery was not attempted' >&2; exit 1; }
run_expect 0
[[ "$(wc -l < "$curl_log")" -eq 7 ]] || { echo 'failed recovery delivery was not retried' >&2; exit 1; }

echo 'production monitor alert regression harness: PASS'
