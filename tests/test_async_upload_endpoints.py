"""Tests for async document upload endpoints."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import io


class TestAsyncUploadEndpoint:
    """Tests for POST /api/upload/async endpoint."""

    def test_async_upload_success(self):
        """Should submit document for async processing."""
        from web.app import app, _DOCUMENTS

        # Clear documents
        _DOCUMENTS.clear()

        # Patch at the module where it's imported
        with patch('tasks.ocr_tasks.submit_document_bytes_for_processing') as mock_submit:
            mock_submit.return_value = {
                "document_id": "test-doc-id",
                "task_id": "test-task-id",
                "status": "pending",
            }

            client = TestClient(app)

            # Create a test file
            file_content = b"test PDF content"
            files = {"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")}

            response = client.post("/api/upload/async", files=files)

            assert response.status_code == 200
            data = response.json()
            assert "document_id" in data
            assert data["task_id"] == "test-task-id"
            assert data["status"] == "processing"

    def test_async_upload_invalid_file_type(self):
        """Should reject unsupported file types."""
        from web.app import app

        client = TestClient(app)

        # Create a test file with unsupported type
        file_content = b"test text content"
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}

        response = client.post("/api/upload/async", files=files)

        assert response.status_code == 400
        # Check error message in the response
        data = response.json()
        assert "Unsupported file type" in str(data)

    def test_async_upload_with_options(self):
        """Should pass document_type and tax_year to task."""
        from web.app import app, _DOCUMENTS

        _DOCUMENTS.clear()

        with patch('tasks.ocr_tasks.submit_document_bytes_for_processing') as mock_submit:
            mock_submit.return_value = {
                "document_id": "test-doc-id",
                "task_id": "test-task-id",
                "status": "pending",
            }

            client = TestClient(app)

            file_content = b"test PDF content"
            files = {"file": ("w2.pdf", io.BytesIO(file_content), "application/pdf")}
            data = {
                "document_type": "w2",
                "tax_year": "2025",
            }

            response = client.post("/api/upload/async", files=files, data=data)

            assert response.status_code == 200

            # Verify options were passed
            call_kwargs = mock_submit.call_args[1]
            assert call_kwargs["document_type"] == "w2"
            assert call_kwargs["tax_year"] == 2025

    def test_async_upload_with_callback_url(self):
        """Should pass callback_url to task."""
        from web.app import app, _DOCUMENTS

        _DOCUMENTS.clear()

        with patch('tasks.ocr_tasks.submit_document_bytes_for_processing') as mock_submit:
            mock_submit.return_value = {
                "document_id": "test-doc-id",
                "task_id": "test-task-id",
                "status": "pending",
            }

            client = TestClient(app)

            file_content = b"test PDF content"
            files = {"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")}
            data = {"callback_url": "https://example.com/callback"}

            response = client.post("/api/upload/async", files=files, data=data)

            assert response.status_code == 200

            # Verify callback_url was passed
            call_kwargs = mock_submit.call_args[1]
            assert call_kwargs["callback_url"] == "https://example.com/callback"


class TestUploadStatusEndpoint:
    """Tests for GET /api/upload/status/{task_id} endpoint."""

    def test_get_status_processing(self):
        """Should return processing status for pending task."""
        from web.app import app

        with patch('tasks.ocr_tasks.get_task_status') as mock_status:
            mock_status.return_value = {
                "task_id": "test-task-id",
                "status": "PENDING",
                "ready": False,
            }

            client = TestClient(app)
            response = client.get("/api/upload/status/test-task-id")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "processing"
            assert data["ready"] is False

    def test_get_status_completed(self):
        """Should return completed status with result."""
        from web.app import app

        with patch('tasks.ocr_tasks.get_task_status') as mock_status:
            mock_status.return_value = {
                "task_id": "test-task-id",
                "status": "SUCCESS",
                "ready": True,
                "result": {
                    "document_id": "doc-123",
                    "document_type": "w2",
                    "tax_year": 2025,
                    "ocr_confidence": 0.95,
                    "extraction_confidence": 0.90,
                    "extracted_fields": [{"name": "wages", "value": "50000"}],
                    "warnings": [],
                    "errors": [],
                },
            }

            client = TestClient(app)
            response = client.get("/api/upload/status/test-task-id")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert data["document_type"] == "w2"
            assert data["extraction_confidence"] == 0.90

    def test_get_status_failed(self):
        """Should return failed status with error."""
        from web.app import app

        with patch('tasks.ocr_tasks.get_task_status') as mock_status:
            mock_status.return_value = {
                "task_id": "test-task-id",
                "status": "FAILURE",
                "ready": True,
                "error": "OCR processing failed",
            }

            client = TestClient(app)
            response = client.get("/api/upload/status/test-task-id")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "failed"
            assert "error" in data


class TestDocumentStatusEndpoint:
    """Tests for GET /api/documents/{document_id}/status endpoint."""

    def test_document_status_completed(self):
        """Should return completed status for processed document."""
        from web.app import app, _DOCUMENTS

        # Set up a completed document
        mock_result = MagicMock()
        mock_result.document_type = "w2"
        mock_result.tax_year = 2025
        mock_result.ocr_confidence = 0.95
        mock_result.extraction_confidence = 0.90

        _DOCUMENTS["test-doc-id"] = {
            "result": mock_result,
            "session_id": "test-session",
            "filename": "test.pdf",
            "created_at": "2025-01-01T00:00:00",
            "status": "completed",
            "task_id": None,
        }

        client = TestClient(app)
        client.cookies.set("tax_session_id", "test-session")

        response = client.get("/api/documents/test-doc-id/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["document_type"] == "w2"

        # Cleanup
        del _DOCUMENTS["test-doc-id"]

    def test_document_status_processing(self):
        """Should return processing status for pending document."""
        from web.app import app, _DOCUMENTS

        _DOCUMENTS["test-doc-id"] = {
            "result": None,
            "session_id": "test-session",
            "filename": "test.pdf",
            "created_at": "2025-01-01T00:00:00",
            "status": "processing",
            "task_id": "test-task-id",
        }

        with patch('tasks.ocr_tasks.get_task_status') as mock_status:
            mock_status.return_value = {
                "task_id": "test-task-id",
                "status": "PENDING",
                "ready": False,
            }

            client = TestClient(app)
            client.cookies.set("tax_session_id", "test-session")

            response = client.get("/api/documents/test-doc-id/status")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "processing"
            assert data["task_id"] == "test-task-id"

        # Cleanup
        del _DOCUMENTS["test-doc-id"]

    def test_document_status_access_denied(self):
        """Should return 403 for document from different session."""
        from web.app import app, _DOCUMENTS

        _DOCUMENTS["test-doc-id"] = {
            "result": None,
            "session_id": "other-session",
            "filename": "test.pdf",
            "created_at": "2025-01-01T00:00:00",
            "status": "completed",
            "task_id": None,
        }

        client = TestClient(app)
        client.cookies.set("tax_session_id", "my-session")

        response = client.get("/api/documents/test-doc-id/status")

        assert response.status_code == 403

        # Cleanup
        del _DOCUMENTS["test-doc-id"]

    def test_document_status_not_found(self):
        """Should return 404 for unknown document."""
        from web.app import app, _DOCUMENTS

        _DOCUMENTS.clear()

        with patch('tasks.ocr_tasks.get_document_status', side_effect=Exception("Not found")):
            client = TestClient(app)

            response = client.get("/api/documents/unknown-doc-id/status")

            assert response.status_code == 404


class TestCancelUploadEndpoint:
    """Tests for POST /api/upload/cancel/{task_id} endpoint."""

    def test_cancel_task_success(self):
        """Should cancel a pending task."""
        from web.app import app

        with patch('tasks.ocr_tasks.cancel_task', return_value=True) as mock_cancel:
            client = TestClient(app)

            response = client.post("/api/upload/cancel/test-task-id")

            assert response.status_code == 200
            data = response.json()
            assert data["cancelled"] is True
            mock_cancel.assert_called_once_with("test-task-id", terminate=False)

    def test_cancel_task_failure(self):
        """Should handle cancellation failure."""
        from web.app import app

        with patch('tasks.ocr_tasks.cancel_task', return_value=False):
            client = TestClient(app)

            response = client.post("/api/upload/cancel/test-task-id")

            assert response.status_code == 400
            data = response.json()
            assert data["cancelled"] is False


class TestAsyncUploadIntegration:
    """Integration tests for async upload workflow."""

    def test_full_async_workflow(self):
        """Test complete async upload -> status check workflow."""
        from web.app import app, _DOCUMENTS

        _DOCUMENTS.clear()

        # Step 1: Upload document
        with patch('tasks.ocr_tasks.submit_document_bytes_for_processing') as mock_submit:
            mock_submit.return_value = {
                "document_id": "workflow-doc-id",
                "task_id": "workflow-task-id",
                "status": "pending",
            }

            client = TestClient(app)

            file_content = b"test PDF content"
            files = {"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")}

            response = client.post("/api/upload/async", files=files)
            assert response.status_code == 200

            upload_data = response.json()
            task_id = upload_data["task_id"]
            document_id = upload_data["document_id"]

        # Step 2: Check status (processing)
        with patch('tasks.ocr_tasks.get_task_status') as mock_status:
            mock_status.return_value = {
                "task_id": task_id,
                "status": "STARTED",
                "ready": False,
            }

            response = client.get(f"/api/upload/status/{task_id}")
            assert response.status_code == 200
            assert response.json()["status"] == "processing"

        # Step 3: Check status (completed)
        with patch('tasks.ocr_tasks.get_task_status') as mock_status:
            mock_status.return_value = {
                "task_id": task_id,
                "status": "SUCCESS",
                "ready": True,
                "result": {
                    "document_id": document_id,
                    "document_type": "w2",
                    "tax_year": 2025,
                    "ocr_confidence": 0.95,
                    "extraction_confidence": 0.90,
                    "extracted_fields": [],
                    "warnings": [],
                    "errors": [],
                },
            }

            response = client.get(f"/api/upload/status/{task_id}")
            assert response.status_code == 200
            assert response.json()["status"] == "completed"
            assert response.json()["document_type"] == "w2"

        # Cleanup
        _DOCUMENTS.clear()
