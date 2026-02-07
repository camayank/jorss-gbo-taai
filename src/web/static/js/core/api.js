/**
 * API Client Module
 * Unified fetch wrapper with error handling, CSRF support, and retry logic.
 *
 * Usage:
 *   import { api, get, post, put, del } from '/static/js/core/api.js';
 *
 *   // Simple calls
 *   const data = await get('/api/users');
 *   const result = await post('/api/users', { name: 'John' });
 *
 *   // With options
 *   const data = await api.get('/api/users', { cache: true });
 */

// ============================================
// CONFIGURATION
// ============================================

const DEFAULT_CONFIG = {
  baseUrl: '',
  timeout: 30000,
  retries: 0,
  retryDelay: 1000,
  headers: {
    'Content-Type': 'application/json',
  },
};

let config = { ...DEFAULT_CONFIG };

/**
 * Configure API defaults
 * @param {Object} options
 */
export function configure(options) {
  config = { ...config, ...options };
}

// ============================================
// CSRF TOKEN HANDLING
// ============================================

let csrfToken = null;

/**
 * Get CSRF token from meta tag or cookie
 * @returns {string|null}
 */
export function getCsrfToken() {
  if (csrfToken) return csrfToken;

  // Try meta tag first
  const metaTag = document.querySelector('meta[name="csrf-token"]');
  if (metaTag) {
    csrfToken = metaTag.getAttribute('content');
    return csrfToken;
  }

  // Try cookie
  const cookies = document.cookie.split(';');
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split('=');
    if (name === 'csrf_token' || name === '_csrf') {
      csrfToken = decodeURIComponent(value);
      return csrfToken;
    }
  }

  return null;
}

/**
 * Set CSRF token manually
 * @param {string} token
 */
export function setCsrfToken(token) {
  csrfToken = token;
}

// ============================================
// ERROR CLASSES
// ============================================

export class ApiError extends Error {
  constructor(message, status, data = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

export class NetworkError extends Error {
  constructor(message) {
    super(message);
    this.name = 'NetworkError';
  }
}

export class TimeoutError extends Error {
  constructor(message = 'Request timed out') {
    super(message);
    this.name = 'TimeoutError';
  }
}

// ============================================
// CORE FETCH WRAPPER
// ============================================

/**
 * Make an API request
 * @param {string} url
 * @param {Object} options
 * @returns {Promise<any>}
 */
async function request(url, options = {}) {
  const {
    method = 'GET',
    body,
    headers = {},
    timeout = config.timeout,
    retries = config.retries,
    retryDelay = config.retryDelay,
    raw = false, // Return raw response instead of JSON
    skipCsrf = false,
    // Loading state options
    loadingContainer = null, // Selector or element to show loading state
    loadingMessage = 'Loading...', // Message for screen readers
    showSkeleton = false, // Use skeleton loading instead of spinner
  } = options;

  // Start loading state if container provided
  let loadingId = null;
  if (loadingContainer && typeof window.LoadingStates !== 'undefined') {
    loadingId = window.LoadingStates.start(loadingContainer, {
      message: loadingMessage,
      showSkeleton: showSkeleton,
      timeout: timeout,
    });
  }

  // Build full URL
  const fullUrl = url.startsWith('http') ? url : `${config.baseUrl}${url}`;

  // Build headers
  const requestHeaders = {
    ...config.headers,
    ...headers,
  };

  // Add CSRF token for state-changing requests
  if (!skipCsrf && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method.toUpperCase())) {
    const token = getCsrfToken();
    if (token) {
      requestHeaders['X-CSRF-Token'] = token;
    }
  }

  // Build request options
  const requestOptions = {
    method: method.toUpperCase(),
    headers: requestHeaders,
    credentials: 'same-origin', // Include cookies
  };

  // Add body for non-GET requests
  if (body && method.toUpperCase() !== 'GET') {
    if (body instanceof FormData) {
      // Let browser set Content-Type for FormData (includes boundary)
      delete requestHeaders['Content-Type'];
      requestOptions.body = body;
    } else if (typeof body === 'object') {
      requestOptions.body = JSON.stringify(body);
    } else {
      requestOptions.body = body;
    }
  }

  // Create abort controller for timeout
  const controller = new AbortController();
  requestOptions.signal = controller.signal;

  const timeoutId = setTimeout(() => controller.abort(), timeout);

  // Retry logic
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetch(fullUrl, requestOptions);
      clearTimeout(timeoutId);

      // Handle non-OK responses
      if (!response.ok) {
        let errorData = null;
        try {
          errorData = await response.json();
        } catch {
          // Response is not JSON
        }

        const errorMessage = errorData?.message || errorData?.error || response.statusText;

        // Show error in loading state if active
        if (loadingId && typeof window.LoadingStates !== 'undefined') {
          window.LoadingStates.showError(loadingId, errorMessage, {
            allowRetry: false,
          });
        }

        throw new ApiError(errorMessage, response.status, errorData);
      }

      // End loading state on success
      if (loadingId && typeof window.LoadingStates !== 'undefined') {
        window.LoadingStates.end(loadingId, { message: 'Complete' });
      }

      // Return raw response if requested
      if (raw) {
        return response;
      }

      // Handle empty responses
      const contentType = response.headers.get('content-type');
      if (!contentType || response.status === 204) {
        return null;
      }

      // Parse JSON response
      if (contentType.includes('application/json')) {
        return await response.json();
      }

      // Return text for other content types
      return await response.text();
    } catch (error) {
      clearTimeout(timeoutId);
      lastError = error;

      // Don't retry on client errors (4xx) or if it's an abort
      if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
        // Loading state already handled in response.ok check
        throw error;
      }

