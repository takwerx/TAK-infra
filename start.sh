#!/bin/bash
##############################################################################
# TAKWERX Console - Launcher
# Emergency Services Infrastructure Management Platform
#
# This is the ONLY script users need to run.
# Everything else happens in the browser.
##############################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$INSTALL_DIR/.config"
AUTH_FILE="$CONFIG_DIR/auth.json"
SETTINGS_FILE="$CONFIG_DIR/settings.json"

clear
echo ""
echo -e "${CYAN}${BOLD}  ╔════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}  ║         TAKWERX Console                       ║${NC}"
echo -e "${CYAN}${BOLD}  ║   Emergency Services Infrastructure Platform  ║${NC}"
echo -e "${CYAN}${BOLD}  ╚════════════════════════════════════════════════╝${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}ERROR: This script must be run as root${NC}"
    echo "Please run: sudo $0"
    exit 1
fi

# ==========================================
# Detect Operating System
# ==========================================
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID="$ID"
        OS_VERSION="$VERSION_ID"
        OS_NAME="$PRETTY_NAME"
    else
        echo -e "${RED}ERROR: Cannot detect operating system${NC}"
        exit 1
    fi

    case "$OS_ID" in
        ubuntu)
            if [[ "$OS_VERSION" == "22.04"* ]]; then
                OS_TYPE="ubuntu-22.04"
                PKG_MGR="apt"
            elif [[ "$OS_VERSION" == "24.04"* ]]; then
                OS_TYPE="ubuntu-24.04"
                PKG_MGR="apt"
            else
                echo -e "${YELLOW}WARNING: Ubuntu $OS_VERSION not tested. Ubuntu 22.04 recommended.${NC}"
                OS_TYPE="ubuntu-$OS_VERSION"
                PKG_MGR="apt"
            fi
            ;;
        rocky|rhel)
            if [[ "$OS_VERSION" == 9* ]]; then
                OS_TYPE="rocky-9"
                PKG_MGR="dnf"
            else
                echo -e "${YELLOW}WARNING: $OS_NAME not tested. Rocky 9 recommended.${NC}"
                OS_TYPE="rocky-$OS_VERSION"
                PKG_MGR="dnf"
            fi
            ;;
        *)
            echo -e "${YELLOW}WARNING: $OS_NAME is not officially supported.${NC}"
            echo -e "${YELLOW}Supported: Ubuntu 22.04, Rocky Linux 9${NC}"
            OS_TYPE="$OS_ID-$OS_VERSION"
            PKG_MGR="unknown"
            ;;
    esac

    echo -e "  Detected: ${GREEN}$OS_NAME${NC}"
    echo -e "  Type:     ${GREEN}$OS_TYPE${NC}"
    echo ""
}

# ==========================================
# Wait for Unattended Upgrades
# ==========================================
wait_for_upgrades() {
    if pgrep -f "/usr/bin/unattended-upgrade$" > /dev/null 2>&1; then
        echo -e "${YELLOW}  System upgrades in progress, waiting...${NC}"
        SECONDS=0
        while pgrep -f "/usr/bin/unattended-upgrade$" > /dev/null 2>&1; do
            printf "\r  Waiting... %02d:%02d elapsed" $((SECONDS/60)) $((SECONDS%60))
            sleep 2
        done
        echo ""
        echo -e "  ${GREEN}✓ System updates complete${NC}"
        echo ""
    fi
}

# ==========================================
# Install Python Dependencies
# ==========================================
install_dependencies() {
    echo -e "  Installing dependencies..."

    case "$PKG_MGR" in
        apt)
            export DEBIAN_FRONTEND=noninteractive
            export NEEDRESTART_MODE=a
            apt-get update -qq > /dev/null 2>&1
            apt-get install -y python3 python3-pip python3-venv openssl > /dev/null 2>&1
            ;;
        dnf)
            dnf install -y python3 python3-pip openssl > /dev/null 2>&1
            ;;
        *)
            echo -e "${RED}  Cannot auto-install dependencies for $PKG_MGR${NC}"
            echo "  Please install: python3, python3-pip, python3-venv, openssl"
            exit 1
            ;;
    esac

    # Create virtual environment if it doesn't exist
    if [ ! -d "$INSTALL_DIR/.venv" ]; then
        python3 -m venv "$INSTALL_DIR/.venv" 2>/dev/null || python3 -m venv "$INSTALL_DIR/.venv" --without-pip
    fi

    # Install Flask and dependencies in venv
    "$INSTALL_DIR/.venv/bin/pip" install --quiet flask psutil werkzeug 2>/dev/null || \
        "$INSTALL_DIR/.venv/bin/pip" install flask psutil werkzeug

    echo -e "  ${GREEN}✓ Dependencies installed${NC}"
    echo ""
}

