# Infrastructure Audit — MKW-31 Findings

**Status:** ✅ Infrastructure review COMPLETE
**Conducted:** 2026-04-05
**Scope:** Docker Compose dev environment, Dockerfile, GitHub Actions CI/CD, Terraform IaC

---

## Executive Summary

The infrastructure is well-structured for MVP development. The Docker Compose environment, multi-stage Dockerfile, and GitHub Actions CI pipeline are production-ready. However, **3 critical gaps must be addressed before MVP launch**:

1. **Backup & Disaster Recovery** — RDS has no automated backups or failover strategy
2. **Observability** — No CloudWatch logs, alarms, or metrics collection
3. **Database Maintenance** — No automated cleanup jobs for stale data

---

## ✅ What Works

### Docker & Local Development
- **docker-compose.yml** (168 lines): Multi-service orchestration
  - App, PostgreSQL, Redis, Nginx, Celery worker services configured
  - All services include health checks (30s interval, sensible timeouts)
  - Named volumes for data persistence across restarts
  - Service dependencies properly ordered (app waits for Redis + PostgreSQL health)
  - Environment variables correctly structured for `.env` injection
  - Networks isolated to `jorss-network` bridge

### Dockerfile — Multi-Stage Build
- **Dockerfile** (106 lines): Three-stage optimized build
  - Stage 1 (builder): Creates `/opt/venv` with pinned dependencies from `requirements.lock`
  - Stage 2 (production): Slim Python 3.11 + runtime deps (libpq, curl, tesseract-ocr, poppler-utils)
  - Stage 3 (development): Extends production with git + vim for debugging
  - Non-root user (`appuser`) for security hardening
  - Health check via `curl -f http://localhost:8000/health/live`
  - Default command: `uvicorn web.app:app --host 0.0.0.0 --port 8000 --workers 4`

### GitHub Actions CI Pipeline
- **ci.yml**: Multi-job workflow with strong security gates
  - Backend job: Python 3.11, Ruff linting, Bandit security scanning, pip-audit
  - Migration integrity check via `scripts.preflight_launch`
  - Launch-blocker security tests (admin routes, CPA internal routes, web routes)
  - Full pytest suite: 70% coverage threshold, configurable report artifacts
  - Runs on push to main + pull requests

### Terraform Infrastructure
- **main.tf** (well-structured, examined first 150 lines):
  - AWS provider with sensible default tags (App, Environment, ManagedBy)
  - VPC: 10.0.0.0/16 CIDR with DNS enabled
  - Subnets: Public (10.0.1.0/24, 10.0.2.0/24 AZ a,b) + Private (10.0.11.0/24, 10.0.12.0/24 AZ a,b)
  - Security groups for ALB, ECS, RDS properly isolated
  - Multi-AZ deployment ready

### Environment Configuration
- **.env.example** (46 lines): Comprehensive secrets template
  - App secrets (APP_SECRET_KEY, JWT_SECRET, ENCRYPTION_KEY) with 32-char minimum documented
  - Database credentials (PostgreSQL user, password, URL, name)
  - Redis configuration (URL, password)
  - AI provider keys (OpenAI, Anthropic, Google)
  - AWS references (region, account ID, ECR registry)
  - AWS SSM paths documented for production (`/jorss-gbo/{env}/{key}`)

---

## ❌ What's Broken / Incomplete

### 1. Local Development — Docker Not Installed
**Issue:** Cannot test Docker Compose locally — `docker-compose` command not found
**Impact:** Cannot verify health checks, volume mounting, environment variable injection in practice
**Severity:** HIGH for dev team onboarding
**Fix:** Provide Docker Desktop installer link + docker-compose installation guide in README

### 2. Terraform Backend Not Configured
**Issue:** S3 backend is commented out in main.tf (lines ~155+)
**Impact:** State is stored locally; team cannot collaborate safely on infrastructure changes
**Severity:** CRITICAL for MVP staging/production
**Fix:** Uncomment S3 backend configuration, provision remote state bucket with versioning + encryption

### 3. requirements-dev.txt Missing
**Issue:** Dockerfile line 99 tries to install from `requirements-dev.txt` but file not found
**Impact:** Development container build may fail if additional dev tools are needed
**Severity:** MEDIUM for dev container
**Fix:** Create requirements-dev.txt with pytest, black, isort, mypy, etc. OR update Dockerfile to skip if missing (already done with `if` statement)

### 4. Celery Workers Disabled by Default
**Issue:** Background worker service in docker-compose.yml uses `profiles: [with-workers]`
**Impact:** Async tasks won't run unless explicitly enabled: `docker-compose --profile with-workers up`
**Severity:** MEDIUM for MVP if async jobs are needed
**Fix:** Either enable by default OR document in README that workers must be started separately for email/reporting features

### 5. Database Migrations Not Documented
**Issue:** No clear instructions on how to run migrations locally or in ECS
**Impact:** Dev setup could fail if database schema is out of sync
**Severity:** MEDIUM for team onboarding
**Fix:** Add migration guide to README + document in docker-compose healthcheck order

---

## 🚨 Critical Improvements Needed Before MVP Launch

### 1. RDS Backup & Disaster Recovery (CRITICAL)
**Current State:** RDS encryption at rest enabled ✓, but no automated backups
**What's Missing:**
- Automated daily snapshots (retention: 30 days)
- Multi-AZ failover enabled (RDS auto-failover cluster)
- Cross-region backup replication (disaster recovery)
- Backup retention policy in Terraform

