# EFIN Security and Handling Policy

**Effective Date:** 2026-04-05
**Owner:** CTO
**Review Cycle:** Annual
**Regulatory Basis:** IRS Publication 1345, IRC §7216, IRS Safeguards Rule (Publication 4600)

---

## 1. Purpose

This policy governs the secure handling, storage, access control, and incident response for jorss-gbo-taai's Electronic Filing Identification Number (EFIN) and Electronic Transmitter Identification Number (ETIN).

## 2. What Is the EFIN/ETIN

- **EFIN:** 6-digit identifier issued by IRS to Authorized e-File Providers. Required on every return transmitted to the IRS. Compromise of EFIN allows fraudulent return filing under our identity.
- **ETIN:** Identifier issued to electronic return transmitters. Required for direct MeF API submission.

## 3. Credential Storage

### 3.1 AWS Secrets Manager (Required)

EFIN and ETIN must NEVER be stored in:
- Source code or version control
- Environment variables in plain text
- Application config files
- Database fields in plaintext
- Logs

**Approved storage:** AWS Secrets Manager only.

| Secret Name | Value | Rotation |
|-------------|-------|----------|
| `prod/irs/efin` | 6-digit EFIN string | Manual (IRS re-issues) |
| `prod/irs/etin` | ETIN string | Manual |
| `prod/mef/api-credentials` | MeF API key/cert bundle | Manual |

### 3.2 IAM Access Policy

Only the `irs-efile-service` IAM role may access EFIN/ETIN secrets:

```json
{
  "Effect": "Allow",
  "Principal": {
    "AWS": "arn:aws:iam::ACCOUNT_ID:role/irs-efile-service"
  },
  "Action": [
    "secretsmanager:GetSecretValue"
  ],
  "Resource": [
    "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:prod/irs/*"
  ]
}
```

All secret access is logged via CloudTrail.

### 3.3 Audit Logging

- CloudTrail: all `GetSecretValue` calls on `prod/irs/*` secrets are logged
- Alerts: CloudWatch alarm triggers if EFIN secret is accessed more than 100 times/hour (anomaly detection)
- Quarterly: CTO reviews access logs for unauthorized or unexpected access

## 4. Personnel Access

- **EFIN value is known to:** Responsible Official (the individual who filed Form 8633) and CTO only
- **No sharing:** EFIN must not be shared with external parties, contractors, or third-party services
- **Offboarding:** If the Responsible Official leaves, Form 8633 amendment required immediately to designate new Responsible Official

## 5. Annual EFIN Verification

The IRS requires annual verification of EFIN status:
1. Log into IRS e-Services at the start of each filing season (January)
2. Verify EFIN is active and in good standing
3. Confirm no unauthorized use has been reported
4. Document verification in this policy's audit log

## 6. Incident Response — EFIN Compromise

If EFIN is suspected to be compromised or misused:

### Immediate Actions (within 1 hour)
1. Revoke MeF API access: disable `irs-efile-service` IAM role
2. Rotate `prod/irs/efin` secret in Secrets Manager (set to placeholder)
3. Notify IRS EFIN Security at 1-866-255-0654
4. Notify CEO and legal counsel

### Within 24 hours
5. File IRS Form 14039 (Identity Theft Affidavit) if fraudulent returns suspected
6. Review CloudTrail logs to determine scope of unauthorized access
7. Notify affected taxpayers if their returns may have been impacted

### Recovery
8. Work with IRS to issue new EFIN
9. Resume transmissions only after new EFIN confirmed active
10. Conduct post-incident review; update this policy

## 7. Written Information Security Plan (WISP)

Per IRS Publication 4557, jorss-gbo-taai maintains a WISP covering:
- Data inventory (what PII we hold, where)
- Access controls (EFIN, SSN, return data)
- Employee security training (annual)
- Incident response plan (this document + `disaster-recovery.md`)
- Vendor due diligence (AWS, any third-party integrations)

Full WISP document: `docs/compliance/irs/wisp.md` (to be created before EFIN issuance).

---

*Non-compliance with EFIN security requirements may result in EFIN revocation and suspension from the IRS e-File program.*
