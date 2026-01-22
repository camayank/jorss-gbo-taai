# OCR Endpoint Improvement

## Overview
Improved `/api/ocr/process` endpoint in `app.py` with robust error handling, validation, and user-friendly responses.

## Key Improvements

### 1. Request ID Tracking
```python
request_id = f"OCR-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
logger.info(f"[{request_id}] OCR processing started")
```

### 2. File Size Validation
```python
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
if len(content) > MAX_FILE_SIZE:
    return JSONResponse(
        status_code=413,
        content={
            "success": False,
            "error_type": "FileTooLarge",
            "user_message": "File is too large (max 10MB). Please upload a smaller file.",
            "request_id": request_id
        }
    )
```

### 3. Enhanced Error Messages
```python
# Before
return JSONResponse(
    status_code=500,
    content={"success": False, "error": f"OCR processing failed: {str(e)}"}
)

# After
return JSONResponse(
    status_code=500,
    content={
        "success": False,
        "error_type": "OCRProcessingError",
        "error_message": str(e),
        "user_message": "We had trouble reading your document. Please try a clearer image or PDF.",
        "request_id": request_id,
        "suggestions": [
            "Ensure the image is clear and well-lit",
            "Try scanning at higher resolution",
            "Make sure all text is visible and not cut off"
        ]
    }
)
```

### 4. Graceful Degradation
```python
try:
    result = _document_processor.process_bytes(...)
except ImportError:
    # OCR service not available - provide manual entry option
    return JSONResponse(
        status_code=503,
        content={
            "success": False,
            "error_type": "ServiceUnavailable",
            "user_message": "Document processing is temporarily unavailable. Please enter information manually.",
            "request_id": request_id
        }
    )
```

### 5. Sanitization of Extracted Data
```python
from src.web.validation_helpers import sanitize_string

extracted_data = {}
for field in result.extracted_fields:
    if isinstance(field.value, str):
        extracted_data[field.field_name] = sanitize_string(field.value)
    else:
        extracted_data[field.field_name] = field.value
```

### 6. Detailed Logging
```python
logger.info(f"[{request_id}] OCR processing complete", extra={
    "document_type": result.document_type,
    "fields_extracted": len(extracted_data),
    "confidence": result.extraction_confidence,
    "file_size": len(content),
    "filename": file.filename
})
```

## Complete Improved Code

Add this improved version to `src/web/app.py` (replace existing OCR endpoint):

