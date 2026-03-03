#!/bin/bash

ALERT_SENT_FILE="/var/lib/takguard/process_alert_sent"
FAIL_COUNT_FILE="/var/lib/takguard/process_fail_count"
LAST_RESTART_FILE="/var/lib/takguard/last_restart_time"
RESTART_LOCK="/var/lib/takguard/restart.lock"

if ! systemctl is-active --quiet takserver; then
  rm -f "$FAIL_COUNT_FILE"
  exit 0
fi

if [ -f "$LAST_RESTART_FILE" ]; then
  LAST_RESTART=$(cat "$LAST_RESTART_FILE")
  CURRENT_TIME=$(date +%s)
  TIME_SINCE_RESTART=$((CURRENT_TIME - LAST_RESTART))
  if [ $TIME_SINCE_RESTART -lt 900 ]; then
    exit 0
  fi
fi

MISSING_PROCESSES=()

if ! pgrep -f "spring.profiles.active=messaging" > /dev/null; then
  MISSING_PROCESSES+=("messaging")
fi

if ! pgrep -f "spring.profiles.active=api" > /dev/null; then
  MISSING_PROCESSES+=("api")
fi

if ! pgrep -f "spring.profiles.active=config" > /dev/null; then
  MISSING_PROCESSES+=("config")
fi

if ! pgrep -f "takserver-pm.jar" > /dev/null; then
  MISSING_PROCESSES+=("plugins")
fi

if ! pgrep -f "takserver-retention.jar" > /dev/null; then
  MISSING_PROCESSES+=("retention")
fi

if [ ${#MISSING_PROCESSES[@]} -gt 0 ]; then
  if [ -f "$FAIL_COUNT_FILE" ]; then
    FAIL_COUNT=$(cat "$FAIL_COUNT_FILE")
    FAIL_COUNT=$((FAIL_COUNT + 1))
  else
    FAIL_COUNT=1
  fi
  echo "$FAIL_COUNT" > "$FAIL_COUNT_FILE"
  
  if [ "$FAIL_COUNT" -ge 3 ]; then
    if [ -f "$RESTART_LOCK" ]; then
      exit 0
    fi
    
    if [ ! -f "$ALERT_SENT_FILE" ] || [ "$(find $ALERT_SENT_FILE -mmin +60 2>/dev/null)" ]; then
      touch "$ALERT_SENT_FILE"
      
      TS="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
      MISSING_LIST=$(IFS=,; echo "${MISSING_PROCESSES[*]}")
      
      SUBJ="TAK Server Process Alert on $(hostname)"
      BODY="TAK Server processes are missing - RESTARTING.

Time (UTC): $TS

Service Status: Running (but incomplete)
Missing Processes: $MISSING_LIST
Consecutive failures: $FAIL_COUNT

Expected 5 processes:
- messaging (client connections)
- api (web interface)
- config (configuration)
- plugins (plugin manager)
- retention (data cleanup)

Action taken: Restarting TAK Server

Check logs after restart:
  tail -100 /opt/tak/logs/takserver-messaging.log
  tail -100 /opt/tak/logs/takserver-api.log
"

      echo -e "$BODY" | mail -s "$SUBJ" "ALERT_EMAIL_PLACEHOLDER"
      if [ -f /opt/tak-guarddog/sms_send.sh ]; then
        TMPF="/tmp/gd-sms-$$.txt"
        printf '%s' "$BODY" > "$TMPF"
        /opt/tak-guarddog/sms_send.sh "$SUBJ" "$TMPF" 2>/dev/null || true
        rm -f "$TMPF"
      fi
      mkdir -p /var/log/takguard
      echo "$(date): TAK Server missing processes: $MISSING_LIST ($FAIL_COUNT failures) - restarting" >> /var/log/takguard/restarts.log
      
      touch "$RESTART_LOCK"
      date +%s > "$LAST_RESTART_FILE"
      systemctl restart takserver
      sleep 30
      rm -f "$RESTART_LOCK"
      rm -f "$FAIL_COUNT_FILE"
    fi
  fi
else
  rm -f "$FAIL_COUNT_FILE"
  rm -f "$ALERT_SENT_FILE"
fi