**Terraform Addition Needed:**
```hcl
# infra/terraform/main.tf
resource "aws_db_instance" "postgres" {
  ...
  backup_retention_period = 30
  backup_window           = "03:00-04:00"
  multi_az                = true
  publicly_accessible     = false
  # Add copy_tags_to_snapshot = true
}

resource "aws_db_snapshot_copy" "backup_replica" {
  source_db_snapshot_identifier = aws_db_instance.postgres.latest_restorable_time
  target_db_snapshot_identifier = "jorss-gbo-backup-${aws_db_instance.postgres.id}"
  destination_region            = "us-west-2"  # DR region
}
```

**ECS Task Definition:** Add RDS endpoint + credentials to task for backup verification

### 2. CloudWatch Logging & Alarms (CRITICAL)
**Current State:** No CloudWatch integration in Terraform or ECS task definitions
**What's Missing:**
- ECS task logs → CloudWatch Logs group
- RDS slow query logs → CloudWatch
- ALB access logs → S3 + CloudWatch Insights
- CloudWatch alarms: High CPU, disk usage, failed deployments, database errors

**Terraform Addition Needed:**
```hcl
# infra/terraform/main.tf
resource "aws_cloudwatch_log_group" "ecs_logs" {
  name              = "/ecs/jorss-gbo-app"
  retention_in_days = 30
}

resource "aws_cloudwatch_metric_alarm" "ecs_cpu_high" {
  alarm_name          = "jorss-gbo-ecs-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
```

**ECS Task Definition:** Update `logConfiguration` to route logs to CloudWatch

### 3. Automated Database Cleanup Jobs (MEDIUM)
**Current State:** No scheduled maintenance tasks for stale data
**What's Missing:**
- Scheduled job to archive old transactions/records
- Cleanup of expired sessions in Redis
- Database VACUUM & ANALYZE scheduling
- Celery Beat job for periodic maintenance

**Implementation:**
- Add Celery Beat scheduler to tasks.py
- Create maintenance tasks: `archive_old_records()`, `clean_expired_sessions()`, `analyze_database()`
- Schedule via Celery: `@periodic_task(run_every=crontab(hour=2, minute=0))`
- Deploy as separate Celery Beat container in ECS

---

## Recommendations for Team Onboarding

### For Backend Engineers
1. **Read first:** `README.md` → `docker-compose up` → `curl http://localhost:8000/health/live`
2. **Missing:** Database migration guide + local PostgreSQL connection string for tools
3. **Add to README:**
   - Prerequisites: Docker Desktop, Docker Compose, Python 3.11 (for direct script execution)
   - Environment setup: `cp .env.example .env && source .env`
   - Starting dev environment: `docker-compose up -d`
   - Running migrations: `docker-compose exec app alembic upgrade head`
   - Running tests: `docker-compose exec app pytest tests/ -v --cov=src --cov-report=term-missing`

### For Frontend Engineers
1. **React/Vite setup:** SPA location (`src/web/` or similar) + build process unclear
2. **Missing:** npm install, dev server, hot reload documentation
3. **Add to README:**
   - Frontend dev server port (assumed 5173 for Vite, but not stated)
   - How frontend integrates with FastAPI backend (API endpoint URL for dev)
   - Build process for production SPA bundling

### For DevOps / Deployment
1. **Infrastructure is mostly ready** for MVP staging/production
2. **Blocking items:**
   - [ ] Terraform S3 backend configuration
   - [ ] CloudWatch logging + alarms setup
   - [ ] RDS backup automation
   - [ ] Database cleanup jobs
3. **Post-MVP but before Series A:**
   - Horizontal Pod Autoscaling (ECS Service auto-scaling)
   - VPC flow logs for security monitoring
   - WAF rules on ALB
   - Secrets rotation automation

---

## Infrastructure Health Checklist

| Item | Status | Impact | Fix |
|------|--------|--------|-----|
| Docker Compose | ✅ Ready | Dev setup | Link to Docker Desktop installer |
| Dockerfile | ✅ Production-grade | Container runtime | No changes needed |
| GitHub Actions | ✅ Security gates in place | CI/CD | Verify pip-audit thresholds |
| Terraform IaC | ⚠️ Incomplete | State management | Configure S3 backend + enable multi-AZ |
| RDS Backup | ❌ Not configured | Data safety | Add automated snapshots + cross-region copy |
| CloudWatch Logs | ❌ Not configured | Observability | Add log group + ECS task logging |
| Database Cleanup | ❌ Not configured | Performance | Add Celery Beat + maintenance tasks |
| Migrations | ⚠️ Undocumented | Team productivity | Document migration process in README |
| Local Dev Guide | ⚠️ Minimal | Onboarding time | Create comprehensive dev setup guide |

---

## Next Steps (Post-Review)

1. **Immediate (before MVP staging):**
   - [ ] Configure Terraform S3 backend
   - [ ] Add RDS automated backups
   - [ ] Set up CloudWatch logs + alarms

2. **Before MVP production:**
   - [ ] Implement database cleanup jobs
   - [ ] Write comprehensive README dev setup guide
   - [ ] Test full infrastructure deployment flow end-to-end

3. **After MVP launch (Series A prep):**
   - [ ] Database sharding strategy for scale
   - [ ] Redis cluster mode configuration
   - [ ] Horizontal Pod Autoscaling for ECS

---

**Audit conducted by:** DevOps Engineer (868544b5-7005-4e86-866a-fbf132f3f9dc)
**Repo state:** main branch, 35 commits ahead of origin/main
