# Jorss-GBO — Complete Coolify Deployment Guide

> Step-by-step guide to deploying the full Jorss-GBO stack on a VPS using **Coolify** as the self-hosted PaaS.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [VPS & Coolify Installation](#2-vps--coolify-installation)
3. [Server Setup in Coolify](#3-server-setup-in-coolify)
4. [Project Setup in Coolify](#4-project-setup-in-coolify)
5. [Database: PostgreSQL 16](#5-database-postgresql-16)
6. [Cache & Broker: Redis 7](#6-cache--broker-redis-7)
7. [Backend: FastAPI Application](#7-backend-fastapi-application)
8. [Background Workers: Celery](#8-background-workers-celery)
9. [Frontend: Jinja2 Templates & Static Assets](#9-frontend-jinja2-templates--static-assets)
10. [Middleware Configuration](#10-middleware-configuration)
11. [API Layer](#11-api-layer)
12. [Domain, SSL & Reverse Proxy](#12-domain-ssl--reverse-proxy)
13. [Environment Variables](#13-environment-variables)
14. [Database Migrations](#14-database-migrations)
15. [Automated Backups](#15-automated-backups)
16. [Health Checks & Monitoring](#16-health-checks--monitoring)
17. [CI/CD: Auto-Deploy on Push](#17-cicd-auto-deploy-on-push)
18. [Maintenance & Operations](#18-maintenance--operations)
19. [Troubleshooting](#19-troubleshooting)

---

## 1. Architecture Overview

```
                    ┌─────────────────────────────────────────┐
                    │              VPS (6 vCores, 12GB RAM)   │
                    │                                         │
  Internet ──────► │  Coolify (manages everything)            │
       :80/:443    │  ┌─────────────────────────────────┐     │
                   │  │  Traefik (auto-SSL via LE)      │     │
                   │  │  ├── app.yourdomain.com ──────────────┤
                   │  │  │                              │     │
                   │  └──┼──────────────────────────────┘     │
                   │     │                                    │
                   │     ▼                                    │
                   │  ┌──────────┐  ┌───────────┐            │
                   │  │ FastAPI  │  │ PostgreSQL │            │
                   │  │ Gunicorn │◄►│   16       │            │
                   │  │ 4 workers│  └───────────┘            │
                   │  └────┬─────┘  ┌───────────┐            │
                   │       │        │  Redis 7   │            │
                   │       ├───────►│ (sessions, │            │
                   │       │        │  cache,    │            │
                   │  ┌────┴─────┐  │  broker)   │            │
                   │  │ Celery   │◄►└───────────┘            │
                   │  │ Worker   │                            │
                   │  │ + Beat   │                            │
                   │  └──────────┘                            │
                   └─────────────────────────────────────────┘
```

**Key difference from raw Docker Compose:**
- Coolify replaces Nginx + Certbot with **Traefik** (built-in reverse proxy + auto-SSL)
- Coolify handles deployments, rollbacks, logs, and monitoring via its web UI
- No need for `deploy.sh` or `vps-setup.sh` — Coolify manages the entire lifecycle

### Services Summary

| Service | Role | Image/Build | Persistent Data |
|---------|------|-------------|-----------------|
| **PostgreSQL 16** | Primary database | `postgres:16-alpine` | `/var/lib/postgresql/data` |
| **Redis 7** | Sessions, cache, Celery broker | `redis:7-alpine` | `/data` (AOF) |
| **FastAPI App** | Backend + Frontend (SSR) | Custom Dockerfile | `/app/data`, `/app/logs`, `/app/uploads` |
| **Celery Worker** | Background task processing | Same image as App | `/app/data`, `/app/logs` |
| **Celery Beat** | Periodic task scheduler | Same image as App | `/app/data` (beat schedule) |
| **Traefik** | Reverse proxy + SSL (managed by Coolify) | Automatic | N/A |

---

## 2. VPS & Coolify Installation

### 2.1 VPS Requirements

| Requirement | Minimum | Recommended (Our VPS) |
|-------------|---------|----------------------|
| CPU | 2 cores | 6 vCores |
| RAM | 2 GB | 12 GB |
| Storage | 30 GB | 100 GB SSD |
| OS | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |

**Recommended VPS providers:** Hetzner, Contabo, DigitalOcean, Vultr, OVH.

### 2.2 Initial VPS Hardening

SSH into your fresh VPS as root:

```bash
# 1. Update system
apt update && apt upgrade -y

# 2. Install firewall
apt install -y ufw fail2ban

# 3. Configure firewall (Coolify needs these ports)
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP (Traefik)
ufw allow 443/tcp   # HTTPS (Traefik)
ufw allow 8000/tcp  # Coolify dashboard (temporary, remove after setup)
ufw --force enable

# 4. Enable fail2ban
systemctl enable fail2ban
systemctl start fail2ban
```

### 2.3 Install Coolify

One command:

```bash
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | sudo bash
```

This installs Docker, Docker Compose, and Coolify itself.

### 2.4 Access Coolify Dashboard

1. Open `http://YOUR_VPS_IP:8000` in your browser
2. **Create your admin account immediately** (first visitor becomes admin)
3. Set a strong password — this controls your entire infrastructure

### 2.5 Set Custom Domain for Coolify (Optional but Recommended)

1. Point a DNS A record: `coolify.yourdomain.com` → VPS IP
2. In Coolify: **Settings** → Set instance domain to `https://coolify.yourdomain.com`
3. Coolify auto-provisions SSL for itself
4. Remove port 8000 from UFW: `ufw delete allow 8000/tcp`

---

## 3. Server Setup in Coolify

### 3.1 Verify Server Connection

Coolify auto-detects the local server (localhost) during installation.

1. Go to **Servers** in the sidebar
2. Click on **localhost**
3. Verify status shows **Connected** (green)
4. Check **Docker Engine** is running

### 3.2 Configure Wildcard Domain (Optional)

For auto-generated subdomains:

1. Create DNS A record: `*.app.yourdomain.com` → VPS IP
2. In **Servers** → **localhost** → Set wildcard domain: `app.yourdomain.com`

---

## 4. Project Setup in Coolify

### 4.1 Create a Project

1. Go to **Projects** in the sidebar
2. Click **+ New Project**
3. Name: `Jorss-GBO`
4. Description: `CPA Lead Platform — Tax Filing SaaS`

### 4.2 Create an Environment

Inside the project:
1. Click **+ New Environment**
2. Name: `production`

You'll deploy all services into this environment.

---

## 5. Database: PostgreSQL 16

### 5.1 Deploy PostgreSQL

1. In your `production` environment, click **+ New Resource**
2. Select **Database** → **PostgreSQL**
3. Configure:

| Setting | Value |
|---------|-------|
| **Name** | `jorss-postgres` |
| **Version/Image** | `postgres:16-alpine` |
| **Default Database** | `jorss_gbo` |
| **User** | `jorss` |
| **Password** | (auto-generated — save this!) |
| **Public Port** | Leave empty (internal only) |

4. Click **Deploy**

### 5.2 Persistent Storage

Coolify auto-creates a Docker volume for PostgreSQL data. Verify:

1. Go to **jorss-postgres** → **Storages** tab
2. Confirm volume mapped to `/var/lib/postgresql/data`

### 5.3 Get Connection String

After deployment, find the internal connection URL:

```
postgresql://jorss:<PASSWORD>@jorss-postgres:5432/jorss_gbo
```

> **Note:** The hostname is the service name (`jorss-postgres`) within Coolify's Docker network. You'll use this in the app's environment variables.

If Coolify appends a UUID to the name (e.g., `jorss-postgres-abc123`), use the full name. Check the **General** tab for the exact container name.

### 5.4 Configure Backups

1. Go to **jorss-postgres** → **Backups** tab
2. **Add S3 destination** (or use Coolify's local backup):
   - Recommended: Backblaze B2, AWS S3, or MinIO
3. Set schedule: `0 2 * * *` (daily at 2 AM)
4. Coolify uses `pg_dump --format=custom` automatically

### 5.5 Performance Tuning

Add custom PostgreSQL config via environment variables:

| Variable | Value | Purpose |
|----------|-------|---------|
| `POSTGRES_INITDB_ARGS` | `--encoding=UTF8` | UTF-8 encoding |
| `POSTGRES_HOST_AUTH_METHOD` | `scram-sha-256` | Secure auth |

Or mount a custom `postgresql.conf` via the **Storages** tab:

```yaml
# In Coolify storage config
Source: ./postgresql.conf
Target: /etc/postgresql/postgresql.conf
Content: |
  shared_buffers = 2GB
  effective_cache_size = 6GB
  work_mem = 32MB
  maintenance_work_mem = 512MB
  max_connections = 100
  wal_buffers = 64MB
```

---

## 6. Cache & Broker: Redis 7

### 6.1 Deploy Redis

1. In `production` environment, click **+ New Resource**
2. Select **Database** → **Redis**
3. Configure:

| Setting | Value |
|---------|-------|
| **Name** | `jorss-redis` |
| **Version/Image** | `redis:7-alpine` |
| **Password** | (auto-generated — save this!) |
| **Public Port** | Leave empty (internal only) |

4. Click **Deploy**

### 6.2 Custom Redis Configuration

In the **Command** override field, set:

```
redis-server --appendonly yes --requirepass YOUR_REDIS_PASSWORD --maxmemory 512mb --maxmemory-policy allkeys-lru
```

This enables:
- **AOF persistence** (survives container restarts)
- **Password auth** (required for production)
- **512MB memory limit** with LRU eviction

### 6.3 Connection URLs

The app needs 3 different Redis DBs:

| Purpose | URL | Redis DB |
|---------|-----|----------|
| Sessions + Cache | `redis://:PASSWORD@jorss-redis:6379/0` | DB 0 |
| Celery Broker | `redis://:PASSWORD@jorss-redis:6379/1` | DB 1 |
| Celery Results | `redis://:PASSWORD@jorss-redis:6379/2` | DB 2 |

> Use the Coolify-assigned container name as the hostname.

---

## 7. Backend: FastAPI Application

### 7.1 Connect Git Repository

1. In `production` environment, click **+ New Resource**
2. Select **Application** → choose your Git provider:
   - **Public Repository**: Paste repo URL
   - **GitHub App**: Connect Coolify to your GitHub account (recommended for auto-deploy)
   - **Deploy Key**: Add SSH deploy key to private repo

### 7.2 Select Build Pack

Choose **Docker Compose** as the build pack.

### 7.3 Create `docker-compose.coolify.yml`

Create this file in your repo root. This is the Coolify-specific compose file:

```yaml
services:
  # ---------------------------------------------------------------------------
  # Main Application — Gunicorn + Uvicorn Workers
  # ---------------------------------------------------------------------------
  app:
    build:
      context: .
      target: production
    environment:
      - PYTHONPATH=/app/src
      - APP_ENVIRONMENT=production
      - DEBUG=false
      - APP_ENFORCE_HTTPS=true
      - DATABASE_URL=${DATABASE_URL:?}
      - REDIS_URL=${REDIS_URL:?}
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - SESSION_STORAGE_TYPE=redis
      - APP_SECRET_KEY=${APP_SECRET_KEY:?}
      - JWT_SECRET=${JWT_SECRET:?}
      - AUTH_SECRET_KEY=${AUTH_SECRET_KEY:?}
      - CSRF_SECRET_KEY=${CSRF_SECRET_KEY:?}
      - PASSWORD_SALT=${PASSWORD_SALT:?}
      - ENCRYPTION_MASTER_KEY=${ENCRYPTION_MASTER_KEY:?}
      - SSN_HASH_SECRET=${SSN_HASH_SECRET:?}
      - SERIALIZER_SECRET_KEY=${SERIALIZER_SECRET_KEY:?}
      - AUDIT_HMAC_KEY=${AUDIT_HMAC_KEY:?}
      - OPENAI_API_KEY=${OPENAI_API_KEY:?}
      - CELERY_BROKER_URL=${CELERY_BROKER_URL}
      - CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND}
      - APP_URL=${APP_URL}
      - CORS_ORIGINS=${CORS_ORIGINS}
      - LOG_LEVEL=INFO
      - SENTRY_DSN=${SENTRY_DSN:-}
      - STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY:-}
      - STRIPE_PUBLISHABLE_KEY=${STRIPE_PUBLISHABLE_KEY:-}
      - STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET:-}
      - SENDGRID_API_KEY=${SENDGRID_API_KEY:-}
    command: >
      gunicorn src.web.app:app
      --bind 0.0.0.0:8000
      --workers 4
      --worker-class uvicorn.workers.UvicornWorker
      --timeout 120
      --keep-alive 5
      --access-logfile -
      --error-logfile -
    volumes:
      - type: bind
        source: ./app-data
        target: /app/data
        is_directory: true
      - type: bind
        source: ./app-logs
        target: /app/logs
        is_directory: true
      - type: bind
        source: ./app-uploads
        target: /app/uploads
        is_directory: true
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/live"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    restart: unless-stopped

  # ---------------------------------------------------------------------------
  # Celery Worker — Background Task Processing
  # ---------------------------------------------------------------------------
  worker:
    build:
      context: .
      target: production
    environment:
      - PYTHONPATH=/app/src
      - APP_ENVIRONMENT=production
      - DATABASE_URL=${DATABASE_URL:?}
      - REDIS_URL=${REDIS_URL:?}
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - APP_SECRET_KEY=${APP_SECRET_KEY:?}
      - JWT_SECRET=${JWT_SECRET:?}
      - ENCRYPTION_MASTER_KEY=${ENCRYPTION_MASTER_KEY:?}
      - CELERY_BROKER_URL=${CELERY_BROKER_URL}
      - CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND}
    command: >
      celery -A tasks.celery_app worker
      --loglevel=info
      --concurrency=2
      --max-tasks-per-child=1000
    volumes:
      - type: bind
        source: ./app-data
        target: /app/data
        is_directory: true
      - type: bind
        source: ./app-logs
        target: /app/logs
        is_directory: true
      - type: bind
        source: ./app-uploads
        target: /app/uploads
        is_directory: true
    exclude_from_hc: true
    restart: unless-stopped

  # ---------------------------------------------------------------------------
  # Celery Beat — Periodic Task Scheduler
  # ---------------------------------------------------------------------------
  beat:
    build:
      context: .
      target: production
    environment:
      - PYTHONPATH=/app/src
      - APP_ENVIRONMENT=production
      - DATABASE_URL=${DATABASE_URL:?}
      - REDIS_URL=${REDIS_URL:?}
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - APP_SECRET_KEY=${APP_SECRET_KEY:?}
      - CELERY_BROKER_URL=${CELERY_BROKER_URL}
      - CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND}
    command: >
      celery -A tasks.celery_app beat
      --loglevel=info
      --schedule=/app/data/celerybeat-schedule
    volumes:
      - type: bind
        source: ./app-data
        target: /app/data
        is_directory: true
    exclude_from_hc: true
    restart: unless-stopped
```

### 7.4 Configure in Coolify UI

After selecting Docker Compose:

| Setting | Value |
|---------|-------|
| **Docker Compose Location** | `docker-compose.coolify.yml` |
| **Base Directory** | `/` |

### 7.5 Connect to Databases

Since PostgreSQL and Redis are deployed as separate Coolify resources, you need to enable cross-service networking:

1. Go to **app** (your compose deployment) → **Settings**
2. Enable **Connect to Predefined Network**
3. Do the same for `jorss-postgres` and `jorss-redis` services

This places all services on Coolify's shared `coolify` network, allowing them to find each other by container name.

### 7.6 Assign Domain

1. Go to the **app** service configuration
2. Set domain: `https://app.yourdomain.com`
3. Coolify + Traefik automatically:
   - Routes traffic to port 8000
   - Provisions Let's Encrypt SSL certificate
   - Handles HTTP → HTTPS redirect

---

## 8. Background Workers: Celery

### 8.1 Worker Configuration

The Celery worker and beat services are defined in the Docker Compose file (Section 7.3). They:

- Share the same Docker image as the app (built once, used three times)
- Connect to Redis for task brokering (DB 1) and result storage (DB 2)
- Connect to PostgreSQL for database operations

### 8.2 Beat Schedule (Pre-Configured)

These periodic tasks run automatically via Celery Beat:

| Task | Schedule | Purpose |
|------|----------|---------|
| `cleanup-dead-letters` | Every 1 hour | Clean failed task queue |
| `purge-expired-sessions` | Every 1 hour | Remove expired user sessions |
| `cleanup-orphaned-uploads` | Every 24 hours | Delete abandoned file uploads |
| `trim-audit-logs` | Every 7 days | Archive old audit records |
| `process-deadline-reminders` | Every 1 hour | Send tax deadline notifications |
| `process-nurture-emails` | Every 1 hour | Lead nurture email campaigns |
| `scan-client-opportunities` | Daily at 6 AM | Find upsell opportunities |
| `compile-daily-digest` | Daily at 7 AM | CPA daily summary email |
| `nightly-database-backup` | Daily at 2 AM | PostgreSQL backup |

### 8.3 Scaling Workers

To increase worker capacity, either:

**Option A — Increase concurrency** (in compose file):
```yaml
command: celery -A tasks.celery_app worker --concurrency=4
```

**Option B — Add more worker containers** (duplicate the worker service):
```yaml
worker-2:
  # Same as worker service, different container_name
```

### 8.4 Monitoring Workers

Check worker status via Coolify's terminal:

```bash
# In the worker container's terminal (Coolify UI → Terminal tab)
celery -A tasks.celery_app inspect active
celery -A tasks.celery_app inspect stats
```

---

## 9. Frontend: Jinja2 Templates & Static Assets

### 9.1 Architecture

Jorss-GBO uses **server-side rendering** — no separate frontend build or SPA:

| Component | Technology | Location |
|-----------|-----------|----------|
| Templates | Jinja2 | `src/web/templates/` (47+ files) |
| CSS | Custom + Components | `src/web/static/css/` |
| JavaScript | Vanilla JS + Alpine.js | `src/web/static/js/` |
| Icons/PWA | Manifest + Service Worker | `src/web/static/` |

### 9.2 How It's Served

FastAPI serves everything from a single process:

1. **HTML pages** — Jinja2 templates rendered server-side by FastAPI route handlers
2. **Static files** — Served by FastAPI's `StaticFiles` mount at `/static/`
3. **API responses** — JSON responses from API routers

### 9.3 Static File Caching

Traefik (Coolify's proxy) handles caching headers. For additional control, the app sets cache headers in its middleware:

- `/static/` — 30-day cache with `Cache-Control: public, immutable`
- API responses — No caching (dynamic)

### 9.4 CSS Build Step (Optional)

There is no required client-side build. However, the `scripts/build.sh` has an optional CSS minification step using PostCSS if Node.js is available. This runs during Docker image build if `package.json` exists.

### 9.5 PWA Support

The app includes PWA manifests and a service worker:
- `src/web/static/manifest.json`
- `src/web/static/service-worker.js`
- Icons at 72px through 512px

These work automatically once the app is served over HTTPS (which Coolify handles).

---

## 10. Middleware Configuration

The app's middleware stack is configured in `src/web/middleware_setup.py`. All middleware is application-level (runs inside the FastAPI process), not in the reverse proxy.

### 10.1 Middleware Stack (Execution Order)

| # | Middleware | Purpose | Config |
|---|-----------|---------|--------|
| 1 | **GZip** | Compress responses > 500 bytes | Built-in |
| 2 | **HTTPS Redirect** | Force HTTPS in production | `APP_ENFORCE_HTTPS=true` |
| 3 | **Security Headers** | HSTS, CSP, X-Frame-Options | Auto in production |
| 4 | **Rate Limiting** | 60 req/min per IP, burst 20 | `ENABLE_RATE_LIMITING=true` |
| 5 | **Request Validation** | Max 50MB content, type checks | Auto |
| 6 | **CSRF Protection** | Token validation for state changes | `CSRF_SECRET_KEY` |
| 7 | **Correlation ID** | Request tracing (`X-Correlation-ID`) | Auto |
| 8 | **RBAC v2** | Permission-based access control | Feature-flagged |
| 9 | **Tenant Isolation** | Multi-tenant data boundaries | Strict in production |
| 10 | **CORS** | Cross-origin request handling | `CORS_ORIGINS` |

### 10.2 Coolify-Specific Considerations

**Traefik handles:**
- SSL termination (so app sees `X-Forwarded-Proto: https`)
- HTTP → HTTPS redirect (redundant with app middleware, but harmless)
- Basic load balancing

**App handles:**
- All security middleware (CSRF, CORS, rate limiting, RBAC)
- Request validation
- Tenant isolation

**Important:** Set `APP_ENFORCE_HTTPS=true` so the app trusts Traefik's `X-Forwarded-Proto` header and generates correct HTTPS URLs.

---

## 11. API Layer

### 11.1 API Structure

The app exposes 30+ API routers organized by domain:

| Category | Prefix | Key Endpoints |
|----------|--------|---------------|
| **Auth** | `/api/v1/auth/`, `/api/core/auth/` | Login, register, MFA, password reset |
| **Tax Filing** | `/api/` | Smart tax, unified filing, guided filing |
| **Advisory** | `/api/` | Advisory reports, tax advisor, AI chat |
| **CPA Panel** | `/api/` | Lead management, client dashboard |
| **Admin** | `/api/v1/` | Admin dashboard, compliance, GDPR |
| **Documents** | `/api/` | Upload, OCR processing, filing packages |
| **Tax Tools** | `/api/` | Capital gains, K-1 basis, depreciation |
| **Health** | `/api/health/` | Liveness, readiness, metrics |
| **WebSocket** | `/ws/` | Real-time events |

### 11.2 API Authentication

| Method | Used For |
|--------|----------|
| JWT Bearer tokens | API authentication (`Authorization: Bearer <token>`) |
| Session cookies | Browser-based authentication |
| CSRF tokens | State-changing browser requests |
| API keys | Webhook callbacks (Stripe, etc.) |

### 11.3 Webhook Endpoints

For Stripe webhooks, set the webhook URL in Stripe dashboard to:
```
https://app.yourdomain.com/api/webhooks/stripe
```

Set `STRIPE_WEBHOOK_SECRET` in Coolify environment variables.

---

## 12. Domain, SSL & Reverse Proxy

### 12.1 DNS Setup

Create these DNS records:

| Type | Name | Value |
|------|------|-------|
| A | `app.yourdomain.com` | `YOUR_VPS_IP` |
| A | `coolify.yourdomain.com` (optional) | `YOUR_VPS_IP` |

### 12.2 SSL Configuration

**Coolify handles this automatically:**

1. When you assign a domain to a service, Traefik provisions a Let's Encrypt certificate
2. Certificates auto-renew before expiry
3. HTTP → HTTPS redirect is enabled by default
4. TLS 1.2+ is enforced

**No manual certbot, nginx config, or cron jobs needed.**

### 12.3 Traefik vs. Our Nginx Config

| Feature | Coolify (Traefik) | Our `nginx.production.conf` |
|---------|-------------------|-----------------------------|
| SSL termination | Automatic | Manual certbot |
| HTTP → HTTPS | Automatic | Manual config |
| Rate limiting | Basic | Advanced (per-zone) |
| Static files | Via app | Direct serve |
| WebSocket | Automatic | Manual config |

**With Coolify, you don't need:**
- `nginx/nginx.production.conf`
- `certbot` container
- `scripts/renew-ssl.sh`
- Manual SSL certificate management

Rate limiting and security headers are handled by the FastAPI middleware stack instead.

---

## 13. Environment Variables

### 13.1 Where to Configure

In Coolify UI: **Your App** → **Environment Variables** tab

Coolify detects `${VARIABLE:?}` syntax from the compose file and shows them with red borders until filled.

### 13.2 Required Variables

Generate all 9 security secrets at once:

```bash
python3 -c "import secrets; [print(f'{k}={secrets.token_hex(32)}') for k in ['APP_SECRET_KEY','JWT_SECRET','AUTH_SECRET_KEY','CSRF_SECRET_KEY','PASSWORD_SALT','ENCRYPTION_MASTER_KEY','SSN_HASH_SECRET','SERIALIZER_SECRET_KEY','AUDIT_HMAC_KEY']]"
```

Then set each in Coolify's environment variables UI:

#### Application

| Variable | Value | Notes |
|----------|-------|-------|
| `APP_URL` | `https://app.yourdomain.com` | Full URL with https |
| `CORS_ORIGINS` | `https://app.yourdomain.com` | Same as APP_URL |

#### Database

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | `postgresql://jorss:<PG_PASSWORD>@jorss-postgres:5432/jorss_gbo` |

> Replace `jorss-postgres` with the actual container name from Coolify (check PostgreSQL resource's General tab).

#### Redis

| Variable | Value |
|----------|-------|
| `REDIS_PASSWORD` | `<your-redis-password>` |
| `REDIS_URL` | `redis://:PASSWORD@jorss-redis:6379/0` |
| `CELERY_BROKER_URL` | `redis://:PASSWORD@jorss-redis:6379/1` |
| `CELERY_RESULT_BACKEND` | `redis://:PASSWORD@jorss-redis:6379/2` |

> Replace `jorss-redis` with the actual container name from Coolify.

#### Security (All Required)

| Variable | How to Generate |
|----------|----------------|
| `APP_SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_SECRET` | Same as above |
| `AUTH_SECRET_KEY` | Same |
| `CSRF_SECRET_KEY` | Same |
| `PASSWORD_SALT` | Same |
| `ENCRYPTION_MASTER_KEY` | Same |
| `SSN_HASH_SECRET` | Same |
| `SERIALIZER_SECRET_KEY` | Same |
| `AUDIT_HMAC_KEY` | Same |

#### External Services

| Variable | Value | Required? |
|----------|-------|-----------|
| `OPENAI_API_KEY` | `sk-...` | Yes (AI features) |
| `STRIPE_SECRET_KEY` | `sk_live_...` | If payments enabled |
| `STRIPE_PUBLISHABLE_KEY` | `pk_live_...` | If payments enabled |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` | If payments enabled |
| `SENDGRID_API_KEY` | `SG....` | If email enabled |
| `SENTRY_DSN` | `https://...` | Recommended |

---

## 14. Database Migrations

### 14.1 Initial Migration (First Deploy)

After the first deployment, run migrations via Coolify's terminal:

1. Go to your **app** service in Coolify
2. Click the **Terminal** tab
3. Run:

```bash
cd /app && PYTHONPATH=/app/src alembic -c alembic.ini upgrade head
```

### 14.2 Migrations on Subsequent Deploys

**Option A — Manual (Recommended initially):**

After each deploy, open Terminal and run migrations manually.

**Option B — Auto-migrate via Docker entrypoint:**

Create a `scripts/docker-entrypoint.sh`:

```bash
#!/bin/bash
set -e

# Run migrations
echo "Running database migrations..."
PYTHONPATH=/app/src alembic -c alembic.ini upgrade head

# Start the application
exec "$@"
```

Then update the Dockerfile to use it:
```dockerfile
COPY scripts/docker-entrypoint.sh /app/docker-entrypoint.sh
ENTRYPOINT ["/app/docker-entrypoint.sh"]
```

And the compose command becomes the CMD (entrypoint runs migrations first, then starts gunicorn).

### 14.3 Rollback Migrations

```bash
# In Coolify terminal for the app container:
PYTHONPATH=/app/src alembic -c alembic.ini downgrade -1
```

---

## 15. Automated Backups

### 15.1 PostgreSQL Backups via Coolify

1. Go to **jorss-postgres** → **Backups** tab
2. Configure S3 destination (Backblaze B2, AWS S3, MinIO, etc.)
3. Set schedule:

| Environment | Cron | Description |
|-------------|------|-------------|
| Production | `0 */4 * * *` | Every 4 hours |
| Staging | `0 2 * * *` | Daily at 2 AM |

4. Coolify auto-runs: `pg_dump --format=custom --no-acl --no-owner`

### 15.2 Restore from Backup

1. Go to **jorss-postgres** → **Backups** tab
2. Select a backup
3. Click **Restore**

Or manually via terminal:
```bash
pg_restore --verbose --clean -d jorss_gbo /path/to/backup.dump
```

### 15.3 Application Data Backups

For `/app/data`, `/app/uploads` — these are stored in bind mounts on the host. Set up a simple cron on the VPS:

```bash
# Add to root crontab
0 3 * * * tar czf /backups/app-data-$(date +\%Y\%m\%d).tar.gz /var/lib/docker/volumes/*app-data* /var/lib/docker/volumes/*app-uploads*
```

---

## 16. Health Checks & Monitoring

### 16.1 Health Check Endpoints

| Endpoint | Purpose | Used By |
|----------|---------|---------|
| `GET /health/live` | Liveness probe — is the process running? | Coolify/Traefik |
| `GET /api/health/` | Basic health status | Monitoring |
| `GET /api/health/ready` | Readiness — all dependencies OK? | Load balancer |
| `GET /api/health/metrics` | CPU, memory, disk, connections | Dashboard |
| `GET /api/health/dependencies` | DB, Redis, OCR, calculator status | Debugging |

### 16.2 Coolify Monitoring

Coolify provides built-in monitoring:

1. **Container Status** — Running, stopped, unhealthy
2. **Logs** — Real-time log streaming (stdout/stderr)
3. **Resource Usage** — CPU and memory per container

Access via: **Your Service** → **Logs** tab

### 16.3 External Monitoring (Recommended)

Set up an uptime monitor pointing to:
```
https://app.yourdomain.com/health/live
```

Recommended services: UptimeRobot (free), Better Stack, Grafana Cloud.

### 16.4 Sentry Error Tracking

Set `SENTRY_DSN` in environment variables. The app auto-configures Sentry SDK for:
- Unhandled exception capture
- Performance monitoring
- User context (without PII)

---

## 17. CI/CD: Auto-Deploy on Push

### 17.1 GitHub Auto-Deploy

If you connected via GitHub App:

1. Go to your app in Coolify → **General** tab
2. Enable **Auto Deploy**
3. Every push to the configured branch triggers a new deployment

### 17.2 Branch Configuration

| Branch | Environment | Auto-Deploy |
|--------|-------------|-------------|
| `main` | Production | Yes (or manual) |
| `staging` | Staging | Yes |
| `feature/*` | Preview | Via PR deployments |

### 17.3 Preview Deployments (Pull Requests)

1. Enable **Preview Deployments** in Coolify
2. Each PR gets a unique URL: `pr-123.app.yourdomain.com`
3. Auto-destroyed when PR is merged/closed

### 17.4 Deployment Workflow

```
Developer pushes to main
        │
        ▼
Coolify detects push (webhook)
        │
        ▼
Coolify pulls latest code
        │
        ▼
Docker builds new image (multi-stage Dockerfile)
        │
        ▼
Health check passes?
   ├── Yes → Route traffic to new container → Remove old container
   └── No  → Keep old container → Alert in Coolify UI
```

---

## 18. Maintenance & Operations

### 18.1 Common Operations

| Task | How |
|------|-----|
| **View logs** | Coolify → Service → Logs tab |
| **Restart service** | Coolify → Service → Restart button |
| **Rollback** | Coolify → Service → Rollbacks tab → Select previous version |
| **Scale workers** | Update compose file → Push → Auto-deploy |
| **Run migrations** | Coolify → App → Terminal → `alembic upgrade head` |
| **SSH to VPS** | `ssh root@YOUR_VPS_IP` |

### 18.2 Update Coolify Itself

```bash
# SSH into VPS
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | sudo bash
```

### 18.3 Disk Space Management

```bash
# Clean unused Docker resources
docker system prune -a --volumes

# Check disk usage
df -h
docker system df
```

### 18.4 Resource Allocation Guide

For your 6 vCores / 12GB RAM VPS:

| Service | CPU | Memory |
|---------|-----|--------|
| Coolify + Traefik | 0.5 cores | 1 GB |
| PostgreSQL | 1 core | 2 GB |
| Redis | 0.5 cores | 512 MB |
| FastAPI (4 workers) | 2 cores | 4 GB |
| Celery Worker | 1 core | 2 GB |
| Celery Beat | 0.25 cores | 256 MB |
| OS / Buffer | 0.75 cores | 2.25 GB |
| **Total** | **6 cores** | **12 GB** |

Set resource limits in Coolify: **Service** → **General** → **Resource Limits**

---

## 19. Troubleshooting

### 19.1 Common Issues

| Problem | Cause | Fix |
|---------|-------|-----|
| App can't connect to PostgreSQL | Wrong hostname | Use Coolify container name (check General tab) |
| App can't connect to Redis | Not on same network | Enable "Connect to Predefined Network" on all services |
| SSL certificate not provisioning | DNS not pointing to VPS | Verify A record: `dig app.yourdomain.com` |
| Container keeps restarting | Health check failing | Check logs, verify `DATABASE_URL` and `REDIS_URL` |
| Celery worker not processing tasks | Wrong broker URL | Verify `CELERY_BROKER_URL` matches Redis container name |
| Static files 404 | Volume not mounted | Check Storages tab in Coolify |
| Migration fails | No database connection | Run `alembic` from app container terminal, not beat/worker |
| Out of memory | No resource limits | Set memory limits per service (see Section 18.4) |

### 19.2 Debug Commands (via Coolify Terminal)

```bash
# Check database connectivity
PYTHONPATH=/app/src python3 -c "
from config.settings import get_settings
s = get_settings()
print(f'DB: {s.database_url[:30]}...')
print(f'Redis: {s.redis.host}:{s.redis.port}')
"

# Check Redis connectivity
redis-cli -h jorss-redis -a YOUR_PASSWORD ping

# Check Celery worker status
celery -A tasks.celery_app inspect ping

# Check migration status
PYTHONPATH=/app/src alembic -c alembic.ini current
PYTHONPATH=/app/src alembic -c alembic.ini history --verbose
```

### 19.3 Logs Location

| Log | Access |
|-----|--------|
| App logs | Coolify → App → Logs tab |
| Worker logs | Coolify → Worker → Logs tab (same compose stack) |
| PostgreSQL logs | Coolify → jorss-postgres → Logs tab |
| Redis logs | Coolify → jorss-redis → Logs tab |
| Traefik logs | `docker logs coolify-proxy` (on VPS) |
| System logs | `journalctl -u docker -f` (on VPS) |

---

## Quick-Start Checklist

```
□ 1.  Provision VPS (Ubuntu 24.04, 6 cores, 12GB RAM)
□ 2.  Harden VPS (UFW, fail2ban)
□ 3.  Install Coolify (one command)
□ 4.  Create admin account
□ 5.  Set up DNS A record → VPS IP
□ 6.  Create Project + Environment in Coolify
□ 7.  Deploy PostgreSQL 16 (one-click)
□ 8.  Deploy Redis 7 (one-click)
□ 9.  Enable Predefined Network on both databases
□ 10. Add docker-compose.coolify.yml to repo
□ 11. Connect Git repo in Coolify (Docker Compose build pack)
□ 12. Set all environment variables (generate secrets!)
□ 13. Enable Predefined Network on app
□ 14. Assign domain (https://app.yourdomain.com)
□ 15. Deploy
□ 16. Run initial migration via Terminal
□ 17. Configure PostgreSQL backups (S3 + schedule)
□ 18. Set up external uptime monitoring
□ 19. Enable auto-deploy on push
□ 20. Test everything: login, file upload, AI chat, payments
```

---

## Files Reference

| File | Purpose | Needed for Coolify? |
|------|---------|-------------------|
| `docker-compose.coolify.yml` | Coolify-specific compose | **Yes — create this** |
| `Dockerfile` | Multi-stage build | **Yes — already exists** |
| `docker-compose.production.yml` | Raw Docker Compose (no Coolify) | No (alternative to Coolify) |
| `nginx/nginx.production.conf` | Nginx reverse proxy | No (Traefik replaces this) |
| `scripts/deploy.sh` | Manual deployment | No (Coolify replaces this) |
| `scripts/vps-setup.sh` | VPS provisioning | Partial (only UFW/fail2ban steps) |
| `.env.production.template` | Env var reference | Reference only (use Coolify UI) |
