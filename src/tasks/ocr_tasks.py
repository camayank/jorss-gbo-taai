"""
OCR Background Tasks - Celery tasks for document processing.

Provides async document processing with:
- File-based OCR processing
- Bytes-based OCR processing
- Status tracking
- Retry logic with exponential backoff
"""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded

from services.ocr import DocumentProcessor, ProcessingResult

logger = logging.getLogger(__name__)


# Task status constants
class TaskStatus:
    """Task status constants."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


def _run_async(coro):
    """
    Run an async coroutine from sync context, handling existing event loops.

    Works in both sync context (Celery workers) and async context (FastAPI tests).
    """
    import asyncio

    try:
        # Check if there's already a running event loop
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - create a new one (normal sync context)
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    else:
        # There's a running loop - we need to handle this differently
        # Create a new thread to run the coroutine
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result(timeout=30)


def _store_document_status(
    document_id: str,
    status: str,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    task_id: Optional[str] = None,
) -> None:
    """
    Store document processing status.

    Uses Redis for status storage if available.
    """
    try:
        from cache.redis_client import RedisClient

        async def _store():
            client = RedisClient()
            await client.connect()
            try:
                status_data = {
                    "document_id": document_id,
                    "status": status,
                    "task_id": task_id,
                    "updated_at": datetime.utcnow().isoformat(),
                }
                if result:
                    status_data["result"] = result
                if error:
                    status_data["error"] = error

                await client.set(
                    f"doc_status:{document_id}",
                    status_data,
                    ttl=86400,  # 24 hours
                )
            finally:
                await client.close()

        _run_async(_store())

    except Exception as e:
        logger.warning(f"Failed to store document status: {e}")


def _get_document_status(document_id: str) -> Optional[Dict[str, Any]]:
    """
    Get document processing status from Redis.
    """
    try:
        from cache.redis_client import RedisClient

        async def _get():
            client = RedisClient()
            await client.connect()
            try:
                return await client.get(f"doc_status:{document_id}")
            finally:
                await client.close()

        return _run_async(_get())

    except Exception as e:
        logger.warning(f"Failed to get document status: {e}")
        return None


@shared_task(
    bind=True,
    name="tasks.ocr_tasks.process_document",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    soft_time_limit=240,
    time_limit=300,
)
def process_document_task(
    self,
    file_path: str,
    document_id: Optional[str] = None,
    document_type: Optional[str] = None,
    tax_year: Optional[int] = None,
    callback_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process a document file asynchronously.

    Args:
        file_path: Path to the document file
        document_id: Optional document identifier
        document_type: Optional document type override
        tax_year: Optional tax year override
        callback_url: Optional URL to call when processing completes

    Returns:
        Processing result dictionary
    """
    document_id = document_id or str(uuid4())
    task_id = self.request.id

    logger.info(
        f"Starting document processing: {document_id}",
        extra={
            "document_id": document_id,
            "task_id": task_id,
            "file_path": file_path,
        },
    )

    # Update status to processing
    _store_document_status(
        document_id=document_id,
        status=TaskStatus.PROCESSING,
        task_id=task_id,
    )

    try:
        # Verify file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Document file not found: {file_path}")

        # Process document
        processor = DocumentProcessor()
        result = processor.process_document(
            file_path=file_path,
            document_type=document_type,
            tax_year=tax_year,
        )

        # Convert result to dict
        result_dict = result.to_dict()
        result_dict["document_id"] = document_id
        result_dict["task_id"] = task_id

        # Store success status
        _store_document_status(
            document_id=document_id,
            status=TaskStatus.COMPLETED,
            result=result_dict,
            task_id=task_id,
        )

        # Call callback if provided
        if callback_url:
            _send_callback(callback_url, result_dict)

        logger.info(
            f"Document processing completed: {document_id}",
            extra={
                "document_id": document_id,
                "task_id": task_id,
                "status": result.status,
                "document_type": result.document_type,
            },
        )

        return result_dict

    except SoftTimeLimitExceeded:
        logger.warning(f"Document processing timed out: {document_id}")
        _store_document_status(
            document_id=document_id,
            status=TaskStatus.FAILED,
            error="Processing timed out",
            task_id=task_id,
        )
        raise

    except Exception as exc:
        retries = self.request.retries
        max_retries = self.max_retries

        if retries < max_retries:
            logger.warning(
                f"Document processing failed, retrying: {document_id}",
                extra={
                    "document_id": document_id,
                    "task_id": task_id,
                    "retry": retries + 1,
                    "error": str(exc),
                },
            )
            _store_document_status(
                document_id=document_id,
                status=TaskStatus.RETRYING,
                error=str(exc),
                task_id=task_id,
            )
            raise

        # Max retries exceeded
        logger.error(
            f"Document processing failed after {max_retries} retries: {document_id}",
            extra={
                "document_id": document_id,
                "task_id": task_id,
                "error": str(exc),
            },
        )
        _store_document_status(
            document_id=document_id,
            status=TaskStatus.FAILED,
            error=str(exc),
            task_id=task_id,
        )
        raise


