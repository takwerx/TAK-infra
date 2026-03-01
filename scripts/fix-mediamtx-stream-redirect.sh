#!/bin/bash
# Fix "too many redirects" on https://stream.<fqdn> by ensuring the LDAP overlay
# is applied and LDAP_ENABLED=1 is set. Run on the server as root after MediaMTX deploy.
# Usage: sudo bash fix-mediamtx-stream-redirect.sh
# Then clear cookies for stream.<yourdomain> and try again.

set -e
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EDITOR_DIR="/opt/mediamtx-webeditor"
EDITOR_FILE="${EDITOR_DIR}/mediamtx_config_editor.py"
OVERLAY_SRC="${REPO_DIR}/mediamtx_ldap_overlay.py"
OVERLAY_DST="${EDITOR_DIR}/mediamtx_ldap_overlay.py"
SVC_FILE="/etc/systemd/system/mediamtx-webeditor.service"

if [ ! -f "$EDITOR_FILE" ]; then
  echo "MediaMTX web editor not found at $EDITOR_FILE. Deploy MediaMTX from infra-TAK first."
  exit 1
fi

# 1) Copy overlay
if [ -f "$OVERLAY_SRC" ]; then
  cp "$OVERLAY_SRC" "$OVERLAY_DST"
  echo "✓ Copied mediamtx_ldap_overlay.py"
else
  echo "⚠ $OVERLAY_SRC not found (run from infra-TAK repo). Skipping overlay copy."
fi

# 2) Inject overlay after "app = Flask(" if not already present
if grep -q "LDAP overlay" "$EDITOR_FILE"; then
  echo "✓ LDAP overlay already present in editor"
else
  python3 << PY
p = "$EDITOR_FILE"
with open(p) as f:
    lines = f.readlines()
block = """
# --- infra-TAK LDAP overlay ---
import os as _os
if _os.environ.get('LDAP_ENABLED'):
    import sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from mediamtx_ldap_overlay import apply_ldap_overlay
    apply_ldap_overlay(app)
# --- end LDAP overlay ---
"""
inserted = False
for i, line in enumerate(lines):
    if 'app = Flask(' in line:
        lines.insert(i + 1, block + chr(10))
        inserted = True
        break
if not inserted:
    for i, line in enumerate(lines):
        if 'app.run(' in line:
            lines.insert(i, block + chr(10))
            inserted = True
            break
if inserted:
    with open(p, 'w') as f:
        f.writelines(lines)
    print("✓ Injected LDAP overlay into editor")
else:
    print("⚠ Could not find inject point (app = Flask / app.run)")
    exit(1)
PY
fi

# 3) Ensure systemd has LDAP_ENABLED and Authentik env
if ! grep -q 'Environment=LDAP_ENABLED' "$SVC_FILE" 2>/dev/null; then
  AUTH_DIR="${AUTH_DIR:-$HOME/authentik}"
  [ -d "$AUTH_DIR" ] || AUTH_DIR="/root/authentik"
  TOKEN=""
  if [ -f "${AUTH_DIR}/.env" ]; then
    TOKEN=$(grep -E '^AUTHENTIK_BOOTSTRAP_TOKEN=|^AUTHENTIK_TOKEN=' "${AUTH_DIR}/.env" | head -1 | cut -d= -f2- | tr -d '\r')
  fi
  # Insert after Environment=MEDIAMTX_API_URL (use Python to avoid sed escaping of token)
  python3 - "$SVC_FILE" "$TOKEN" << 'PY'
import sys
path = sys.argv[1]
token = sys.argv[2]
with open(path) as f:
    lines = f.readlines()
new_lines = []
for line in lines:
    new_lines.append(line)
    if 'Environment=MEDIAMTX_API_URL' in line and 'LDAP_ENABLED' not in ''.join(lines):
        new_lines.append('Environment=LDAP_ENABLED=1\n')
        new_lines.append('Environment=AUTHENTIK_API_URL=http://127.0.0.1:9090\n')
        new_lines.append(f'Environment=AUTHENTIK_TOKEN={token}\n')
with open(path, 'w') as f:
    f.writelines(new_lines)
PY
  echo "✓ Added LDAP_ENABLED and Authentik env to systemd unit"
else
  echo "✓ systemd already has LDAP env"
fi

# 4) Restart
systemctl daemon-reload
systemctl restart mediamtx-webeditor
echo "✓ Restarted mediamtx-webeditor"

echo ""
echo "Next: In Chrome/Firefox, clear cookies for stream.<yourdomain> (or clear all for the site),"
echo "then open https://stream.<yourdomain> again and log in with Authentik if prompted."
