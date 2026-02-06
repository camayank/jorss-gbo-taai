/**
 * Confirmation Dialog Module
 * Accessible confirmation dialogs for destructive actions.
 *
 * Usage:
 *   import { confirm, confirmDelete, confirmReset } from '/static/js/core/confirm-dialog.js';
 *
 *   // Basic confirmation
 *   const confirmed = await confirm({
 *     title: 'Delete Return?',
 *     message: 'This action cannot be undone.',
 *     confirmText: 'Delete',
 *     type: 'danger'
 *   });
 *
 *   // Quick delete confirmation
 *   if (await confirmDelete('tax return')) {
 *     await deleteReturn(id);
 *   }
 */

(function(global) {
  'use strict';

  // Dialog types with their styles
  const DIALOG_TYPES = {
    danger: {
      icon: '⚠️',
      iconClass: 'confirm-icon--danger',
      buttonClass: 'btn--danger',
    },
    warning: {
      icon: '⚠️',
      iconClass: 'confirm-icon--warning',
      buttonClass: 'btn--warning',
    },
    info: {
      icon: 'ℹ️',
      iconClass: 'confirm-icon--info',
      buttonClass: 'btn--primary',
    },
  };

  /**
   * Show a confirmation dialog
   * @param {Object} options - Dialog options
   * @param {string} options.title - Dialog title
   * @param {string} options.message - Dialog message
   * @param {string} options.confirmText - Confirm button text (default: 'Confirm')
   * @param {string} options.cancelText - Cancel button text (default: 'Cancel')
   * @param {string} options.type - Dialog type: 'danger', 'warning', 'info' (default: 'danger')
   * @param {boolean} options.requireConfirmation - Require typing to confirm (for critical actions)
   * @param {string} options.confirmationText - Text user must type to confirm
   * @returns {Promise<boolean>} True if confirmed, false if cancelled
   */
  function confirm(options = {}) {
    const {
      title = 'Are you sure?',
      message = 'This action cannot be undone.',
      confirmText = 'Confirm',
      cancelText = 'Cancel',
      type = 'danger',
      requireConfirmation = false,
      confirmationText = 'DELETE',
    } = options;

    const typeConfig = DIALOG_TYPES[type] || DIALOG_TYPES.danger;

    return new Promise((resolve) => {
      // Create overlay
      const overlay = document.createElement('div');
      overlay.className = 'confirm-overlay';
      overlay.setAttribute('role', 'presentation');

      // Create dialog
      const dialog = document.createElement('div');
      dialog.className = 'confirm-dialog';
      dialog.setAttribute('role', 'alertdialog');
      dialog.setAttribute('aria-modal', 'true');
      dialog.setAttribute('aria-labelledby', 'confirm-title');
      dialog.setAttribute('aria-describedby', 'confirm-message');

      dialog.innerHTML = `
        <div class="confirm-content">
          <div class="confirm-header">
            <span class="confirm-icon ${typeConfig.iconClass}" aria-hidden="true">${typeConfig.icon}</span>
            <h2 id="confirm-title" class="confirm-title">${escapeHtml(title)}</h2>
          </div>
          <p id="confirm-message" class="confirm-message">${escapeHtml(message)}</p>
          ${requireConfirmation ? `
            <div class="confirm-input-wrapper">
              <label for="confirm-input" class="confirm-input-label">
                Type <strong>${escapeHtml(confirmationText)}</strong> to confirm:
              </label>
              <input
                type="text"
                id="confirm-input"
                class="confirm-input"
                autocomplete="off"
                spellcheck="false"
              />
            </div>
          ` : ''}
          <div class="confirm-actions">
            <button type="button" class="btn btn--secondary confirm-cancel">
              ${escapeHtml(cancelText)}
            </button>
            <button type="button" class="btn ${typeConfig.buttonClass} confirm-submit" ${requireConfirmation ? 'disabled' : ''}>
              ${escapeHtml(confirmText)}
            </button>
          </div>
        </div>
      `;

      overlay.appendChild(dialog);
      document.body.appendChild(overlay);

      // Get elements
      const cancelBtn = dialog.querySelector('.confirm-cancel');
      const submitBtn = dialog.querySelector('.confirm-submit');
      const confirmInput = dialog.querySelector('.confirm-input');

      // Focus management
      const focusableElements = dialog.querySelectorAll('button, input');
      const firstFocusable = focusableElements[0];
      const lastFocusable = focusableElements[focusableElements.length - 1];

      // Store previous focus
      const previousFocus = document.activeElement;

      // Focus first element
      setTimeout(() => {
        if (confirmInput) {
          confirmInput.focus();
        } else {
          cancelBtn.focus();
        }
      }, 10);

      // Handle confirmation input
      if (confirmInput) {
        confirmInput.addEventListener('input', () => {
          submitBtn.disabled = confirmInput.value !== confirmationText;
        });

        confirmInput.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' && confirmInput.value === confirmationText) {
            cleanup(true);
          }
        });
      }

      // Cleanup function
      function cleanup(confirmed) {
        overlay.classList.add('confirm-overlay--closing');
        dialog.classList.add('confirm-dialog--closing');

        setTimeout(() => {
          document.body.removeChild(overlay);
          if (previousFocus) {
            previousFocus.focus();
          }
          resolve(confirmed);
        }, 150);
      }

      // Event handlers
      cancelBtn.addEventListener('click', () => cleanup(false));
      submitBtn.addEventListener('click', () => cleanup(true));

      // Close on overlay click
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
          cleanup(false);
        }
      });

      // Keyboard handling
      dialog.addEventListener('keydown', (e) => {
        // Close on Escape
        if (e.key === 'Escape') {
          e.preventDefault();
          cleanup(false);
        }

        // Trap focus
        if (e.key === 'Tab') {
          if (e.shiftKey && document.activeElement === firstFocusable) {
            e.preventDefault();
            lastFocusable.focus();
          } else if (!e.shiftKey && document.activeElement === lastFocusable) {
            e.preventDefault();
            firstFocusable.focus();
          }
        }
      });

      // Prevent body scroll
      document.body.style.overflow = 'hidden';
      overlay.addEventListener('transitionend', () => {
        if (overlay.classList.contains('confirm-overlay--closing')) {
          document.body.style.overflow = '';
        }
      }, { once: true });

      // Animate in
      requestAnimationFrame(() => {
        overlay.classList.add('confirm-overlay--visible');
        dialog.classList.add('confirm-dialog--visible');
      });
    });
  }

  /**
   * Quick confirmation for delete actions
   * @param {string} itemName - Name of item being deleted
   * @param {Object} options - Additional options
   * @returns {Promise<boolean>}
   */
  function confirmDelete(itemName, options = {}) {
    return confirm({
      title: `Delete ${itemName}?`,
      message: `Are you sure you want to delete this ${itemName.toLowerCase()}? This action cannot be undone.`,
      confirmText: 'Delete',
      cancelText: 'Cancel',
      type: 'danger',
      ...options,
    });
  }

  /**
   * Quick confirmation for reset/clear actions
   * @param {string} itemName - Name of item being reset
   * @param {Object} options - Additional options
   * @returns {Promise<boolean>}
   */
  function confirmReset(itemName, options = {}) {
    return confirm({
      title: `Reset ${itemName}?`,
      message: `Are you sure you want to reset this ${itemName.toLowerCase()}? All changes will be lost.`,
      confirmText: 'Reset',
      cancelText: 'Keep Changes',
      type: 'warning',
      ...options,
    });
  }

  /**
   * Confirmation for submitting/filing actions
   * @param {string} actionName - Name of the action
   * @param {Object} options - Additional options
   * @returns {Promise<boolean>}
   */
  function confirmSubmit(actionName, options = {}) {
    return confirm({
      title: `Submit ${actionName}?`,
      message: `Please review your information carefully. Once submitted, changes may require additional steps to modify.`,
      confirmText: 'Submit',
      cancelText: 'Review Again',
      type: 'info',
      ...options,
    });
  }

  /**
   * Critical action confirmation (requires typing)
   * @param {string} actionName - Name of the action
   * @param {Object} options - Additional options
   * @returns {Promise<boolean>}
   */
  function confirmCritical(actionName, options = {}) {
    return confirm({
      title: `Confirm ${actionName}`,
      message: `This is a critical action that cannot be undone. Please type the confirmation text to proceed.`,
      confirmText: actionName,
      cancelText: 'Cancel',
      type: 'danger',
      requireConfirmation: true,
      confirmationText: options.confirmationText || actionName.toUpperCase().replace(/\s+/g, ''),
      ...options,
    });
  }

  /**
   * Escape HTML entities
   * @param {string} text
   * @returns {string}
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Inject CSS styles
  const styles = `
    .confirm-overlay {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10000;
      padding: 20px;
      transition: background 0.15s ease;
    }

    .confirm-overlay--visible {
      background: rgba(0, 0, 0, 0.5);
    }

    .confirm-overlay--closing {
      background: rgba(0, 0, 0, 0);
    }

    .confirm-dialog {
      background: var(--bg-surface, white);
      border-radius: var(--radius-lg, 12px);
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
      max-width: 420px;
      width: 100%;
      opacity: 0;
      transform: scale(0.95) translateY(-10px);
      transition: opacity 0.15s ease, transform 0.15s ease;
    }

    .confirm-dialog--visible {
      opacity: 1;
      transform: scale(1) translateY(0);
    }

    .confirm-dialog--closing {
      opacity: 0;
      transform: scale(0.95) translateY(-10px);
    }

    .confirm-content {
      padding: 24px;
    }

    .confirm-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
    }

    .confirm-icon {
      font-size: 24px;
      flex-shrink: 0;
    }

    .confirm-icon--danger {
      color: var(--color-error-500, #ef4444);
    }

    .confirm-icon--warning {
      color: var(--color-warning-500, #f59e0b);
    }

    .confirm-icon--info {
      color: var(--color-primary-500, #1e3a5f);
    }

    .confirm-title {
      font-size: 18px;
      font-weight: 600;
      color: var(--text-primary, #111827);
      margin: 0;
    }

    .confirm-message {
      font-size: 14px;
      color: var(--text-secondary, #6b7280);
      line-height: 1.5;
      margin: 0 0 20px;
    }

    .confirm-input-wrapper {
      margin-bottom: 20px;
    }

    .confirm-input-label {
      display: block;
      font-size: 14px;
      color: var(--text-secondary, #6b7280);
      margin-bottom: 8px;
    }

    .confirm-input-label strong {
      color: var(--color-error-500, #ef4444);
      font-family: monospace;
    }

    .confirm-input {
      width: 100%;
      padding: 10px 12px;
      border: 1px solid var(--border-color, #e5e7eb);
      border-radius: var(--radius-md, 6px);
      font-size: 14px;
      font-family: monospace;
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }

    .confirm-input:focus {
      outline: none;
      border-color: var(--color-primary-500, #1e3a5f);
      box-shadow: 0 0 0 3px rgba(30, 58, 95, 0.15);
    }

    .confirm-actions {
      display: flex;
      justify-content: flex-end;
      gap: 12px;
    }

    .confirm-actions .btn {
      padding: 10px 20px;
      font-size: 14px;
      font-weight: 500;
      border-radius: var(--radius-md, 6px);
      cursor: pointer;
      transition: all 0.15s ease;
    }

    .confirm-actions .btn--secondary {
      background: var(--bg-surface, white);
      border: 1px solid var(--border-color, #e5e7eb);
      color: var(--text-primary, #111827);
    }

    .confirm-actions .btn--secondary:hover {
      background: var(--bg-muted, #f9fafb);
    }

    .confirm-actions .btn--danger {
      background: var(--color-error-500, #ef4444);
      border: 1px solid var(--color-error-500, #ef4444);
      color: white;
    }

    .confirm-actions .btn--danger:hover:not(:disabled) {
      background: var(--color-error-600, #dc2626);
    }

    .confirm-actions .btn--warning {
      background: var(--color-warning-500, #f59e0b);
      border: 1px solid var(--color-warning-500, #f59e0b);
      color: white;
    }

    .confirm-actions .btn--warning:hover:not(:disabled) {
      background: var(--color-warning-600, #d97706);
    }

    .confirm-actions .btn--primary {
      background: var(--color-primary-500, #1e3a5f);
      border: 1px solid var(--color-primary-500, #1e3a5f);
      color: white;
    }

    .confirm-actions .btn--primary:hover:not(:disabled) {
      background: var(--color-primary-600, #162d4a);
    }

    .confirm-actions .btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    .confirm-actions .btn:focus-visible {
      outline: 2px solid var(--color-primary-500, #1e3a5f);
      outline-offset: 2px;
    }

    /* Reduced motion */
    @media (prefers-reduced-motion: reduce) {
      .confirm-overlay,
      .confirm-dialog {
        transition: none;
      }
    }
  `;

  // Inject styles
  const styleSheet = document.createElement('style');
  styleSheet.textContent = styles;
  document.head.appendChild(styleSheet);

  // Export to global scope
  global.ConfirmDialog = {
    confirm,
    confirmDelete,
    confirmReset,
    confirmSubmit,
    confirmCritical,
  };

  // Also export individual functions
  global.confirm = confirm;
  global.confirmDelete = confirmDelete;
  global.confirmReset = confirmReset;
  global.confirmSubmit = confirmSubmit;
  global.confirmCritical = confirmCritical;

})(window);
