# Celery Workers Setup & Testing

This document covers the setup, testing, and monitoring of Celery background workers for the AI Tax Advisor platform.

## Overview

Celery workers handle asynchronous background tasks:
- **OCR Document Processing** — PDF/image text extraction via Tesseract
- **Email Delivery** — Async notification dispatch
- **Report Generation** — PDF creation and delivery
- **Analytics** — Materialized view refresh scheduler
- **Data Maintenance** — Session purge, audit log cleanup, orphaned file cleanup

## Development Setup (Docker Compose)

### Start All Services Including Workers

```bash
docker-compose up
```

This starts:
- **app** (FastAPI server on http://localhost:8000)
- **worker** (Celery worker with 4 concurrent tasks)
- **flower** (Task monitoring UI on http://localhost:5555)
- **redis** (Message broker & result backend)
- **postgres** (Database)

### Monitor Active Tasks

```bash
# Via Flower web UI
open http://localhost:5555/flower/

# Or via CLI
celery -A tasks.celery_app inspect active

# Check worker status
celery -A tasks.celery_app inspect stats
```

### Run End-to-End Test

1. **Queue a task** (e.g., document OCR):
```python
from tasks.ocr_tasks import process_document_async

# Submit a test task
result = process_document_async.delay(file_path="/path/to/document.pdf")
print(f"Task ID: {result.id}")
```

2. **Monitor execution in Flower**:
   - Visit http://localhost:5555/flower/
   - Look for the task in the **Tasks** tab
   - Verify status transitions: PENDING → STARTED → SUCCESS (or FAILURE)

3. **Check logs**:
```bash
docker-compose logs -f worker
```

## Production Setup (ECS Fargate)

### Deployment

The worker runs as a separate ECS service:
- **Task Definition**: `jorss-gbo-{env}-worker`
- **Service Name**: `jorss-gbo-{env}-worker`
- **Desired Count**: 2 (configurable via `worker_desired_count` variable)
- **CPU/Memory**: Same as app service (default: 512 CPU, 1GB memory)

### Configuration

Workers are configured via Terraform variables:

```hcl
worker_desired_count = 2  # Number of concurrent worker tasks
log_retention_days = 14   # CloudWatch log retention
```

### Monitoring

1. **CloudWatch Logs**:
   - Log group: `/ecs/jorss-gbo-{env}-worker`
   - Log stream: `worker/{task-id}`

2. **CloudWatch Metrics** (Recommended):
   - Task count (desired vs running)
   - CPU & memory utilization
   - Celery task success/failure rates

3. **Alarms** (To be configured in MKW-45):
   - Worker task count drops below desired
   - Task failure rate exceeds threshold (e.g., > 5%)
   - Worker CPU/memory exceeded
   - Redis connection failures

## Task Configuration

### Available Tasks

Located in `src/tasks/`:

| Module | Tasks | Schedule |
|--------|-------|----------|
| `ocr_tasks.py` | Document OCR processing | On-demand |
| `notification_tasks.py` | Deadline reminders | Hourly |
| | Nurture emails | Hourly |
| | Opportunity scans | Daily @ 6 AM UTC |
| | Daily digest | Daily @ 7 AM UTC |
| `data_retention.py` | Session purge | Hourly |
| | Orphaned file cleanup | Daily @ midnight |
| | Audit log trim | Weekly |
| `backup.py` | Database backup | Daily @ 2 AM UTC |

### Testing Individual Tasks

```python
from tasks.ocr_tasks import process_document_async
from tasks.notification_tasks import process_deadline_reminders
from celery import current_app

# Run synchronously (for testing)
result = process_document_async.apply()

# Run asynchronously
result = process_document_async.delay(file_path="...")
print(f"Task queued: {result.id}")

# Check task status
from tasks.celery_app import get_task_info
info = get_task_info(result.id)
print(info)
```

## Troubleshooting

### Workers Not Processing Tasks

1. **Check Redis connection**:
```bash
redis-cli -h localhost -p 6379 -a changeme ping
# Should return: PONG
```

2. **Check worker is running**:
```bash
docker-compose ps worker
# Status should be "Up"
```

3. **Verify task was queued**:
```bash
celery -A tasks.celery_app inspect active
# Should show tasks in queue
```

4. **Check worker logs**:
```bash
docker-compose logs worker | tail -50
```

### High Memory Usage

- Reduce concurrency in worker command: `--concurrency=2` (default 4)
- Increase time limits: `--time-limit=3600` (1 hour)
- Monitor with Flower

### Tasks Getting Stuck

- Check for deadlocked database transactions
- Verify database connections aren't exhausted
- Check Redis memory usage
- Review task logs in CloudWatch

## Performance Tuning

### Worker Concurrency
Default: **4 concurrent tasks per worker**

For CPU-heavy tasks (OCR): Keep at 2-4
For I/O-heavy tasks (emails): Can increase to 6-8

Change in docker-compose.yml or ECS task command.

### Time Limits
- **Hard limit** (time-limit): 3600 seconds (1 hour)
- **Soft limit** (soft-time-limit): 3300 seconds (55 min)

Tasks exceeding soft limit receive SoftTimeLimitExceeded exception.

### Prefetch Multiplier
Default: **4** (worker prefetches 4 tasks at a time)

Reduce for long-running tasks, increase for quick tasks.

## Next Steps (MKW-45)

- [ ] Set up X-Ray distributed tracing for Celery tasks
- [ ] Add Sentry integration for error tracking
- [ ] Create CloudWatch dashboard with task metrics
- [ ] Configure alarms for worker health
- [ ] Implement structured JSON logging with correlation IDs
- [ ] Add dead letter queue (DLQ) handling for failed tasks
- [ ] Implement task result expiration cleanup
