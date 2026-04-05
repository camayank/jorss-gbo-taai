# RDS Backup & Disaster Recovery Guide

## Overview

This document describes the backup and disaster recovery architecture for the AI Tax Advisor platform's PostgreSQL database. The system is designed for **zero-RPO** (zero data loss) primary failover and **near-zero-RTO** (near-zero recovery time) with automated failover.

## Architecture

### Components

1. **Primary Database (us-east-1)**
   - Multi-AZ PostgreSQL instance with synchronous replication
   - Automated daily snapshots with 30-day retention
   - CloudWatch logs exported for analysis

2. **Read Replica (us-west-2)**
   - Cross-region read replica for geo-redundancy
   - Can be promoted to standalone instance for failover
   - Enables faster recovery in case of regional outage

3. **Automated Snapshots**
   - Daily snapshots at 03:00 UTC
   - 30-day retention policy
   - Automatic tags propagated for resource management

4. **Backup Validation**
   - Weekly automated backup verification
   - Restore-and-verify testing to catch corruption early
   - CloudWatch logging for audit trail

## Recovery Objectives

### RTO (Recovery Time Objective)

| Scenario | RTO | Details |
|----------|-----|---------|
| Primary node failure | **< 5 minutes** | Automatic failover to standby in different AZ |
| Primary AZ outage | **< 5 minutes** | Same as above (Multi-AZ) |
| Regional outage (us-east-1) | **15-30 minutes** | Promote us-west-2 read replica + application migration |
| Corruption/data loss | **30-60 minutes** | Restore from snapshot + validation |

### RPO (Recovery Point Objective)

| Scenario | RPO | Details |
|----------|-----|---------|
| Node failure | **0 minutes** | Synchronous Multi-AZ replication (zero data loss) |
| Regional outage | **0-5 minutes** | Read replica has minimal replication lag |
| Snapshot restore | **Up to 24 hours** | Can restore to any point with snapshots |

## Failover Procedures

### Scenario 1: Primary Node Failure (AZ Failure)

**Automatic** — AWS RDS handles failover automatically.

Timeline:
1. Instance becomes unavailable (0-1 minute detection)
2. Automatic failover triggered (< 1 minute)
3. Standby instance promoted (2-3 minutes)
4. DNS endpoint updated (< 1 minute)
5. Application reconnects automatically
6. Service restored

**Action Required:** None — fully automatic with Multi-AZ.

**Validation:**
```bash
# Check Multi-AZ status
aws rds describe-db-instances \
  --db-instance-identifier jorss-gbo-prod-postgres \
  --region us-east-1 \
  --query 'DBInstances[0].MultiAZ'
```

### Scenario 2: Regional Outage (us-east-1 Unavailable)

**Manual** — Requires application and DNS reconfiguration.

Timeline:
1. Detect us-east-1 outage (requires external monitoring)
2. Promote read replica in us-west-2 (< 5 minutes)
3. Update application connection strings
4. Redirect DNS/ALB to us-west-2
5. Repoint backups to new primary

**Steps:**

#### Phase 1: Promote Read Replica

```bash
# 1. Identify the read replica
aws rds describe-db-instances \
  --region us-west-2 \
  --db-instance-identifier jorss-gbo-prod-postgres-replica-usw2 \
  --query 'DBInstances[0].{Status: DBInstanceStatus, Endpoint: Endpoint.Address}'

# 2. Promote read replica to standalone instance
aws rds promote-read-replica \
  --db-instance-identifier jorss-gbo-prod-postgres-replica-usw2 \
  --region us-west-2 \
  --backup-retention-period 7

# 3. Wait for promotion to complete (monitor for ~5 minutes)
aws rds describe-db-instances \
  --region us-west-2 \
  --db-instance-identifier jorss-gbo-prod-postgres-replica-usw2 \
  --query 'DBInstances[0].DBInstanceStatus'
```

#### Phase 2: Update Application Configuration

