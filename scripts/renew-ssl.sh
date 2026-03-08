#!/bin/bash
# =============================================================================
# SSL Certificate Renewal — Cron Job
# =============================================================================
# Add to crontab:
#   0 3 * * * cd /path/to/jorss-gbo && ./scripts/renew-ssl.sh >> /var/log/jorss-ssl-renew.log 2>&1
# =============================================================================

set -euo pipefail

COMPOSE_FILE="docker-compose.production.yml"

echo "[$(date)] Starting SSL certificate renewal check..."

# Renew via the certbot container (webroot mode, nginx stays running)
docker compose -f "$COMPOSE_FILE" run --rm certbot \
    certbot renew --webroot -w /var/www/certbot --quiet

# Reload nginx to pick up any renewed certs
docker compose -f "$COMPOSE_FILE" exec nginx nginx -s reload

echo "[$(date)] SSL renewal check complete."