# ==========================================
# First-Time Setup (password only)
# ==========================================
first_time_setup() {
    mkdir -p "$CONFIG_DIR"
    chmod 700 "$CONFIG_DIR"

    echo -e "${BOLD}  First-time setup${NC}"
    echo ""

    # Set admin password
    while true; do
        read -s -p "  Set admin password: " ADMIN_PASS
        echo ""
        read -s -p "  Confirm password:   " ADMIN_PASS_CONFIRM
        echo ""

        if [ -z "$ADMIN_PASS" ]; then
            echo -e "  ${RED}Password cannot be empty${NC}"
            continue
        fi

        if [ "$ADMIN_PASS" != "$ADMIN_PASS_CONFIRM" ]; then
            echo -e "  ${RED}Passwords do not match${NC}"
            continue
        fi

        break
    done

    # Hash the password using Python
    PASS_HASH=$("$INSTALL_DIR/.venv/bin/python3" -c "
from werkzeug.security import generate_password_hash
import sys
print(generate_password_hash(sys.argv[1]))
" "$ADMIN_PASS")

    # Save auth config
    cat > "$AUTH_FILE" << EOF
{
    "password_hash": "$PASS_HASH",
    "created": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
}
EOF
    chmod 600 "$AUTH_FILE"

    # Detect server IP
    SERVER_IP=$(hostname -I | awk '{print $1}')

    # Save settings — always start in IP/self-signed mode
    # FQDN setup happens in the browser through the Caddy module
    cat > "$SETTINGS_FILE" << EOF
{
    "ssl_mode": "self-signed",
    "fqdn": "",
    "server_ip": "$SERVER_IP",
    "os_type": "$OS_TYPE",
    "os_name": "$OS_NAME",
    "pkg_mgr": "$PKG_MGR",
    "console_port": 5001,
    "install_dir": "$INSTALL_DIR",
    "created": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
}
EOF
    chmod 600 "$SETTINGS_FILE"

    echo ""
    echo -e "  ${GREEN}✓ Configuration saved${NC}"
}

# ==========================================
# Generate Self-Signed Certificate
# ==========================================
generate_self_signed_cert() {
    CERT_DIR="$CONFIG_DIR/ssl"
    mkdir -p "$CERT_DIR"

    if [ ! -f "$CERT_DIR/console.key" ]; then
        echo -e "  Generating self-signed certificate..."
        
        SERVER_IP=$(hostname -I | awk '{print $1}')
        
        openssl req -x509 -newkey rsa:4096 \
            -keyout "$CERT_DIR/console.key" \
            -out "$CERT_DIR/console.crt" \
            -sha256 -days 3650 -nodes \
            -subj "/C=US/ST=TAK/L=TAK/O=TAKWERX/CN=$SERVER_IP" \
            -addext "subjectAltName=IP:$SERVER_IP,IP:127.0.0.1,DNS:localhost" \
            2>/dev/null

        chmod 600 "$CERT_DIR/console.key"
        chmod 644 "$CERT_DIR/console.crt"
        
        echo -e "  ${GREEN}✓ Self-signed certificate generated${NC}"
    fi
}

# ==========================================
# Create systemd Service
# ==========================================
create_service() {
    cat > /etc/systemd/system/takwerx-console.service << EOF
[Unit]
Description=TAKWERX Console - Infrastructure Management Platform
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/.venv/bin/python3 $INSTALL_DIR/app.py
WorkingDirectory=$INSTALL_DIR
Restart=always
RestartSec=5
User=root
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable takwerx-console > /dev/null 2>&1
}

# ==========================================
# Main
# ==========================================
detect_os
wait_for_upgrades
install_dependencies

# First-time setup if no auth file exists
if [ ! -f "$AUTH_FILE" ]; then
    first_time_setup
fi

# Always use self-signed cert for console (Caddy handles FQDN SSL)
generate_self_signed_cert

# Create and start systemd service
create_service

# Stop existing instance if running
systemctl stop takwerx-console 2>/dev/null || true
sleep 1

# Start the console
systemctl start takwerx-console

# Get access URL
SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo -e "${GREEN}${BOLD}  ╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}  ║         TAKWERX Console is running!           ║${NC}"
echo -e "${GREEN}${BOLD}  ╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Access:${NC} https://$SERVER_IP:5001"
echo -e "  ${YELLOW}(Accept the self-signed certificate warning in your browser)${NC}"
echo ""
echo -e "  ${BOLD}Service:${NC} systemctl status takwerx-console"
echo -e "  ${BOLD}Logs:${NC}    journalctl -u takwerx-console -f"
echo ""
echo -e "  ${CYAN}Tip: Set up a domain name through the Caddy module${NC}"
echo -e "  ${CYAN}in the console for proper SSL and full functionality.${NC}"
echo ""