      if (error.name === 'AbortError') {
        // Show timeout in loading state
        if (loadingId && typeof window.LoadingStates !== 'undefined') {
          window.LoadingStates.showError(loadingId, 'Request timed out', {
            allowRetry: true,
          });
        }
        throw new TimeoutError();
      }

      // Retry on network errors or server errors
      if (attempt < retries) {
        await new Promise((resolve) => setTimeout(resolve, retryDelay * Math.pow(2, attempt)));
        continue;
      }

      // Show error in loading state for final failure
      if (loadingId && typeof window.LoadingStates !== 'undefined') {
        window.LoadingStates.showError(loadingId, error.message || 'Request failed', {
          allowRetry: true,
        });
      }

      if (error instanceof ApiError || error instanceof TimeoutError) {
        throw error;
      }

      throw new NetworkError(error.message || 'Network request failed');
    }
  }

  // End loading state for final error
  if (loadingId && typeof window.LoadingStates !== 'undefined') {
    window.LoadingStates.showError(loadingId, lastError?.message || 'Request failed', {
      allowRetry: true,
    });
  }

  throw lastError;
}

// ============================================
// HTTP METHOD SHORTCUTS
// ============================================

/**
 * GET request
 * @param {string} url
 * @param {Object} options
 * @returns {Promise<any>}
 */
export async function get(url, options = {}) {
  return request(url, { ...options, method: 'GET' });
}

/**
 * POST request
 * @param {string} url
 * @param {any} body
 * @param {Object} options
 * @returns {Promise<any>}
 */
export async function post(url, body, options = {}) {
  return request(url, { ...options, method: 'POST', body });
}

/**
 * PUT request
 * @param {string} url
 * @param {any} body
 * @param {Object} options
 * @returns {Promise<any>}
 */
export async function put(url, body, options = {}) {
  return request(url, { ...options, method: 'PUT', body });
}

/**
 * PATCH request
 * @param {string} url
 * @param {any} body
 * @param {Object} options
 * @returns {Promise<any>}
 */
export async function patch(url, body, options = {}) {
  return request(url, { ...options, method: 'PATCH', body });
}

/**
 * DELETE request
 * @param {string} url
 * @param {Object} options
 * @returns {Promise<any>}
 */
export async function del(url, options = {}) {
  return request(url, { ...options, method: 'DELETE' });
}

// ============================================
// SPECIALIZED REQUESTS
// ============================================

/**
 * Upload file(s)
 * @param {string} url
 * @param {File|File[]|FormData} files
 * @param {Object} additionalData
 * @param {Object} options
 * @returns {Promise<any>}
 */
export async function upload(url, files, additionalData = {}, options = {}) {
  let formData;

  if (files instanceof FormData) {
    formData = files;
  } else {
    formData = new FormData();

    // Handle single file or array of files
    const fileList = Array.isArray(files) ? files : [files];
    fileList.forEach((file, index) => {
      formData.append(fileList.length > 1 ? `file_${index}` : 'file', file);
    });

    // Add additional data
    Object.entries(additionalData).forEach(([key, value]) => {
      formData.append(key, typeof value === 'object' ? JSON.stringify(value) : value);
    });
  }

  return post(url, formData, options);
}

/**
 * Download file
 * @param {string} url
 * @param {string} filename
 * @param {Object} options
 * @returns {Promise<void>}
 */
export async function download(url, filename, options = {}) {
  const response = await request(url, { ...options, raw: true });
  const blob = await response.blob();

  // Create download link
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename || getFilenameFromResponse(response) || 'download';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
}

