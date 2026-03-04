#!/usr/bin/env bash
##############################################################################
# Set Docker container log limits (max-size, max-file) to prevent a single
# container (e.g. Node-RED, Authentik LDAP) from filling the disk.
# Run once per server; then: sudo systemctl restart docker
##############################################################################

set -e

DAEMON_JSON="/etc/docker/daemon.json"
LOG_OPTS='{"max-size": "50m", "max-file": "3"}'

if [ ! -d /etc/docker ]; then
    echo "Error: /etc/docker not found. Install Docker first."
    exit 1
fi

if [ "$EUID" -ne 0 ]; then
    echo "Run as root: sudo $0"
    exit 1
fi

# Merge or create daemon.json
if [ -f "$DAEMON_JSON" ] && [ -s "$DAEMON_JSON" ]; then
    # Merge: add or update log-driver and log-opts, keep other keys
    python3 -c "
import json, sys
try:
    with open('$DAEMON_JSON') as f:
        d = json.load(f)
except (json.JSONDecodeError, FileNotFoundError):
    d = {}
d['log-driver'] = 'json-file'
d['log-opts'] = {'max-size': '50m', 'max-file': '3'}
with open('$DAEMON_JSON', 'w') as f:
    json.dump(d, f, indent=2)
    f.write('\n')
print('Updated existing daemon.json with log limits.')
" || {
        echo "Failed to merge daemon.json. Writing new file (backup existing)."
        [ -f "$DAEMON_JSON" ] && cp -a "$DAEMON_JSON" "${DAEMON_JSON}.bak"
        cat > "$DAEMON_JSON" << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  }
}
EOF
    }
else
    mkdir -p /etc/docker
    cat > "$DAEMON_JSON" << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  }
}
EOF
    echo "Created daemon.json with log limits."
fi

echo ""
echo "Docker log limits are set (50 MB per file, 3 files per container = 150 MB max per container)."
echo "Restart Docker for limits to apply:  sudo systemctl restart docker"
echo "Note: Existing containers will restart; do this in a maintenance window if needed."
