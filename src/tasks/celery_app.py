"""
Celery App Configuration - Background task processing with Redis broker.

Configures Celery for:
- OCR document processing
- Background calculations
- Async report generation

Usage:
    # Run worker
    celery -A tasks.celery_app worker --loglevel=info

    # Run with beat scheduler
    celery -A tasks.celery_app worker --beat --loglevel=info
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict, Optional

from celery import Celery, Task
from celery.signals import (
    task_failure,
    task_postrun,
    task_prerun,
    task_retry,
    task_success,
    worker_ready,
    worker_shutdown,
)

from config.settings import get_settings, CelerySettings, RedisSettings

logger = logging.getLogger(__name__)


def create_celery_app(
    redis_settings: Optional[RedisSettings] = None,
    celery_settings: Optional[CelerySettings] = None,
) -> Celery:
    """
    Create and configure a Celery application.

    Args:
        redis_settings: Redis connection settings
        celery_settings: Celery configuration settings

    Returns:
        Configured Celery application
    """
    settings = get_settings()
    redis_settings = redis_settings or settings.redis
    celery_settings = celery_settings or settings.celery

    # Build broker and backend URLs
    auth = f":{redis_settings.password}@" if redis_settings.password else ""
    protocol = "rediss" if redis_settings.ssl else "redis"
    base_url = f"{protocol}://{auth}{redis_settings.host}:{redis_settings.port}"

    broker_url = f"{base_url}/{celery_settings.broker_db}"
    result_backend = f"{base_url}/{celery_settings.result_db}"

    # Create Celery app
    app = Celery(
        "tax_platform",
        broker=broker_url,
        backend=result_backend,
        include=[
            "tasks.ocr_tasks",
            "tasks.data_retention",
        ],
    )

    # Configure Celery
    app.conf.update(
        # Serialization
        task_serializer=celery_settings.task_serializer,
        result_serializer=celery_settings.result_serializer,
        accept_content=celery_settings.accept_content,
        result_accept_content=celery_settings.accept_content,

        # Task acknowledgment
        task_acks_late=celery_settings.task_acks_late,
        task_reject_on_worker_lost=celery_settings.task_reject_on_worker_lost,

        # Worker settings
        worker_prefetch_multiplier=celery_settings.worker_prefetch_multiplier,

        # Time limits
        task_time_limit=celery_settings.task_time_limit,
        task_soft_time_limit=celery_settings.task_soft_time_limit,

        # Result settings
        result_expires=3600,  # Results expire after 1 hour
        result_extended=True,  # Store additional task metadata

        # Task tracking
        task_track_started=True,
        task_send_sent_event=True,

        # Retry settings
        task_default_retry_delay=60,  # 1 minute default retry delay

        # Timezone
        timezone="UTC",
        enable_utc=True,

        # Beat schedule (for periodic tasks)
        beat_schedule={
            "cleanup-dead-letters": {
                "task": "tasks.dead_letter.cleanup_old_dead_letters",
                "schedule": 3600.0,  # Every hour
            },
            "purge-expired-sessions": {
                "task": "tasks.data_retention.purge_expired_sessions",
                "schedule": 3600.0,  # Every hour
            },
            "cleanup-orphaned-uploads": {
                "task": "tasks.data_retention.cleanup_orphaned_uploads",
                "schedule": 86400.0,  # Every 24 hours
            },
            "trim-audit-logs": {
                "task": "tasks.data_retention.trim_audit_logs",
                "schedule": 604800.0,  # Every 7 days
            },
        },
    )

    return app


# Global Celery app instance
celery_app = create_celery_app()


@lru_cache
def get_celery_app() -> Celery:
    """Get the global Celery app instance."""
    return celery_app


class TaskBase(Task):
    """
    Base task class with common functionality.

    Provides:
    - Automatic retry logic
    - Error handling
    - Logging
    """

    abstract = True
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600  # Max 10 minutes between retries
    retry_jitter = True
    max_retries = 3

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(
            f"Task {self.name}[{task_id}] failed: {exc}",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "args": args,
                "kwargs": kwargs,
                "exception": str(exc),
            },
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        logger.info(
            f"Task {self.name}[{task_id}] succeeded",
            extra={
                "task_id": task_id,
                "task_name": self.name,
            },
        )
        super().on_success(retval, task_id, args, kwargs)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        logger.warning(
            f"Task {self.name}[{task_id}] retrying: {exc}",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "retry_count": self.request.retries,
                "exception": str(exc),
            },
        )
        super().on_retry(exc, task_id, args, kwargs, einfo)


# Register base task class
celery_app.Task = TaskBase


# Signal handlers for monitoring
@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """Log when worker is ready."""
    logger.info(f"Celery worker ready: {sender}")


@worker_shutdown.connect
def on_worker_shutdown(sender, **kwargs):
    """Log when worker shuts down."""
    logger.info(f"Celery worker shutting down: {sender}")


@task_prerun.connect
def on_task_prerun(task_id, task, args, kwargs, **other):
    """Log task start."""
    logger.debug(
        f"Task starting: {task.name}[{task_id}]",
        extra={
            "task_id": task_id,
            "task_name": task.name,
        },
    )


@task_postrun.connect
def on_task_postrun(task_id, task, args, kwargs, retval, state, **other):
    """Log task completion."""
    logger.debug(
        f"Task completed: {task.name}[{task_id}] state={state}",
        extra={
            "task_id": task_id,
            "task_name": task.name,
            "state": state,
        },
    )


@task_success.connect
def on_task_success(sender, result, **kwargs):
    """Handle successful task completion."""
    pass  # Additional success handling if needed


@task_failure.connect
def on_task_failure(task_id, exception, args, kwargs, traceback, einfo, **other):
    """Handle task failure - route to dead letter queue if max retries exceeded."""
    from tasks.dead_letter import handle_failed_task

    task = other.get("sender")
    if task and hasattr(task, "request"):
        retries = task.request.retries
        max_retries = getattr(task, "max_retries", 3)

        if retries >= max_retries:
            # Task has exhausted retries - send to dead letter queue
            handle_failed_task(
                task_id=task_id,
                task_name=task.name if task else "unknown",
                args=args,
                kwargs=kwargs,
                exception=str(exception),
                traceback=str(traceback) if traceback else None,
            )


@task_retry.connect
def on_task_retry(request, reason, einfo, **kwargs):
    """Log task retry."""
    logger.warning(
        f"Task retry: {request.task}[{request.id}] - {reason}",
        extra={
            "task_id": request.id,
            "task_name": request.task,
            "retry_reason": str(reason),
        },
    )


def get_task_info(task_id: str) -> Dict[str, Any]:
    """
    Get information about a task.

    Args:
        task_id: Celery task ID

    Returns:
        Dict with task status and result
    """
    result = celery_app.AsyncResult(task_id)

    info = {
        "task_id": task_id,
        "status": result.status,
        "ready": result.ready(),
        "successful": result.successful() if result.ready() else None,
        "failed": result.failed() if result.ready() else None,
    }

    if result.ready():
        if result.successful():
            info["result"] = result.result
        elif result.failed():
            info["error"] = str(result.result)
            info["traceback"] = result.traceback

    return info


def revoke_task(task_id: str, terminate: bool = False) -> bool:
    """
    Revoke a pending or running task.

    Args:
        task_id: Celery task ID
        terminate: Whether to terminate running task

    Returns:
        True if revocation was sent
    """
    try:
        celery_app.control.revoke(task_id, terminate=terminate)
        logger.info(f"Task revoked: {task_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to revoke task {task_id}: {e}")
        return False
