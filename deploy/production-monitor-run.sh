#!/usr/bin/env bash
set -euo pipefail
umask 077

# Run the production checker, persist alert state across timer invocations, send
# deduplicated push alerts, and emit a recovery notification after an incident.
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
CHECKER="${MONITOR_CHECKER:-$ROOT/current/deploy/production-monitor-check.sh}"
STATE_FILE="${MONITOR_STATE_FILE:-$ROOT/shared/production-monitor.state}"

[[ -r "$ENV_FILE" ]] || { echo "production env is not readable: $ENV_FILE" >&2; exit 1; }
[[ -x "$CHECKER" || -r "$CHECKER" ]] || { echo "production monitor checker is missing: $CHECKER" >&2; exit 1; }

read_env() {
  local key="$1"
  sed -n "s/^${key}=//p" "$ENV_FILE" | tail -n 1
}

alerts_required="$(read_env MONITOR_ALERTS_REQUIRED)"
alerts_required="${alerts_required:-0}"
repeat_seconds="$(read_env MONITOR_ALERT_REPEAT_SECONDS)"
repeat_seconds="${repeat_seconds:-21600}"
telegram_token="$(read_env MONITOR_TELEGRAM_BOT_TOKEN)"
telegram_chat_id="$(read_env MONITOR_TELEGRAM_CHAT_ID)"
webhook_url="$(read_env MONITOR_ALERT_WEBHOOK_URL)"
webhook_format="$(read_env MONITOR_ALERT_WEBHOOK_FORMAT)"
webhook_format="${webhook_format:-slack}"

[[ "$alerts_required" == "0" || "$alerts_required" == "1" ]] || { echo "MONITOR_ALERTS_REQUIRED must be 0 or 1" >&2; exit 1; }
[[ "$repeat_seconds" =~ ^[0-9]+$ ]] || { echo "MONITOR_ALERT_REPEAT_SECONDS must be an unsigned integer" >&2; exit 1; }
[[ "$webhook_format" == "slack" || "$webhook_format" == "discord" ]] || { echo "MONITOR_ALERT_WEBHOOK_FORMAT must be slack or discord" >&2; exit 1; }

have_telegram=0
[[ -n "$telegram_token" && -n "$telegram_chat_id" ]] && have_telegram=1
have_webhook=0
[[ -n "$webhook_url" ]] && have_webhook=1
if [[ "$alerts_required" == "1" && "$have_telegram" == "0" && "$have_webhook" == "0" ]]; then
  echo "monitor alert delivery is required but no Telegram or webhook destination is configured" >&2
  exit 1
fi

set +e
output="$(ROOT="$ROOT" ENV_FILE="$ENV_FILE" bash "$CHECKER" 2>&1)"
checker_rc=$?
set -e
printf '%s\n' "$output"

case "$checker_rc" in
  0) status="ok" ;;
  1) status="critical" ;;
  2) status="warning" ;;
  75)
    # Planned deploy/rollback/backup maintenance is explicitly not an incident.
    exit 0
    ;;
  *) status="critical" ;;
esac

previous_status="unknown"
previous_hash=""
last_alert_epoch="0"
if [[ -r "$STATE_FILE" ]]; then
  previous_status="$(sed -n 's/^status=//p' "$STATE_FILE" | tail -n 1)"
  previous_hash="$(sed -n 's/^message_sha256=//p' "$STATE_FILE" | tail -n 1)"
  last_alert_epoch="$(sed -n 's/^last_alert_epoch=//p' "$STATE_FILE" | tail -n 1)"
fi
[[ "$last_alert_epoch" =~ ^[0-9]+$ ]] || last_alert_epoch=0

message_hash="$(printf '%s' "$output" | sha256sum | awk '{print $1}')"
now_epoch="$(date -u +%s)"
should_alert=0
alert_kind="$status"

if [[ "$status" == "ok" ]]; then
  if [[ "$previous_status" == "critical" || "$previous_status" == "warning" ]]; then
    should_alert=1
    alert_kind="recovery"
  fi
else
  if [[ "$status" != "$previous_status" || "$message_hash" != "$previous_hash" ]]; then
    should_alert=1
  elif (( now_epoch - last_alert_epoch >= repeat_seconds )); then
    should_alert=1
  fi
fi

host="$(hostname -f 2>/dev/null || hostname)"
alert_text="[112233.es][$alert_kind][$host] $output"

send_alert() {
  local attempted=0
  local delivered=0
  local payload

  if [[ "$have_telegram" == "1" ]]; then
    attempted=1
    if curl --fail --silent --show-error --max-time 15 \
      -X POST "https://api.telegram.org/bot${telegram_token}/sendMessage" \
      --data-urlencode "chat_id=$telegram_chat_id" \
      --data-urlencode "text=$alert_text" >/dev/null; then
      delivered=1
    else
      echo "Telegram monitor alert delivery failed" >&2
    fi
  fi

  if [[ "$have_webhook" == "1" ]]; then
    attempted=1
    payload="$(ALERT_TEXT="$alert_text" WEBHOOK_FORMAT="$webhook_format" python3 - <<'PY'
import json
import os
key = "text" if os.environ["WEBHOOK_FORMAT"] == "slack" else "content"
print(json.dumps({key: os.environ["ALERT_TEXT"]}))
PY
)"
    if curl --fail --silent --show-error --max-time 15 \
      -X POST -H 'Content-Type: application/json' \
      --data-binary "$payload" "$webhook_url" >/dev/null; then
      delivered=1
    else
      echo "webhook monitor alert delivery failed" >&2
    fi
  fi

  if [[ "$attempted" == "0" ]]; then
    echo "monitor alert destination is not configured; incident remains in systemd journal" >&2
    return 1
  fi
  [[ "$delivered" == "1" ]]
}

alert_failed=0
if [[ "$should_alert" == "1" ]]; then
  if send_alert; then
    last_alert_epoch="$now_epoch"
  else
    alert_failed=1
    echo "monitor alert delivery failed" >&2
  fi
fi

mkdir -p "$(dirname "$STATE_FILE")"
temporary_state="$(mktemp "${STATE_FILE}.tmp.XXXXXX")"
{
  printf 'status=%s\n' "$status"
  printf 'message_sha256=%s\n' "$message_hash"
  printf 'last_alert_epoch=%s\n' "$last_alert_epoch"
  printf 'last_check_epoch=%s\n' "$now_epoch"
} > "$temporary_state"
chmod 600 "$temporary_state"
mv -f "$temporary_state" "$STATE_FILE"

if [[ "$alert_failed" == "1" && "$alerts_required" == "1" ]]; then
  exit 1
fi
exit "$checker_rc"
