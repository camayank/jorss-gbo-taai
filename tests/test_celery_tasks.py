"""Tests for Celery background tasks."""

import base64
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4


class TestCeleryApp:
    """Tests for Celery app configuration."""

    def test_create_celery_app(self):
        """Should create a Celery app with correct configuration."""
        mock_redis = MagicMock()
        mock_redis.host = "localhost"
        mock_redis.port = 6379
        mock_redis.password = None
        mock_redis.ssl = False

        mock_celery = MagicMock()
        mock_celery.broker_db = 1
        mock_celery.result_db = 2
        mock_celery.task_serializer = "json"
        mock_celery.result_serializer = "json"
        mock_celery.accept_content = ["json"]
        mock_celery.task_acks_late = True
        mock_celery.task_reject_on_worker_lost = True
        mock_celery.worker_prefetch_multiplier = 1
        mock_celery.task_time_limit = 300
        mock_celery.task_soft_time_limit = 240

        from tasks.celery_app import create_celery_app
        app = create_celery_app(
            redis_settings=mock_redis,
            celery_settings=mock_celery
        )

        assert app is not None
        assert app.main == "tax_platform"

    def test_get_task_info(self):
        """Should return task information."""
        from tasks.celery_app import get_task_info, celery_app

        mock_result = MagicMock()
        mock_result.status = "SUCCESS"
        mock_result.ready.return_value = True
        mock_result.successful.return_value = True
        mock_result.failed.return_value = False
        mock_result.result = {"test": "result"}

        with patch.object(celery_app, 'AsyncResult', return_value=mock_result):
            info = get_task_info("test-task-id")

            assert info["task_id"] == "test-task-id"
            assert info["status"] == "SUCCESS"
            assert info["ready"] is True
            assert info["successful"] is True
            assert info["result"] == {"test": "result"}

    def test_get_task_info_pending(self):
        """Should handle pending task."""
        from tasks.celery_app import get_task_info, celery_app

        mock_result = MagicMock()
        mock_result.status = "PENDING"
        mock_result.ready.return_value = False

        with patch.object(celery_app, 'AsyncResult', return_value=mock_result):
            info = get_task_info("test-task-id")

            assert info["status"] == "PENDING"
            assert info["ready"] is False
            assert "result" not in info

    def test_get_task_info_failed(self):
        """Should handle failed task."""
        from tasks.celery_app import get_task_info, celery_app

        mock_result = MagicMock()
        mock_result.status = "FAILURE"
        mock_result.ready.return_value = True
        mock_result.successful.return_value = False
        mock_result.failed.return_value = True
        mock_result.result = Exception("Test error")
        mock_result.traceback = "Test traceback"

        with patch.object(celery_app, 'AsyncResult', return_value=mock_result):
            info = get_task_info("test-task-id")

            assert info["status"] == "FAILURE"
            assert info["failed"] is True
            assert "error" in info

    def test_revoke_task(self):
        """Should revoke a task."""
        from tasks.celery_app import revoke_task, celery_app

        with patch.object(celery_app.control, 'revoke') as mock_revoke:
            result = revoke_task("test-task-id")

            assert result is True
            mock_revoke.assert_called_once_with("test-task-id", terminate=False)

    def test_revoke_task_with_terminate(self):
        """Should revoke and terminate a running task."""
        from tasks.celery_app import revoke_task, celery_app

        with patch.object(celery_app.control, 'revoke') as mock_revoke:
            result = revoke_task("test-task-id", terminate=True)

            assert result is True
            mock_revoke.assert_called_once_with("test-task-id", terminate=True)


class TestTaskBase:
    """Tests for TaskBase class."""

    def test_task_base_autoretry(self):
        """TaskBase should have autoretry configured."""
        from tasks.celery_app import TaskBase

        assert TaskBase.autoretry_for == (Exception,)
        assert TaskBase.retry_backoff is True
        assert TaskBase.max_retries == 3


