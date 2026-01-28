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
function getCsrfToken() {
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
  } = options;

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
        throw new ApiError(errorMessage, response.status, errorData);
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
        throw error;
      }

      if (error.name === 'AbortError') {
        throw new TimeoutError();
      }

      // Retry on network errors or server errors
      if (attempt < retries) {
        await new Promise((resolve) => setTimeout(resolve, retryDelay * Math.pow(2, attempt)));
        continue;
      }

      if (error instanceof ApiError || error instanceof TimeoutError) {
        throw error;
      }

      throw new NetworkError(error.message || 'Network request failed');
    }
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
// API OBJECT (for namespaced usage)
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
