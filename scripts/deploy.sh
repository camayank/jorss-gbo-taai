#!/bin/bash
# =============================================================================
# Jorss-GBO — One-Command VPS Deployment
# =============================================================================
# Usage: ./scripts/deploy.sh
#
# This script:
#   1. Checks prerequisites (docker, docker compose)
#   2. Validates .env.production
#   3. Obtains SSL certificates (first run only)
#   4. Builds and starts all services
#   5. Runs database migrations
#   6. Prints status and URLs
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

COMPOSE_FILE="docker-compose.production.yml"
ENV_FILE=".env.production"
ENV_TEMPLATE=".env.production.template"

log()   { echo -e "${BLUE}[deploy]${NC} $*"; }
ok()    { echo -e "${GREEN}[  ok  ]${NC} $*"; }
warn()  { echo -e "${YELLOW}[ warn ]${NC} $*"; }
error() { echo -e "${RED}[error]${NC} $*"; exit 1; }

# -------------------------------------------------------------------------
# 1. Check prerequisites
# -------------------------------------------------------------------------
log "Checking prerequisites..."

command -v docker >/dev/null 2>&1 || error "Docker is not installed. Run scripts/vps-setup.sh first."
docker compose version >/dev/null 2>&1 || error "Docker Compose plugin is not installed."

ok "Docker and Docker Compose found"

# -------------------------------------------------------------------------
# 2. Check .env.production
# -------------------------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_TEMPLATE" ]; then
        warn ".env.production not found — copying from template"
        cp "$ENV_TEMPLATE" "$ENV_FILE"
        echo ""
        echo -e "${YELLOW}========================================${NC}"
        echo -e "${YELLOW} IMPORTANT: Edit .env.production now!${NC}"
        echo -e "${YELLOW}========================================${NC}"
        echo ""
        echo "  1. Set DOMAIN to your domain name"
        echo "  2. Set all CHANGE_ME values"
        echo "  3. Generate security secrets with:"
        echo "     python3 -c \"import secrets; [print(f'{k}={secrets.token_hex(32)}') for k in ['APP_SECRET_KEY','JWT_SECRET','AUTH_SECRET_KEY','CSRF_SECRET_KEY','PASSWORD_SALT','ENCRYPTION_MASTER_KEY','SSN_HASH_SECRET','SERIALIZER_SECRET_KEY','AUDIT_HMAC_KEY']]\""
        echo ""
        echo "  Then re-run: ./scripts/deploy.sh"
        exit 1
    else
        error "Neither .env.production nor .env.production.template found"
    fi
fi

ok ".env.production exists"

# -------------------------------------------------------------------------
# 3. Validate DOMAIN
# -------------------------------------------------------------------------
# shellcheck disable=SC1090
source <(grep -E '^DOMAIN=' "$ENV_FILE")

if [ -z "${DOMAIN:-}" ] || [ "$DOMAIN" = "CHANGE_ME" ]; then
    error "DOMAIN is not set in .env.production. Set it to your domain (e.g. app.example.com)"
fi

ok "DOMAIN=$DOMAIN"

# Check for remaining CHANGE_ME values
CHANGE_ME_COUNT=$(grep -c 'CHANGE_ME' "$ENV_FILE" || true)
if [ "$CHANGE_ME_COUNT" -gt 0 ]; then
    warn "$CHANGE_ME_COUNT placeholder(s) still contain CHANGE_ME — make sure all are replaced"
fi

# -------------------------------------------------------------------------
# 4. Update nginx config with domain
# -------------------------------------------------------------------------
log "Configuring nginx for $DOMAIN..."

if [ -f "nginx/nginx.production.conf" ]; then
    sed -i.bak "s/YOUR_DOMAIN/$DOMAIN/g" "nginx/nginx.production.conf"
    rm -f "nginx/nginx.production.conf.bak"
    ok "Nginx configured for $DOMAIN"
else
    error "nginx/nginx.production.conf not found"
fi

# -------------------------------------------------------------------------
# 5. SSL certificates
# -------------------------------------------------------------------------
log "Checking SSL certificates..."

