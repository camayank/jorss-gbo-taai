# Disaster Recovery Plan

## Overview
This document covers backup, recovery, and business continuity procedures for the Jorss-GBO Tax Platform.

## Recovery Objectives
- **RTO (Recovery Time Objective):** 4 hours
- **RPO (Recovery Point Objective):** 1 hour (based on nightly backups + WAL archiving)

## Backup Strategy

### Database (Neon PostgreSQL)
- **Point-in-Time Recovery (PITR):** Neon provides automatic PITR with 7-day retention (Pro plan) or 24-hour retention (Free plan)
- **Nightly pg_dump:** Automated via Celery beat task at 02:00 UTC
- **Backup storage:** Encrypted backups stored in configured backup location

### Redis (Upstash)
- Upstash provides automatic persistence
- Non-critical data (cache, rate limits) can be regenerated
- Token blacklists are short-lived (TTL-based)

### Application State
- All application state is stored in PostgreSQL or Redis
- No local file system state required for recovery
- Configuration via environment variables (documented in .env.example)

## Recovery Procedures

### Scenario 1: Database Corruption or Data Loss
1. Identify the point of corruption using application logs and Sentry
2. Use Neon PITR to restore to a point before corruption:
   ```bash
   # Via Neon Console: Project → Branches → Create branch from point-in-time
   # Select timestamp before corruption
   ```
3. Update DATABASE_URL to point to the restored branch
4. Verify data integrity with smoke tests
5. Switch DNS/traffic to restored instance

### Scenario 2: Complete Infrastructure Failure
1. Provision new Render service from GitHub main branch
2. Set all environment variables from secure backup (1Password/Vault)
3. Restore database from Neon PITR or latest pg_dump
4. Verify with `scripts/smoke_test.py`
5. Update DNS records

### Scenario 3: Redis Failure
1. Application continues with degraded functionality (in-memory fallbacks in dev)
2. In production: provision new Upstash instance
3. Update REDIS_URL environment variable
4. Restart application — caches rebuild automatically

### Scenario 4: Compromised Credentials
1. Rotate all secrets immediately (JWT_SECRET, APP_SECRET_KEY, etc.)
2. Invalidate all active sessions (flush Redis blacklist data)
3. Force password reset for affected users
4. Review audit logs for unauthorized access
5. Update secrets in deployment environment

## Backup Verification
- Nightly automated backup task logs success/failure to Sentry
- Monthly manual restore test to staging environment
- Backup integrity check via checksum verification

## Contact & Escalation
- Primary: Platform lead (check internal docs)
- Secondary: Infrastructure team
- Neon Support: https://neon.tech/docs/support
- Render Support: https://render.com/support
