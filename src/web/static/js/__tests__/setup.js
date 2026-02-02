/**
 * Test Setup File
 *
 * This file runs before each test file and sets up the testing environment.
 */

import { vi } from 'vitest';

// Mock fetch globally
global.fetch = vi.fn();

// Mock document.cookie
Object.defineProperty(document, 'cookie', {
  writable: true,
  value: '',
});

// Reset all mocks before each test
beforeEach(() => {
  vi.clearAllMocks();
  document.cookie = '';
  document.head.innerHTML = '';
  document.body.innerHTML = '';
});

// Cleanup after each test
afterEach(() => {
  vi.restoreAllMocks();
});

/**
 * Helper to create a mock Response object
 */
global.createMockResponse = (data, options = {}) => {
  const {
    status = 200,
    statusText = 'OK',
    headers = {},
    contentType = 'application/json',
  } = options;

  const responseHeaders = new Headers({
    'content-type': contentType,
    ...headers,
  });

  return {
    ok: status >= 200 && status < 300,
    status,
    statusText,
    headers: responseHeaders,
    json: vi.fn().mockResolvedValue(data),
    text: vi.fn().mockResolvedValue(typeof data === 'string' ? data : JSON.stringify(data)),
    blob: vi.fn().mockResolvedValue(new Blob([JSON.stringify(data)])),
  };
};

/**
 * Helper to set up CSRF token in meta tag
 */
global.setCsrfMetaTag = (token) => {
  const meta = document.createElement('meta');
  meta.name = 'csrf-token';
  meta.content = token;
  document.head.appendChild(meta);
};

/**
 * Helper to set up CSRF token in cookie
 */
global.setCsrfCookie = (token) => {
  document.cookie = `csrf_token=${encodeURIComponent(token)}`;
};
