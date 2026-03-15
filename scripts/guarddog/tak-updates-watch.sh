#!/bin/bash
# Guard Dog: check for available updates (infra-TAK, Authentik, MediaMTX, CloudTAK, TAK Portal) and email once per change.

SERVER_IDENTIFIER=$(cat /opt/tak-guarddog/server_identifier 2>/dev/null || echo "$(hostname)")
ALERT_EMAIL="ALERT_EMAIL_PLACEHOLDER"
CONSOLE_VERSION="CONSOLE_VERSION_PLACEHOLDER"
STATE_FILE="/var/lib/takguard/updates_notified"
CURL_TIMEOUT=15

[ -z "$ALERT_EMAIL" ] || [ "$ALERT_EMAIL" = "ALERT_EMAIL_PLACEHOLDER" ] && exit 0

# Fetch latest tag from GitHub (repo = org/repo). Strips version/ and v prefix.
latest_tag() {
  local repo="$1"
  raw=$(curl -sS -f --max-time "$CURL_TIMEOUT" \
    -H "Accept: application/vnd.github.v3+json" -H "User-Agent: infra-TAK" \
    "https://api.github.com/repos/${repo}/releases/latest" 2>/dev/null | \
    grep -o '"tag_name":[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)".*/\1/')
  echo "$raw" | sed 's/^version\///' | sed 's/^v//'
}

# For infra-TAK we use tags API (no releases/latest)
latest_infratak() {
  curl -sS -f --max-time "$CURL_TIMEOUT" \
    -H "Accept: application/vnd.github.v3+json" -H "User-Agent: infra-TAK" \
    "https://api.github.com/repos/takwerx/infra-TAK/tags?per_page=5" 2>/dev/null | \
    grep -o '"name":[[:space:]]*"v[^"]*"' | head -1 | sed 's/.*"v\([^"]*\)".*/\1/'
}

# Return 0 if update available (cur empty or cur < latest), 1 otherwise.
need_update() {
  local cur="$1" latest="$2"
  [ -z "$latest" ] && return 1
  [ -z "$cur" ] && return 0
  max=$(printf '%s\n%s\n' "${cur}" "${latest}" | sort -V 2>/dev/null | tail -1)
  [ "$max" = "$latest" ] && [ "$cur" != "$latest" ] && return 0
  return 1
}

UPDATES=""
SIG=""

# infra-TAK
latest_console=$(latest_infratak)
cur_console="$CONSOLE_VERSION"
if need_update "$cur_console" "$latest_console"; then
  UPDATES="${UPDATES}  - infra-TAK: current ${cur_console:-unknown}, latest ${latest_console}\n"
  SIG="${SIG}infratak:${latest_console};"
fi

# Authentik (only if installed)
if [ -f "$HOME/authentik/.env" ]; then
  cur_ak=$(grep -E '^AUTHENTIK_TAG=' "$HOME/authentik/.env" 2>/dev/null | cut -d= -f2- | tr -d '"' | sed 's/^v//')
  latest_ak=$(latest_tag "goauthentik/authentik")
  if need_update "$cur_ak" "$latest_ak"; then
    UPDATES="${UPDATES}  - Authentik: current ${cur_ak:-unknown}, latest ${latest_ak}\n"
    SIG="${SIG}authentik:${latest_ak};"
  fi
fi

# MediaMTX (only if binary present)
if [ -x "/usr/local/bin/mediamtx" ]; then
  cur_mtx=$(/usr/local/bin/mediamtx -version 2>/dev/null | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1 | sed 's/^v//')
  [ -z "$cur_mtx" ] && cur_mtx=$(strings /usr/local/bin/mediamtx 2>/dev/null | grep -oE '^[0-9]+\.[0-9]+\.[0-9]+$' | head -1)
  latest_mtx=$(latest_tag "bluenviron/mediamtx")
  if need_update "$cur_mtx" "$latest_mtx"; then
    UPDATES="${UPDATES}  - MediaMTX: current ${cur_mtx:-unknown}, latest ${latest_mtx}\n"
    SIG="${SIG}mediamtx:${latest_mtx};"
  fi
fi

# CloudTAK (only if installed)
if [ -f "$HOME/CloudTAK/api/package.json" ]; then
  cur_ct=$(grep -o '"version":[[:space:]]*"[^"]*"' "$HOME/CloudTAK/api/package.json" 2>/dev/null | head -1 | sed 's/.*"\([^"]*\)".*/\1/')
  latest_ct=$(latest_tag "dfpc-coe/CloudTAK")
  if need_update "$cur_ct" "$latest_ct"; then
    UPDATES="${UPDATES}  - CloudTAK: current ${cur_ct:-unknown}, latest ${latest_ct}\n"
    SIG="${SIG}cloudtak:${latest_ct};"
  fi
fi

# TAK Portal (current from package.json, latest from container logs [update-check] — same as console)
if [ -f "$HOME/TAK-Portal/package.json" ]; then
  cur_portal=$(grep -o '"version":[[:space:]]*"[^"]*"' "$HOME/TAK-Portal/package.json" 2>/dev/null | head -1 | sed 's/.*"\([^"]*\)".*/\1/')
  latest_portal=""
  if docker ps --filter name=tak-portal -q 2>/dev/null | grep -q .; then
    latest_portal=$(docker logs tak-portal --tail 200 2>/dev/null | grep '\[update-check\]' | tail -1 | sed -n 's/.*latest=\([^[:space:]]*\).*/\1/p')
  fi
  if [ -n "$latest_portal" ] && need_update "$cur_portal" "$latest_portal"; then
    UPDATES="${UPDATES}  - TAK Portal: current ${cur_portal:-unknown}, latest ${latest_portal}\n"
    SIG="${SIG}takportal:${latest_portal};"
  fi
fi

[ -z "$UPDATES" ] && exit 0

# Only send if we haven't sent for this exact set of updates, or last send was >7 days ago
mkdir -p /var/lib/takguard
SHOULD_SEND=false
if [ ! -f "$STATE_FILE" ]; then
  SHOULD_SEND=true
elif [ -n "$(find "$STATE_FILE" -mtime +7 2>/dev/null)" ]; then
  SHOULD_SEND=true
else
  old_sig=$(cat "$STATE_FILE" 2>/dev/null)
  [ "$old_sig" != "$SIG" ] && SHOULD_SEND=true
fi

if $SHOULD_SEND; then
  printf '%s' "$SIG" > "$STATE_FILE"
  TS="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  SUBJ="infra-TAK: Updates available on $SERVER_IDENTIFIER"
  BODY="One or more updates are available for your infra-TAK stack.

Server: $SERVER_IDENTIFIER
Time (UTC): $TS

Updates available:
$(printf '%b' "$UPDATES")

To update:
- infra-TAK: Console → Update Now (or pull + restart)
- Authentik: Authentik page → Update
- MediaMTX: MediaMTX page → Update / redeploy
- CloudTAK: CloudTAK page → Update
- TAK Portal: TAK Portal page → Update
"

  [ -n "$ALERT_EMAIL" ] && echo -e "$BODY" | mail -s "$SUBJ" "$ALERT_EMAIL"
  if [ -f /opt/tak-guarddog/sms_send.sh ]; then
    TMPF="/tmp/gd-updates-$$.txt"
    printf '%s' "$BODY" > "$TMPF"
    /opt/tak-guarddog/sms_send.sh "$SUBJ" "$TMPF" 2>/dev/null || true
    rm -f "$TMPF"
  fi
fi