```bash
# Update SSM parameters with new endpoint
NEW_ENDPOINT=$(aws rds describe-db-instances \
  --region us-west-2 \
  --db-instance-identifier jorss-gbo-prod-postgres-replica-usw2 \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text)

aws ssm put-parameter \
  --name "/jorss-gbo/production/database-url" \
  --value "postgresql://postgres:PASSWORD@${NEW_ENDPOINT}:5432/jorss_gbo" \
  --overwrite \
  --region us-west-2

# Redeploy application to use new endpoint
# (Use your standard deployment process)
```

#### Phase 3: Verify Replication and Backups

```bash
# 1. Verify the new primary is accepting writes
psql -h $(echo $NEW_ENDPOINT) -U postgres -d jorss_gbo \
  -c "SELECT version();"

# 2. Check backup status
aws rds describe-db-instances \
  --region us-west-2 \
  --db-instance-identifier jorss-gbo-prod-postgres-replica-usw2 \
  --query 'DBInstances[0].{BackupRetention: BackupRetentionPeriod, LatestBackup: LatestRestorableTime}'

# 3. Create new read replica in another region if desired
```

### Scenario 3: Data Corruption / Accidental Deletion

**Manual restore** — Restore from automated snapshot.

Timeline:
1. Identify last good snapshot
2. Create new instance from snapshot (or restore to source)
3. Validate data integrity
4. Switch traffic to restored instance
5. Total: 30-60 minutes depending on data size

**Steps:**

```bash
# 1. List available snapshots
aws rds describe-db-snapshots \
  --db-instance-identifier jorss-gbo-prod-postgres \
  --region us-east-1 \
  --query 'DBSnapshots[*].[DBSnapshotIdentifier,SnapshotCreateTime,Status]' \
  --output table

# 2. Create new instance from snapshot
SNAPSHOT_ID="<select-latest-good-snapshot>"
NEW_INSTANCE_ID="jorss-gbo-prod-postgres-restore-$(date +%s)"

aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier $NEW_INSTANCE_ID \
  --db-snapshot-identifier $SNAPSHOT_ID \
  --db-instance-class db.t3.micro \
  --region us-east-1

# 3. Wait for restore (monitor progress)
aws rds describe-db-instances \
  --db-instance-identifier $NEW_INSTANCE_ID \
  --region us-east-1 \
  --query 'DBInstances[0].DBInstanceStatus'

# 4. Run validation script
python3 infra/scripts/validate-backup.py \
  --db-identifier $NEW_INSTANCE_ID \
  --region us-east-1 \
  --password-ssm-param /jorss-gbo/production/db-password

# 5. Swap DNS/application to use restored instance
# (Use your standard deployment process)

# 6. Delete corrupted instance after verification
aws rds delete-db-instance \
  --db-instance-identifier jorss-gbo-prod-postgres \
  --skip-final-snapshot \
  --region us-east-1
```

## Backup Validation

### Automated Validation (Weekly)

The backup validation script runs automatically (via Lambda or cron) every week to verify backup integrity:

```bash
python3 infra/scripts/validate-backup.py \
  --db-identifier jorss-gbo-prod-postgres \
  --region us-east-1 \
  --password-ssm-param /jorss-gbo/production/db-password \
  --timeout-hours 2
```

**What it does:**
1. Finds the most recent automated backup
2. Restores to temporary test database
3. Validates database structure and sample data
4. Logs results to CloudWatch
5. Cleans up test database

**CloudWatch Logs:**
- Location: `/aws/rds/jorss-gbo-prod-postgres/backup-validation`
- Stream: `YYYY/MM/DD/backup-validation`
- Monitor for status and errors

### Manual Validation

To manually verify a backup:

