#!/usr/bin/env bash
# ==============================================================================
# SeeGuide EC2 Production Deployment Script
# Targets: Ubuntu 22.04 / 24.04 LTS (AWS Free Tier t4g.micro ARM64 / t2.micro x86_64)
# Configures: Python 3 runtime, virtualenv, systemd service, Caddy TLS reverse proxy
# ==============================================================================

set -euo pipefail

echo "===================================================================="
echo "Starting SeeGuide Single-Command AWS Free Tier Deployment"
echo "===================================================================="

# Check root/sudo permissions
if [[ $EUID -ne 0 ]]; then
   echo "ERROR: This deployment script must be run as root or with sudo." 
   exit 1
fi

APP_DIR="/opt/seeguide"
APP_USER="${SUDO_USER:-ubuntu}"
ENV_FILE="${APP_DIR}/.env"

# 1. System Package Updates & Prerequisites
echo "[1/7] Updating system packages and installing prerequisites..."
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    curl \
    debian-keyring \
    debian-archive-keyring \
    apt-transport-https

# 2. Install Official Caddy Web Server
echo "[2/7] Installing Caddy reverse proxy server..."
if ! command -v caddy &> /dev/null; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg --yes
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -y
    DEBIAN_FRONTEND=noninteractive apt-get install -y caddy
    echo "Caddy installed successfully."
else
    echo "Caddy is already installed."
fi

# 3. Repository Provisioning
echo "[3/7] Provisioning SeeGuide repository in ${APP_DIR}..."
if [[ ! -d "${APP_DIR}" ]]; then
    if [[ -d "$(pwd)/server" && -d "$(pwd)/vision" ]]; then
        # Running from inside cloned repo, copy to /opt/seeguide
        mkdir -p "${APP_DIR}"
        cp -r ./* "${APP_DIR}/"
    else
        git clone https://github.com/SeeGuide/seeguide.git "${APP_DIR}"
    fi
else
    echo "Directory ${APP_DIR} already exists. Preserving contents."
fi

# Ensure application user ownership
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

# 4. Python Virtual Environment Setup
echo "[4/7] Creating Python virtual environment and installing dependencies..."
sudo -u "${APP_USER}" python3 -m venv "${APP_DIR}/venv"
sudo -u "${APP_USER}" "${APP_DIR}/venv/bin/pip" install --upgrade pip setuptools wheel
sudo -u "${APP_USER}" "${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

# 5. Environment File Setup
echo "[5/7] Verifying production environment configuration..."
if [[ ! -f "${ENV_FILE}" ]]; then
    cat <<EOF > "${ENV_FILE}"
# SeeGuide Production Configuration
ENVIRONMENT=production
LOG_LEVEL=INFO
HOST=127.0.0.1
PORT=8000
USE_MOCK_STORAGE=True
DYNAMODB_TRACE_TABLE=seeguide-traces
AWS_DEFAULT_REGION=us-east-1
DOMAIN=seeguide.duckdns.org
EOF
    chown "${APP_USER}:${APP_USER}" "${ENV_FILE}"
    chmod 600 "${ENV_FILE}"
    echo "Generated default production .env at ${ENV_FILE}"
else
    echo "Existing .env found at ${ENV_FILE}"
fi

# 6. Systemd Service Installation
echo "[6/7] Creating systemd service for SeeGuide backend (/etc/systemd/system/seeguide.service)..."
cat <<EOF > /etc/systemd/system/seeguide.service
[Unit]
Description=SeeGuide Assistive Vision WebSocket Backend
After=network.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=-${ENV_FILE}
ExecStart=${APP_DIR}/venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8000 --workers 1 --loop uvloop
Restart=always
RestartSec=5s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=seeguide

# Security Sandbox
ProtectSystem=full
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable seeguide
systemctl restart seeguide
echo "SeeGuide backend service started and enabled."

# 7. Caddyfile Configuration & Service Restart
echo "[7/7] Configuring Caddy reverse proxy..."
if [[ -f "${APP_DIR}/infra/Caddyfile" ]]; then
    cp "${APP_DIR}/infra/Caddyfile" /etc/caddy/Caddyfile
fi

mkdir -p /var/log/caddy
chown -R caddy:caddy /var/log/caddy

systemctl restart caddy
systemctl enable caddy

echo "===================================================================="
echo "SeeGuide Deployment COMPLETE!"
echo "Service status: $(systemctl is-active seeguide)"
echo "Caddy status:   $(systemctl is-active caddy)"
echo "Application URL: https://seeguide.duckdns.org (or configured DOMAIN)"
echo "===================================================================="
