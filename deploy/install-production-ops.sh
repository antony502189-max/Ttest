#!/usr/bin/env bash
set -euo pipefail
umask 077

# Install the repository-owned systemd timers on the VPS. This script is not run
# by deploy-release.sh: enabling operational schedules remains an explicit
# one-time production action after credentials and alert destinations exist.
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
RELEASE_DIR="${RELEASE_DIR:-$ROOT/current}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"

[[ "$(id -u)" -eq 0 ]] || { echo "install-production-ops.sh must run as root" >&2; exit 77; }
[[ -r "$ENV_FILE" ]] || { echo "production env is not readable: $ENV_FILE" >&2; exit 65; }
[[ "$(stat -c %a "$ENV_FILE")" == "600" ]] || { echo "$ENV_FILE must have mode 600" >&2; exit 65; }
[[ -d "$RELEASE_DIR/deploy/systemd" ]] || { echo "systemd unit directory is missing from current release" >&2; exit 65; }
command -v systemctl >/dev/null || { echo "systemctl is required" >&2; exit 69; }
command -v systemd-analyze >/dev/null || { echo "systemd-analyze is required" >&2; exit 69; }
command -v docker >/dev/null || { echo "docker is required" >&2; exit 69; }

read_env() {
  local key="$1"
  sed -n "s/^${key}=//p" "$ENV_FILE" | tail -n 1
}
require_env() {
  local key="$1" value
  value="$(read_env "$key")"
  [[ -n "$value" ]] || { echo "$key must be configured before operational timers are enabled" >&2; exit 65; }
}

# Disaster-recovery timers are useless without an independent destination.
require_env OFFSITE_BACKUP_ENDPOINT
require_env OFFSITE_BACKUP_ACCESS_KEY
require_env OFFSITE_BACKUP_SECRET_KEY
require_env OFFSITE_BACKUP_BUCKET

for script in \
  production-monitor-check.sh \
  production-monitor-run.sh \
  disaster-recovery-cycle.sh \
  offsite-backup-sync.sh \
  offsite-restore-drill.sh; do
  [[ -r "$RELEASE_DIR/deploy/$script" ]] || { echo "missing production script: $script" >&2; exit 65; }
done

units=(
  112233-monitor.service
  112233-monitor.timer
  112233-dr-cycle.service
  112233-dr-cycle.timer
  112233-offsite-restore-drill.service
  112233-offsite-restore-drill.timer
)

for unit in "${units[@]}"; do
  install -o root -g root -m 0644 "$RELEASE_DIR/deploy/systemd/$unit" "$SYSTEMD_DIR/$unit"
done
systemd-analyze verify "${units[@]/#/$SYSTEMD_DIR/}"
systemctl daemon-reload
systemctl enable --now \
  112233-monitor.timer \
  112233-dr-cycle.timer \
  112233-offsite-restore-drill.timer

# Prove the monitor is executable now; maintenance (75) is acceptable if this
# installation overlaps a release operation, but any other failure blocks a
# successful installation verdict.
set +e
ROOT="$ROOT" ENV_FILE="$ENV_FILE" "$RELEASE_DIR/deploy/production-monitor-run.sh"
monitor_rc=$?
set -e
if [[ "$monitor_rc" -ne 0 && "$monitor_rc" -ne 75 ]]; then
  echo "production monitor failed immediately after installation (rc=$monitor_rc)" >&2
  exit "$monitor_rc"
fi

systemctl --no-pager --full list-timers \
  112233-monitor.timer \
  112233-dr-cycle.timer \
  112233-offsite-restore-drill.timer
printf 'production operational timers installed successfully\n'
