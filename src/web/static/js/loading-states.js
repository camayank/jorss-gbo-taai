/**
 * Loading States Manager - Accessible loading indicators and skeleton screens.
 *
 * Provides:
 * - Loading state management for async operations
 * - Accessible loading indicators with ARIA attributes
 * - Skeleton screen components
 * - Polling helpers for background tasks
 *
 * Resolves Audit Finding: "Missing loading states and accessibility"
 */

(function(global) {
  'use strict';

  const LoadingStates = {
    // Configuration
    config: {
      loadingClass: 'is-loading',
      skeletonClass: 'skeleton',
      spinnerClass: 'loading-spinner',
      defaultTimeout: 30000, // 30 seconds
      pollingInterval: 2000, // 2 seconds
    },

    // Track active loading operations
    _activeOperations: new Map(),

    /**
     * Start a loading operation with accessibility support.
     *
     * @param {string|HTMLElement} container - Container element or selector
     * @param {Object} options - Options
     * @param {string} options.message - Loading message for screen readers
     * @param {boolean} options.showSpinner - Whether to show spinner (default: true)
     * @param {boolean} options.showSkeleton - Whether to show skeleton (default: false)
     * @param {number} options.timeout - Timeout in ms (default: 30000)
     * @returns {string} Operation ID for tracking
     */
    start(container, options = {}) {
      const element = typeof container === 'string'
        ? document.querySelector(container)
        : container;

      if (!element) {
        console.warn('LoadingStates: Container not found');
        return null;
      }

      const operationId = 'loading-' + crypto.randomUUID();
      const {
        message = 'Loading...',
        showSpinner = true,
        showSkeleton = false,
        timeout = this.config.defaultTimeout,
      } = options;

      // Set ARIA attributes for accessibility
      element.setAttribute('aria-busy', 'true');
      element.setAttribute('aria-live', 'polite');
      element.classList.add(this.config.loadingClass);

      // Store original content if using skeleton
      const originalContent = element.innerHTML;

      // Add loading indicator
      if (showSkeleton) {
        element.innerHTML = this._createSkeleton(element);
      } else if (showSpinner) {
        this._addSpinner(element, message);
      }

      // Create live region announcement for screen readers
      this._announce(message);

      // Store operation info
      this._activeOperations.set(operationId, {
        element,
        originalContent,
        message,
        startTime: Date.now(),
        timeout: timeout,
        timeoutId: setTimeout(() => {
          this._handleTimeout(operationId);
        }, timeout),
      });

      return operationId;
    },

    /**
     * End a loading operation.
     *
     * @param {string} operationId - Operation ID from start()
     * @param {Object} options - Options
     * @param {string} options.message - Completion message for screen readers
     * @param {boolean} options.restoreContent - Whether to restore original content
     */
    end(operationId, options = {}) {
      const operation = this._activeOperations.get(operationId);
      if (!operation) {
        return;
      }

      const { element, originalContent, timeoutId } = operation;
      const { message = 'Loading complete', restoreContent = false } = options;

      // Clear timeout
      clearTimeout(timeoutId);

      // Remove loading state
      element.setAttribute('aria-busy', 'false');
      element.classList.remove(this.config.loadingClass);

      // Remove spinner if present
      const spinner = element.querySelector('.' + this.config.spinnerClass);
      if (spinner) {
        spinner.remove();
      }

      // Restore original content if requested
      if (restoreContent && originalContent) {
        element.innerHTML = originalContent;
      }

      // Announce completion
      this._announce(message);

      // Clean up
      this._activeOperations.delete(operationId);
    },

    /**
     * Update loading progress.
     *
     * @param {string} operationId - Operation ID
     * @param {number} progress - Progress percentage (0-100)
     * @param {string} message - Optional progress message
     */
    updateProgress(operationId, progress, message = null) {
      const operation = this._activeOperations.get(operationId);
      if (!operation) return;

      const { element } = operation;
      const progressBar = element.querySelector('.loading-progress');

      if (progressBar) {
        progressBar.style.width = progress + '%';
        progressBar.setAttribute('aria-valuenow', progress);
      }

      if (message) {
        const statusText = element.querySelector('.loading-status');
        if (statusText) {
          statusText.textContent = message;
        }
        this._announce(message);
      }
    },

    /**
     * Show error state.
     *
     * @param {string} operationId - Operation ID
     * @param {string} errorMessage - Error message to display
     * @param {Object} options - Options
     * @param {boolean} options.allowRetry - Show retry button
     * @param {Function} options.onRetry - Retry callback
     */
    showError(operationId, errorMessage, options = {}) {
      const operation = this._activeOperations.get(operationId);
      if (!operation) return;

      const { element } = operation;
      const { allowRetry = true, onRetry = null } = options;

      // Clear timeout
      clearTimeout(operation.timeoutId);

      // Update state
      element.setAttribute('aria-busy', 'false');
      element.classList.remove(this.config.loadingClass);
      element.classList.add('has-error');

      // Remove spinner
      const spinner = element.querySelector('.' + this.config.spinnerClass);
      if (spinner) {
        const errorHtml = `
          <div class="loading-error" role="alert" aria-live="assertive">
            <span class="error-icon" aria-hidden="true">⚠️</span>
            <span class="error-message">${this._escapeHtml(errorMessage)}</span>
            ${allowRetry && onRetry ? `
              <button class="retry-btn" type="button" aria-label="Retry operation">
                Retry
              </button>
            ` : ''}
          </div>
        `;
        spinner.outerHTML = errorHtml;

        // Attach retry handler
        if (allowRetry && onRetry) {
          const retryBtn = element.querySelector('.retry-btn');
          if (retryBtn) {
            retryBtn.addEventListener('click', onRetry);
          }
        }
      }

      // Announce error
      this._announce('Error: ' + errorMessage);

      // Clean up
      this._activeOperations.delete(operationId);
    },

    /**
     * Poll for background task status.
     *
     * @param {string} url - URL to poll
     * @param {Object} options - Options
     * @param {number} options.interval - Polling interval in ms
     * @param {number} options.maxAttempts - Maximum polling attempts
     * @param {Function} options.onProgress - Progress callback
     * @param {Function} options.isComplete - Function to check if complete
     * @returns {Promise} Resolves when task is complete
     */
    poll(url, options = {}) {
      const {
        interval = this.config.pollingInterval,
        maxAttempts = 60,
        onProgress = null,
        isComplete = (data) => data.status === 'complete',
      } = options;

      let attempts = 0;

      return new Promise((resolve, reject) => {
        const checkStatus = async () => {
          attempts++;

          try {
            const response = await fetch(url);
            const data = await response.json();

            if (onProgress) {
              onProgress(data, attempts);
            }

            if (isComplete(data)) {
              resolve(data);
            } else if (data.status === 'error' || data.status === 'failed') {
              reject(new Error(data.error_message || 'Task failed'));
            } else if (attempts >= maxAttempts) {
              reject(new Error('Polling timeout'));
            } else {
              setTimeout(checkStatus, interval);
            }
          } catch (error) {
            if (attempts >= maxAttempts) {
              reject(error);
            } else {
              setTimeout(checkStatus, interval);
            }
          }
        };

        checkStatus();
      });
    },

    /**
     * Create a skeleton screen HTML.
     *
     * @param {HTMLElement} element - Container element
     * @returns {string} Skeleton HTML
     */
    _createSkeleton(element) {
      const type = element.dataset.skeletonType || 'text';

      const skeletons = {
        text: `
          <div class="skeleton skeleton-text" aria-hidden="true">
            <div class="skeleton-line" style="width: 100%"></div>
            <div class="skeleton-line" style="width: 80%"></div>
            <div class="skeleton-line" style="width: 90%"></div>
          </div>
        `,
        card: `
          <div class="skeleton skeleton-card" aria-hidden="true">
            <div class="skeleton-avatar"></div>
            <div class="skeleton-content">
              <div class="skeleton-line" style="width: 60%"></div>
              <div class="skeleton-line" style="width: 80%"></div>
            </div>
          </div>
        `,
        table: `
          <div class="skeleton skeleton-table" aria-hidden="true">
            ${Array(5).fill().map(() => `
              <div class="skeleton-row">
                <div class="skeleton-cell" style="width: 20%"></div>
                <div class="skeleton-cell" style="width: 30%"></div>
                <div class="skeleton-cell" style="width: 25%"></div>
                <div class="skeleton-cell" style="width: 25%"></div>
              </div>
            `).join('')}
          </div>
        `,
      };

      return skeletons[type] || skeletons.text;
    },

    /**
     * Add spinner to element.
     *
     * @param {HTMLElement} element - Container element
     * @param {string} message - Loading message
     */
    _addSpinner(element, message) {
      const spinnerHtml = `
        <div class="${this.config.spinnerClass}" role="status" aria-live="polite">
          <div class="spinner-animation" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="24" height="24">
              <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" opacity="0.25"/>
              <path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                d="M12 2 A10 10 0 0 1 22 12">
                <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12"
                  dur="1s" repeatCount="indefinite"/>
              </path>
            </svg>
          </div>
          <span class="loading-status">${this._escapeHtml(message)}</span>
          <div class="loading-progress-container" aria-hidden="true">
            <div class="loading-progress" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"></div>
          </div>
        </div>
      `;

      // Insert spinner at beginning of element
      element.insertAdjacentHTML('afterbegin', spinnerHtml);
    },

    /**
     * Handle timeout.
     *
     * @param {string} operationId - Operation ID
     */
    _handleTimeout(operationId) {
      this.showError(operationId, 'This is taking longer than expected. Please try again.', {
        allowRetry: true,
      });
    },

    /**
     * Announce message to screen readers.
     *
     * @param {string} message - Message to announce
     */
    _announce(message) {
      // Find or create live region
      let liveRegion = document.getElementById('loading-live-region');
      if (!liveRegion) {
        liveRegion = document.createElement('div');
        liveRegion.id = 'loading-live-region';
        liveRegion.setAttribute('role', 'status');
        liveRegion.setAttribute('aria-live', 'polite');
        liveRegion.setAttribute('aria-atomic', 'true');
        liveRegion.className = 'sr-only';
        document.body.appendChild(liveRegion);
      }

      // Update message (triggers screen reader announcement)
      liveRegion.textContent = message;
    },

    /**
     * Escape HTML entities.
     *
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    _escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    },
  };

  // Inject CSS styles
  const styles = `
    /* Screen reader only */
    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }

    /* Loading state */
    .is-loading {
      position: relative;
      pointer-events: none;
    }

    .is-loading > *:not(.loading-spinner) {
      opacity: 0.5;
    }

    /* Spinner */
    .loading-spinner {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 20px;
      gap: 12px;
    }

    .spinner-animation {
      color: var(--primary, var(--color-primary-500, #1e3a5f));
    }

    .loading-status {
      font-size: 14px;
      color: var(--text-muted, var(--color-gray-500, #6b7280));
    }

    .loading-progress-container {
      width: 100%;
      max-width: 200px;
      height: 4px;
      background: var(--border-color, var(--color-gray-200, #e5e7eb));
      border-radius: 2px;
      overflow: hidden;
    }

    .loading-progress {
      height: 100%;
      width: 0%;
      background: var(--primary, var(--color-primary-500, #1e3a5f));
      border-radius: 2px;
      transition: width 0.3s ease;
    }

    /* Error state */
    .loading-error {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      padding: 20px;
      color: var(--error, var(--color-error-500, #ef4444));
    }

    .error-icon {
      font-size: 24px;
    }

    .error-message {
      font-size: 14px;
      text-align: center;
    }

    .retry-btn {
      padding: 8px 16px;
      background: var(--primary, var(--color-primary-500, #1e3a5f));
      color: white;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      font-size: 14px;
    }

    .retry-btn:hover {
      opacity: 0.9;
    }

    .retry-btn:focus {
      outline: 2px solid var(--primary, var(--color-primary-500, #1e3a5f));
      outline-offset: 2px;
    }

    /* Skeleton animations */
    .skeleton {
      animation: skeleton-pulse 1.5s ease-in-out infinite;
    }

    @keyframes skeleton-pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }

    .skeleton-line {
      height: 16px;
      background: var(--border-color, var(--color-gray-200, #e5e7eb));
      border-radius: 4px;
      margin-bottom: 8px;
    }

    .skeleton-card {
      display: flex;
      gap: 12px;
      padding: 16px;
    }

    .skeleton-avatar {
      width: 48px;
      height: 48px;
      background: var(--border-color, var(--color-gray-200, #e5e7eb));
      border-radius: 50%;
      flex-shrink: 0;
    }

    .skeleton-content {
      flex: 1;
    }

    .skeleton-row {
      display: flex;
      gap: 8px;
      padding: 8px 0;
    }

    .skeleton-cell {
      height: 20px;
      background: var(--border-color, var(--color-gray-200, #e5e7eb));
      border-radius: 4px;
    }
  `;

  // Inject styles
  const styleSheet = document.createElement('style');
  styleSheet.textContent = styles;
  document.head.appendChild(styleSheet);

  // Export to global scope
  global.LoadingStates = LoadingStates;

})(window);
