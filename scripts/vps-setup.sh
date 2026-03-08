#!/bin/bash
# =============================================================================
# Jorss-GBO — VPS Initial Provisioning (Ubuntu/Debian)
# =============================================================================
# Run on a fresh VPS as root:
#   curl -sSL https://raw.githubusercontent.com/YOUR_REPO/main/scripts/vps-setup.sh | bash
#   — or —
#   bash scripts/vps-setup.sh
#
# This script:
#   1. Updates system packages
#   2. Installs Docker + Docker Compose plugin
#   3. Installs fail2ban + configures UFW firewall
#   4. Creates app user and directory
#   5. Prints next steps
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()   { echo -e "${BLUE}[setup]${NC} $*"; }
ok()    { echo -e "${GREEN}[  ok ]${NC} $*"; }
warn()  { echo -e "${YELLOW}[ warn]${NC} $*"; }
error() { echo -e "${RED}[error]${NC} $*"; exit 1; }

# Must run as root
if [ "$(id -u)" -ne 0 ]; then
    error "This script must be run as root (use sudo)"
fi

echo ""
echo -e "${BLUE}=============================================${NC}"
echo -e "${BLUE} Jorss-GBO VPS Setup${NC}"
echo -e "${BLUE}=============================================${NC}"
echo ""

# -------------------------------------------------------------------------
# 1. Update system packages
# -------------------------------------------------------------------------
log "Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq
ok "System packages updated"

# -------------------------------------------------------------------------
# 2. Install Docker
# -------------------------------------------------------------------------
log "Installing Docker..."

if command -v docker >/dev/null 2>&1; then
    ok "Docker already installed: $(docker --version)"
else
    # Install prerequisites
    apt-get install -y -qq ca-certificates curl gnupg lsb-release

    # Add Docker GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Add Docker repository
    # shellcheck disable=SC1091
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$(. /etc/os-release && echo "$ID") \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    systemctl enable docker
    systemctl start docker
    ok "Docker installed: $(docker --version)"
fi

# Verify compose plugin
docker compose version >/dev/null 2>&1 || error "Docker Compose plugin not found"
ok "Docker Compose: $(docker compose version --short)"

# -------------------------------------------------------------------------
# 3. Install security tools
# -------------------------------------------------------------------------
log "Installing fail2ban..."
apt-get install -y -qq fail2ban
systemctl enable fail2ban
systemctl start fail2ban
ok "fail2ban installed and running"

log "Configuring UFW firewall..."
apt-get install -y -qq ufw

# Reset UFW to defaults
ufw --force reset >/dev/null 2>&1

# Default policies
ufw default deny incoming
ufw default allow outgoing

# Allow SSH, HTTP, HTTPS
ufw allow 22/tcp comment "SSH"
ufw allow 80/tcp comment "HTTP"
ufw allow 443/tcp comment "HTTPS"

# Enable UFW
ufw --force enable
ok "UFW firewall configured (ports 22, 80, 443)"

# -------------------------------------------------------------------------
# 4. Create app user and directory
# -------------------------------------------------------------------------
APP_USER="jorss"
APP_DIR="/opt/jorss-gbo"

log "Setting up app user and directory..."

if id "$APP_USER" >/dev/null 2>&1; then
    ok "User '$APP_USER' already exists"
else
    useradd -m -s /bin/bash "$APP_USER"
    usermod -aG docker "$APP_USER"
    ok "Created user '$APP_USER' with Docker access"
fi

mkdir -p "$APP_DIR"
chown "$APP_USER":"$APP_USER" "$APP_DIR"
ok "App directory: $APP_DIR"

# -------------------------------------------------------------------------
# 5. Print next steps
# -------------------------------------------------------------------------
echo ""
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN} VPS Setup Complete${NC}"
echo -e "${GREEN}=============================================${NC}"
echo ""
echo "Next steps:"
echo ""
echo "  1. Clone the repository:"
echo "     su - $APP_USER"
echo "     git clone <your-repo-url> $APP_DIR"
echo "     cd $APP_DIR"
echo ""
echo "  2. Create production config:"
echo "     cp .env.production.template .env.production"
echo "     nano .env.production    # Fill in all CHANGE_ME values"
echo ""
echo "  3. Deploy:"
echo "     ./scripts/deploy.sh"
echo ""
echo "  4. Set up SSL renewal cron:"
echo "     crontab -e"
echo "     # Add: 0 3 * * * cd $APP_DIR && ./scripts/renew-ssl.sh >> /var/log/jorss-ssl-renew.log 2>&1"
echo ""
