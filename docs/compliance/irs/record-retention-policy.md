# IRS Record Retention Policy

**Effective Date:** 2026-04-05
**Owner:** CTO
**Review Cycle:** Annual
**Regulatory Basis:** IRC §6107, IRS Publication 1345, IRS e-File Program requirements

---

## 1. Purpose

This policy establishes jorss-gbo-taai's obligations to retain electronic filing records in compliance with IRS requirements for Authorized IRS e-File Providers.

## 2. Scope

Applies to all tax return data, acknowledgments, and related records processed through the jorss-gbo-taai platform.

## 3. Retention Requirements

### 3.1 Minimum Retention Period: 4 Years

The IRS requires Authorized e-File Providers to retain records for **4 years** from the due date of the return or the date it was filed, whichever is later.

### 3.2 What Must Be Retained

| Record Type | Format | Retention Period | Storage Location |
|-------------|--------|------------------|------------------|
| Submitted return XML | XML (gzipped) | 4 years | S3: `s3://jorss-tax-returns-archive/{year}/returns/` |
| IRS Acknowledgment (ACK) | XML | 4 years | S3: `s3://jorss-tax-returns-archive/{year}/acks/` |
| Rejection codes and messages | JSON | 4 years | PostgreSQL: `return_submissions` table + S3 |
| Taxpayer consent/authorization | PDF or JSON | 4 years | S3: `s3://jorss-tax-returns-archive/{year}/consents/` |
| Transmission logs | JSON | 4 years | CloudWatch Logs (retained) + S3 archival |
| EFIN usage logs | JSON | 4 years | CloudWatch Logs + S3 |

### 3.3 What Must NOT Be Retained

- Social Security Numbers (SSNs) in plaintext logs
- Full return data in application logs (structured log entries only)
- PII in error messages or stack traces

## 4. Storage Architecture

### 4.1 Primary Storage
- **Database:** PostgreSQL RDS (return metadata, status, identifiers)
- **Object Storage:** AWS S3 with versioning enabled
  - Bucket: `jorss-tax-returns-archive`
  - Encryption: SSE-S3 (AES-256) at rest
  - Versioning: Enabled (protects against accidental deletion)

### 4.2 S3 Lifecycle Policy
```json
{
  "Rules": [
    {
      "Status": "Enabled",
      "Transitions": [
        {
          "Days": 365,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 730,
          "StorageClass": "GLACIER"
        }
      ],
      "Expiration": {
        "Days": 1826
      }
    }
  ]
}
```

Retention: 5 years in S3 (1 year buffer beyond IRS 4-year minimum).

### 4.3 Access Controls
- S3 bucket: private, no public access
- IAM role: only `irs-efile-service` role can write; compliance audit role can read
- S3 access logging: enabled, logs shipped to `s3://jorss-access-logs/`

## 5. Deletion Procedures

After the 4-year retention period:
1. Automated S3 lifecycle expiration handles deletion
2. Database records are soft-deleted (anonymized) — taxpayer PII removed, aggregate statistics retained
3. Deletion events logged to CloudTrail

## 6. Audit and Verification

- Annual review: CTO verifies retention configuration
- Quarterly: automated test queries to confirm records exist for current - 4 years
- Incident response: if records are found missing, notify legal and IRS liaison immediately

---

*This policy satisfies IRS Publication 1345 Section 2 retention requirements for Authorized e-File Providers.*