class TestOCRTasks:
    """Tests for OCR background tasks."""

    def test_task_status_constants(self):
        """Should have correct task status constants."""
        from tasks.ocr_tasks import TaskStatus

        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.PROCESSING == "processing"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.RETRYING == "retrying"

    @patch('tasks.ocr_tasks._store_document_status')
    @patch('tasks.ocr_tasks.DocumentProcessor')
    def test_process_document_task_success(self, mock_processor_class, mock_store_status):
        """Should process document successfully."""
        from tasks.ocr_tasks import process_document_task

        # Mock processor
        mock_processor = MagicMock()
        mock_result = MagicMock()
        mock_result.status = "success"
        mock_result.document_type = "w2"
        mock_result.to_dict.return_value = {
            "document_id": "test-doc",
            "status": "success",
            "document_type": "w2",
        }
        mock_processor.process_document.return_value = mock_result
        mock_processor_class.return_value = mock_processor

        with patch('os.path.exists', return_value=True):
            # Use apply() to run synchronously with proper task context
            result = process_document_task.apply(
                args=("/tmp/test.pdf",),
                kwargs={"document_id": "test-doc"},
            )

        assert result.successful()
        assert result.result["status"] == "success"
        assert result.result["document_type"] == "w2"
        mock_processor.process_document.assert_called_once()

    @patch('tasks.ocr_tasks._store_document_status')
    def test_process_document_task_file_not_found(self, mock_store_status):
        """Should handle missing file."""
        from tasks.ocr_tasks import process_document_task

        with patch('os.path.exists', return_value=False):
            # Use apply() - the task will fail with FileNotFoundError
            result = process_document_task.apply(
                args=("/tmp/nonexistent.pdf",),
                kwargs={"document_id": "test-doc"},
            )

        assert result.failed()
        assert "FileNotFoundError" in str(result.traceback)

    @patch('tasks.ocr_tasks._store_document_status')
    @patch('tasks.ocr_tasks.DocumentProcessor')
    def test_process_document_bytes_task_success(self, mock_processor_class, mock_store_status):
        """Should process document bytes successfully."""
        from tasks.ocr_tasks import process_document_bytes_task

        # Mock processor
        mock_processor = MagicMock()
        mock_result = MagicMock()
        mock_result.status = "success"
        mock_result.document_type = "1099-int"
        mock_result.to_dict.return_value = {
            "document_id": "test-doc",
            "status": "success",
            "document_type": "1099-int",
        }
        mock_processor.process_bytes.return_value = mock_result
        mock_processor_class.return_value = mock_processor

        # Create test data
        test_data = b"test document content"
        data_base64 = base64.b64encode(test_data).decode("utf-8")

        # Use apply() to run synchronously with proper task context
        result = process_document_bytes_task.apply(
            args=(data_base64, "application/pdf", "test.pdf"),
            kwargs={"document_id": "test-doc"},
        )

        assert result.successful()
        assert result.result["status"] == "success"
        assert result.result["document_type"] == "1099-int"
        mock_processor.process_bytes.assert_called_once()

    def test_get_task_status(self):
        """Should get task status from Celery."""
        from tasks.ocr_tasks import get_task_status
        from tasks.celery_app import celery_app

        mock_result = MagicMock()
        mock_result.status = "SUCCESS"
        mock_result.ready.return_value = True
        mock_result.successful.return_value = True
        mock_result.result = {"test": "result"}

        with patch.object(celery_app, 'AsyncResult', return_value=mock_result):
            status = get_task_status("test-task-id")

            assert status["task_id"] == "test-task-id"
            assert status["status"] == "SUCCESS"
            assert status["result"] == {"test": "result"}

    @patch('tasks.ocr_tasks._get_document_status')
    def test_get_document_status_found(self, mock_get_status):
        """Should get document status from Redis."""
        from tasks.ocr_tasks import get_document_status

        mock_get_status.return_value = {
            "document_id": "test-doc",
            "status": "completed",
        }

        status = get_document_status("test-doc")

        assert status["document_id"] == "test-doc"
        assert status["status"] == "completed"

    @patch('tasks.ocr_tasks._get_document_status')
    def test_get_document_status_not_found(self, mock_get_status):
        """Should handle missing document status."""
        from tasks.ocr_tasks import get_document_status

        mock_get_status.return_value = None

        status = get_document_status("unknown-doc")

        assert status["status"] == "unknown"

    def test_cancel_task(self):
        """Should cancel a task."""
        import sys
        from tasks.ocr_tasks import cancel_task

        # Get the actual module, not the celery_app instance
        celery_module = sys.modules['tasks.celery_app']

        with patch.object(celery_module, 'revoke_task', return_value=True) as mock_revoke:
            result = cancel_task("test-task-id")

            assert result is True
            mock_revoke.assert_called_once_with("test-task-id", terminate=False)

    @patch('tasks.ocr_tasks._store_document_status')
    @patch('tasks.ocr_tasks.process_document_task.delay')
    def test_submit_document_for_processing(self, mock_delay, mock_store_status):
        """Should submit document for async processing."""
        from tasks.ocr_tasks import submit_document_for_processing, TaskStatus

        mock_task = MagicMock()
        mock_task.id = "celery-task-id"
        mock_delay.return_value = mock_task

        result = submit_document_for_processing(
            file_path="/tmp/test.pdf",
            document_id="test-doc",
        )

        assert result["document_id"] == "test-doc"
        assert result["task_id"] == "celery-task-id"
        assert result["status"] == TaskStatus.PENDING
        mock_delay.assert_called_once()

    @patch('tasks.ocr_tasks._store_document_status')
    @patch('tasks.ocr_tasks.process_document_bytes_task.delay')
    def test_submit_document_bytes_for_processing(self, mock_delay, mock_store_status):
        """Should submit document bytes for async processing."""
        from tasks.ocr_tasks import submit_document_bytes_for_processing, TaskStatus

        mock_task = MagicMock()
        mock_task.id = "celery-task-id"
        mock_delay.return_value = mock_task

        result = submit_document_bytes_for_processing(
            data=b"test data",
            mime_type="application/pdf",
            original_filename="test.pdf",
            document_id="test-doc",
        )

        assert result["document_id"] == "test-doc"
        assert result["task_id"] == "celery-task-id"
        assert result["status"] == TaskStatus.PENDING
        mock_delay.assert_called_once()


