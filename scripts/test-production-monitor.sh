#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MONITOR="$ROOT_DIR/deploy/production-monitor-check.sh"
TEST_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TEST_DIR"
}
trap cleanup EXIT

mkdir -p \
  "$TEST_DIR/bin" \
  "$TEST_DIR/root/shared" \
  "$TEST_DIR/root/current" \
  "$TEST_DIR/root/releases" \
  "$TEST_DIR/root/backups"
: > "$TEST_DIR/root/current/docker-compose.production.yml"

cat > "$TEST_DIR/root/shared/production.env" <<'ENV'
POSTGRES_USER=ttest
POSTGRES_DB=ttest
EXTERNAL_WORKER_STALE_AFTER_SECONDS=300
EXTERNAL_IMPORT_INTERVAL_SECONDS=7200
EXTERNAL_IMPORT_MIN_HEALTHY_SOURCES=3
EXTERNAL_IMPORT_SOURCES=fotocasa,pisos,pisocompartido
ENV

cat > "$TEST_DIR/bin/df" <<'EOF_DF'
#!/usr/bin/env bash
printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\n'
printf 'fake 100 10 90 10%% /\n'
EOF_DF
chmod +x "$TEST_DIR/bin/df"

write_fake_docker() {
  cat > "$TEST_DIR/bin/docker" <<'EOF_DOCKER'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "inspect" ]]; then
  if [[ -n "${FAKE_INSPECT_MARKER:-}" ]]; then
    : > "$FAKE_INSPECT_MARKER"
  fi
  if [[ -n "${FAKE_INSPECT_DELAY:-}" ]]; then
    sleep "$FAKE_INSPECT_DELAY"
  fi
  echo 'running|healthy'
  exit 0
fi
if [[ "$1" == "compose" ]]; then
  shift
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --env-file|-f)
        shift 2
        ;;
      ps)
        echo worker-id
        exit 0
        ;;
      exec)
        all="$*"
        if [[ "$all" == *"FROM external_worker_state"* ]]; then
          echo "${FAKE_STATE_ROW:-healthy|10|100}"
          exit 0
        fi
        if [[ "$all" == *"WITH completed_cycles"* ]]; then
          echo "${FAKE_CYCLE_ROW:-run-default|3|100}"
          exit 0
        fi
        ;;
      *)
        shift
        ;;
    esac
  done
fi
printf 'unexpected fake docker invocation: %s\n' "$*" >&2
exit 99
EOF_DOCKER
  chmod +x "$TEST_DIR/bin/docker"
}
write_fake_docker

run_case() {
  local name="$1" expected="$2"
  shift 2
  local output rc
  set +e
  output="$(env PATH="$TEST_DIR/bin:$PATH" ROOT="$TEST_DIR/root" "$@" bash "$MONITOR" 2>&1)"
  rc=$?
  set -e
  if [[ "$rc" -ne "$expected" ]]; then
    printf '%s: expected rc=%s, got rc=%s\n%s\n' "$name" "$expected" "$rc" "$output" >&2
    exit 1
  fi
  printf '%s: PASS (rc=%s)\n' "$name" "$rc"
}

run_case healthy 0 \
  FAKE_STATE_ROW='healthy|10|100' \
  FAKE_CYCLE_ROW='run-healthy|3|100'

cp "$TEST_DIR/root/shared/production.env" "$TEST_DIR/root/shared/production.env.original"
sed -i \
  's/^EXTERNAL_IMPORT_SOURCES=.*/EXTERNAL_IMPORT_SOURCES=fotocasa,pisos,pisocompartido,thinkspain/' \
  "$TEST_DIR/root/shared/production.env"
run_case degraded-source 2 \
  FAKE_STATE_ROW='healthy|10|100' \
  FAKE_CYCLE_ROW='run-degraded|3|100'
mv "$TEST_DIR/root/shared/production.env.original" "$TEST_DIR/root/shared/production.env"

run_case below-required-threshold 1 \
  FAKE_STATE_ROW='healthy|10|100' \
  FAKE_CYCLE_ROW='run-below-threshold|2|100'

run_case stale-idle-cycle 1 \
  FAKE_STATE_ROW='healthy|10|8000' \
  FAKE_CYCLE_ROW='run-stale|3|8000'

run_case active-long-cycle 0 \
  FAKE_STATE_ROW='running|10|8000' \
  FAKE_CYCLE_ROW='run-active|3|8000'

: > "$TEST_DIR/root/shared/release.lock"
flock "$TEST_DIR/root/shared/release.lock" -c 'sleep 1' &
lock_holder=$!
sleep 0.1
run_case maintenance-lock 75 \
  FAKE_STATE_ROW='healthy|10|100' \
  FAKE_CYCLE_ROW='run-maintenance|3|100'
wait "$lock_holder"

# Prove that a slow monitor probe does not itself hold the shared release lock.
marker="$TEST_DIR/inspect-started"
env \
  PATH="$TEST_DIR/bin:$PATH" \
  ROOT="$TEST_DIR/root" \
  FAKE_INSPECT_MARKER="$marker" \
  FAKE_INSPECT_DELAY=1 \
  FAKE_STATE_ROW='healthy|10|100' \
  FAKE_CYCLE_ROW='run-lock-race|3|100' \
  bash "$MONITOR" > "$TEST_DIR/monitor.out" 2>&1 &
monitor_pid=$!
for _ in $(seq 1 100); do
  [[ -e "$marker" ]] && break
  sleep 0.01
done
[[ -e "$marker" ]] || { echo 'monitor did not reach the delayed inspect probe' >&2; kill "$monitor_pid" || true; exit 1; }
flock -n "$TEST_DIR/root/shared/release.lock" -c true || {
  echo 'monitor unexpectedly retained the release lock' >&2
  kill "$monitor_pid" || true
  exit 1
}
wait "$monitor_pid"
echo 'nonblocking-release-lock: PASS'

echo 'production monitor regression harness: PASS'
