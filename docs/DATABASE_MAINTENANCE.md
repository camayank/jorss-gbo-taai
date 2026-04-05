# Database Maintenance & Retention Policies

This document outlines the automated database maintenance strategy, data retention policies, and monitoring for the AI Tax Advisor platform.

## Overview

Database maintenance is automated via Celery beat scheduled tasks running in the production environment. All operations are monitored, logged, and integrate with CloudWatch for observability.

### Goals

- **Performance**: Regular VACUUM ANALYZE and statistics collection to optimize query plans
- **Compliance**: Archive audit logs for regulatory retention requirements (7 years)
- **Storage**: Delete orphaned files and expired temporary data
- **Visibility**: Continuous monitoring of database health metrics

---

## Scheduled Maintenance Tasks

All times are in UTC. These tasks are defined in `src/tasks/database_maintenance.py` and scheduled in `src/tasks/celery_app.py`.

### 1. VACUUM ANALYZE High-Churn Tables

**Schedule**: Weekly, Sunday at 1:00 AM UTC
**Task**: `tasks.database_maintenance.vacuum_analyze_high_churn`
**Duration**: 5-15 minutes depending on table sizes

#### What It Does

Runs `VACUUM ANALYZE` on high-activity tables to:
- Reclaim disk space from deleted rows
- Update table statistics for query planner
- Improve index efficiency

#### Target Tables

These tables experience frequent updates/deletes and benefit most from VACUUM ANALYZE:

| Table | Reason |
|-------|--------|
| `tax_returns` | Active processing, frequent status updates |
| `document_processing` | OCR status tracking, high churn |
| `session_states` | Session lifecycle management |
| `audit_log` | Append-heavy audit trail |
| `calculations` | Computation results, frequent deletes on completion |

#### Configuration

```python
HIGH_CHURN_TABLES = [
    "tax_returns",
    "document_processing",
    "session_states",
    "audit_log",
    "calculations",
]
```

#### Monitoring

CloudWatch metrics published:
- `TaxPlatform/Database/TableDeadTuples_{table}` - Dead row count
- `TaxPlatform/Database/TableLiveTuples_{table}` - Live row count
- `TaxPlatform/Database/VacuumAnalyzeSuccess` - Success indicator (1 = success, 0 = failure)

#### Database Impact

- **Exclusive Lock**: Short-term locks on target tables (seconds per table)
- **IO**: Moderate disk read/write during VACUUM
- **CPU**: Moderate spike during statistics analysis
- **Impact on Queries**: Minimal; happens outside business hours

---

### 2. Archive Audit Logs to S3

**Schedule**: Weekly, Monday at 3:00 AM UTC
**Task**: `tasks.database_maintenance.archive_audit_logs`
**Duration**: 10-30 minutes depending on volume

#### What It Does

Archives audit log entries older than 90 days to S3:
1. Fetches audit logs older than 90 days
2. Compresses and uploads to S3 in JSONL format (one JSON per line)
3. Deletes archived logs from PostgreSQL database
4. Validates archive integrity

#### Retention Policies

| Data Type | Retention | Rationale |
|-----------|-----------|-----------|
| **Audit Logs (Production)** | 7 years | IRS/regulatory requirement (SOX compliance) |
| **Audit Logs (Hot Database)** | 90 days | Balance: live DB performance vs. recent activity access |
| **Audit Logs (Cold Storage)** | Indefinite | Long-term regulatory compliance archive |

#### S3 Archive Structure

```
s3://bucket/archives/audit-logs/
├── 2026-04-05/
│   ├── batch-0.jsonl
│   ├── batch-1.jsonl
│   └── ...
└── 2026-04-04/
    ├── batch-0.jsonl
    └── ...
```

Each JSONL file contains one audit event per line:

```json
{"id":"uuid","timestamp":"2026-04-05T10:30:00Z","event_type":"data_export","resource_type":"tax_return","action":"download","actor_id":"cpa-123","severity":"info","details":{}}
```

#### Configuration

```python
# Environment variables
AUDIT_LOG_ARCHIVE_DAYS=90       # Days before archival to S3
AWS_DOCUMENT_BUCKET=jorss-gbo-documents
```

