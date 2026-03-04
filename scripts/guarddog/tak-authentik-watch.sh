#!/bin/bash
# Guard Dog: Authentik container health. On 3 consecutive failures: alert and restart containers.

STATE_DIR="/var/lib/takguard"
FAIL_FILE="$STATE_DIR/authentik.failcount"
COOLDOWN_FILE="$STATE_DIR/authentik_last_restart"
MAX_FAILS=3
COOLDOWN_SECS=900

mkdir -p "$STATE_DIR"

AK_DIR="${HOME:-/root}/authentik"
[ ! -f "$AK_DIR/docker-compose.yml" ] && exit 0

# Health: HTTP to Authentik server (9090)
CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://127.0.0.1:9090/ 2>/dev/null || echo "000")
if [ "$CODE" = "200" ] || [ "$CODE" = "302" ] || [ "$CODE" = "301" ]; then
  echo 0 > "$FAIL_FILE"
  exit 0
fi

# Failure
FAILS=$(( $(cat "$FAIL_FILE" 2>/dev/null || echo 0) + 1 ))
echo "$FAILS" > "$FAIL_FILE"

if [ "$FAILS" -lt "$MAX_FAILS" ]; then
  exit 0
fi

# Cooldown: don't restart more than once per COOLDOWN_SECS
if [ -f "$COOLDOWN_FILE" ]; then
  LAST=$(cat "$COOLDOWN_FILE")
  NOW=$(date +%s)
  if [ $(( NOW - LAST )) -lt $COOLDOWN_SECS ]; then
    exit 0
  fi
fi

TS="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
mkdir -p /var/log/takguard
echo "$TS | restart | Authentik unhealthy (HTTP $CODE) — restarting containers" >> /var/log/takguard/restarts.log

SUBJ="Guard Dog: Authentik restarted on $(hostname)"
BODY="Authentik failed health check (HTTP $CODE) for $FAILS consecutive checks.

Time (UTC): $TS
Action: Restarting Authentik containers (docker compose restart).

Check /var/log/takguard/restarts.log for history.
"
echo -e "$BODY" | mail -s "$SUBJ" "ALERT_EMAIL_PLACEHOLDER"
if [ -f /opt/tak-guarddog/sms_send.sh ]; then
  TMPF="/tmp/gd-sms-$$.txt"
  printf '%s' "$BODY" > "$TMPF"
  /opt/tak-guarddog/sms_send.sh "$SUBJ" "$TMPF" 2>/dev/null || true
  rm -f "$TMPF"
fi

cd "$AK_DIR" && docker compose restart 2>&1
echo 0 > "$FAIL_FILE"
date +%s > "$COOLDOWN_FILE"
