# Frontend Error Handling Guide

## Overview

This guide provides best practices and implementation patterns for handling errors in the tax platform frontend. All examples integrate with the improved backend API error responses.

---

## Table of Contents

1. [Error Types](#error-types)
2. [Error Handling Patterns](#error-handling-patterns)
3. [UI Components](#ui-components)
4. [Retry Logic](#retry-logic)
5. [Loading States](#loading-states)
6. [Validation Display](#validation-display)
7. [Network Error Handling](#network-error-handling)
8. [Complete Examples](#complete-examples)

---

## Error Types

### Backend Error Response Format

All improved APIs return consistent error structures:

```javascript
{
    "error_type": "ValidationError",              // Error category
    "error_message": "SSN format invalid",        // Technical details
    "user_message": "Please check your SSN",      // Display to user
    "request_id": "REQ-20250121123456789",       // For support
    "validation_errors": ["SSN is required"],     // Specific errors
    "suggestions": ["Format: XXX-XX-XXXX"]        // How to fix
}
```

### Error Categories

1. **ValidationError (422)** - Invalid user input
2. **ServiceUnavailable (503)** - Service temporarily down
3. **FileTooLarge (413)** - File size exceeded
4. **OCRProcessingError (500)** - Document reading failed
5. **CalculationError (500)** - Tax calculation failed
6. **SessionNotFound (404)** - Invalid/expired session
7. **UnexpectedError (500)** - Unknown error

---

## Error Handling Patterns

### Pattern 1: Basic Error Handler

```javascript
async function apiCall(url, options) {
    try {
        const response = await fetch(url, options);

        if (!response.ok) {
            const error = await response.json();
            handleApiError(error);
            return null;
        }

        return await response.json();

    } catch (error) {
        // Network error
        handleNetworkError(error);
        return null;
    }
}

function handleApiError(errorData) {
    const { error_type, user_message, validation_errors, suggestions, request_id } = errorData;

    // Log for debugging
    console.error(`API Error (${error_type}):`, {
        request_id,
        message: user_message,
        errors: validation_errors
    });

    // Show user message
    showNotification(user_message, 'error');

    // Handle specific error types
    switch(error_type) {
        case 'ValidationError':
            highlightInvalidFields(validation_errors);
            showSuggestions(suggestions);
            break;

        case 'SessionNotFound':
            redirectToLogin();
            break;

        case 'ServiceUnavailable':
            showServiceDownBanner();
            break;

        case 'OCRProcessingError':
            offerManualEntry();
            break;
    }
}
```

### Pattern 2: Express Lane Submission

```javascript
async function submitExpressLane(formData) {
    const submitButton = document.getElementById('submit-btn');
    const progressDiv = document.getElementById('progress');

    try {
        // Show loading state
        submitButton.disabled = true;
        submitButton.textContent = 'Processing...';
        progressDiv.textContent = 'Calculating your taxes...';

        const response = await fetch('/api/tax-returns/express-lane', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        const result = await response.json();

        if (!response.ok) {
            handleExpressLaneError(result);
            return;
        }

        // Success - show results
        displayTaxResults(result);
        showSuccessMessage(`Return ${result.return_id} created!`);

    } catch (error) {
        showError('Unable to submit your return. Please check your connection and try again.');
        console.error('Submit error:', error);

    } finally {
        // Always reset UI
        submitButton.disabled = false;
        submitButton.textContent = 'Submit Return';
        progressDiv.textContent = '';
    }
}

function handleExpressLaneError(errorData) {
    const { error_type, user_message, validation_errors, request_id } = errorData;

    // Show main error
    showErrorBanner(user_message);

    // Specific error handling
    if (error_type === 'ValidationError' && validation_errors) {
        // Highlight invalid fields
        validation_errors.forEach(error => {
            const field = document.querySelector(`[name="${error.field}"]`);
            if (field) {
                markFieldInvalid(field, error.message);
            }
        });

        // Scroll to first error
        const firstError = document.querySelector('.field-error');
        if (firstError) {
            firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    // Save request ID for support
    sessionStorage.setItem('last_error_request_id', request_id);
}
```

### Pattern 3: Document Upload with Retry

```javascript
async function uploadDocument(file, maxRetries = 3) {
    const uploadArea = document.getElementById('upload-area');
    const progressBar = document.getElementById('progress-bar');
    const statusText = document.getElementById('status-text');

    let attempt = 0;

    while (attempt < maxRetries) {
        try {
            attempt++;

            // Update UI
            statusText.textContent = `Uploading... ${attempt > 1 ? `(attempt ${attempt})` : ''}`;
            progressBar.style.width = '50%';

            // Upload file
            const formData = new FormData();
            formData.append('file', file);
            formData.append('session_id', getSessionId());

            const response = await fetch('/api/ocr/process', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (!result.success) {
                // OCR failed
                if (result.error_type === 'OCRProcessingError' && attempt < maxRetries) {
                    // Retry
                    statusText.textContent = 'Processing failed, retrying...';
                    await sleep(1000 * attempt);  // Exponential backoff
                    continue;
                }

                // No more retries or non-retryable error
                handleUploadError(result);
                return null;
            }

            // Success
            progressBar.style.width = '100%';
            statusText.textContent = 'Document processed successfully!';
            displayExtractedData(result.extracted_data);
            return result;

        } catch (error) {
            // Network error
            if (attempt < maxRetries) {
                statusText.textContent = 'Connection issue, retrying...';
                await sleep(1000 * attempt);
                continue;
            }

            showError('Unable to upload document. Please check your connection.');
            return null;
        }
    }
}

function handleUploadError(errorData) {
    const { error_type, user_message, suggestions } = errorData;

    // Show error message
    showNotification(user_message, 'error');

    // Show suggestions
    if (suggestions && suggestions.length > 0) {
        const suggestionsList = document.getElementById('upload-suggestions');
        suggestionsList.innerHTML = '<strong>Try these tips:</strong>';

        const ul = document.createElement('ul');
        suggestions.forEach(tip => {
            const li = document.createElement('li');
            li.textContent = tip;
            ul.appendChild(li);
        });

        suggestionsList.appendChild(ul);
        suggestionsList.classList.add('visible');
    }

    // Specific error handling
    if (error_type === 'FileTooLarge') {
        showCompressionOption();
    } else if (error_type === 'InvalidFileType') {
        highlightAcceptedFormats();
    } else if (error_type === 'NoDataExtracted') {
        offerManualEntry();
    }
}
```

### Pattern 4: AI Chat Error Recovery

```javascript
async function sendChatMessage(message) {
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-btn');

    try {
        // Disable input
        chatInput.disabled = true;
        sendButton.disabled = true;

        // Add user message to UI
        appendMessage('user', message);

        // Show typing indicator
        showTypingIndicator();

        const response = await fetch('/api/ai-chat/message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: getSessionId(),
                user_message: message
            })
        });

        const result = await response.json();

        if (!response.ok) {
            handleChatError(result, message);
            return;
        }

        // Hide typing indicator
        hideTypingIndicator();

        // Display AI response
        appendMessage('assistant', result.response);

        // Show quick actions
        if (result.quick_actions) {
            displayQuickActions(result.quick_actions);
        }

        // Show data cards
        if (result.data_cards) {
            displayDataCards(result.data_cards);
        }

    } catch (error) {
        hideTypingIndicator();
        appendMessage('system', 'Unable to send message. Please check your connection.');
        console.error('Chat error:', error);

    } finally {
        // Re-enable input
        chatInput.disabled = false;
        sendButton.disabled = false;
        chatInput.focus();
    }
}

function handleChatError(errorData, originalMessage) {
    const { error_type, user_message } = errorData;

    hideTypingIndicator();

    // Show error in chat
    appendMessage('system', user_message);

    // Specific error handling
    if (error_type === 'SessionNotFound') {
        // Start new session
        showMessage('Starting a new conversation...');
        createNewSession();

    } else if (error_type === 'ProcessingTimeout') {
        // Offer retry
        showRetryButton(originalMessage);

    } else {
        // Offer fallback options
        showQuickActions([
            { label: 'Start over', value: 'reset' },
            { label: 'Get help', value: 'help' }
        ]);
    }
}
```

---

## UI Components

### Error Banner Component

```html
<!-- Error banner at top of page -->
<div id="error-banner" class="error-banner hidden">
    <div class="error-content">
        <span class="error-icon">⚠️</span>
        <span class="error-message" id="error-message"></span>
        <button class="error-close" onclick="hideErrorBanner()">×</button>
    </div>
    <div id="error-suggestions" class="error-suggestions hidden"></div>
</div>
```

```css
.error-banner {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    background: #fee;
    border-bottom: 2px solid #c33;
    padding: 15px;
    z-index: 1000;
    animation: slideDown 0.3s ease;
}

.error-banner.hidden {
    display: none;
}

.error-content {
    display: flex;
    align-items: center;
    gap: 10px;
    max-width: 1200px;
    margin: 0 auto;
}

.error-icon {
    font-size: 24px;
}

.error-message {
    flex: 1;
    color: #c33;
    font-weight: 500;
}

.error-close {
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: #c33;
}

@keyframes slideDown {
    from {
        transform: translateY(-100%);
    }
    to {
        transform: translateY(0);
    }
}
```

```javascript
function showErrorBanner(message, suggestions = []) {
    const banner = document.getElementById('error-banner');
    const messageEl = document.getElementById('error-message');
    const suggestionsEl = document.getElementById('error-suggestions');

    messageEl.textContent = message;
    banner.classList.remove('hidden');

    // Show suggestions if provided
    if (suggestions.length > 0) {
        const ul = document.createElement('ul');
        suggestions.forEach(tip => {
            const li = document.createElement('li');
            li.textContent = tip;
            ul.appendChild(li);
        });

        suggestionsEl.innerHTML = '<strong>Suggestions:</strong>';
        suggestionsEl.appendChild(ul);
        suggestionsEl.classList.remove('hidden');
    }

    // Auto-hide after 10 seconds
    setTimeout(() => {
        if (!banner.classList.contains('hidden')) {
            hideErrorBanner();
        }
    }, 10000);
}

function hideErrorBanner() {
    document.getElementById('error-banner').classList.add('hidden');
    document.getElementById('error-suggestions').classList.add('hidden');
}
```

### Toast Notification Component

```html
<div id="toast-container"></div>
```

```javascript
function showNotification(message, type = 'info', duration = 5000) {
    const container = document.getElementById('toast-container');

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icon = {
        success: '✓',
        error: '✗',
        warning: '⚠',
        info: 'ℹ'
    }[type] || 'ℹ';

    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <span class="toast-message">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;

    container.appendChild(toast);

    // Auto-remove
    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}
```

```css
#toast-container {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 2000;
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.toast {
    background: white;
    border-radius: 8px;
    padding: 15px 20px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 300px;
    animation: slideIn 0.3s ease;
}

.toast-success { border-left: 4px solid #4caf50; }
.toast-error { border-left: 4px solid #f44336; }
.toast-warning { border-left: 4px solid #ff9800; }
.toast-info { border-left: 4px solid #2196f3; }

.toast.fade-out {
    animation: slideOut 0.3s ease forwards;
}

@keyframes slideIn {
    from {
        transform: translateX(400px);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

@keyframes slideOut {
    to {
        transform: translateX(400px);
        opacity: 0;
    }
}
```

### Field Validation Component

```html
<div class="form-field" data-field="ssn">
    <label for="ssn">Social Security Number <span class="required">*</span></label>
    <input
        type="text"
        id="ssn"
        name="ssn"
        placeholder="XXX-XX-XXXX"
        maxlength="11"
    >
    <span class="field-error hidden" id="ssn-error"></span>
    <span class="field-help">Format: XXX-XX-XXXX</span>
</div>
```

```javascript
function markFieldInvalid(fieldName, errorMessage) {
    const field = document.querySelector(`[name="${fieldName}"]`);
    if (!field) return;

    const formField = field.closest('.form-field');
    const errorEl = formField.querySelector('.field-error');

    // Add error class
    formField.classList.add('has-error');
    field.classList.add('invalid');

    // Show error message
    errorEl.textContent = errorMessage;
    errorEl.classList.remove('hidden');

    // Clear error on input
    field.addEventListener('input', function clearError() {
        formField.classList.remove('has-error');
        field.classList.remove('invalid');
        errorEl.classList.add('hidden');
        field.removeEventListener('input', clearError);
    }, { once: true });
}

function clearAllFieldErrors() {
    document.querySelectorAll('.form-field').forEach(field => {
        field.classList.remove('has-error');
    });

    document.querySelectorAll('input, select, textarea').forEach(input => {
        input.classList.remove('invalid');
    });

    document.querySelectorAll('.field-error').forEach(error => {
        error.classList.add('hidden');
    });
}
```

```css
.form-field {
    margin-bottom: 20px;
}

.form-field label {
    display: block;
    margin-bottom: 5px;
    font-weight: 500;
}

.form-field input,
.form-field select,
.form-field textarea {
    width: 100%;
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 16px;
}

.form-field input.invalid {
    border-color: #f44336;
    background: #fff5f5;
}

.form-field.has-error label {
    color: #f44336;
}

.field-error {
    display: block;
    color: #f44336;
    font-size: 14px;
    margin-top: 5px;
}

.field-error.hidden {
    display: none;
}

.field-help {
    display: block;
    color: #666;
    font-size: 14px;
    margin-top: 5px;
}

.required {
    color: #f44336;
}
```

---

## Loading States

```javascript
class LoadingManager {
    constructor() {
        this.loadingCount = 0;
    }

    show(message = 'Loading...') {
        this.loadingCount++;

        if (this.loadingCount === 1) {
            // Show loading overlay
            const overlay = document.getElementById('loading-overlay') || this.createOverlay();
            overlay.querySelector('.loading-message').textContent = message;
            overlay.classList.remove('hidden');

            // Disable forms
            document.querySelectorAll('form').forEach(form => {
                form.classList.add('loading');
            });
        }
    }

    hide() {
        this.loadingCount = Math.max(0, this.loadingCount - 1);

        if (this.loadingCount === 0) {
            // Hide loading overlay
            const overlay = document.getElementById('loading-overlay');
            if (overlay) {
                overlay.classList.add('hidden');
            }

            // Re-enable forms
            document.querySelectorAll('form').forEach(form => {
                form.classList.remove('loading');
            });
        }
    }

    createOverlay() {
        const overlay = document.createElement('div');
        overlay.id = 'loading-overlay';
        overlay.className = 'loading-overlay';
        overlay.innerHTML = `
            <div class="loading-content">
                <div class="spinner"></div>
                <div class="loading-message">Loading...</div>
            </div>
        `;
        document.body.appendChild(overlay);
        return overlay;
    }
}

// Global instance
const loading = new LoadingManager();

// Usage
async function someApiCall() {
    loading.show('Processing your tax return...');
    try {
        const result = await fetch('/api/...');
        return result;
    } finally {
        loading.hide();
    }
}
```

---

## Complete Examples

### Express Lane Full Flow

```javascript
class ExpressLaneTaxReturn {
    constructor() {
        this.documents = [];
        this.extractedData = {};
        this.userEdits = {};
    }

    async uploadDocument(file) {
        try {
            loading.show('Reading your document...');

            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('/api/ocr/process', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (!result.success) {
                this.handleOCRError(result);
                return false;
            }

            // Store extracted data
            this.extractedData = { ...this.extractedData, ...result.extracted_data };
            this.documents.push(result.document_id || `file-${Date.now()}`);

            // Show extracted data for review
            this.displayExtractedData(result.extracted_data);

            showNotification('Document processed successfully!', 'success');
            return true;

        } catch (error) {
            showError('Unable to process document. Please try again.');
            return false;

        } finally {
            loading.hide();
        }
    }

    async submitReturn() {
        try {
            // Clear previous errors
            clearAllFieldErrors();

            // Validate locally first
            const localErrors = this.validateLocally();
            if (localErrors.length > 0) {
                localErrors.forEach(error => {
                    markFieldInvalid(error.field, error.message);
                });
                showErrorBanner('Please fix the highlighted fields.');
                return false;
            }

            loading.show('Calculating your taxes...');

            // Submit to backend
            const response = await fetch('/api/tax-returns/express-lane', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    extracted_data: this.extractedData,
                    documents: this.documents,
                    user_edits: this.userEdits
                })
            });

            const result = await response.json();

            if (!response.ok) {
                this.handleSubmitError(result);
                return false;
            }

            // Success!
            this.displayResults(result);
            showNotification(`Return ${result.return_id} created successfully!`, 'success');
            return true;

        } catch (error) {
            showError('Unable to submit return. Please check your connection.');
            return false;

        } finally {
            loading.hide();
        }
    }

    validateLocally() {
        const errors = [];

        // Check required fields
        if (!this.extractedData.first_name) {
            errors.push({ field: 'first_name', message: 'First name is required' });
        }

        if (!this.extractedData.ssn) {
            errors.push({ field: 'ssn', message: 'SSN is required' });
        }

        // Basic SSN format check
        if (this.extractedData.ssn && !/^\d{3}-?\d{2}-?\d{4}$/.test(this.extractedData.ssn)) {
            errors.push({ field: 'ssn', message: 'Invalid SSN format (XXX-XX-XXXX)' });
        }

        return errors;
    }

    handleOCRError(errorData) {
        const { error_type, user_message, suggestions } = errorData;

        showErrorBanner(user_message, suggestions);

        // Specific handling
        if (error_type === 'NoDataExtracted') {
            this.showManualEntryOption();
        } else if (error_type === 'FileTooLarge') {
            this.showCompressionHelp();
        }
    }

    handleSubmitError(errorData) {
        const { error_type, user_message, validation_errors } = errorData;

        showErrorBanner(user_message);

        if (error_type === 'ValidationError' && validation_errors) {
            // Highlight invalid fields
            validation_errors.forEach(error => {
                markFieldInvalid(error.field, error.message);
            });

            // Scroll to first error
            const firstError = document.querySelector('.has-error');
            if (firstError) {
                firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }

        // Save request ID
        sessionStorage.setItem('last_error_request_id', errorData.request_id);
    }
}
```

---

## Summary

### Key Takeaways

1. **Always handle both success and error cases**
2. **Show user-friendly messages, not technical errors**
3. **Provide actionable suggestions when errors occur**
4. **Use loading states to indicate progress**
5. **Implement retry logic for transient failures**
6. **Highlight validation errors on specific fields**
7. **Log request IDs for debugging production issues**
8. **Test error handling as thoroughly as happy paths**

### Error Handling Checklist

- [ ] Network errors handled gracefully
- [ ] API errors display user-friendly messages
- [ ] Validation errors highlight specific fields
- [ ] Loading states shown during processing
- [ ] Retry logic for transient failures
- [ ] Request IDs logged for debugging
- [ ] Error tracking in analytics
- [ ] Graceful degradation when services unavailable
- [ ] Accessibility: errors announced to screen readers
- [ ] Mobile-friendly error displays

---

**Version:** 1.0
**Last Updated:** 2025-01-21
**Status:** Production Ready
