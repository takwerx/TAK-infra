#!/bin/bash
# Reset the infra-TAK console admin password. Run on the server from the install directory:
#   cd /root/infra-TAK   # or your install path
#   sudo ./reset-console-password.sh
set -e
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$INSTALL_DIR/.config"
AUTH_FILE="$CONFIG_DIR/auth.json"

if [ ! -d "$INSTALL_DIR/.venv" ]; then
    echo "Error: .venv not found. Run this from the infra-TAK install directory."
    exit 1
fi

mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

echo ""
echo "Reset console admin password (install: $INSTALL_DIR)"
echo ""

read -s -p "New password: " NEW_PASS
echo ""
read -s -p "Confirm:      " NEW_PASS_CONFIRM
echo ""

if [ -z "$NEW_PASS" ]; then
    echo "Password cannot be empty."
    exit 1
fi
if [ "$NEW_PASS" != "$NEW_PASS_CONFIRM" ]; then
    echo "Passwords do not match."
    exit 1
fi

PASS_HASH=$("$INSTALL_DIR/.venv/bin/python3" -c "
from werkzeug.security import generate_password_hash
import sys
print(generate_password_hash(sys.argv[1]))
" "$NEW_PASS")

cat > "$AUTH_FILE" << EOF
{
    "password_hash": "$PASS_HASH",
    "created": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
}
EOF
chmod 600 "$AUTH_FILE"

echo "Password updated. Restarting console..."
systemctl restart takwerx-console 2>/dev/null || true
echo "Done. Log in at https://<this-server-ip>:5001 with the new password."
echo ""
