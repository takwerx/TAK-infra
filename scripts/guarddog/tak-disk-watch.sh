#!/bin/bash

ALERT_SENT_FILE="/var/lib/takguard/disk_alert_sent"
ALERT_THRESHOLD=80
CRITICAL_THRESHOLD=90

ROOT_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
LOGS_USAGE=$(df /opt/tak/logs 2>/dev/null | awk 'NR==2 {print $5}' | sed 's/%//' || echo "0")

NEED_ALERT=false
ALERT_MSG=""

if [ "$ROOT_USAGE" -ge "$CRITICAL_THRESHOLD" ]; then
  NEED_ALERT=true
  ALERT_MSG="${ALERT_MSG}CRITICAL: Root filesystem at ${ROOT_USAGE}%\n"
elif [ "$ROOT_USAGE" -ge "$ALERT_THRESHOLD" ]; then
  NEED_ALERT=true
  ALERT_MSG="${ALERT_MSG}WARNING: Root filesystem at ${ROOT_USAGE}%\n"
fi

if [ -n "$LOGS_USAGE" ] && [ "$LOGS_USAGE" -ge "$CRITICAL_THRESHOLD" ]; then
  NEED_ALERT=true
  ALERT_MSG="${ALERT_MSG}CRITICAL: TAK logs filesystem at ${LOGS_USAGE}%\n"
elif [ -n "$LOGS_USAGE" ] && [ "$LOGS_USAGE" -ge "$ALERT_THRESHOLD" ]; then
  NEED_ALERT=true
  ALERT_MSG="${ALERT_MSG}WARNING: TAK logs filesystem at ${LOGS_USAGE}%\n"
fi

if $NEED_ALERT; then
  if [ ! -f "$ALERT_SENT_FILE" ] || [ "$(find $ALERT_SENT_FILE -mtime +1 2>/dev/null)" ]; then
    touch "$ALERT_SENT_FILE"
    
    TS="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    
    SUBJ="TAK Server Disk Space Alert on $(hostname)"
    BODY="TAK Server disk space is running low.

Time (UTC): $TS

${ALERT_MSG}

Disk Usage Details:
$(df -h /)
$(df -h /opt/tak/logs 2>/dev/null || true)

Action Required:
1. Review Data Retention settings in TAK Server web UI
2. Clean up old logs: /opt/tak/logs/
3. Consider increasing disk size if needed

Largest log files:
$(du -h /opt/tak/logs/*.log 2>/dev/null | sort -rh | head -5 || echo 'N/A')
"

    [ -n "ALERT_EMAIL_PLACEHOLDER" ] && echo -e "$BODY" | mail -s "$SUBJ" "ALERT_EMAIL_PLACEHOLDER"
    if [ -f /opt/tak-guarddog/sms_send.sh ]; then
      TMPF="/tmp/gd-sms-$$.txt"
      printf '%s' "$BODY" > "$TMPF"
      /opt/tak-guarddog/sms_send.sh "$SUBJ" "$TMPF" 2>/dev/null || true
      rm -f "$TMPF"
    fi
  fi
else
  rm -f "$ALERT_SENT_FILE"
fi