function getFilenameFromResponse(response) {
  const contentDisposition = response.headers.get('content-disposition');
  if (contentDisposition) {
    const match = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
    if (match) {
      return match[1].replace(/['"]/g, '');
    }
  }
  return null;
}

// ============================================
// CACHED REQUESTS
// ============================================

const cache = new Map();

/**
 * GET request with caching
 * @param {string} url
 * @param {Object} options
 * @returns {Promise<any>}
 */
export async function getCached(url, options = {}) {
  const { ttl = 60000, forceRefresh = false } = options;
  const cacheKey = url;

  // Check cache
  if (!forceRefresh && cache.has(cacheKey)) {
    const cached = cache.get(cacheKey);
    if (Date.now() - cached.timestamp < ttl) {
      return cached.data;
    }
  }

  // Fetch fresh data
  const data = await get(url, options);

  // Store in cache
  cache.set(cacheKey, {
    data,
    timestamp: Date.now(),
  });

  return data;
}

/**
 * Clear cache
 * @param {string} urlPattern - Optional URL pattern to clear
 */
export function clearCache(urlPattern) {
  if (urlPattern) {
    for (const key of cache.keys()) {
      if (key.includes(urlPattern)) {
        cache.delete(key);
      }
    }
  } else {
    cache.clear();
  }
}

// ============================================
// BUTTON LOADING HELPERS
// ============================================

/**
 * Disable button and show loading state during async operation
 * @param {HTMLButtonElement|string} button - Button element or selector
 * @param {Function} asyncFn - Async function to execute
 * @param {Object} options - Options
 * @returns {Promise<any>} Result of asyncFn
 */
export async function withButtonLoading(button, asyncFn, options = {}) {
  const btn = typeof button === 'string'
    ? document.querySelector(button)
    : button;

  if (!btn) {
    return asyncFn();
  }

  const {
    loadingText = 'Processing...',
    successText = null, // If set, shows success state briefly
    errorText = 'Error',
    successDuration = 1500,
  } = options;

  const originalText = btn.innerHTML;
  const originalDisabled = btn.disabled;

  // Show loading state
  btn.disabled = true;
  btn.setAttribute('aria-busy', 'true');
  btn.innerHTML = `
    <span class="btn-spinner" aria-hidden="true">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83">
          <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="1s" repeatCount="indefinite"/>
        </path>
      </svg>
    </span>
    <span class="btn-text">${loadingText}</span>
  `;

  try {
    const result = await asyncFn();

    // Show success state if configured
    if (successText) {
      btn.innerHTML = `<span class="btn-text">${successText}</span>`;
      btn.classList.add('btn-success');
      await new Promise(resolve => setTimeout(resolve, successDuration));
      btn.classList.remove('btn-success');
    }

    return result;
  } catch (error) {
    // Brief error indication
    btn.innerHTML = `<span class="btn-text">${errorText}</span>`;
    btn.classList.add('btn-error');
    await new Promise(resolve => setTimeout(resolve, 1000));
    btn.classList.remove('btn-error');
    throw error;
  } finally {
    // Restore original state
    btn.disabled = originalDisabled;
    btn.setAttribute('aria-busy', 'false');
    btn.innerHTML = originalText;
  }
}

/**
 * Create a submit handler with automatic loading state
 * @param {HTMLFormElement|string} form - Form element or selector
 * @param {Function} submitFn - Async submit handler (receives FormData)
 * @param {Object} options - Options
 * @returns {Function} Event handler
 */
export function createSubmitHandler(form, submitFn, options = {}) {
  const formEl = typeof form === 'string'
    ? document.querySelector(form)
    : form;

  if (!formEl) {
    console.warn('Form not found for submit handler');
    return () => {};
  }

  const {
    submitButton = formEl.querySelector('button[type="submit"], input[type="submit"]'),
    validateFn = null,
    onSuccess = null,
    onError = null,
    preventDoubleSubmit = true,
  } = options;

  let isSubmitting = false;

  return async function handleSubmit(event) {
    event.preventDefault();

    // Prevent double submission
    if (preventDoubleSubmit && isSubmitting) {
      return;
    }

    // Validate if validator provided
    if (validateFn && !validateFn(formEl)) {
      return;
    }

    isSubmitting = true;
    const formData = new FormData(formEl);

    try {
      const result = await withButtonLoading(
        submitButton,
        () => submitFn(formData, formEl),
        options
      );

      if (onSuccess) {
        onSuccess(result);
      }

      return result;
    } catch (error) {
      if (onError) {
        onError(error);
      }
      throw error;
    } finally {
      isSubmitting = false;
    }
  };
}

// ============================================
// API OBJECT (updated with loading helpers)
// ============================================

export const api = {
  configure,
  setCsrfToken,
  request,
  get,
  post,
  put,
  patch,
  delete: del,
  upload,
  download,
  getCached,
  clearCache,
  withButtonLoading,
  createSubmitHandler,
  ApiError,
  NetworkError,
  TimeoutError,
};

// ============================================
// EXPORT AS GLOBAL (for non-module usage)
// ============================================

if (typeof window !== 'undefined') {
  window.TaxApi = api;
}

export default api;
