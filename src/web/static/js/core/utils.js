/**
 * Shared Utility Functions
 * Used across: index.html, intelligent_advisor.html, cpa_dashboard.html, admin_dashboard.html
 *
 * Usage (ES Module):
 *   import { escapeHtml, formatCurrency, debounce } from '/static/js/core/utils.js';
 *
 * Usage (Global):
 *   window.TaxUtils.escapeHtml(str)
 */

// ============================================
// STRING UTILITIES
// ============================================

/**
 * Escape HTML to prevent XSS
 * @param {string} str - Raw string
 * @returns {string} - HTML-safe string
 */
export function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  if (typeof str !== 'string') str = String(str);
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Unescape HTML entities
 * @param {string} str - HTML-encoded string
 * @returns {string} - Decoded string
 */
export function unescapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.innerHTML = str;
  return div.textContent || div.innerText || '';
}

/**
 * Capitalize first letter
 * @param {string} str
 * @returns {string}
 */
export function capitalizeFirst(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1);
}

/**
 * Convert string to title case
 * @param {string} str
 * @returns {string}
 */
export function toTitleCase(str) {
  if (!str) return '';
  return str.toLowerCase().replace(/\b\w/g, (char) => char.toUpperCase());
}

/**
 * Get initials from name
 * @param {string} name
 * @returns {string}
 */
export function getInitials(name) {
  if (!name) return '??';
  return name
    .split(' ')
    .filter(Boolean)
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

/**
 * Truncate string with ellipsis
 * @param {string} str
 * @param {number} maxLength
 * @returns {string}
 */
export function truncate(str, maxLength = 50) {
  if (!str || str.length <= maxLength) return str || '';
  return str.slice(0, maxLength - 3) + '...';
}

/**
 * Generate a random ID
 * @param {number} length
 * @returns {string}
 */
export function generateId(length = 8) {
  return Math.random()
    .toString(36)
    .substring(2, 2 + length);
}

/**
 * Convert snake_case to Title Case
 * @param {string} str
 * @returns {string}
 */
export function snakeToTitle(str) {
  if (!str) return '';
  return str
    .split('_')
    .map((word) => capitalizeFirst(word))
    .join(' ');
}

// ============================================
// NUMBER FORMATTING
// ============================================

/**
 * Format as currency
 * @param {number} value
 * @param {string} currency - Currency code (default: USD)
 * @param {boolean} showCents - Show decimal places
 * @returns {string}
 */
export function formatCurrency(value, currency = 'USD', showCents = false) {
  if (value === null || value === undefined || isNaN(value)) return '$0';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: showCents ? 2 : 0,
    maximumFractionDigits: showCents ? 2 : 0,
  }).format(value);
}

/**
 * Format number with commas
 * @param {number} value
 * @returns {string}
 */
export function formatNumber(value) {
  if (value === null || value === undefined || isNaN(value)) return '0';
  return new Intl.NumberFormat('en-US').format(value);
}

/**
 * Format percentage
 * @param {number} value - Decimal value (0.15 = 15%)
 * @param {number} decimals
 * @returns {string}
 */
