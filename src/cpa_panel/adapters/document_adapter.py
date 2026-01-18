"""
Document Adapter for CPA Panel

Bridges the OCR document processing service to the CPA panel,
enabling document upload, processing, and data extraction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from datetime import datetime
from pathlib import Path
from uuid import UUID
import logging
import os

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

logger = logging.getLogger(__name__)


@dataclass
class DocumentInfo:
    """Information about an uploaded document."""
    document_id: str
    session_id: str
    filename: str
    document_type: str
    status: str
    upload_time: str
    processing_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "document_id": self.document_id,
            "session_id": self.session_id,
            "filename": self.filename,
            "document_type": self.document_type,
            "status": self.status,
            "upload_time": self.upload_time,
            "processing_result": self.processing_result,
        }


class DocumentAdapter:
    """
    Adapter for document processing in the CPA panel.

    Provides:
    - Document upload handling
    - OCR processing via DocumentProcessor
    - Extracted data retrieval
    - Application to tax returns
    """

    def __init__(self, storage_path: Optional[str] = None):
        """Initialize document adapter."""
        self.storage_path = storage_path or os.path.join("/tmp", "cpa_documents")
        Path(self.storage_path).mkdir(parents=True, exist_ok=True)

        self._processor = None
        self._integration = None

        # In-memory document storage (would be DB in production)
        self._documents: Dict[str, Dict[str, DocumentInfo]] = {}

    @property
    def processor(self):
        """Lazy load document processor."""
        if self._processor is None:
            from services.ocr.document_processor import DocumentProcessor
            self._processor = DocumentProcessor(storage_path=self.storage_path)
        return self._processor

    @property
    def integration(self):
        """Lazy load document integration."""
        if self._integration is None:
            from services.ocr.document_processor import DocumentIntegration
            self._integration = DocumentIntegration()
        return self._integration

    def get_tax_return(self, session_id: str) -> Optional["TaxReturn"]:
        """Get tax return from session."""
        try:
            from cpa_panel.adapters import TaxReturnAdapter
            adapter = TaxReturnAdapter()
            return adapter.get_tax_return(session_id)
        except Exception as e:
            logger.error(f"Failed to get tax return for {session_id}: {e}")
            return None

    def upload_document(
        self,
        session_id: str,
        file_data: bytes,
        filename: str,
        mime_type: str,
        document_type: Optional[str] = None,
        tax_year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Upload and process a document.

        Args:
            session_id: Client session ID
            file_data: Document bytes
            filename: Original filename
            mime_type: MIME type of the document
            document_type: Optional override for document type
            tax_year: Optional override for tax year

        Returns:
            Processing result with extracted data
        """
        try:
            # Process the document
            result = self.processor.process_bytes(
                data=file_data,
                mime_type=mime_type,
                original_filename=filename,
                document_type=document_type,
                tax_year=tax_year,
            )

            # Create document info
            doc_info = DocumentInfo(
                document_id=str(result.document_id),
                session_id=session_id,
                filename=filename,
                document_type=result.document_type,
                status=result.status,
                upload_time=datetime.utcnow().isoformat(),
                processing_result=result.to_dict(),
            )

            # Store document info
            if session_id not in self._documents:
                self._documents[session_id] = {}
            self._documents[session_id][str(result.document_id)] = doc_info

            return {
                "success": True,
                "document_id": str(result.document_id),
                "document_type": result.document_type,
                "tax_year": result.tax_year,
                "status": result.status,
                "ocr_confidence": result.ocr_confidence,
                "extraction_confidence": result.extraction_confidence,
                "extracted_data": result.get_extracted_data(),
                "field_count": len(result.extracted_fields),
                "warnings": result.warnings,
                "errors": result.errors,
                "processing_time_ms": result.processing_time_ms,
            }

        except Exception as e:
            logger.error(f"Document upload failed for {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_documents(self, session_id: str) -> Dict[str, Any]:
        """
        Get all documents for a session.

        Args:
            session_id: Client session ID

        Returns:
            List of document info
        """
        documents = self._documents.get(session_id, {})
        doc_list = [doc.to_dict() for doc in documents.values()]

        # Sort by upload time (newest first)
        doc_list.sort(key=lambda x: x["upload_time"], reverse=True)

        return {
            "success": True,
            "session_id": session_id,
            "documents": doc_list,
            "total": len(doc_list),
        }

    def get_document(self, session_id: str, document_id: str) -> Dict[str, Any]:
        """
        Get a specific document's details.

        Args:
            session_id: Client session ID
            document_id: Document ID

        Returns:
            Document info with processing result
        """
        documents = self._documents.get(session_id, {})
        doc = documents.get(document_id)

        if not doc:
            return {
                "success": False,
                "error": f"Document not found: {document_id}",
            }

        return {
            "success": True,
            **doc.to_dict(),
        }

    def get_extracted_data(self, session_id: str, document_id: str) -> Dict[str, Any]:
        """
        Get extracted data from a processed document.

        Args:
            session_id: Client session ID
            document_id: Document ID

        Returns:
            Extracted fields and data
        """
        doc_result = self.get_document(session_id, document_id)
        if not doc_result.get("success"):
            return doc_result

        processing_result = doc_result.get("processing_result", {})

        # Extract field data
        fields = processing_result.get("extracted_fields", [])
        extracted_data = {}

        for field in fields:
            if field.get("normalized_value") is not None:
                extracted_data[field["field_name"]] = {
                    "value": field["normalized_value"],
                    "raw_value": field.get("raw_value"),
                    "confidence": field.get("confidence", 0),
                    "label": field.get("field_label", field["field_name"]),
                }

        return {
            "success": True,
            "document_id": document_id,
            "document_type": doc_result.get("document_type"),
            "extracted_data": extracted_data,
            "field_count": len(extracted_data),
            "warnings": processing_result.get("warnings", []),
        }

    def apply_to_return(self, session_id: str, document_id: str) -> Dict[str, Any]:
        """
        Apply extracted document data to the tax return.

        Args:
            session_id: Client session ID
            document_id: Document ID

        Returns:
            Result of applying data to return
        """
        # Get document
        doc_result = self.get_document(session_id, document_id)
        if not doc_result.get("success"):
            return doc_result

        # Get tax return
        tax_return = self.get_tax_return(session_id)
        if not tax_return:
            return {
                "success": False,
                "error": f"Tax return not found for session {session_id}",
            }

        processing_result = doc_result.get("processing_result", {})
        document_type = doc_result.get("document_type")

        if not processing_result:
            return {
                "success": False,
                "error": "No processing result available",
            }

        try:
            # Create a ProcessingResult-like object for the integration
            from services.ocr.document_processor import ProcessingResult, ExtractedField
            from services.ocr.field_extractor import FieldType
            from uuid import UUID

            # Reconstruct extracted fields
            fields = []
            for field_data in processing_result.get("extracted_fields", []):
                # Determine field type
                field_type_str = field_data.get("field_type", "TEXT")
                try:
                    field_type = FieldType[field_type_str]
                except (KeyError, TypeError):
                    field_type = FieldType.TEXT

                field = ExtractedField(
                    field_name=field_data.get("field_name", ""),
                    field_label=field_data.get("field_label", ""),
                    field_type=field_type,
                    raw_value=field_data.get("raw_value", ""),
                    normalized_value=field_data.get("normalized_value"),
                    confidence=field_data.get("confidence", 0),
                )
                fields.append(field)

            result = ProcessingResult(
                document_id=UUID(document_id),
                document_type=document_type,
                tax_year=processing_result.get("tax_year", 2025),
                status=processing_result.get("status", "success"),
                ocr_confidence=processing_result.get("ocr_confidence", 0),
                extraction_confidence=processing_result.get("extraction_confidence", 0),
                extracted_fields=fields,
                raw_text=processing_result.get("raw_text", ""),
                processing_time_ms=processing_result.get("processing_time_ms", 0),
                warnings=processing_result.get("warnings", []),
                errors=processing_result.get("errors", []),
            )

            # Apply to return
            success, messages = self.integration.apply_document_to_return(result, tax_return)

            if success:
                return {
                    "success": True,
                    "document_id": document_id,
                    "document_type": document_type,
                    "applied": True,
                    "message": f"Successfully applied {document_type} data to tax return",
                    "warnings": messages,
                }
            else:
                return {
                    "success": False,
                    "error": messages[0] if messages else "Failed to apply document",
                    "messages": messages,
                }

        except Exception as e:
            logger.error(f"Failed to apply document {document_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_supported_types(self) -> Dict[str, Any]:
        """Get list of supported document types."""
        return {
            "success": True,
            "supported_types": self.processor.get_supported_document_types(),
            "auto_apply_types": ["w2", "1099-int", "1099-div", "1099-nec"],
            "manual_entry_types": ["k1", "1098", "1099-b", "1099-r"],
        }


# Singleton instance
_document_adapter: Optional[DocumentAdapter] = None


def get_document_adapter() -> DocumentAdapter:
    """Get or create singleton document adapter."""
    global _document_adapter
    if _document_adapter is None:
        _document_adapter = DocumentAdapter()
    return _document_adapter
