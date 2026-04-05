# IRS MeF Backup Transmission Procedures

**Effective Date:** 2026-04-05
**Owner:** CTO
**Review Cycle:** Annual
**Regulatory Basis:** IRS Publication 1345, MeF Submission Composition Guide

---

## 1. Purpose

Defines procedures when the primary IRS MeF (Modernized e-File) connection is unavailable, ensuring returns are filed by deadline and taxpayers are notified of any delays.

## 2. Primary Transmission Path

- **Endpoint:** IRS MeF production API (`https://la.www4.irs.gov/mef/`)
- **Protocol:** SOAP over HTTPS with IRS-issued TLS client certificate
- **Service:** `irs-efile-service` (ECS task in `us-east-1`)
- **Submission window:** IRS accepts transmissions 24/7 except during scheduled maintenance (typically Sunday 00:00–08:00 ET)

## 3. Failure Detection

The e-File service reports:
- `CONNECTION_FAILED`: Cannot reach IRS endpoint
- `AUTH_REJECTED`: Credentials invalid or ETIN suspended
- `SERVICE_UNAVAILABLE`: IRS maintenance window
- `TRANSMISSION_REJECTED`: Return failed IRS validation (not an infrastructure failure)

Automatic alerting: CloudWatch alarm → PagerDuty → CTO on-call within 5 minutes of IRS endpoint failure.

## 4. Backup Procedures

### 4.1 IRS Scheduled Maintenance (Planned)
- Duration: typically 8 hours on Sunday
- Action: queue returns; auto-retry when service resumes
- Taxpayer notification: none required (not a delay, returns queued)
- SLA: all queued returns transmitted within 2 hours of IRS service restoration

### 4.2 IRS Unplanned Outage (Up to 24 hours)
1. `irs-efile-service` queues all new submissions to SQS dead-letter queue
2. CTO notified; IRS outage status checked at `https://www.irs.gov/e-file-providers/irs-efile-health-check`
3. Taxpayers with imminent deadlines (within 24 hours) notified via email: "Your return has been prepared and will be filed as soon as the IRS system is restored."
4. Auto-retry every 30 minutes
5. If outage > 24 hours: escalate to CEO; evaluate IRS deadline relief provisions

### 4.3 Extended IRS Outage (24+ hours, or deadline approaching)
1. IRS typically grants automatic deadline extensions for documented system outages
2. Document the outage with IRS status page screenshots
3. Taxpayer communication: proactive email with IRS outage acknowledgment
4. Paper filing fallback: if a taxpayer's deadline is imminent and IRS is unreachable for >48 hours, offer to generate a paper return PDF for manual mailing (last resort)

### 4.4 Platform-Side Failure (our infrastructure)
If `irs-efile-service` fails but IRS is available:
- ECS auto-scaling respawns failed tasks
- SQS ensures no transmissions are lost
- RTO: 15 minutes (ECS task respawn)
- RPO: 0 (all submissions durable in SQS before processing)

## 5. Transmission Queue Architecture

```
Taxpayer Submit → API Gateway
                      ↓
                  SQS Queue (irs-submission-queue)
                      ↓
              irs-efile-service (ECS)
                      ↓
              IRS MeF Endpoint
                      ↓
              ACK stored in S3 + DB
```

- SQS message retention: 14 days
- Dead-letter queue: `irs-submission-dlq` (after 3 failed attempts)
- Manual DLQ replay: CTO can trigger via AWS console or CLI

## 6. Taxpayer Notifications

| Scenario | Notification Trigger | Message |
|----------|---------------------|---------|
| Return queued (IRS maintenance) | Auto, after 2-hour delay | "Your return is queued and will be filed shortly." |
| IRS outage > 4 hours | Auto | "IRS system is temporarily unavailable. We'll file your return as soon as it's restored." |
| Outage near deadline | Manual (CTO) | "Due to an IRS system outage, your return filing may be delayed. We're monitoring the situation." |
| Return successfully filed | Auto | Standard ACK confirmation email |

## 7. Testing

- **Quarterly:** test SQS retry logic in staging using IRS ATS environment
- **Annual:** tabletop exercise of extended outage scenario with engineering lead
- **Pre-filing season (January):** verify IRS endpoint connectivity and credentials

---

*These procedures are designed to ensure compliance with IRS e-File Program requirements while protecting taxpayers from missed deadlines due to infrastructure events.*