#### CloudWatch Metrics

- `TaxPlatform/Database/AuditLogsArchived` - Logs archived count
- `TaxPlatform/Database/AuditLogsBytesTransferred` - Data transferred to S3 (bytes)

#### Compliance Notes

- **Access**: Archived logs are immutable and stored in secure S3 bucket with versioning enabled
- **Encryption**: Server-side encryption (AES-256) applied to all archived objects
- **Retention**: Configured for indefinite retention (required for 7-year hold)
- **Retrieval**: Accessible via AWS API/CLI for compliance audits

---

### 3. Collect PostgreSQL Statistics

**Schedule**: Hourly (every 60 minutes)
**Task**: `tasks.database_maintenance.collect_pg_stats`
**Duration**: 1-2 seconds

#### What It Does

Collects key PostgreSQL performance metrics from `pg_stat` views and publishes to CloudWatch:

| Metric | Description |
|--------|-------------|
| Cache Hit Ratios | Heap block cache hit % and index block cache hit % |
| Active Connections | Current active connections vs. max configured |
| Slow Queries | Queries exceeding 1 second execution time |
| Database Size | Total database size and largest 5 tables |
| Table Statistics | Live/dead tuples and modification counts |

#### CloudWatch Metrics Published

```
TaxPlatform/Database/CacheHitRatio_Heap          - %
TaxPlatform/Database/CacheHitRatio_Index         - %
TaxPlatform/Database/ActiveConnections           - count
TaxPlatform/Database/ConnectionUtilization       - %
TaxPlatform/Database/SlowQueries                 - count
TaxPlatform/Database/StatsCollectionSuccess      - 1 or 0
```

#### Alert Thresholds (Recommended)

Configure CloudWatch alarms:

| Metric | Warning | Critical |
|--------|---------|----------|
| Cache Hit Ratio (Index) | < 95% | < 90% |
| Connection Utilization | > 70% | > 85% |
| Slow Queries | > 10 | > 25 |
| Database Size Growth | > 50% increase/week | > 100% increase/week |

---

### 4. Clean Up OCR Temporary Files

**Schedule**: Daily at midnight UTC
**Task**: `tasks.database_maintenance.cleanup_ocr_temp_files`
**Duration**: 30 seconds - 5 minutes (depends on temp file volume)

#### What It Does

Removes temporary OCR processing files older than 7 days:
- `.tmp` files from incomplete OCR processing
- `.processing` files left behind by crashed workers
- Orphaned intermediate documents

#### Retention Policy

| File Type | Retention | Rationale |
|-----------|-----------|-----------|
| OCR Temp (.tmp, .processing) | 7 days | Processing typically completes in < 1 hour; 7 days allows for retry/investigation |
| OCR Results | Permanent | Final processed documents stored in primary archive |

#### Cleanup Directories

```
/app/data/ocr/temp/
/app/data/ocr/processing/
```

#### Configuration

```python
OCR_TEMP_FILE_RETENTION_DAYS = 7  # Environment variable
```

#### CloudWatch Metrics

- `TaxPlatform/Database/OcrTempFilesDeleted` - Number of files deleted
- `TaxPlatform/Database/OcrTempBytesFreed` - Storage reclaimed (bytes)

---

### 5. Setup pg_cron (Database-Side Maintenance)

**Schedule**: One-time setup task (non-recurring)
**Task**: `tasks.database_maintenance.setup_pg_cron`

#### What It Does

Enables the PostgreSQL `pg_cron` extension (if available with superuser privileges) to schedule database-side maintenance jobs:

| Job | Schedule | Purpose |
|-----|----------|---------|
| `reindex-high-churn-tables` | Daily 4:00 AM UTC | Rebuild fragmented indexes on hot tables |
| `analyze-database` | Hourly at :15 minutes | Update table statistics |

#### Requirements

- Requires PostgreSQL superuser privilege (DBA role)
- `pg_cron` extension must be available on RDS instance
- May require AWS RDS Parameter Group modification

#### Configuration

If RDS parameter group is updated to allow pg_cron:

