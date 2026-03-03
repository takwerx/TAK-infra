#!/bin/bash

ALERT_SENT_FILE="/var/lib/takguard/db_alert_sent"
LAST_RESTART_FILE="/var/lib/takguard/last_restart_time"

if [ -f "$LAST_RESTART_FILE" ]; then
  LAST_RESTART=$(cat "$LAST_RESTART_FILE")
  CURRENT_TIME=$(date +%s)
  TIME_SINCE_RESTART=$((CURRENT_TIME - LAST_RESTART))
  if [ $TIME_SINCE_RESTART -lt 900 ]; then
    exit 0
  fi
fi

if ! systemctl is-active --quiet postgresql 2>/dev/null; then
  if ! systemctl is-active --quiet postgresql-15 2>/dev/null; then
    if [ ! -f "$ALERT_SENT_FILE" ] || [ "$(find $ALERT_SENT_FILE -mmin +60 2>/dev/null)" ]; then
      touch "$ALERT_SENT_FILE"
      
      TS="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
      
      SUBJ="TAK Server Database Alert on $(hostname)"
      BODY="PostgreSQL service is not running.

Time (UTC): $TS

This will cause:
- TAK Server failure to start
- Data loss
- Service interruption

Check PostgreSQL status:
  systemctl status postgresql

Restart PostgreSQL:
  systemctl restart postgresql
"

      echo -e "$BODY" | mail -s "$SUBJ" "ALERT_EMAIL_PLACEHOLDER"
      if [ -f /opt/tak-guarddog/sms_send.sh ]; then
        TMPF="/tmp/gd-sms-$$.txt"
        printf '%s' "$BODY" > "$TMPF"
        /opt/tak-guarddog/sms_send.sh "$SUBJ" "$TMPF" 2>/dev/null || true
        rm -f "$TMPF"
      fi
      systemctl restart postgresql 2>/dev/null || systemctl restart postgresql-15 2>/dev/null || true
      
      mkdir -p /var/log/takguard
      if systemctl is-active --quiet postgresql 2>/dev/null || systemctl is-active --quiet postgresql-15 2>/dev/null; then
        echo "$(date): PostgreSQL was down, restarted successfully" >> /var/log/takguard/restarts.log
      else
        echo "$(date): PostgreSQL was down, restart FAILED" >> /var/log/takguard/restarts.log
      fi
    fi
  fi
else
  rm -f "$ALERT_SENT_FILE"
fi
