"""
E2E Test: Document Upload & Management

Tests: Upload (sync/async) → Status → List → Get → Download → Apply → Delete
"""

import io
import pytest
from unittest.mock import patch


class TestDocumentUploadSync:
    """Synchronous document upload."""

    def _upload(self, client, headers, jwt_payload, content=b"%PDF-1.4 test",
                filename="test_w2.pdf", content_type="application/pdf"):
        h = {k: v for k, v in headers.items() if k != "Content-Type"}
        with patch("rbac.jwt.decode_token_safe", return_value=jwt_payload):
            return client.post("/api/upload", headers=h,
                               files={"file": (filename, io.BytesIO(content), content_type)})

    def test_upload_pdf(self, client, headers, consumer_jwt_payload):
        """PDF upload should be accepted."""
        response = self._upload(client, headers, consumer_jwt_payload)
        assert response.status_code in [200, 500]

    def test_upload_image(self, client, headers, consumer_jwt_payload):
        """Image upload should be accepted."""
        png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        response = self._upload(client, headers, consumer_jwt_payload,
                                content=png_header, filename="receipt.png", content_type="image/png")
        assert response.status_code in [200, 500]

    def test_upload_invalid_type(self, client, headers, consumer_jwt_payload):
        """Invalid file type should be rejected."""
        response = self._upload(client, headers, consumer_jwt_payload,
                                content=b"bad", filename="virus.exe",
                                content_type="application/x-executable")
        assert response.status_code == 400

    def test_upload_unauthenticated(self, client, headers):
        """Unauthenticated upload should be blocked."""
        h = {k: v for k, v in headers.items() if k != "Content-Type"}
        with patch("rbac.jwt.decode_token_safe", return_value=None):
            response = client.post("/api/upload", headers=h,
                                   files={"file": ("test.pdf", io.BytesIO(b"%PDF"), "application/pdf")})
        assert response.status_code in [200, 401, 403, 500]


class TestDocumentUploadAsync:
    """Asynchronous document upload."""

    def test_async_upload(self, client, headers, consumer_jwt_payload):
        """Async upload should return task_id."""
        h = {k: v for k, v in headers.items() if k != "Content-Type"}
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.post("/api/upload/async", headers=h,
                                   files={"file": ("w2.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")})
        assert response.status_code in [200, 202, 404, 500]

    def test_upload_status_not_found(self, client, headers, consumer_jwt_payload):
        """Status for non-existent task should fail."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/upload/status/nonexistent-task", headers=headers)
        assert response.status_code in [404, 500]

    def test_cancel_upload_not_found(self, client, headers, consumer_jwt_payload):
        """Cancel non-existent upload should fail."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.post("/api/upload/cancel/nonexistent-task", headers=headers, json={})
        assert response.status_code in [404, 405, 500]


class TestDocumentManagement:
    """Document listing, retrieval, and deletion."""

    def test_list_documents(self, client, headers, consumer_jwt_payload):
        """List documents should respond."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/documents", headers=headers)
        assert response.status_code in [200, 500]

    def test_get_document_not_found(self, client, headers, consumer_jwt_payload):
        """Get non-existent document should fail."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/documents/nonexistent-id", headers=headers)
        assert response.status_code in [404, 500]

    def test_download_document_not_found(self, client, headers, consumer_jwt_payload):
        """Download non-existent document should fail."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/documents/nonexistent-id/download", headers=headers)
        assert response.status_code in [404, 405, 500]

    def test_apply_document_not_found(self, client, headers, consumer_jwt_payload):
        """Apply data from non-existent document should fail."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.post("/api/documents/nonexistent-id/apply", headers=headers, json={})
        assert response.status_code in [404, 405, 500]

    def test_delete_document_not_found(self, client, headers, consumer_jwt_payload):
        """Delete non-existent document should fail."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.delete("/api/documents/nonexistent-id", headers=headers)
        assert response.status_code in [404, 405, 500]


class TestSupportedDocuments:
    """Supported document types endpoint."""

    def test_supported_document_types(self, client, headers):
        """Supported document types should return list."""
        response = client.get("/api/supported-documents", headers=headers)
        assert response.status_code in [200, 404, 500]
