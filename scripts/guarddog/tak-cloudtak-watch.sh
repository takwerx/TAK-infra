#!/bin/bash
# Guard Dog: CloudTAK container health. On 3 consecutive failures: alert and restart containers.

STATE_DIR="/var/lib/takguard"
FAIL_FILE="$STATE_DIR/cloudtak.failcount"
COOLDOWN_FILE="$STATE_DIR/cloudtak_last_restart"
MAX_FAILS=3
COOLDOWN_SECS=900

mkdir -p "$STATE_DIR"

CT_DIR="${HOME:-/root}/CloudTAK"
[ -z "$CT_DIR" ] && CT_DIR="/root/CloudTAK"
[ ! -f "$CT_DIR/docker-compose.yml" ] && exit 0

# Health: cloudtak-api container running
STATUS=$(docker ps --filter name=cloudtak-api --format "{{.Status}}" 2>/dev/null || true)
if echo "$STATUS" | grep -q "Up"; then
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
echo "$TS | restart | CloudTAK container not up — restarting" >> /var/log/takguard/restarts.log

SUBJ="Guard Dog: CloudTAK restarted on $(hostname)"
BODY="CloudTAK container was not running for $FAILS consecutive checks.

Time (UTC): $TS
Action: Restarting CloudTAK containers (docker compose restart).

Check /var/log/takguard/restarts.log for history.
"
echo -e "$BODY" | mail -s "$SUBJ" "ALERT_EMAIL_PLACEHOLDER"
if [ -f /opt/tak-guarddog/sms_send.sh ]; then
  TMPF="/tmp/gd-sms-$$.txt"
  printf '%s' "$BODY" > "$TMPF"
  /opt/tak-guarddog/sms_send.sh "$SUBJ" "$TMPF" 2>/dev/null || true
  rm -f "$TMPF"
fi

cd "$CT_DIR" && docker compose restart 2>&1
echo 0 > "$FAIL_FILE"
date +%s > "$COOLDOWN_FILE"
