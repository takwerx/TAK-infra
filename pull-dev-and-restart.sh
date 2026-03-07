#!/bin/bash
# Pull latest from origin/dev and restart the console.
# Run from the infra-TAK clone (e.g. /root/infra-TAK). Use: ./pull-dev-and-restart.sh
# For non-interactive use: sudo ./pull-dev-and-restart.sh
set -e
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$INSTALL_DIR"

git fetch origin
git checkout dev
git pull origin dev

echo "Restarting takwerx-console..."
sudo systemctl restart takwerx-console
echo "Done. Console restarted."
