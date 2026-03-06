#!/bin/bash

STATE_DIR="/var/lib/takguard"
FAIL_FILE="$STATE_DIR/8089.failcount"
COOLDOWN_FILE="$STATE_DIR/last_restart"
REASON_FILE="$STATE_DIR/restart_reason"
LAST_RESTART_FILE="$STATE_DIR/last_restart_time"
RESTART_LOCK="$STATE_DIR/restart.lock"

PORT=8089
MAX_FAILS=3
COOLDOWN_SECS=900
MIN_UPTIME_SECS=900

mkdir -p "$STATE_DIR"

# Don't run during first 15 minutes after boot
UPTIME_SECS=$(awk '{print int($1)}' /proc/uptime)
if [ "$UPTIME_SECS" -lt "$MIN_UPTIME_SECS" ]; then
  exit 0
fi

# Check if we're in grace period (15 minutes after any restart)
if [ -f "$LAST_RESTART_FILE" ]; then
  LAST_RESTART=$(cat "$LAST_RESTART_FILE")
  CURRENT_TIME=$(date +%s)
  TIME_SINCE_RESTART=$((CURRENT_TIME - LAST_RESTART))
  
  # 900 seconds = 15 minutes
  if [ $TIME_SINCE_RESTART -lt 900 ]; then
    # Still in grace period, skip check
    exit 0
  fi
fi

# Only run if takserver is active
systemctl is-active --quiet takserver || exit 0

# Check if another monitor is already restarting
if [ -f "$RESTART_LOCK" ]; then
  exit 0
fi

# Check if port 8089 is listening and accepting connections
LQ_LINE=$(ss -ltn "sport = :$PORT" | awk 'NR==2')

LISTEN_OK=false
BACKLOG_BAD=false

if echo "$LQ_LINE" | grep -q LISTEN; then
  LISTEN_OK=true
  RECVQ=$(echo "$LQ_LINE" | awk '{print $2}')
  SENDQ=$(echo "$LQ_LINE" | awk '{print $3}')

  # Check if listen backlog is saturated
  if [ -n "$RECVQ" ] && [ -n "$SENDQ" ] && [ "$SENDQ" -gt 0 ] && [ "$RECVQ" -ge $((SENDQ-5)) ]; then
    BACKLOG_BAD=true
  fi
fi

# If healthy, reset fail counter
if $LISTEN_OK && ! $BACKLOG_BAD; then
  echo 0 > "$FAIL_FILE"
  exit 0
fi

# Increment fail counter
FAILS=0
[ -f "$FAIL_FILE" ] && FAILS=$(cat "$FAIL_FILE")
FAILS=$((FAILS+1))
echo "$FAILS" > "$FAIL_FILE"

# Need 3 consecutive failures
if [ "$FAILS" -lt "$MAX_FAILS" ]; then
  exit 0
fi

# Check cooldown period (15 minutes between restarts)
NOW=$(date +%s)
LAST=0
[ -f "$COOLDOWN_FILE" ] && LAST=$(cat "$COOLDOWN_FILE")
if [ $((NOW - LAST)) -lt "$COOLDOWN_SECS" ]; then
  exit 0
fi

# Log and alert
logger -t takguard "8089 unhealthy for $FAILS checks; restarting takserver"

echo "$NOW" > "$COOLDOWN_FILE"
echo 0 > "$FAIL_FILE"
echo "guard dog_8089" > "$REASON_FILE"

# Detailed logging
LOGDIR="/var/log/takguard"
LOGFILE="$LOGDIR/restarts.log"
mkdir -p "$LOGDIR"

TS="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
LOAD="$(cut -d' ' -f1-3 /proc/loadavg)"
MEMFREE="$(free -h | awk '/Mem:/ {print $4}')"
MSGPID="$(ps -ef | grep takserver.war | grep messaging | grep -v grep | awk '{print $2}' | head -n1)"

echo "$TS | restart | 8089 unhealthy | load=$LOAD | mem_free=$MEMFREE | msg_pid=${MSGPID:-na}" >> "$LOGFILE"

# Send alerts
SUBJ="TAK Guard Dog Restart on $(hostname)"
BODY="TAK Server was automatically restarted by the guard dog.

Reason: TCP 8089 unhealthy for $FAILS consecutive checks.
Time (UTC): $TS

System State:
- Load: $LOAD
- Free Memory: $MEMFREE
- Messaging PID before restart: ${MSGPID:-na}

This usually indicates:
- Dead TLS connections accumulating
- Client reconnect loops
- Network issues

Check /var/log/takguard/restarts.log for history.
"

[ -n "ALERT_EMAIL_PLACEHOLDER" ] && echo -e "$BODY" | mail -s "$SUBJ" "ALERT_EMAIL_PLACEHOLDER"
[ -n "ALERT_SMS_PLACEHOLDER" ] && echo -e "$BODY" | mail -s "$SUBJ" "ALERT_SMS_PLACEHOLDER"
if [ -f /opt/tak-guarddog/sms_send.sh ]; then
  TMPF="/tmp/gd-sms-$$.txt"
  printf '%s' "$BODY" > "$TMPF"
  /opt/tak-guarddog/sms_send.sh "$SUBJ" "$TMPF" 2>/dev/null || true
  rm -f "$TMPF"
fi

# Create restart lock
touch "$RESTART_LOCK"

# Record restart time for grace period
date +%s > "$LAST_RESTART_FILE"

# Restart TAK Server
systemctl restart takserver

# Wait 30 seconds then remove lock
sleep 30
rm -f "$RESTART_LOCK"
