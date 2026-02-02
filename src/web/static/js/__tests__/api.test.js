/**
 * API Client Tests
 *
 * Tests for the core API module including:
 * - HTTP method wrappers (get, post, put, patch, delete)
 * - CSRF token handling
 * - Error handling (ApiError, NetworkError, TimeoutError)
 * - Caching functionality
 * - File upload/download
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  api,
  get,
  post,
  put,
  patch,
  del,
  upload,
  getCached,
  clearCache,
  configure,
  setCsrfToken,
  ApiError,
  NetworkError,
  TimeoutError,
} from '../core/api.js';

describe('API Client', () => {
  beforeEach(() => {
    // Reset configuration
    configure({
      baseUrl: '',
      timeout: 30000,
      retries: 0,
    });
    clearCache();
  });

  describe('CSRF Token Handling', () => {
    it('should get CSRF token from meta tag', async () => {
      setCsrfMetaTag('test-csrf-token-meta');
      fetch.mockResolvedValueOnce(createMockResponse({ success: true }));

      await post('/api/test', { data: 'value' });

      expect(fetch).toHaveBeenCalledWith(
        '/api/test',
        expect.objectContaining({
          headers: expect.objectContaining({
            'X-CSRF-Token': 'test-csrf-token-meta',
          }),
        })
      );
    });

    it('should get CSRF token from cookie if meta tag not present', async () => {
      setCsrfCookie('test-csrf-token-cookie');
      fetch.mockResolvedValueOnce(createMockResponse({ success: true }));

      // Need to reset the cached token first
      setCsrfToken(null);
      await post('/api/test', { data: 'value' });

      expect(fetch).toHaveBeenCalledWith(
        '/api/test',
        expect.objectContaining({
          headers: expect.objectContaining({
            'X-CSRF-Token': 'test-csrf-token-cookie',
          }),
        })
      );
    });

    it('should allow manually setting CSRF token', async () => {
      setCsrfToken('manual-token');
      fetch.mockResolvedValueOnce(createMockResponse({ success: true }));

      await post('/api/test', { data: 'value' });

      expect(fetch).toHaveBeenCalledWith(
        '/api/test',
        expect.objectContaining({
          headers: expect.objectContaining({
            'X-CSRF-Token': 'manual-token',
          }),
        })
      );
    });

    it('should not include CSRF token for GET requests', async () => {
      setCsrfToken('should-not-appear');
      fetch.mockResolvedValueOnce(createMockResponse({ data: 'test' }));

      await get('/api/test');

      const callHeaders = fetch.mock.calls[0][1].headers;
      expect(callHeaders['X-CSRF-Token']).toBeUndefined();
    });

    it('should include CSRF token for POST requests', async () => {
      setCsrfToken('post-token');
      fetch.mockResolvedValueOnce(createMockResponse({ success: true }));

      await post('/api/test', {});

      const callHeaders = fetch.mock.calls[0][1].headers;
      expect(callHeaders['X-CSRF-Token']).toBe('post-token');
    });

    it('should include CSRF token for PUT requests', async () => {
      setCsrfToken('put-token');
      fetch.mockResolvedValueOnce(createMockResponse({ success: true }));

      await put('/api/test', {});

      const callHeaders = fetch.mock.calls[0][1].headers;
      expect(callHeaders['X-CSRF-Token']).toBe('put-token');
    });

    it('should include CSRF token for DELETE requests', async () => {
      setCsrfToken('delete-token');
      fetch.mockResolvedValueOnce(createMockResponse({ success: true }));

      await del('/api/test');

      const callHeaders = fetch.mock.calls[0][1].headers;
      expect(callHeaders['X-CSRF-Token']).toBe('delete-token');
    });
  });

  describe('HTTP Methods', () => {
    it('should make GET request', async () => {
      const mockData = { users: [{ id: 1, name: 'Test' }] };
      fetch.mockResolvedValueOnce(createMockResponse(mockData));

      const result = await get('/api/users');

      expect(fetch).toHaveBeenCalledWith('/api/users', expect.objectContaining({
        method: 'GET',
      }));
      expect(result).toEqual(mockData);
    });

    it('should make POST request with JSON body', async () => {
      const postData = { name: 'New User', email: 'test@example.com' };
      fetch.mockResolvedValueOnce(createMockResponse({ id: 1, ...postData }));

      const result = await post('/api/users', postData);

      expect(fetch).toHaveBeenCalledWith('/api/users', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(postData),
      }));
      expect(result.name).toBe('New User');
    });

    it('should make PUT request', async () => {
      const updateData = { name: 'Updated User' };
      fetch.mockResolvedValueOnce(createMockResponse({ id: 1, ...updateData }));

      const result = await put('/api/users/1', updateData);

      expect(fetch).toHaveBeenCalledWith('/api/users/1', expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify(updateData),
      }));
      expect(result.name).toBe('Updated User');
    });

    it('should make PATCH request', async () => {
      const patchData = { status: 'active' };
      fetch.mockResolvedValueOnce(createMockResponse({ id: 1, ...patchData }));

      const result = await patch('/api/users/1', patchData);

      expect(fetch).toHaveBeenCalledWith('/api/users/1', expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify(patchData),
      }));
      expect(result.status).toBe('active');
    });

    it('should make DELETE request', async () => {
      fetch.mockResolvedValueOnce(createMockResponse(null, { status: 204 }));

      const result = await del('/api/users/1');

      expect(fetch).toHaveBeenCalledWith('/api/users/1', expect.objectContaining({
        method: 'DELETE',
      }));
      expect(result).toBeNull();
    });
  });

  describe('Error Handling', () => {
    it('should throw ApiError on 4xx responses', async () => {
      fetch.mockResolvedValueOnce(createMockResponse(
        { error: 'Not found', message: 'User not found' },
        { status: 404, statusText: 'Not Found' }
      ));

      await expect(get('/api/users/999')).rejects.toThrow(ApiError);

      try {
        await get('/api/users/999');
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError);
        expect(error.status).toBe(404);
        expect(error.message).toBe('User not found');
      }
    });

    it('should throw ApiError on 5xx responses', async () => {
      fetch.mockResolvedValueOnce(createMockResponse(
        { error: 'Internal server error' },
        { status: 500, statusText: 'Internal Server Error' }
      ));

      await expect(get('/api/data')).rejects.toThrow(ApiError);
    });

    it('should throw NetworkError on fetch failure', async () => {
      fetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(get('/api/data')).rejects.toThrow(NetworkError);
    });

    it('should throw TimeoutError on request timeout', async () => {
      // Configure short timeout
      configure({ timeout: 100 });

      // Mock a slow response
      fetch.mockImplementationOnce(() =>
        new Promise((resolve) => setTimeout(() => resolve(createMockResponse({})), 200))
      );

      await expect(get('/api/slow')).rejects.toThrow(TimeoutError);
    });

    it('should include error data in ApiError', async () => {
      const errorData = {
        error: 'validation_error',
        message: 'Validation failed',
        details: { field: 'email', error: 'Invalid format' },
      };

      fetch.mockResolvedValueOnce(createMockResponse(errorData, { status: 422 }));

      try {
        await post('/api/users', { email: 'invalid' });
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError);
        expect(error.data).toEqual(errorData);
        expect(error.data.details.field).toBe('email');
      }
    });
  });

  describe('Configuration', () => {
    it('should use configured base URL', async () => {
      configure({ baseUrl: 'https://api.example.com' });
      fetch.mockResolvedValueOnce(createMockResponse({ data: 'test' }));

      await get('/users');

      expect(fetch).toHaveBeenCalledWith(
        'https://api.example.com/users',
        expect.any(Object)
      );
    });

    it('should not modify absolute URLs', async () => {
      configure({ baseUrl: 'https://api.example.com' });
      fetch.mockResolvedValueOnce(createMockResponse({ data: 'test' }));

      await get('https://other-api.com/data');

      expect(fetch).toHaveBeenCalledWith(
        'https://other-api.com/data',
        expect.any(Object)
      );
    });

    it('should use configured default headers', async () => {
      configure({
        headers: {
          'Content-Type': 'application/json',
          'X-Custom-Header': 'custom-value',
        },
      });
      fetch.mockResolvedValueOnce(createMockResponse({ data: 'test' }));

      await get('/api/test');

      expect(fetch).toHaveBeenCalledWith(
        '/api/test',
        expect.objectContaining({
          headers: expect.objectContaining({
            'X-Custom-Header': 'custom-value',
          }),
        })
      );
    });
  });

  describe('Caching', () => {
    it('should cache GET requests', async () => {
      const mockData = { data: 'cached' };
      fetch.mockResolvedValue(createMockResponse(mockData));

      // First call - should fetch
      const result1 = await getCached('/api/data');
      expect(fetch).toHaveBeenCalledTimes(1);
      expect(result1).toEqual(mockData);

      // Second call - should use cache
      const result2 = await getCached('/api/data');
      expect(fetch).toHaveBeenCalledTimes(1); // Still 1
      expect(result2).toEqual(mockData);
    });

    it('should respect TTL for cached requests', async () => {
      const mockData = { data: 'cached' };
      fetch.mockResolvedValue(createMockResponse(mockData));

      // First call with short TTL
      await getCached('/api/data', { ttl: 50 });
      expect(fetch).toHaveBeenCalledTimes(1);

      // Wait for cache to expire
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Second call - cache expired, should fetch again
      await getCached('/api/data', { ttl: 50 });
      expect(fetch).toHaveBeenCalledTimes(2);
    });

    it('should force refresh when requested', async () => {
      fetch.mockResolvedValue(createMockResponse({ data: 'fresh' }));

      await getCached('/api/data');
      expect(fetch).toHaveBeenCalledTimes(1);

      await getCached('/api/data', { forceRefresh: true });
      expect(fetch).toHaveBeenCalledTimes(2);
    });

    it('should clear cache for specific URL pattern', async () => {
      fetch.mockResolvedValue(createMockResponse({ data: 'test' }));

      await getCached('/api/users');
      await getCached('/api/posts');

      clearCache('users');

      await getCached('/api/users');
      expect(fetch).toHaveBeenCalledTimes(3); // users fetched again

      await getCached('/api/posts');
      expect(fetch).toHaveBeenCalledTimes(3); // posts still cached
    });

    it('should clear all cache', async () => {
      fetch.mockResolvedValue(createMockResponse({ data: 'test' }));

      await getCached('/api/users');
      await getCached('/api/posts');

      clearCache();

      await getCached('/api/users');
      await getCached('/api/posts');
      expect(fetch).toHaveBeenCalledTimes(4); // Both fetched again
    });
  });

  describe('File Upload', () => {
    it('should upload single file', async () => {
      const file = new File(['test content'], 'test.txt', { type: 'text/plain' });
      fetch.mockResolvedValueOnce(createMockResponse({ uploaded: true }));

      await upload('/api/upload', file);

      const [url, options] = fetch.mock.calls[0];
      expect(url).toBe('/api/upload');
      expect(options.method).toBe('POST');
      expect(options.body).toBeInstanceOf(FormData);
    });

    it('should upload multiple files', async () => {
      const files = [
        new File(['content1'], 'file1.txt', { type: 'text/plain' }),
        new File(['content2'], 'file2.txt', { type: 'text/plain' }),
      ];
      fetch.mockResolvedValueOnce(createMockResponse({ uploaded: 2 }));

      await upload('/api/upload', files);

      const formData = fetch.mock.calls[0][1].body;
      expect(formData).toBeInstanceOf(FormData);
    });

    it('should include additional data with upload', async () => {
      const file = new File(['test'], 'test.txt', { type: 'text/plain' });
      fetch.mockResolvedValueOnce(createMockResponse({ uploaded: true }));

      await upload('/api/upload', file, { category: 'documents', tags: ['important'] });

      const formData = fetch.mock.calls[0][1].body;
      expect(formData).toBeInstanceOf(FormData);
    });
  });

  describe('API Object', () => {
    it('should expose all methods', () => {
      expect(api.get).toBeDefined();
      expect(api.post).toBeDefined();
      expect(api.put).toBeDefined();
      expect(api.patch).toBeDefined();
      expect(api.delete).toBeDefined();
      expect(api.upload).toBeDefined();
      expect(api.download).toBeDefined();
      expect(api.getCached).toBeDefined();
      expect(api.clearCache).toBeDefined();
      expect(api.configure).toBeDefined();
      expect(api.setCsrfToken).toBeDefined();
    });

    it('should expose error classes', () => {
      expect(api.ApiError).toBe(ApiError);
      expect(api.NetworkError).toBe(NetworkError);
      expect(api.TimeoutError).toBe(TimeoutError);
    });
  });
});
