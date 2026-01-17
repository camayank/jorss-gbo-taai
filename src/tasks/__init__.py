"""
Background Tasks Module - Celery-based async task processing.

Provides:
- Celery app configuration with Redis broker
- OCR document processing tasks
- Dead letter queue handling
- Task monitoring and retry logic
"""

from .celery_app import celery_app, get_celery_app
from .ocr_tasks import (
    process_document_task,
    process_document_bytes_task,
    get_task_status,
    cancel_task,
)
from .dead_letter import (
    DeadLetterHandler,
    handle_failed_task,
    retry_dead_letter_task,
    get_dead_letter_tasks,
)

__all__ = [
    # Celery app
    "celery_app",
    "get_celery_app",
    # OCR tasks
    "process_document_task",
    "process_document_bytes_task",
    "get_task_status",
    "cancel_task",
    # Dead letter handling
    "DeadLetterHandler",
    "handle_failed_task",
    "retry_dead_letter_task",
    "get_dead_letter_tasks",
]