@shared_task(
    bind=True,
    name="tasks.ocr_tasks.process_document_bytes",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    soft_time_limit=240,
    time_limit=300,
)
def process_document_bytes_task(
    self,
    data_base64: str,
    mime_type: str,
    original_filename: str,
    document_id: Optional[str] = None,
    document_type: Optional[str] = None,
    tax_year: Optional[int] = None,
    callback_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process document bytes asynchronously.

    Args:
        data_base64: Base64-encoded document data
        mime_type: MIME type of the document
        original_filename: Original filename
        document_id: Optional document identifier
        document_type: Optional document type override
        tax_year: Optional tax year override
        callback_url: Optional callback URL

    Returns:
        Processing result dictionary
    """
    document_id = document_id or str(uuid4())
    task_id = self.request.id

    logger.info(
        f"Starting document bytes processing: {document_id}",
        extra={
            "document_id": document_id,
            "task_id": task_id,
            "filename": original_filename,
            "mime_type": mime_type,
        },
    )

    # Update status to processing
    _store_document_status(
        document_id=document_id,
        status=TaskStatus.PROCESSING,
        task_id=task_id,
    )

    try:
        # Decode base64 data
        data = base64.b64decode(data_base64)

        # Process document
        processor = DocumentProcessor()
        result = processor.process_bytes(
            data=data,
            mime_type=mime_type,
            original_filename=original_filename,
            document_type=document_type,
            tax_year=tax_year,
        )

        # Convert result to dict
        result_dict = result.to_dict()
        result_dict["document_id"] = document_id
        result_dict["task_id"] = task_id
        result_dict["original_filename"] = original_filename

        # Store success status
        _store_document_status(
            document_id=document_id,
            status=TaskStatus.COMPLETED,
            result=result_dict,
            task_id=task_id,
        )

        # Call callback if provided
        if callback_url:
            _send_callback(callback_url, result_dict)

        logger.info(
            f"Document bytes processing completed: {document_id}",
            extra={
                "document_id": document_id,
                "task_id": task_id,
                "status": result.status,
                "document_type": result.document_type,
            },
        )

        return result_dict

    except SoftTimeLimitExceeded:
        logger.warning(f"Document bytes processing timed out: {document_id}")
        _store_document_status(
            document_id=document_id,
            status=TaskStatus.FAILED,
            error="Processing timed out",
            task_id=task_id,
        )
        raise

    except Exception as exc:
        retries = self.request.retries
        max_retries = self.max_retries

        if retries < max_retries:
            logger.warning(
                f"Document bytes processing failed, retrying: {document_id}",
                extra={
                    "document_id": document_id,
                    "task_id": task_id,
                    "retry": retries + 1,
                    "error": str(exc),
                },
            )
            _store_document_status(
                document_id=document_id,
                status=TaskStatus.RETRYING,
                error=str(exc),
                task_id=task_id,
            )
            raise

        # Max retries exceeded
        logger.error(
            f"Document bytes processing failed after {max_retries} retries: {document_id}",
            extra={
                "document_id": document_id,
                "task_id": task_id,
                "error": str(exc),
            },
        )
        _store_document_status(
            document_id=document_id,
            status=TaskStatus.FAILED,
            error=str(exc),
            task_id=task_id,
        )
        raise


def _send_callback(url: str, result: Dict[str, Any]) -> None:
    """Send callback notification when processing completes."""
    try:
        import requests

        response = requests.post(
            url,
            json=result,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        logger.info(f"Callback sent successfully to {url}")

    except Exception as e:
        logger.warning(f"Failed to send callback to {url}: {e}")


def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Get the status of a processing task.

    Args:
        task_id: Celery task ID

    Returns:
        Task status dictionary
    """
    from tasks.celery_app import celery_app

    result = celery_app.AsyncResult(task_id)

    status = {
        "task_id": task_id,
        "status": result.status,
        "ready": result.ready(),
    }

    if result.ready():
        if result.successful():
            status["result"] = result.result
        elif result.failed():
            status["error"] = str(result.result)

    return status


def get_document_status(document_id: str) -> Dict[str, Any]:
    """
    Get the status of document processing.

    Args:
        document_id: Document identifier

    Returns:
        Document status dictionary
    """
    status = _get_document_status(document_id)

    if status:
        return status

    return {
        "document_id": document_id,
        "status": "unknown",
        "message": "Document status not found",
    }


def cancel_task(task_id: str, terminate: bool = False) -> bool:
    """
    Cancel a pending or running task.

    Args:
        task_id: Celery task ID
        terminate: Whether to terminate running task

    Returns:
        True if cancellation was sent
    """
    from tasks.celery_app import revoke_task

    return revoke_task(task_id, terminate=terminate)


# Convenience functions for API usage
def submit_document_for_processing(
    file_path: str,
    document_id: Optional[str] = None,
    document_type: Optional[str] = None,
    tax_year: Optional[int] = None,
    callback_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Submit a document for async processing.

    Args:
        file_path: Path to the document file
        document_id: Optional document identifier
        document_type: Optional document type
        tax_year: Optional tax year
        callback_url: Optional callback URL

    Returns:
        Dict with task_id and document_id
    """
    document_id = document_id or str(uuid4())

    # Store initial status
    _store_document_status(
        document_id=document_id,
        status=TaskStatus.PENDING,
    )

    # Submit task
    task = process_document_task.delay(
        file_path=file_path,
        document_id=document_id,
        document_type=document_type,
        tax_year=tax_year,
        callback_url=callback_url,
    )

    # Update status with task ID
    _store_document_status(
        document_id=document_id,
        status=TaskStatus.PENDING,
        task_id=task.id,
    )

    return {
        "document_id": document_id,
        "task_id": task.id,
        "status": TaskStatus.PENDING,
    }


def submit_document_bytes_for_processing(
    data: bytes,
    mime_type: str,
    original_filename: str,
    document_id: Optional[str] = None,
    document_type: Optional[str] = None,
    tax_year: Optional[int] = None,
    callback_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Submit document bytes for async processing.

    Args:
        data: Document bytes
        mime_type: MIME type
        original_filename: Original filename
        document_id: Optional document identifier
        document_type: Optional document type
        tax_year: Optional tax year
        callback_url: Optional callback URL

    Returns:
        Dict with task_id and document_id
    """
    document_id = document_id or str(uuid4())

    # Store initial status
    _store_document_status(
        document_id=document_id,
        status=TaskStatus.PENDING,
    )

    # Encode data as base64 for Celery serialization
    data_base64 = base64.b64encode(data).decode("utf-8")

    # Submit task
    task = process_document_bytes_task.delay(
        data_base64=data_base64,
        mime_type=mime_type,
        original_filename=original_filename,
        document_id=document_id,
        document_type=document_type,
        tax_year=tax_year,
        callback_url=callback_url,
    )

    # Update status with task ID
    _store_document_status(
        document_id=document_id,
        status=TaskStatus.PENDING,
        task_id=task.id,
    )

    return {
        "document_id": document_id,
        "task_id": task.id,
        "status": TaskStatus.PENDING,
    }