```bash
# AWS RDS Parameter Group setting
rds.allowed_extensions = pg_cron
```

#### Status

Check if pg_cron is enabled:

```bash
# Check extension status
psql -c "SELECT * FROM pg_extension WHERE extname = 'pg_cron'"

# List active cron jobs
psql -c "SELECT * FROM cron.job"
```

---

### 6. Redis Session Purge (Existing Task)

**Schedule**: Hourly
**Task**: `tasks.data_retention.purge_expired_sessions`
**Duration**: < 1 second

#### What It Does

- **SQLite Sessions**: Deletes sessions that have exceeded their TTL from session persistence store
- **Redis Sessions**: Auto-expire via TTL; task cleans up orphaned index entries

#### Retention Policy

| Storage | TTL | Cleanup |
|---------|-----|---------|
| Redis | 72 hours (SESSION_RETENTION_HOURS) | TTL-based auto-expiry |
| SQLite | 72 hours | Hourly cleanup task |

#### Configuration

```python
SESSION_RETENTION_HOURS = 72  # Environment variable
```

---

## Data Retention Summary

### Production Environment Retention Windows

| Data | Live Database | Archive | Total Retention | Purpose |
|------|---------------|---------|-----------------|---------|
| **Audit Logs** | 90 days | S3 (indefinite) | 7+ years | Regulatory/IRS compliance |
| **Session Data** | 72 hours | None | 72 hours | User session lifecycle |
| **Tax Returns** | Permanent | Not archived | Permanent | Core business data |
| **OCR Temp Files** | 7 days | None | 7 days | Processing retry window |
| **Orphaned Uploads** | 30 days | None | 30 days | File cleanup safety window |
| **Calculations Cache** | 30 days | None | 30 days | Audit trail and performance |

### Development/Staging Environment

- **Audit Logs**: 90 days total (no archive to S3)
- **Backups**: 1 day retention (vs 30 days in production)
- **Sessions**: Same as production (72 hours)

---

## Monitoring & Alerting

### CloudWatch Dashboard

Create a dashboard in AWS CloudWatch to visualize:

1. **Performance Metrics**
   - Cache hit ratios (target: > 95%)
   - Active connections vs. max
   - Slow query count

2. **Maintenance Status**
   - Last VACUUM ANALYZE success/failure
   - Audit logs archived count
   - OCR temp files cleaned

3. **Storage Trends**
   - Database size growth
   - Largest tables over time
   - Archive size in S3

### Recommended CloudWatch Alarms

```bash
# High connection utilization
Connection Utilization > 80% for 5 minutes

# Low cache hit ratio
Index Cache Hit Ratio < 90% for 15 minutes

# High slow query volume
Slow Queries > 20 for 10 minutes

# Maintenance task failure
VacuumAnalyzeSuccess = 0 for 1 occurrence
StatsCollectionSuccess = 0 for 1 occurrence
```

### Viewing Metrics

```bash
# List all custom metrics
aws cloudwatch list-metrics --namespace "TaxPlatform/Database"

# Get recent metric data
aws cloudwatch get-metric-statistics \
  --namespace "TaxPlatform/Database" \
  --metric-name "VacuumAnalyzeSuccess" \
  --start-time 2026-04-03T00:00:00Z \
  --end-time 2026-04-05T00:00:00Z \
  --period 86400 \
  --statistics Sum
```

---

## Operational Procedures

### Manual VACUUM ANALYZE (Emergency)

If a table is experiencing severe bloat, run manually:

```bash
# SSH into application or RDS bastion host
psql $DATABASE_URL -c "VACUUM ANALYZE tax_returns;"
```

### Retrieve Archived Audit Logs

Query archived logs from S3:

```bash
# List audit log archives
aws s3 ls s3://jorss-gbo-documents/archives/audit-logs/

# Download specific date's archive
aws s3 cp s3://jorss-gbo-documents/archives/audit-logs/2026-04-05/ . --recursive

# Search across multiple archives
zgrep "user_id:12345" *.jsonl | jq .
```

### Monitor REINDEX Status

If pg_cron is enabled:

```bash
# Check last execution
psql -c "SELECT * FROM cron.job_run_details ORDER BY end_time DESC LIMIT 5;"
```