class TestDeadLetterTask:
    """Tests for DeadLetterTask dataclass."""

    def test_to_dict(self):
        """Should convert to dictionary."""
        from tasks.dead_letter import DeadLetterTask

        task = DeadLetterTask(
            id="dlq-123",
            task_id="task-456",
            task_name="test.task",
            args=[1, 2, 3],
            kwargs={"key": "value"},
            exception="Test error",
            traceback="Test traceback",
            failed_at="2025-01-01T00:00:00",
        )

        d = task.to_dict()

        assert d["id"] == "dlq-123"
        assert d["task_id"] == "task-456"
        assert d["task_name"] == "test.task"
        assert d["args"] == [1, 2, 3]
        assert d["kwargs"] == {"key": "value"}
        assert d["exception"] == "Test error"

    def test_from_dict(self):
        """Should create from dictionary."""
        from tasks.dead_letter import DeadLetterTask

        data = {
            "id": "dlq-123",
            "task_id": "task-456",
            "task_name": "test.task",
            "args": [1, 2, 3],
            "kwargs": {"key": "value"},
            "exception": "Test error",
            "traceback": None,
            "failed_at": "2025-01-01T00:00:00",
            "retry_count": 1,
            "last_retry_at": None,
            "metadata": {},
        }

        task = DeadLetterTask.from_dict(data)

        assert task.id == "dlq-123"
        assert task.task_name == "test.task"
        assert task.retry_count == 1