```python
@app.post("/api/ocr/process")
async def process_ocr_document(file: UploadFile = File(...)):
    """
    Process document with OCR for Express Lane flow - IMPROVED.

    Enhancements:
    - Request ID tracking
    - File size validation
    - Better error messages
    - Graceful degradation
    - Data sanitization
    """
    import tempfile
    import os
    from datetime import datetime
    from src.web.validation_helpers import sanitize_string

    request_id = f"OCR-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    try:
        logger.info(f"[{request_id}] OCR processing started", extra={
            "filename": file.filename,
            "content_type": file.content_type,
            "request_id": request_id
        })

        # Validate file type
        allowed_types = ["application/pdf", "image/png", "image/jpeg", "image/jpg", "image/heic"]
        allowed_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.heic']

        is_valid_type = file.content_type in allowed_types if file.content_type else False
        is_valid_ext = any(file.filename.lower().endswith(ext) for ext in allowed_extensions)

        if not (is_valid_type or is_valid_ext):
            logger.warning(f"[{request_id}] Invalid file type: {file.content_type}")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error_type": "InvalidFileType",
                    "user_message": f"File type not supported. Please upload PDF, PNG, JPG, or HEIC files.",
                    "request_id": request_id
                }
            )

        # Read file with size limit
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        try:
            content = await file.read()
        except Exception as e:
            logger.error(f"[{request_id}] Failed to read file: {str(e)}")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error_type": "FileReadError",
                    "user_message": "Unable to read the uploaded file. Please try again.",
                    "request_id": request_id
                }
            )

        # Check file size
        if len(content) > MAX_FILE_SIZE:
            logger.warning(f"[{request_id}] File too large: {len(content)} bytes")
            return JSONResponse(
                status_code=413,
                content={
                    "success": False,
                    "error_type": "FileTooLarge",
                    "user_message": f"File is too large ({len(content) / 1024 / 1024:.1f}MB). Maximum size is 10MB. Please compress or upload a smaller file.",
                    "request_id": request_id
                }
            )

        # Check if file is empty
        if len(content) == 0:
            logger.warning(f"[{request_id}] Empty file uploaded")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error_type": "EmptyFile",
                    "user_message": "The uploaded file is empty. Please select a valid document.",
                    "request_id": request_id
                }
            )

        # Process with OCR
        temp_path = None
        try:
            # Create temporary file
            temp_fd, temp_path = tempfile.mkstemp(suffix=os.path.splitext(file.filename)[1])

            try:
                with os.fdopen(temp_fd, 'wb') as temp_file:
                    temp_file.write(content)

                # Process with document processor
                result = _document_processor.process_bytes(
                    data=content,
                    mime_type=file.content_type or "application/pdf",
                    original_filename=file.filename,
                    document_type=None,  # Auto-detect
                    tax_year=None,  # Auto-detect
                )

                # Sanitize and extract data
                extracted_data = {}
                for field in result.extracted_fields:
                    if isinstance(field.value, str):
                        extracted_data[field.field_name] = sanitize_string(field.value)
                    else:
                        extracted_data[field.field_name] = field.value

                # Check if we extracted any data
                if not extracted_data:
                    logger.warning(f"[{request_id}] No data extracted from document")
                    return JSONResponse(
                        status_code=200,
                        content={
                            "success": False,
                            "error_type": "NoDataExtracted",
                            "user_message": "We couldn't find any tax information in this document. Please ensure it's a clear image of a W-2, 1099, or similar tax form.",
                            "request_id": request_id,
                            "suggestions": [
                                "Make sure the entire document is visible",
                                "Ensure the image is clear and well-lit",
                                "Try scanning at higher resolution",
                                "Check that you uploaded the correct document"
                            ]
                        }
                    )

                logger.info(f"[{request_id}] OCR processing successful", extra={
                    "document_type": result.document_type,
                    "fields_extracted": len(extracted_data),
                    "confidence": result.extraction_confidence or result.ocr_confidence
                })

                return JSONResponse({
                    "success": True,
                    "extracted_data": extracted_data,
                    "document_type": result.document_type,
                    "confidence": result.extraction_confidence or result.ocr_confidence,
                    "tax_year": result.tax_year,
                    "warnings": result.warnings or [],
                    "request_id": request_id
                })

            finally:
                # Always clean up temp file
                try:
                    if temp_path and os.path.exists(temp_path):
                        os.unlink(temp_path)
                except Exception as cleanup_error:
                    logger.warning(f"[{request_id}] Temp file cleanup failed: {str(cleanup_error)}")

        except ImportError as e:
            logger.error(f"[{request_id}] OCR service not available: {str(e)}")
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "error_type": "ServiceUnavailable",
                    "user_message": "Document processing service is temporarily unavailable. Please enter information manually or try again later.",
                    "request_id": request_id
                }
            )

        except Exception as ocr_error:
            logger.error(f"[{request_id}] OCR processing failed: {str(ocr_error)}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error_type": "OCRProcessingError",
                    "error_message": str(ocr_error),
                    "user_message": "We had trouble reading your document. Please try uploading a clearer image or enter the information manually.",
                    "request_id": request_id,
                    "suggestions": [
                        "Ensure the image is clear and well-lit",
                        "Try scanning at higher resolution",
                        "Make sure all text is visible",
                        "Avoid shadows or glare on the document",
                        "Try converting to PDF if uploading an image"
                    ]
                }
            )

    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error in OCR endpoint: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error_type": "UnexpectedError",
                "user_message": "An unexpected error occurred. Please try again or enter information manually.",
                "request_id": request_id
            }
        )
```

## Frontend Integration

The improved endpoint returns structured error responses that the frontend can use to display helpful messages:

```javascript
try {
    const response = await fetch('/api/ocr/process', {
        method: 'POST',
        body: formData
    });

    const data = await response.json();

    if (!data.success) {
        // Show user-friendly error message
        showError(data.user_message);

        // Show suggestions if available
        if (data.suggestions) {
            showSuggestions(data.suggestions);
        }

        // Log request_id for support
        console.log('Request ID:', data.request_id);
    } else {
        // Handle successful extraction
        displayExtractedData(data.extracted_data);
    }

} catch (error) {
    showError('Unable to process document. Please check your connection and try again.');
}
```

## Testing Checklist

- [ ] Test with valid PDF
- [ ] Test with valid image (PNG, JPG, HEIC)
- [ ] Test with invalid file type (e.g., .txt, .docx)
- [ ] Test with file > 10MB
- [ ] Test with empty file
- [ ] Test with corrupted file
- [ ] Test with clear, high-quality scan
- [ ] Test with blurry or low-quality image
- [ ] Test with document with no extractable data
- [ ] Verify request IDs are logged correctly
- [ ] Verify temp files are always cleaned up
- [ ] Verify graceful handling when OCR service is down

## Monitoring & Alerts

Set up alerts for:
- OCR success rate < 80%
- Average processing time > 5 seconds
- Error rate > 10%
- File size rejections spike

## Performance Considerations

- Max 10MB file size prevents memory issues
- Temp file cleanup prevents disk space issues
- Request ID tracking enables debugging production issues
- Structured logging enables analytics