### Check Maintenance Task Logs

```bash
# Docker compose
docker-compose logs -f celery-worker | grep database_maintenance

# Kubernetes
kubectl logs -l app=celery-worker --tail=100 -f | grep database_maintenance
```

---

## Performance Impact Analysis

### Resource Usage Estimates

| Task | Frequency | Duration | CPU | Disk I/O | Memory | Lock Impact |
|------|-----------|----------|-----|----------|--------|-------------|
| VACUUM ANALYZE | Weekly | 5-15m | 20% | High | 100MB | Exclusive/brief |
| Archive Audit Logs | Weekly | 10-30m | 5% | Medium | 200MB | None |
| Collect pg_stats | Hourly | 1-2s | 1% | Low | 10MB | None |
| OCR Temp Cleanup | Daily | 30s-5m | 2% | Low | 20MB | None |
| Redis Session Purge | Hourly | < 1s | < 1% | None | 5MB | None |

### Recommended Off-Peak Windows

- **High-Impact Tasks**: VACUUM ANALYZE (weekly Sunday 1-2 AM UTC)
- **Medium-Impact Tasks**: Archive Audit Logs (weekly Monday 3-4 AM UTC)
- **Low-Impact Tasks**: Can run anytime (stats, cleanup)

---

## Troubleshooting

### VACUUM ANALYZE Running Long

**Symptom**: VACUUM ANALYZE takes > 30 minutes

**Causes**:
- Table has severe bloat (many dead rows)
- Disk I/O contention
- Other locks on the table

**Solutions**:
1. Check table bloat: `SELECT schemaname, tablename, round(100.0 * (ROUND(cc::float/ma,4)) - 1, 2) AS ratio FROM pgstattuple_approx('table_name');`
2. If > 50% bloat, consider `REINDEX CONCURRENT`
3. Check for long-running queries: `SELECT * FROM pg_stat_activity;`

### Audit Log Archival Fails

**Symptom**: `archive_audit_logs` task fails

**Causes**:
- S3 bucket not accessible
- IAM permissions insufficient
- Network connectivity issue

**Solutions**:
1. Verify S3 bucket exists: `aws s3 ls s3://jorss-gbo-documents/`
2. Test put object: `aws s3 cp test.txt s3://jorss-gbo-documents/test.txt`
3. Check ECS task role permissions for `s3:PutObject`
4. Check CloudWatch logs for detailed error

### High Connection Utilization

**Symptom**: Connection utilization > 80%

**Causes**:
- Increased traffic
- Connection leaks
- Inefficient connection pooling

**Solutions**:
1. Check slow queries: `SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC;`
2. Scale ECS task count
3. Increase RDS `max_connections` parameter
4. Add connection pooling (PgBouncer)

---

## Related Documentation

- [AWS RDS Documentation](https://docs.aws.amazon.com/rds/)
- [PostgreSQL VACUUM](https://www.postgresql.org/docs/current/sql-vacuum.html)
- [PostgreSQL Statistics](https://www.postgresql.org/docs/current/monitoring-stats.html)
- [pg_cron Extension](https://github.com/citusdata/pg_cron)
- [Celery Beat Documentation](https://docs.celeryproject.io/en/stable/userguide/periodic-tasks.html)

---

## Maintenance Task Runbook

### Monthly Review

1. Check CloudWatch dashboard for trends
2. Review slow query logs
3. Verify archive growth is reasonable (should be 1-5 GB/month)
4. Check for any task failures in Celery
5. Adjust thresholds/schedules if needed

### Quarterly Review

1. Validate 90-day archive volume matches expectations
2. Test audit log retrieval from S3
3. Review pg_stat metrics for anomalies
4. Capacity planning: project storage growth

### Annual Review

1. Verify 7-year audit log archives are accessible
2. Disaster recovery: practice restoring from backups
3. Update retention policies if regulatory changes
4. Performance tuning based on growth metrics

---

## Contact & Escalation

**Database Maintenance Issues**: DevOps team (Slack: #devops)
**Production Incidents**: On-call engineer
**Compliance/Regulatory Questions**: Legal team
