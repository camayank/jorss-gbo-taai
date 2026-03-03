/**
 * Shared toast notification component.
 *
 * Usage:
 *   <script src="/static/js/toast.js"></script>
 *   showToast('Saved successfully', 'success');
 *
 * Supports types: 'info' (default), 'success', 'warning', 'error'.
 */
(function () {
  'use strict';

  // Ensure a toast container exists
  function getContainer() {
    var container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.style.cssText =
        'position:fixed;bottom:20px;right:20px;z-index:10000;display:flex;flex-direction:column;gap:8px;max-width:400px;';
      document.body.appendChild(container);
    }
    return container;
  }

  var colors = {
    error: 'var(--color-error-500, #ef4444)',
    success: 'var(--color-success-500, #22c55e)',
    warning: 'var(--color-warning-500, #f59e0b)',
    info: 'var(--color-info-500, #3b82f6)',
  };

  function showToast(message, type) {
    type = type || 'info';
    var container = getContainer();
    var toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
    toast.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite');
    toast.textContent = message;
    toast.style.cssText =
      'padding:12px 24px;border-radius:8px;color:#fff;font-weight:500;' +
      'animation:toastSlideIn 0.3s ease;transition:opacity 0.3s;' +
      'background:' + (colors[type] || colors.info) + ';';
    container.appendChild(toast);

    setTimeout(function () {
      toast.style.opacity = '0';
      setTimeout(function () { toast.remove(); }, 300);
    }, 4000);
  }

  // Inject keyframes once
  if (!document.getElementById('toast-keyframes')) {
    var style = document.createElement('style');
    style.id = 'toast-keyframes';
    style.textContent = '@keyframes toastSlideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}';
    document.head.appendChild(style);
  }

  // Expose globally
  window.showToast = showToast;
})();
