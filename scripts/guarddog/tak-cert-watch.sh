#!/bin/bash

ALERT_SENT_FILE="/var/lib/takguard/cert_alert_sent"

if [ -f "/opt/tak/certs/files/takserver-le.jks" ]; then
  TEMP_CERT="/tmp/takserver-le-temp.pem"
  keytool -exportcert -keystore /opt/tak/certs/files/takserver-le.jks -storepass atakatak -alias takserver -rfc > "$TEMP_CERT" 2>/dev/null
  
  if [ -f "$TEMP_CERT" ]; then
    EXPIRY_DATE=$(openssl x509 -enddate -noout -in "$TEMP_CERT" | cut -d= -f2)
    EXPIRY_EPOCH=$(date -d "$EXPIRY_DATE" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$EXPIRY_DATE" +%s 2>/dev/null)
    NOW_EPOCH=$(date +%s)
    DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))
    
    rm -f "$TEMP_CERT"
    
    if [ "$DAYS_LEFT" -lt 40 ]; then
      if [ ! -f "$ALERT_SENT_FILE" ] || [ "$(find $ALERT_SENT_FILE -mtime +7 2>/dev/null)" ]; then
        touch "$ALERT_SENT_FILE"
        
        TS="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
        
        SUBJ="TAK Server Certificate Expiring on $(hostname)"
        BODY="TAK Server Let's Encrypt certificate will expire soon.

Time (UTC): $TS
Days Remaining: $DAYS_LEFT
Expires: $EXPIRY_DATE

Action Required:
1. Verify auto-renewal is working:
   systemctl status takserver-cert-renewal.timer

2. Manual renewal if needed:
   sudo /opt/tak/renew-letsencrypt.sh

If renewal fails, clients will be unable to connect after expiration.
"

        echo -e "$BODY" | mail -s "$SUBJ" "ALERT_EMAIL_PLACEHOLDER"
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
  fi
fi
