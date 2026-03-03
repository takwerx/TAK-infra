#!/bin/bash

LOGFILE="/opt/tak/logs/takserver-messaging.log"
STATEFILE="/var/run/tak_oom.state"
SERVICE="takserver"

# Check for OutOfMemoryError in logs
if grep -q "OutOfMemoryError: Java heap space" "$LOGFILE" 2>/dev/null; then
  # Only restart once until log clears
  if [ ! -f "$STATEFILE" ]; then
    touch "$STATEFILE"
    
    TS="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    LOAD="$(cut -d' ' -f1-3 /proc/loadavg)"
    MEMFREE="$(free -h | awk '/Mem:/ {print $4}')"
    
    mkdir -p /var/log/takguard
    echo "$TS | restart | OOM detected | load=$LOAD | mem_free=$MEMFREE" >> /var/log/takguard/restarts.log
    
    SUBJ="TAK OOM Restart on $(hostname)"
    BODY="TAK Server experienced Out of Memory error and was restarted.

Time (UTC): $TS
Load: $LOAD
Free Memory: $MEMFREE

This usually indicates:
- Java heap exhaustion (not system RAM)
- Memory leak in application
- Too many concurrent connections
- Client reconnect loops causing object accumulation

Check /opt/tak/logs/takserver-messaging.log for details.
Consider reviewing Data Retention settings in TAK Server UI.
"

    echo -e "$BODY" | mail -s "$SUBJ" "ALERT_EMAIL_PLACEHOLDER"
    [ -n "ALERT_SMS_PLACEHOLDER" ] && echo -e "$BODY" | mail -s "$SUBJ" "ALERT_SMS_PLACEHOLDER"
    if [ -f /opt/tak-guarddog/sms_send.sh ]; then
      TMPF="/tmp/gd-sms-$$.txt"
      printf '%s' "$BODY" > "$TMPF"
      /opt/tak-guarddog/sms_send.sh "$SUBJ" "$TMPF" 2>/dev/null || true
      rm -f "$TMPF"
    fi
    systemctl restart $SERVICE
  fi
else
  rm -f "$STATEFILE"
fi
