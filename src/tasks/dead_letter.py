"""
Dead Letter Queue Handler - Failed task management.

Handles tasks that have exhausted all retries:
- Stores failed task details
- Provides retry mechanism
- Cleanup of old entries
- Monitoring and alerting hooks
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from celery import shared_task

logger = logging.getLogger(__name__)


# Dead letter storage key prefix
DLQ_PREFIX = "dlq:"
DLQ_LIST_KEY = "dlq:tasks"


@dataclass
class DeadLetterTask:
    """Represents a task in the dead letter queue."""
    id: str
    task_id: str
    task_name: str
    args: List[Any]
    kwargs: Dict[str, Any]
    exception: str
    traceback: Optional[str]
    failed_at: str
    retry_count: int = 0
    last_retry_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeadLetterTask":
        """Create from dictionary."""
        return cls(**data)


class DeadLetterHandler:
    """
    Handles dead letter queue operations.

    Provides storage, retrieval, and retry functionality
    for tasks that have failed permanently.
    """

    def __init__(self, max_retention_days: int = 30):
        """
        Initialize dead letter handler.

        Args:
            max_retention_days: Days to keep failed tasks
        """
        self.max_retention_days = max_retention_days
        self._alert_callbacks: List[Callable[[DeadLetterTask], None]] = []

    def register_alert_callback(
        self,
        callback: Callable[[DeadLetterTask], None]
    ) -> None:
        """
        Register a callback for dead letter alerts.

        Args:
            callback: Function to call when task enters DLQ
        """
        self._alert_callbacks.append(callback)

    async def store_failed_task(
        self,
        task_id: str,
        task_name: str,
        args: List[Any],
        kwargs: Dict[str, Any],
        exception: str,
        traceback: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DeadLetterTask:
        """
        Store a failed task in the dead letter queue.

        Args:
            task_id: Celery task ID
            task_name: Task name
            args: Task positional arguments
            kwargs: Task keyword arguments
            exception: Exception message
            traceback: Full traceback
            metadata: Additional metadata

        Returns:
            Created DeadLetterTask
        """
        dlq_id = str(uuid4())

        task = DeadLetterTask(
            id=dlq_id,
            task_id=task_id,
            task_name=task_name,
            args=list(args) if args else [],
            kwargs=dict(kwargs) if kwargs else {},
            exception=exception,
            traceback=traceback,
            failed_at=datetime.utcnow().isoformat(),
            metadata=metadata or {},
        )

        try:
            from cache.redis_client import RedisClient

            client = RedisClient()
            await client.connect()

            try:
                # Store task details
                await client.set(
                    f"{DLQ_PREFIX}{dlq_id}",
                    task.to_dict(),
                    ttl=self.max_retention_days * 86400,
                )

                # Add to list for enumeration
                await client.hset(DLQ_LIST_KEY, dlq_id, task.failed_at)

                logger.warning(
                    f"Task added to dead letter queue: {task_name}[{task_id}]",
                    extra={
                        "dlq_id": dlq_id,
                        "task_id": task_id,
                        "task_name": task_name,
                        "exception": exception,
                    },
                )

            finally:
                await client.close()

        except Exception as e:
            logger.error(f"Failed to store dead letter task: {e}")

        # Trigger alert callbacks
        for callback in self._alert_callbacks:
            try:
                callback(task)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

        return task

    async def get_task(self, dlq_id: str) -> Optional[DeadLetterTask]:
        """
        Get a task from the dead letter queue.

        Args:
            dlq_id: Dead letter queue ID

        Returns:
            DeadLetterTask or None
        """
        try:
            from cache.redis_client import RedisClient

            client = RedisClient()
            await client.connect()

            try:
                data = await client.get(f"{DLQ_PREFIX}{dlq_id}")
                if data:
                    return DeadLetterTask.from_dict(data)
                return None
            finally:
                await client.close()

        except Exception as e:
            logger.error(f"Failed to get dead letter task: {e}")
            return None

    async def list_tasks(
        self,
        limit: int = 100,
        offset: int = 0,
        task_name: Optional[str] = None,
    ) -> List[DeadLetterTask]:
        """
        List tasks in the dead letter queue.

        Args:
            limit: Maximum tasks to return
            offset: Number of tasks to skip
            task_name: Filter by task name

        Returns:
            List of DeadLetterTasks
        """
        try:
            from cache.redis_client import RedisClient

            client = RedisClient()
            await client.connect()

            try:
                # Get all DLQ IDs
                dlq_ids = await client.hgetall(DLQ_LIST_KEY)
                if not dlq_ids:
                    return []

                # Sort by failed_at (newest first)
                sorted_ids = sorted(
                    dlq_ids.keys(),
                    key=lambda k: dlq_ids[k],
                    reverse=True,
                )

                # Apply pagination
                paginated_ids = sorted_ids[offset:offset + limit]

                # Fetch tasks
                tasks = []
                for dlq_id in paginated_ids:
                    data = await client.get(f"{DLQ_PREFIX}{dlq_id}")
                    if data:
                        task = DeadLetterTask.from_dict(data)
                        if task_name is None or task.task_name == task_name:
                            tasks.append(task)

                return tasks

            finally:
                await client.close()

        except Exception as e:
            logger.error(f"Failed to list dead letter tasks: {e}")
            return []

    async def retry_task(self, dlq_id: str) -> Optional[str]:
        """
        Retry a task from the dead letter queue.

        Args:
            dlq_id: Dead letter queue ID

        Returns:
            New Celery task ID or None if retry failed
        """
        task = await self.get_task(dlq_id)
        if not task:
            logger.warning(f"Dead letter task not found: {dlq_id}")
            return None

        try:
            from tasks.celery_app import celery_app

            # Get the task function
            celery_task = celery_app.tasks.get(task.task_name)
            if not celery_task:
                logger.error(f"Task not found in Celery: {task.task_name}")
                return None

            # Submit new task
            result = celery_task.apply_async(
                args=task.args,
                kwargs=task.kwargs,
            )

            # Update retry info
            task.retry_count += 1
            task.last_retry_at = datetime.utcnow().isoformat()

            from cache.redis_client import RedisClient

            client = RedisClient()
            await client.connect()

            try:
                await client.set(
                    f"{DLQ_PREFIX}{dlq_id}",
                    task.to_dict(),
                    ttl=self.max_retention_days * 86400,
                )
            finally:
                await client.close()

            logger.info(
                f"Dead letter task retried: {task.task_name}",
                extra={
                    "dlq_id": dlq_id,
                    "new_task_id": result.id,
                    "retry_count": task.retry_count,
                },
            )

            return result.id

        except Exception as e:
            logger.error(f"Failed to retry dead letter task: {e}")
            return None

    async def delete_task(self, dlq_id: str) -> bool:
        """
        Delete a task from the dead letter queue.

        Args:
            dlq_id: Dead letter queue ID

        Returns:
            True if deleted
        """
        try:
            from cache.redis_client import RedisClient

            client = RedisClient()
            await client.connect()

            try:
                await client.delete(f"{DLQ_PREFIX}{dlq_id}")
                await client.hdel(DLQ_LIST_KEY, dlq_id)

                logger.info(f"Dead letter task deleted: {dlq_id}")
                return True

            finally:
                await client.close()

        except Exception as e:
            logger.error(f"Failed to delete dead letter task: {e}")
            return False

    async def cleanup_old_tasks(self) -> int:
        """
        Clean up tasks older than retention period.

        Returns:
            Number of tasks deleted
        """
        try:
            from cache.redis_client import RedisClient

            client = RedisClient()
            await client.connect()

            try:
                dlq_ids = await client.hgetall(DLQ_LIST_KEY)
                if not dlq_ids:
                    return 0

                cutoff = (
                    datetime.utcnow() - timedelta(days=self.max_retention_days)
                ).isoformat()

                deleted = 0
                for dlq_id, failed_at in dlq_ids.items():
                    if failed_at < cutoff:
                        await client.delete(f"{DLQ_PREFIX}{dlq_id}")
                        await client.hdel(DLQ_LIST_KEY, dlq_id)
                        deleted += 1

                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} old dead letter tasks")

                return deleted

            finally:
                await client.close()

        except Exception as e:
            logger.error(f"Failed to cleanup dead letter tasks: {e}")
            return 0

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get dead letter queue statistics.

        Returns:
            Stats dictionary
        """
        try:
            from cache.redis_client import RedisClient

            client = RedisClient()
            await client.connect()

            try:
                dlq_ids = await client.hgetall(DLQ_LIST_KEY)

                total = len(dlq_ids) if dlq_ids else 0

                # Count by task name
                by_task = {}
                for dlq_id in (dlq_ids or {}).keys():
                    data = await client.get(f"{DLQ_PREFIX}{dlq_id}")
                    if data:
                        task_name = data.get("task_name", "unknown")
                        by_task[task_name] = by_task.get(task_name, 0) + 1

                return {
                    "total": total,
                    "by_task": by_task,
                }

            finally:
                await client.close()

        except Exception as e:
            logger.error(f"Failed to get dead letter stats: {e}")
            return {"total": 0, "by_task": {}}


