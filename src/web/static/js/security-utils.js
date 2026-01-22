/**
 * Security Utilities for Frontend
 *
 * Provides centralized security functions to prevent:
 * - XSS (Cross-Site Scripting)
 * - CSRF (Cross-Site Request Forgery)
 * - Injection attacks
 *
 * Usage:
 *   import { escapeHtml, safeInnerHTML, secureFetch } from './security-utils.js';
 *
 *   // Instead of: element.innerHTML = userInput;
 *   // Use: safeInnerHTML(element, userInput);
 *
 *   // Instead of: fetch(url, options);
 *   // Use: secureFetch(url, options);
 */

(function(global) {
    'use strict';

    // =========================================================================
    // XSS Prevention
    // =========================================================================

    /**
     * HTML entity map for escaping
     */
    const HTML_ENTITIES = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '/': '&#x2F;',
        '`': '&#x60;',
        '=': '&#x3D;'
    };

    /**
     * Escape HTML special characters to prevent XSS
     * @param {string} str - String to escape
     * @returns {string} Escaped string safe for HTML insertion
     */
    function escapeHtml(str) {
        if (str === null || str === undefined) {
            return '';
        }
        return String(str).replace(/[&<>"'`=\/]/g, char => HTML_ENTITIES[char]);
    }

    /**
     * Escape string for use in HTML attributes
     * @param {string} str - String to escape
     * @returns {string} Escaped string safe for attribute values
     */
    function escapeAttribute(str) {
        if (str === null || str === undefined) {
            return '';
        }
        // More aggressive escaping for attributes
        return String(str)
            .replace(/[&<>"'`=\/]/g, char => HTML_ENTITIES[char])
            .replace(/\s+/g, ' ')  // Normalize whitespace
            .trim();
    }

    /**
     * Escape string for use in JavaScript strings
     * @param {string} str - String to escape
     * @returns {string} Escaped string safe for JS string literals
     */
    function escapeJs(str) {
        if (str === null || str === undefined) {
            return '';
        }
        return String(str)
            .replace(/\\/g, '\\\\')
            .replace(/'/g, "\\'")
            .replace(/"/g, '\\"')
            .replace(/\n/g, '\\n')
            .replace(/\r/g, '\\r')
            .replace(/\t/g, '\\t')
            .replace(/<\/script/gi, '<\\/script');
    }

    /**
     * Safely set innerHTML with automatic escaping
     * Use this instead of element.innerHTML = userContent
     *
     * @param {HTMLElement} element - Target element
     * @param {string} html - HTML content (user data will be escaped)
     * @param {Object} data - Data object with values to interpolate (will be escaped)
     */
    function safeInnerHTML(element, template, data = {}) {
        if (!element) {
            console.warn('safeInnerHTML: element is null');
            return;
        }

        let html = template;

        // Replace ${key} patterns with escaped values
        Object.keys(data).forEach(key => {
            const value = data[key];
            const escaped = escapeHtml(value);
            // Replace both ${key} and {{key}} patterns
            html = html.replace(new RegExp('\\$\\{' + key + '\\}', 'g'), escaped);
            html = html.replace(new RegExp('\\{\\{' + key + '\\}\\}', 'g'), escaped);
        });

        element.innerHTML = html;
    }

    /**
     * Create an element safely with escaped content
     * @param {string} tag - HTML tag name
     * @param {Object} attrs - Attributes (values will be escaped)
     * @param {string} textContent - Text content (will be escaped)
     * @returns {HTMLElement}
     */
    function createElement(tag, attrs = {}, textContent = null) {
        const element = document.createElement(tag);

        Object.keys(attrs).forEach(key => {
            if (key === 'class') {
                element.className = escapeAttribute(attrs[key]);
            } else if (key === 'style') {
                element.style.cssText = attrs[key]; // CSS is harder to XSS
            } else if (key.startsWith('data-')) {
                element.setAttribute(key, escapeAttribute(attrs[key]));
            } else if (key === 'href' || key === 'src') {
                // Validate URLs
                const url = attrs[key];
                if (isValidUrl(url)) {
                    element.setAttribute(key, url);
                }
            } else {
                element.setAttribute(key, escapeAttribute(attrs[key]));
            }
        });

        if (textContent !== null) {
            element.textContent = textContent; // textContent is safe
        }

        return element;
    }

    /**
     * Validate URL to prevent javascript: and data: XSS
     * @param {string} url - URL to validate
     * @returns {boolean}
     */
    function isValidUrl(url) {
        if (!url) return false;

        const normalized = url.toLowerCase().trim();

        // Block dangerous protocols
        if (normalized.startsWith('javascript:')) return false;
        if (normalized.startsWith('data:') && !normalized.startsWith('data:image/')) return false;
        if (normalized.startsWith('vbscript:')) return false;

        return true;
    }

    // =========================================================================
    // CSRF Protection
    // =========================================================================

    /**
     * Get CSRF token from meta tag or cookie
     * @returns {string|null}
     */
    function getCSRFToken() {
        // Try meta tag first
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            return metaTag.getAttribute('content');
        }

        // Try cookie
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrf_token' || name === 'csrftoken' || name === '_csrf') {
                return decodeURIComponent(value);
            }
        }

        return null;
    }

    /**
     * Secure fetch wrapper that automatically includes CSRF token
     * @param {string} url - Request URL
     * @param {Object} options - Fetch options
     * @returns {Promise<Response>}
     */
    async function secureFetch(url, options = {}) {
        const csrfToken = getCSRFToken();

        // Merge headers
        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        };

        // Add CSRF token for state-changing requests
        const method = (options.method || 'GET').toUpperCase();
        if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
            if (csrfToken) {
                headers['X-CSRF-Token'] = csrfToken;
            }
            // Also add as form field for compatibility
            headers['X-Requested-With'] = 'XMLHttpRequest';
        }

        // Add credentials for same-origin requests
        const fetchOptions = {
            ...options,
            headers,
            credentials: options.credentials || 'same-origin'
        };

        // Add timeout using AbortController
        const timeout = options.timeout || 30000; // 30 second default
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        try {
            const response = await fetch(url, {
                ...fetchOptions,
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            return response;
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                throw new Error(`Request timeout after ${timeout}ms`);
            }
            throw error;
        }
    }

    // =========================================================================
    // URL Parameter Safety
    // =========================================================================

    /**
     * Safely encode URL parameters
     * @param {Object} params - Key-value pairs to encode
     * @returns {string} Encoded query string
     */
    function encodeParams(params) {
        return Object.keys(params)
            .filter(key => params[key] !== null && params[key] !== undefined)
            .map(key => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
            .join('&');
    }

    /**
     * Build safe URL with encoded parameters
     * @param {string} baseUrl - Base URL
     * @param {Object} params - Query parameters
     * @returns {string}
     */
    function buildUrl(baseUrl, params = {}) {
        const queryString = encodeParams(params);
        if (!queryString) return baseUrl;

        const separator = baseUrl.includes('?') ? '&' : '?';
        return `${baseUrl}${separator}${queryString}`;
    }

    // =========================================================================
    // Safe Event Handling (prevents onclick injection)
    // =========================================================================

    /**
     * Safely bind click handler with data
     * Use instead of onclick="handler('${unsafeData}')"
     *
     * @param {HTMLElement} element - Element to bind to
     * @param {Function} handler - Click handler function
     * @param {*} data - Data to pass to handler (stored safely)
     */
    function safeClick(element, handler, data = null) {
        if (!element) return;

        // Store data in dataset (automatically escaped)
        if (data !== null) {
            element.dataset.clickData = JSON.stringify(data);
        }

        element.addEventListener('click', function(e) {
            e.preventDefault();
            const storedData = this.dataset.clickData
                ? JSON.parse(this.dataset.clickData)
                : null;
            handler.call(this, e, storedData);
        });
    }

    /**
     * Create a button with safe click handler
     * @param {string} text - Button text
     * @param {Function} handler - Click handler
     * @param {*} data - Data to pass to handler
     * @param {string} className - CSS class(es)
     * @returns {HTMLButtonElement}
     */
    function createButton(text, handler, data = null, className = '') {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = text; // Safe - uses textContent
        if (className) {
            button.className = className;
        }
        safeClick(button, handler, data);
        return button;
    }

    // =========================================================================
    // Input Sanitization
    // =========================================================================

    /**
     * Sanitize user input - removes dangerous patterns
     * @param {string} input - User input
     * @returns {string} Sanitized input
     */
    function sanitizeInput(input) {
        if (input === null || input === undefined) {
            return '';
        }

        return String(input)
            // Remove null bytes
            .replace(/\0/g, '')
            // Remove script tags
            .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
            // Remove event handlers
            .replace(/\bon\w+\s*=/gi, '')
            // Normalize whitespace
            .trim();
    }

    /**
     * Validate and sanitize ID (alphanumeric, dash, underscore only)
     * @param {string} id - ID to validate
     * @returns {string|null} Sanitized ID or null if invalid
     */
    function sanitizeId(id) {
        if (!id) return null;

        const sanitized = String(id).replace(/[^a-zA-Z0-9_-]/g, '');

        // Must start with letter or underscore
        if (!/^[a-zA-Z_]/.test(sanitized)) {
            return null;
        }

        return sanitized;
    }

    // =========================================================================
    // Content Security
    // =========================================================================

    /**
     * Check if content appears to contain malicious patterns
     * @param {string} content - Content to check
     * @returns {boolean} True if suspicious patterns found
     */
    function hasSuspiciousContent(content) {
        if (!content) return false;

        const suspicious = [
            /<script/i,
            /javascript:/i,
            /on\w+\s*=/i,
            /data:text\/html/i,
            /expression\s*\(/i,
            /url\s*\(\s*["']?\s*javascript/i
        ];

        return suspicious.some(pattern => pattern.test(content));
    }

    // =========================================================================
    // Export
    // =========================================================================

    const SecurityUtils = {
        // XSS Prevention
        escapeHtml,
        escapeAttribute,
        escapeJs,
        safeInnerHTML,
        createElement,
        isValidUrl,

        // CSRF Protection
        getCSRFToken,
        secureFetch,

        // URL Safety
        encodeParams,
        buildUrl,

        // Safe Event Handling
        safeClick,
        createButton,

        // Input Sanitization
        sanitizeInput,
        sanitizeId,
        hasSuspiciousContent
    };

    // Export for different module systems
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = SecurityUtils;
    } else if (typeof define === 'function' && define.amd) {
        define([], function() { return SecurityUtils; });
    } else {
        global.SecurityUtils = SecurityUtils;
    }

})(typeof window !== 'undefined' ? window : this);
