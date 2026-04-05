# Observability Stack Setup

Complete monitoring and observability infrastructure for the AI Tax Advisor platform using AWS CloudWatch, X-Ray, and Sentry.

## Overview

The observability stack provides:
- **CloudWatch Logs** - Centralized logging from all ECS tasks
- **CloudWatch Alarms** - Proactive alerting on key metrics
- **CloudWatch Dashboard** - Real-time service health overview
- **X-Ray** - Distributed tracing for request flow analysis
- **Sentry** - Application error tracking and reporting

## CloudWatch Logs

### Log Groups

All services log to CloudWatch:

| Service | Log Group | Retention |
|---------|-----------|-----------|
| Application | `/ecs/jorss-gbo-{env}` | 14 days |
| Workers | `/ecs/jorss-gbo-{env}-worker` | 14 days |

### Log Metrics

Automatic metrics extracted from logs:

- **Error Count** — Detects ERROR, CRITICAL, Exception, 5xx/502/503 status
- **5xx Errors** — HTTP 5xx response codes from ALB

## CloudWatch Alarms

### Alarm Configuration

All alarms send to SNS topics:
- **alerts** — Standard alerts (email, Slack)
- **critical_alerts** — Critical alerts requiring immediate action

### Configured Alarms

| Alarm | Metric | Threshold | Action |
|-------|--------|-----------|--------|
| ECS CPU High | CPUUtilization | > 80% (10 min) | alerts |
| ECS Memory High | MemoryUtilization | > 85% (10 min) | alerts |
| RDS CPU High | CPUUtilization | > 75% | alerts |
| RDS Storage Low | FreeStorageSpace | < 2GB | critical_alerts |
| RDS Replica Lag | ReplicaLag | > 1s (prod only) | alerts |
| ALB Unhealthy Hosts | UnHealthyHostCount | ≥ 1 | critical_alerts |
| ALB Response Time | TargetResponseTime | > 2s (avg) | alerts |
| HTTP 5xx Errors | HTTPCode_Target_5XX_Count | > 10 (5min) | critical_alerts |
| App Errors | Log metric | ≥ 10 (5min) | alerts |
| Worker Tasks Low | RunningCount | < desired | critical_alerts |

## CloudWatch Dashboard

### Access

Open CloudWatch Dashboard: `/ecs/jorss-gbo-{env}-dashboard`

Contains 6 visualizations:
1. **ALB Health & Performance** — Host count, request rate, response time
2. **HTTP Errors** — 4xx and 5xx error counts
3. **ECS Task Performance** — CPU and memory utilization
4. **RDS Performance** — CPU, connections, memory
5. **RDS Storage & Backups** — Storage space and backup usage
6. **Application Errors** — Error count from logs

## X-Ray Integration (TODO)

### Setup Requirements

1. **Enable X-Ray Service** in AWS
2. **IAM Permissions** — Add X-Ray write permissions to ECS task role
3. **AWS SDK Configuration** — Enable X-Ray daemon in application
4. **FastAPI Middleware** — Add X-Ray middleware to capture requests

### Implementation

```python
# In src/web/app.py
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

# Patch AWS clients
patch_all()

# Add middleware to FastAPI
app.add_middleware(XRayMiddleware)

# Wrap database calls
xray_recorder.begin_segment("database")
# ... query ...
xray_recorder.end_segment()
```

### Trace Visibility

- **Request Flow** — FastAPI → RDS → Redis → Celery
- **Worker Tasks** — Celery task execution with timestamps
- **Database Queries** — SQL query timing and results
- **Redis Operations** — Cache hits/misses with latency
- **External APIs** — OpenAI API calls with duration

## Structured JSON Logging (TODO)

### Requirements

1. **JSON Formatter** — Convert logs to structured JSON
2. **Correlation IDs** — Trace requests across services
3. **Application Context** — User, request, transaction IDs

### Fields to Include

```json
{
  "timestamp": "2026-04-05T11:30:00Z",
  "level": "INFO",
  "message": "Document processed",
  "correlation_id": "req-12345",
  "user_id": "user-999",
  "request_id": "api-req-456",
  "service": "app",
  "duration_ms": 1234,
  "error": null,
  "context": {
    "document_id": "doc-123",
    "file_size": 2048000,
    "processing_type": "OCR"
  }
}
```

## Sentry Integration (TODO)

### Setup Steps

1. **Create Sentry Project** for the application
2. **Install SDK** — `pip install sentry-sdk[fastapi]`
3. **Configure** in FastAPI app initialization:

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init(
    dsn=settings.sentry_dsn,
    integrations=[
        FastApiIntegration(),
        CeleryIntegration(),
    ],
    traces_sample_rate=0.1,  # 10% of requests
    profiles_sample_rate=0.1,  # 10% profiling
)
```

4. **Link CloudWatch** — Configure CloudWatch Logs trigger to send errors to Sentry
5. **Unified View** — All errors visible in Sentry dashboard with CloudWatch context

### Error Workflow

1. Error occurs in app
2. Sentry captures and sends to Sentry.io
3. CloudWatch Logs also capture via metric filter
4. Alarms trigger if error threshold exceeded
5. Engineers see errors in Sentry + alerts in SNS/Slack

## Monitoring Best Practices

### Alert Response

1. **Critical Alerts** — Immediate action required
   - ALB unhealthy (service down)
   - RDS storage critical
   - Worker tasks failing

2. **Standard Alerts** — Review within 1 hour
   - High CPU/memory
   - Slow response times
   - Elevated error rates

### Dashboard Usage

- **Daily Review** — Check dashboard for trends
- **On-Call** — Monitor when on-call rotation
- **Post-Incident** — Review dashboard during postmortem

### Log Analysis

Find errors:
```
# Via CloudWatch Logs Insights
fields @timestamp, @message, @level
| filter @level like /ERROR|CRITICAL/
| stats count() by @level
```

Track performance:
```
fields @duration
| stats avg(@duration), max(@duration), pct(@duration, 99)
```

## Troubleshooting

### No Logs Appearing

1. Check ECS task CloudWatch Logs configuration
2. Verify IAM permissions for CloudWatch Logs
3. Confirm log group exists and is writable
4. Check container startup logs

### Alarms Not Firing

1. Verify SNS topic subscriptions
2. Check alarm evaluation period (may need 10+ minutes)
3. Verify metric data is being published
4. Check alarm state history in CloudWatch

### Missing Metrics

- **Database connections** — Requires RDS Enhanced Monitoring
- **P99 latency** — Requires ALB access logs + processing
- **Redis memory** — Requires ElastiCache (if used)

## Next Steps

**Priority 1** (High Impact):
- [ ] Enable X-Ray distributed tracing
- [ ] Implement structured JSON logging
- [ ] Add correlation IDs to all logs

**Priority 2** (Important):
- [ ] Set up Sentry integration
- [ ] Link CloudWatch → Sentry
- [ ] Configure on-call alerting

**Priority 3** (Nice to Have):
- [ ] Custom dashboards per team
- [ ] Anomaly detection
- [ ] Capacity planning reports

## Configuration

### Terraform Variables

```hcl
log_retention_days = 14  # Adjust based on compliance needs
```

### Environment Variables

```bash
# X-Ray
AWS_XRAY_TRACING_ENABLED=true

# Sentry
SENTRY_DSN=https://key@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=1.0.0
```

## References

- [AWS CloudWatch Documentation](https://docs.aws.amazon.com/cloudwatch/)
- [AWS X-Ray Developer Guide](https://docs.aws.amazon.com/xray/latest/devguide/)
- [Sentry Python SDK](https://docs.sentry.io/platforms/python/)