export function formatPercent(value, decimals = 1) {
  if (value === null || value === undefined || isNaN(value)) return '0%';
  return new Intl.NumberFormat('en-US', {
    style: 'percent',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/**
 * Parse currency string to number
 * @param {string} str - Currency string like "$1,234.56"
 * @returns {number}
 */
export function parseCurrency(str) {
  if (!str) return 0;
  const cleaned = str.replace(/[^0-9.-]/g, '');
  const parsed = parseFloat(cleaned);
  return isNaN(parsed) ? 0 : parsed;
}

/**
 * Round to specified decimal places
 * @param {number} value
 * @param {number} decimals
 * @returns {number}
 */
export function roundTo(value, decimals = 2) {
  const factor = Math.pow(10, decimals);
  return Math.round(value * factor) / factor;
}

// ============================================
// DATE & TIME FORMATTING
// ============================================

/**
 * Format date
 * @param {Date|string|number} date
 * @param {string} format - 'short', 'long', 'iso'
 * @returns {string}
 */
export function formatDate(date, format = 'short') {
  if (!date) return '';
  const d = new Date(date);
  if (isNaN(d.getTime())) return '';

  const options = {
    short: { month: 'short', day: 'numeric', year: 'numeric' },
    long: { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' },
    iso: undefined,
  };

  if (format === 'iso') {
    return d.toISOString().split('T')[0];
  }

  return d.toLocaleDateString('en-US', options[format] || options.short);
}

/**
 * Format relative time (e.g., "2 hours ago")
 * @param {Date|string|number} date
 * @returns {string}
 */
export function formatRelativeTime(date) {
  if (!date) return '';
  const now = new Date();
  const then = new Date(date);
  if (isNaN(then.getTime())) return '';

  const diffMs = now - then;
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  const diffWeeks = Math.floor(diffDays / 7);
  const diffMonths = Math.floor(diffDays / 30);

  if (diffSecs < 60) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffWeeks < 4) return `${diffWeeks}w ago`;
  if (diffMonths < 12) return `${diffMonths}mo ago`;

  return then.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

/**
 * Format time
 * @param {Date|string|number} date
 * @returns {string}
 */
export function formatTime(date) {
  if (!date) return '';
  const d = new Date(date);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

// ============================================
// FUNCTION UTILITIES
// ============================================

/**
 * Debounce function calls
 * @param {Function} func
 * @param {number} wait - Milliseconds
 * @returns {Function}
 */
export function debounce(func, wait = 300) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func.apply(this, args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

/**
 * Throttle function calls
 * @param {Function} func
 * @param {number} limit - Milliseconds
 * @returns {Function}
 */
export function throttle(func, limit = 300) {
  let inThrottle;
  return function (...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
}

/**
 * Sleep/delay promise
 * @param {number} ms - Milliseconds
 * @returns {Promise}
 */
export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Retry a function with exponential backoff
 * @param {Function} fn - Async function to retry
 * @param {number} maxRetries
 * @param {number} baseDelay - Base delay in ms
 * @returns {Promise}
 */
export async function retry(fn, maxRetries = 3, baseDelay = 1000) {
  let lastError;
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      if (i < maxRetries - 1) {
        await sleep(baseDelay * Math.pow(2, i));
      }
    }
  }
  throw lastError;
}

// ============================================
// OBJECT UTILITIES
// ============================================

/**
 * Deep clone an object
 * @param {any} obj
 * @returns {any}
 */
export function deepClone(obj) {
  if (obj === null || typeof obj !== 'object') return obj;
  if (obj instanceof Date) return new Date(obj);
  if (obj instanceof Array) return obj.map((item) => deepClone(item));
  if (obj instanceof Object) {
    return Object.fromEntries(Object.entries(obj).map(([key, val]) => [key, deepClone(val)]));
  }
  return obj;
}

/**
 * Check if object is empty
 * @param {Object} obj
 * @returns {boolean}
 */
export function isEmpty(obj) {
  if (obj === null || obj === undefined) return true;
  if (Array.isArray(obj)) return obj.length === 0;
  if (typeof obj === 'object') return Object.keys(obj).length === 0;
  if (typeof obj === 'string') return obj.trim().length === 0;
  return false;
}

/**
 * Get nested object value safely
 * @param {Object} obj
 * @param {string} path - Dot notation path (e.g., 'user.address.city')
 * @param {any} defaultValue
 * @returns {any}
 */
export function get(obj, path, defaultValue = undefined) {
  if (!obj || !path) return defaultValue;
  const keys = path.split('.');
  let result = obj;
  for (const key of keys) {
    if (result === null || result === undefined) return defaultValue;
    result = result[key];
  }
  return result !== undefined ? result : defaultValue;
}

// ============================================
// UI UTILITIES
// ============================================

/**
 * Show toast notification
 * @param {string} message
 * @param {string} type - 'success' | 'error' | 'warning' | 'info'
 * @param {number} duration - Milliseconds
 */
export function showToast(message, type = 'info', duration = 3000) {
  const container = document.getElementById('toast-container') || createToastContainer();

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${getToastIcon(type)}</span>
    <span class="toast-message">${escapeHtml(message)}</span>
    <button class="toast-close" onclick="this.parentElement.remove()">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M18 6L6 18M6 6l12 12"/>
      </svg>
    </button>
  `;

  container.appendChild(toast);

  // Trigger animation
  requestAnimationFrame(() => toast.classList.add('visible'));

  // Auto-remove
  if (duration > 0) {
    setTimeout(() => {
      toast.classList.remove('visible');
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  return toast;
}

function createToastContainer() {
  const container = document.createElement('div');
  container.id = 'toast-container';
  container.className = 'toast-container';
  document.body.appendChild(container);
  return container;
}

function getToastIcon(type) {
  const icons = {
    success:
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
    error:
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
    warning:
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    info: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
  };
  return icons[type] || icons.info;
}

/**
 * Show loading overlay
 * @param {boolean} show
 * @param {string} message
 */
export function showLoading(show, message = 'Loading...') {
  let overlay = document.getElementById('loading-overlay');

  if (show) {
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'loading-overlay';
      overlay.className = 'loading-overlay';
      overlay.innerHTML = `
        <div class="loading-spinner"></div>
        <p class="loading-message">${escapeHtml(message)}</p>
      `;
      document.body.appendChild(overlay);
    } else {
      const msgEl = overlay.querySelector('.loading-message');
      if (msgEl) msgEl.textContent = message;
    }
    requestAnimationFrame(() => overlay.classList.add('visible'));
  } else if (overlay) {
    overlay.classList.remove('visible');
    setTimeout(() => overlay.remove(), 300);
  }
}

/**
 * Copy text to clipboard
 * @param {string} text
 * @returns {Promise<boolean>}
 */
export async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (err) {
    // Fallback for older browsers
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand('copy');
      return true;
    } catch (e) {
      return false;
    } finally {
      document.body.removeChild(textarea);
    }
  }
}

/**
 * Scroll to element
 * @param {string|Element} target - Selector or element
 * @param {Object} options
 */
export function scrollTo(target, options = {}) {
  const element = typeof target === 'string' ? document.querySelector(target) : target;
  if (!element) return;

  const { offset = 0, behavior = 'smooth' } = options;
  const top = element.getBoundingClientRect().top + window.pageYOffset - offset;

  window.scrollTo({ top, behavior });
}

// ============================================
// VALIDATION UTILITIES
// ============================================

/**
 * Validate email format
 * @param {string} email
 * @returns {boolean}
 */
export function isValidEmail(email) {
  if (!email) return false;
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
}

/**
 * Validate phone number (US format)
 * @param {string} phone
 * @returns {boolean}
 */
export function isValidPhone(phone) {
  if (!phone) return false;
  const cleaned = phone.replace(/\D/g, '');
  return cleaned.length === 10 || (cleaned.length === 11 && cleaned[0] === '1');
}

/**
 * Validate SSN format
 * @param {string} ssn
 * @returns {boolean}
 */
export function isValidSSN(ssn) {
  if (!ssn) return false;
  const cleaned = ssn.replace(/\D/g, '');
  return cleaned.length === 9;
}

/**
 * Validate EIN format
 * @param {string} ein
 * @returns {boolean}
 */
export function isValidEIN(ein) {
  if (!ein) return false;
  const cleaned = ein.replace(/\D/g, '');
  return cleaned.length === 9;
}

/**
 * Format phone number
 * @param {string} phone
 * @returns {string}
 */
export function formatPhone(phone) {
  if (!phone) return '';
  const cleaned = phone.replace(/\D/g, '');
  if (cleaned.length === 10) {
    return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6)}`;
  }
  if (cleaned.length === 11 && cleaned[0] === '1') {
    return `+1 (${cleaned.slice(1, 4)}) ${cleaned.slice(4, 7)}-${cleaned.slice(7)}`;
  }
  return phone;
}

/**
 * Format SSN (masked)
 * @param {string} ssn
 * @param {boolean} mask - Whether to mask the first 5 digits
 * @returns {string}
 */
export function formatSSN(ssn, mask = true) {
  if (!ssn) return '';
  const cleaned = ssn.replace(/\D/g, '');
  if (cleaned.length !== 9) return ssn;
  if (mask) {
    return `***-**-${cleaned.slice(5)}`;
  }
  return `${cleaned.slice(0, 3)}-${cleaned.slice(3, 5)}-${cleaned.slice(5)}`;
}

// ============================================
// STORAGE UTILITIES
// ============================================

/**
 * Safe localStorage get
 * @param {string} key
 * @param {any} defaultValue
 * @returns {any}
 */
export function storageGet(key, defaultValue = null) {
  try {
    const item = localStorage.getItem(key);
    return item ? JSON.parse(item) : defaultValue;
  } catch {
    return defaultValue;
  }
}

/**
 * Safe localStorage set
 * @param {string} key
 * @param {any} value
 */
export function storageSet(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    console.warn('localStorage not available:', e);
  }
}

/**
 * Safe localStorage remove
 * @param {string} key
 */
export function storageRemove(key) {
  try {
    localStorage.removeItem(key);
  } catch {
    // Ignore
  }
}

// ============================================
// URL UTILITIES
// ============================================

/**
 * Get URL query parameters
 * @param {string} url - Optional URL (defaults to current)
 * @returns {Object}
 */
export function getQueryParams(url = window.location.href) {
  const params = {};
  const searchParams = new URL(url).searchParams;
  searchParams.forEach((value, key) => {
    params[key] = value;
  });
  return params;
}

/**
 * Build URL with query parameters
 * @param {string} baseUrl
 * @param {Object} params
 * @returns {string}
 */
export function buildUrl(baseUrl, params = {}) {
  const url = new URL(baseUrl, window.location.origin);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      url.searchParams.set(key, value);
    }
  });
  return url.toString();
}

// ============================================
// EXPORT AS GLOBAL (for non-module usage)
// ============================================

if (typeof window !== 'undefined') {
  window.TaxUtils = {
    // String
    escapeHtml,
    unescapeHtml,
    capitalizeFirst,
    toTitleCase,
    getInitials,
    truncate,
    generateId,
    snakeToTitle,
    // Number
    formatCurrency,
    formatNumber,
    formatPercent,
    parseCurrency,
    roundTo,
    // Date
    formatDate,
    formatRelativeTime,
    formatTime,
    // Function
    debounce,
    throttle,
    sleep,
    retry,
    // Object
    deepClone,
    isEmpty,
    get,
    // UI
    showToast,
    showLoading,
    copyToClipboard,
    scrollTo,
    // Validation
    isValidEmail,
    isValidPhone,
    isValidSSN,
    isValidEIN,
    formatPhone,
    formatSSN,
    // Storage
    storageGet,
    storageSet,
    storageRemove,
    // URL
    getQueryParams,
    buildUrl,
  };
}