```bash
# Option 1: Using validation script
python3 infra/scripts/validate-backup.py \
  --db-identifier jorss-gbo-prod-postgres \
  --region us-east-1 \
  --username postgres \
  --password-ssm-param /jorss-gbo/production/db-password

# Option 2: Manual restore and test
SNAPSHOT=$(aws rds describe-db-snapshots \
  --db-instance-identifier jorss-gbo-prod-postgres \
  --region us-east-1 \
  --query 'DBSnapshots[-1].[DBSnapshotIdentifier]' \
  --output text)

aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier jorss-gbo-manual-test-$(date +%s) \
  --db-snapshot-identifier $SNAPSHOT \
  --db-instance-class db.t3.micro \
  --region us-east-1

# Wait for restore, then connect and verify
psql -h <restored-endpoint> -U postgres -d jorss_gbo \
  -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname='public';"
```

## Monitoring & Alerting

### CloudWatch Metrics to Monitor

```bash
# Backup window completion
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name SnapshotStorageUsed \
  --dimensions Name=DBInstanceIdentifier,Value=jorss-gbo-prod-postgres \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Maximum
```

### Recommended Alarms

1. **Backup Failure** — No backup completed in 26 hours
2. **Replication Lag** — Read replica lag > 1 second (for cross-region)
3. **Multi-AZ Failover** — Alert when failover occurs
4. **Validation Failure** — Backup validation script returns failure
5. **Disk Space** — Free storage < 10% of allocated

## Maintenance & Testing

### Monthly Failover Drill (Recommended)

Once monthly, practice failover procedures in a staging environment:

1. Simulate primary failure
2. Trigger failover to standby
3. Verify application connectivity
4. Document any issues
5. Update runbooks

### Quarterly Snapshot Restore Test

Quarterly, restore a production snapshot to staging and run integration tests:

```bash
# Get latest snapshot
SNAPSHOT=$(aws rds describe-db-snapshots \
  --db-instance-identifier jorss-gbo-prod-postgres \
  --region us-east-1 \
  --snapshot-type automated \
  --query 'DBSnapshots[-1].DBSnapshotIdentifier' \
  --output text)

# Restore to staging
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier jorss-gbo-staging-postgres-$(date +%s) \
  --db-snapshot-identifier $SNAPSHOT \
  --db-instance-class db.t3.micro \
  --region us-east-1

# Run integration tests
# ... your test commands ...

# Clean up
```

## Compliance & Documentation

- **Backup Retention Policy**: 30 days (automated snapshots)
- **Retention Compliance**: Meets regulatory data preservation requirements
- **RTO SLA**: 5 minutes (primary failover), 30 minutes (regional failover)
- **RPO SLA**: 0 minutes (primary), 5 minutes (regional)
- **Last Tested**: Track in Paperclip/issue management
- **Next Review**: Quarterly

## Terraform Configuration

The backup and disaster recovery configuration is defined in:
- `infra/terraform/main.tf` — Primary DB with Multi-AZ, 30-day retention
- `infra/terraform/main.tf` — Cross-region read replica
- `infra/terraform/outputs.tf` — Endpoints and configuration outputs

To apply changes:

```bash
cd infra/terraform
terraform plan
terraform apply
```

## Support & Escalation

For DR incidents:

1. **On-Call**: Escalate to CTO/Engineering Lead
2. **Communication**: Update status channel immediately
3. **Post-Mortem**: Document incident and improvements within 24 hours
4. **Testing**: Run failover drill within 1 week of incident

## Quick Reference

| Task | Command |
|------|---------|
| Check primary status | `aws rds describe-db-instances --db-instance-identifier jorss-gbo-prod-postgres --region us-east-1` |
| Check replica lag | `aws rds describe-db-instances --db-instance-identifier jorss-gbo-prod-postgres-replica-usw2 --region us-west-2` |
| List snapshots | `aws rds describe-db-snapshots --db-instance-identifier jorss-gbo-prod-postgres --region us-east-1` |
| Start validation | `python3 infra/scripts/validate-backup.py --db-identifier jorss-gbo-prod-postgres --region us-east-1` |
| View validation logs | `aws logs tail /aws/rds/jorss-gbo-prod-postgres/backup-validation --follow` |

---

**Document Version**: 1.0
**Last Updated**: 2026-04-05
**Reviewed By**: DevOps Engineer
**Next Review**: 2026-07-05
