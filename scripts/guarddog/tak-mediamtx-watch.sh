#!/bin/bash
# Guard Dog: MediaMTX systemd service health. On 3 consecutive failures: alert and restart.

STATE_DIR="/var/lib/takguard"
FAIL_FILE="$STATE_DIR/mediamtx.failcount"
COOLDOWN_FILE="$STATE_DIR/mediamtx_last_restart"
MAX_FAILS=3
COOLDOWN_SECS=900

mkdir -p "$STATE_DIR"

# Don't run during first 15 minutes after boot (avoid restarting during startup)
UPTIME_SECS=$(awk '{print int($1)}' /proc/uptime 2>/dev/null || echo 0)
[ "$UPTIME_SECS" -lt 900 ] && exit 0

# Only run if MediaMTX is installed (systemd unit)
systemctl list-unit-files mediamtx.service >/dev/null 2>&1 || exit 0

# Health: systemctl is-active
if systemctl is-active --quiet mediamtx; then
  echo 0 > "$FAIL_FILE"
  exit 0
fi

# Failure
FAILS=$(( $(cat "$FAIL_FILE" 2>/dev/null || echo 0) + 1 ))
echo "$FAILS" > "$FAIL_FILE"

if [ "$FAILS" -lt "$MAX_FAILS" ]; then
  exit 0
fi

# Cooldown
if [ -f "$COOLDOWN_FILE" ]; then
  LAST=$(cat "$COOLDOWN_FILE")
  NOW=$(date +%s)
  if [ $(( NOW - LAST )) -lt $COOLDOWN_SECS ]; then
    exit 0
  fi
fi

TS="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
mkdir -p /var/log/takguard
echo "$TS | restart | MediaMTX not active — restarting" >> /var/log/takguard/restarts.log

SUBJ="Guard Dog: MediaMTX restarted on $(hostname)"
BODY="MediaMTX was not running for $FAILS consecutive checks.

Time (UTC): $TS
Action: systemctl restart mediamtx

Check /var/log/takguard/restarts.log for history.
"
[ -n "ALERT_EMAIL_PLACEHOLDER" ] && echo -e "$BODY" | mail -s "$SUBJ" "ALERT_EMAIL_PLACEHOLDER"
if [ -f /opt/tak-guarddog/sms_send.sh ]; then
  TMPF="/tmp/gd-sms-$$.txt"
  printf '%s' "$BODY" > "$TMPF"
  /opt/tak-guarddog/sms_send.sh "$SUBJ" "$TMPF" 2>/dev/null || true
  rm -f "$TMPF"
fi

systemctl restart mediamtx 2>&1
echo 0 > "$FAIL_FILE"
date +%s > "$COOLDOWN_FILE"