# Global handler instance
_handler: Optional[DeadLetterHandler] = None


def get_dead_letter_handler() -> DeadLetterHandler:
    """Get or create the global dead letter handler."""
    global _handler
    if _handler is None:
        _handler = DeadLetterHandler()
    return _handler


# Synchronous wrappers for use in Celery signal handlers
def handle_failed_task(
    task_id: str,
    task_name: str,
    args: List[Any],
    kwargs: Dict[str, Any],
    exception: str,
    traceback: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Synchronous wrapper to handle a failed task.

    Called from Celery signal handlers.
    """
    import asyncio

    handler = get_dead_letter_handler()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(
            handler.store_failed_task(
                task_id=task_id,
                task_name=task_name,
                args=args,
                kwargs=kwargs,
                exception=exception,
                traceback=traceback,
                metadata=metadata,
            )
        )
    finally:
        loop.close()


def retry_dead_letter_task(dlq_id: str) -> Optional[str]:
    """
    Synchronous wrapper to retry a dead letter task.
    """
    import asyncio

    handler = get_dead_letter_handler()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(handler.retry_task(dlq_id))
    finally:
        loop.close()


def get_dead_letter_tasks(
    limit: int = 100,
    offset: int = 0,
    task_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Synchronous wrapper to list dead letter tasks.
    """
    import asyncio

    handler = get_dead_letter_handler()

    loop = asyncio.new_event_loop()
    try:
        tasks = loop.run_until_complete(
            handler.list_tasks(limit=limit, offset=offset, task_name=task_name)
        )
        return [t.to_dict() for t in tasks]
    finally:
        loop.close()


# Celery task for periodic cleanup
@shared_task(name="tasks.dead_letter.cleanup_old_dead_letters")
def cleanup_old_dead_letters() -> Dict[str, Any]:
    """
    Periodic task to clean up old dead letter entries.

    Scheduled via Celery beat.
    """
    import asyncio

    handler = get_dead_letter_handler()

    loop = asyncio.new_event_loop()
    try:
        deleted = loop.run_until_complete(handler.cleanup_old_tasks())
        return {"deleted": deleted}
    finally:
        loop.close()
