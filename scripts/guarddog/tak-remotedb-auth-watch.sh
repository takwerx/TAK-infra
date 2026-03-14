#!/bin/bash
# Guard Dog: Remote Database Credential monitor (two-server mode).
# Validates that the martiuser password in CoreConfig.xml actually
# authenticates against PostgreSQL on Server One. Catches credential
# drift before it silently breaks TAK Server / CloudTAK.
#
# Placeholders replaced at deploy time:
#   DB_HOST_PLACEHOLDER        → Server One IP/hostname
#   DB_PORT_PLACEHOLDER        → Database port (default 5432)
#   SSH_KEY_PLACEHOLDER        → SSH key path for Server One
#   SSH_USER_PLACEHOLDER       → SSH user for Server One
#   ALERT_EMAIL_PLACEHOLDER    → Alert email (empty = no email)

DB_HOST="DB_HOST_PLACEHOLDER"
DB_PORT="DB_PORT_PLACEHOLDER"
SSH_KEY="SSH_KEY_PLACEHOLDER"
SSH_USER="SSH_USER_PLACEHOLDER"

ALERT_SENT_FILE="/var/lib/takguard/remotedb_auth_alert_sent"
FAIL_COUNT_FILE="/var/lib/takguard/remotedb_auth_fail_count"

LAST_RESTART_FILE="/var/lib/takguard/last_restart_time"
if [ -f "$LAST_RESTART_FILE" ]; then
  LAST_RESTART=$(cat "$LAST_RESTART_FILE")
  CURRENT_TIME=$(date +%s)
  TIME_SINCE_RESTART=$((CURRENT_TIME - LAST_RESTART))
  if [ $TIME_SINCE_RESTART -lt 900 ]; then
    exit 0
  fi
fi

# Extract martiuser password from CoreConfig.xml on this host (Server Two / core)
CORE_CONFIG="/opt/tak/CoreConfig.xml"
if [ ! -f "$CORE_CONFIG" ]; then
  CORE_CONFIG_CONTENT=$(sudo cat /opt/tak/CoreConfig.xml 2>/dev/null)
else
  CORE_CONFIG_CONTENT=$(cat "$CORE_CONFIG" 2>/dev/null)
fi

if [ -z "$CORE_CONFIG_CONTENT" ]; then
  exit 0
fi

DB_PASSWORD=$(echo "$CORE_CONFIG_CONTENT" | grep -oP '<connection[^>]*url="jdbc:postgresql://[^"]+/cot"[^>]*password="\K[^"]*' | head -1)
if [ -z "$DB_PASSWORD" ]; then
  DB_PASSWORD=$(echo "$CORE_CONFIG_CONTENT" | grep -oP '<connection[^>]*username="martiuser"[^>]*password="\K[^"]*' | head -1)
fi
if [ -z "$DB_PASSWORD" ]; then
  DB_PASSWORD=$(echo "$CORE_CONFIG_CONTENT" | grep -oP 'password="\K[^"]*' | head -1)
fi

if [ -z "$DB_PASSWORD" ]; then
  exit 0
fi

HEALTHY=true
DETAILS=""

if [ -n "$SSH_KEY" ] && [ -f "$SSH_KEY" ]; then
  AUTH_OUT=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
    "${SSH_USER}@${DB_HOST}" \
    "PGPASSWORD='${DB_PASSWORD}' psql -h 127.0.0.1 -p ${DB_PORT} -U martiuser -d cot -tAc 'select 1' 2>/dev/null | tr -d '[:space:]'" \
    2>/dev/null)
  if [ "$AUTH_OUT" != "1" ]; then
    HEALTHY=false
    DETAILS="martiuser password from CoreConfig.xml failed authentication against PostgreSQL on ${DB_HOST}:${DB_PORT}. Use Sync DB Password in infra-TAK to fix."
  fi
else
  exit 0
fi

if $HEALTHY; then
  rm -f "$ALERT_SENT_FILE" "$FAIL_COUNT_FILE"
  exit 0
fi

FAIL_COUNT=0
[ -f "$FAIL_COUNT_FILE" ] && FAIL_COUNT=$(cat "$FAIL_COUNT_FILE")
FAIL_COUNT=$((FAIL_COUNT + 1))
echo "$FAIL_COUNT" > "$FAIL_COUNT_FILE"

if [ "$FAIL_COUNT" -lt 2 ]; then
  exit 0
fi

if [ -f "$ALERT_SENT_FILE" ] && [ -z "$(find "$ALERT_SENT_FILE" -mmin +60 2>/dev/null)" ]; then
  exit 0
fi

touch "$ALERT_SENT_FILE"
TS="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

SUBJ="TAK Server DB Credential Alert on $(hostname)"
BODY="CREDENTIAL DRIFT DETECTED — martiuser password mismatch.

Time (UTC): $TS
Consecutive failures: $FAIL_COUNT
Details: $DETAILS

The password in /opt/tak/CoreConfig.xml does not authenticate against
PostgreSQL on Server One ($DB_HOST:$DB_PORT).

This will cause TAK Server connection pool exhaustion (HikariPool errors)
and break CloudTAK registration.

FIX: Open infra-TAK → TAK Server → Sync DB Password.
Or manually get the correct password from Server One CoreConfig.example.xml
and update /opt/tak/CoreConfig.xml on this host.
"

[ -n "ALERT_EMAIL_PLACEHOLDER" ] && echo -e "$BODY" | mail -s "$SUBJ" "ALERT_EMAIL_PLACEHOLDER"
if [ -f /opt/tak-guarddog/sms_send.sh ]; then
  TMPF="/tmp/gd-sms-$$.txt"
  printf '%s' "$BODY" > "$TMPF"
  /opt/tak-guarddog/sms_send.sh "$SUBJ" "$TMPF" 2>/dev/null || true
  rm -f "$TMPF"
fi
mkdir -p /var/log/takguard
echo "$(date): DB credential drift detected — martiuser auth failed on $DB_HOST:$DB_PORT (failures: $FAIL_COUNT)" >> /var/log/takguard/restarts.log