class TestDeadLetterHandler:
    """Tests for DeadLetterHandler class."""

    def test_init(self):
        """Should initialize with default retention."""
        from tasks.dead_letter import DeadLetterHandler

        handler = DeadLetterHandler()
        assert handler.max_retention_days == 30

    def test_init_custom_retention(self):
        """Should accept custom retention period."""
        from tasks.dead_letter import DeadLetterHandler

        handler = DeadLetterHandler(max_retention_days=7)
        assert handler.max_retention_days == 7

    def test_register_alert_callback(self):
        """Should register alert callback."""
        from tasks.dead_letter import DeadLetterHandler

        handler = DeadLetterHandler()

        callback = MagicMock()
        handler.register_alert_callback(callback)

        assert callback in handler._alert_callbacks

    @pytest.mark.asyncio
    async def test_store_failed_task(self):
        """Should store failed task in Redis."""
        from tasks.dead_letter import DeadLetterHandler

        handler = DeadLetterHandler()

        with patch('cache.redis_client.RedisClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            task = await handler.store_failed_task(
                task_id="task-123",
                task_name="test.task",
                args=[1, 2],
                kwargs={"key": "value"},
                exception="Test error",
            )

            assert task.task_id == "task-123"
            assert task.task_name == "test.task"
            assert task.exception == "Test error"
            mock_client.set.assert_called_once()
            mock_client.hset.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_task(self):
        """Should get task from Redis."""
        from tasks.dead_letter import DeadLetterHandler

        handler = DeadLetterHandler()

        task_data = {
            "id": "dlq-123",
            "task_id": "task-456",
            "task_name": "test.task",
            "args": [],
            "kwargs": {},
            "exception": "Test error",
            "traceback": None,
            "failed_at": "2025-01-01T00:00:00",
            "retry_count": 0,
            "last_retry_at": None,
            "metadata": {},
        }

        with patch('cache.redis_client.RedisClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = task_data
            mock_client_class.return_value = mock_client

            task = await handler.get_task("dlq-123")

            assert task is not None
            assert task.id == "dlq-123"
            assert task.task_name == "test.task"

    @pytest.mark.asyncio
    async def test_get_task_not_found(self):
        """Should return None for missing task."""
        from tasks.dead_letter import DeadLetterHandler

        handler = DeadLetterHandler()

        with patch('cache.redis_client.RedisClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = None
            mock_client_class.return_value = mock_client

            task = await handler.get_task("unknown-id")

            assert task is None

    @pytest.mark.asyncio
    async def test_delete_task(self):
        """Should delete task from Redis."""
        from tasks.dead_letter import DeadLetterHandler

        handler = DeadLetterHandler()

        with patch('cache.redis_client.RedisClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await handler.delete_task("dlq-123")

            assert result is True
            mock_client.delete.assert_called_once()
            mock_client.hdel.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Should return queue statistics."""
        from tasks.dead_letter import DeadLetterHandler

        handler = DeadLetterHandler()

        with patch('cache.redis_client.RedisClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.hgetall.return_value = {
                "dlq-1": "2025-01-01T00:00:00",
                "dlq-2": "2025-01-02T00:00:00",
            }
            mock_client.get.side_effect = [
                {"task_name": "task.a"},
                {"task_name": "task.b"},
            ]
            mock_client_class.return_value = mock_client

            stats = await handler.get_stats()

            assert stats["total"] == 2
            assert "by_task" in stats


class TestDeadLetterSyncWrappers:
    """Tests for synchronous wrapper functions."""

    @patch('tasks.dead_letter.get_dead_letter_handler')
    def test_handle_failed_task(self, mock_get_handler):
        """Should call handler store method."""
        from tasks.dead_letter import handle_failed_task

        mock_handler = MagicMock()
        mock_handler.store_failed_task = AsyncMock()
        mock_get_handler.return_value = mock_handler

        handle_failed_task(
            task_id="task-123",
            task_name="test.task",
            args=[],
            kwargs={},
            exception="Test error",
        )

        mock_handler.store_failed_task.assert_called_once()

    @patch('tasks.dead_letter.get_dead_letter_handler')
    def test_get_dead_letter_tasks(self, mock_get_handler):
        """Should list dead letter tasks."""
        from tasks.dead_letter import get_dead_letter_tasks, DeadLetterTask

        mock_handler = MagicMock()
        mock_task = DeadLetterTask(
            id="dlq-123",
            task_id="task-456",
            task_name="test.task",
            args=[],
            kwargs={},
            exception="Error",
            traceback=None,
            failed_at="2025-01-01T00:00:00",
        )
        mock_handler.list_tasks = AsyncMock(return_value=[mock_task])
        mock_get_handler.return_value = mock_handler

        tasks = get_dead_letter_tasks()

        assert len(tasks) == 1
        assert tasks[0]["id"] == "dlq-123"

    @patch('tasks.dead_letter.get_dead_letter_handler')
    def test_retry_dead_letter_task(self, mock_get_handler):
        """Should retry a dead letter task."""
        from tasks.dead_letter import retry_dead_letter_task

        mock_handler = MagicMock()
        mock_handler.retry_task = AsyncMock(return_value="new-task-id")
        mock_get_handler.return_value = mock_handler

        result = retry_dead_letter_task("dlq-123")

        assert result == "new-task-id"
        mock_handler.retry_task.assert_called_once_with("dlq-123")