CERT_PATH="/etc/letsencrypt/live/$DOMAIN"

# Check if certs exist in the certbot volume (via docker)
CERTS_EXIST=false
if docker volume inspect jorss-gbo_certbot-certs >/dev/null 2>&1; then
    if docker run --rm -v jorss-gbo_certbot-certs:/etc/letsencrypt alpine test -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" 2>/dev/null; then
        CERTS_EXIST=true
    fi
fi

if [ "$CERTS_EXIST" = true ]; then
    ok "SSL certificates already exist for $DOMAIN"
else
    log "Obtaining SSL certificates from Let's Encrypt..."
    warn "Make sure DNS for $DOMAIN points to this server's IP"

    # Stop nginx if running (port 80 must be free for standalone)
    docker compose -f "$COMPOSE_FILE" stop nginx 2>/dev/null || true

    # Get certs using certbot standalone mode
    docker run --rm \
        -p 80:80 \
        -v jorss-gbo_certbot-certs:/etc/letsencrypt \
        -v jorss-gbo_certbot-www:/var/www/certbot \
        certbot/certbot certonly \
        --standalone \
        --non-interactive \
        --agree-tos \
        --email "$(grep -E '^SUPPORT_EMAIL=' "$ENV_FILE" | cut -d= -f2 | tr -d '"' || echo "admin@$DOMAIN")" \
        -d "$DOMAIN" \
        || error "Failed to obtain SSL certificates. Ensure DNS is configured and port 80 is open."

    ok "SSL certificates obtained for $DOMAIN"
fi

# -------------------------------------------------------------------------
# 6. Build and start
# -------------------------------------------------------------------------
log "Building Docker images..."
docker compose -f "$COMPOSE_FILE" build
ok "Images built"

log "Starting services..."
docker compose -f "$COMPOSE_FILE" up -d
ok "Services started"

# -------------------------------------------------------------------------
# 7. Wait for health checks
# -------------------------------------------------------------------------
log "Waiting for services to be healthy..."

MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if docker compose -f "$COMPOSE_FILE" ps --format json 2>/dev/null | grep -q '"Health":"healthy"' 2>/dev/null; then
        # Check if app specifically is healthy
        APP_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' jorss-gbo-app 2>/dev/null || echo "unknown")
        if [ "$APP_HEALTH" = "healthy" ]; then
            break
        fi
    fi
    sleep 2
    WAITED=$((WAITED + 2))
    printf "."
done
echo ""

if [ $WAITED -ge $MAX_WAIT ]; then
    warn "Timed out waiting for health checks — checking status..."
    docker compose -f "$COMPOSE_FILE" ps
    echo ""
    warn "Services may still be starting. Check logs: docker compose -f $COMPOSE_FILE logs -f"
else
    ok "All services healthy"
fi

# -------------------------------------------------------------------------
# 8. Run database migrations
# -------------------------------------------------------------------------
log "Running database migrations..."
docker compose -f "$COMPOSE_FILE" exec app alembic -c alembic.ini upgrade head \
    && ok "Migrations complete" \
    || warn "Migration failed — check logs"

# -------------------------------------------------------------------------
# 9. Print status
# -------------------------------------------------------------------------
echo ""
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN} Jorss-GBO Deployment Complete${NC}"
echo -e "${GREEN}=============================================${NC}"
echo ""
docker compose -f "$COMPOSE_FILE" ps
echo ""
echo -e "  ${BLUE}App:${NC}     https://$DOMAIN"
echo -e "  ${BLUE}Health:${NC}  https://$DOMAIN/health/live"
echo -e "  ${BLUE}Logs:${NC}    docker compose -f $COMPOSE_FILE logs -f"
echo -e "  ${BLUE}Stop:${NC}    docker compose -f $COMPOSE_FILE down"
echo ""
echo -e "  ${YELLOW}SSL renewal cron:${NC}"
echo "  0 3 * * * cd $(pwd) && ./scripts/renew-ssl.sh >> /var/log/jorss-ssl-renew.log 2>&1"
echo ""
