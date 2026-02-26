/* ==========================================
   Unified Consent Management
   ========================================== */

  function disableChat() {
    const chatInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    if (chatInput) {
      chatInput.classList.add('chat-disabled');
      chatInput.disabled = true;
    }
    if (sendBtn) {
      sendBtn.classList.add('chat-disabled');
      sendBtn.disabled = true;
    }
  }

  function enableChat() {
    const chatInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    if (chatInput) {
      chatInput.classList.remove('chat-disabled');
      chatInput.disabled = false;
    }
    if (sendBtn) {
      sendBtn.classList.remove('chat-disabled');
      sendBtn.disabled = false;
    }
  }

  /** Returns true if user already consented this session */
  function checkAdvisorConsent() {
    if (sessionStorage.getItem('advisor_consent') === 'true') {
      var modal = document.getElementById('advisorConsentModal');
      if (modal) modal.classList.add('hidden');
      enableChat();
      return true;
    }
    // Show consent modal, disable chat
    var modal = document.getElementById('advisorConsentModal');
    if (modal) modal.classList.remove('hidden');
    disableChat();
    return false;
  }

  /** Wire up consent modal checkbox + button */
  function setupAdvisorConsent() {
    var checkbox = document.getElementById('advisorConsentCheck');
    var btn = document.getElementById('advisorConsentBtn');
    if (!checkbox || !btn) return;

    checkbox.addEventListener('change', function () {
      btn.disabled = !this.checked;
    });

    btn.addEventListener('click', async function () {
      sessionStorage.setItem('advisor_consent', 'true');
      sessionStorage.setItem('advisor_consent_at', new Date().toISOString());
      var modal = document.getElementById('advisorConsentModal');
      if (modal) modal.classList.add('hidden');
      enableChat();

      // Log acknowledgment to server
      try {
        await fetch('/api/intelligent-advisor/acknowledge-standards', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: typeof sessionId !== 'undefined' ? sessionId : 'unknown',
            acknowledged_at: new Date().toISOString()
          })
        });
      } catch (e) {
        console.warn('Could not log acknowledgment:', e);
      }

      // Initialize session after consent
      initializeSession();
      showToast('Welcome! Your data will be handled securely.', 'success');
    });
  }

  /** Wire up the dismissible notice banner */
  function setupNoticeBanner() {
    var dismissBtn = document.getElementById('dismissNoticeBtn');
    var banner = document.getElementById('advisorNoticeBanner');
    if (dismissBtn && banner) {
      dismissBtn.addEventListener('click', function () {
        banner.style.display = 'none';
      });
    }
  }

  // Check on page load
  document.addEventListener('DOMContentLoaded', function () {
    setupAdvisorConsent();
    setupNoticeBanner();
    checkAdvisorConsent();
  });


/* ==========================================
   Main Application Logic
   ========================================== */

    let sessionId = null;
    let conversationHistory = [];
    let extractedData = {
      // Lead Information (for CPA handoff)
      contact: {
        name: null,
        email: null,
        phone: null,
        preferred_contact: null
      },

      // Tax Profile
      tax_profile: {
        filing_status: null,
        total_income: null,
        w2_income: null,
        business_income: null,
        investment_income: null,
        rental_income: null,
        dependents: null,
        state: null
      },

      // Deductions & Credits
      tax_items: {
        mortgage_interest: null,
        property_tax: null,
        charitable: null,
        medical: null,
        student_loan_interest: null,
        retirement_contributions: null,
        has_hsa: false,
        has_529: false
      },

      // Business Details (if applicable)
      business: {
        type: null,
        revenue: null,
        expenses: null,
        entity_type: null
      },

      // Lead Scoring
      lead_data: {
        score: 0,
        complexity: 'simple', // simple, moderate, complex
        estimated_savings: 0,
        engagement_level: 0,
        ready_for_cpa: false,
        urgency: 'normal' // normal, high, urgent
      },

      // Documents uploaded
      documents: []
    };
    let isProcessing = false;
    let taxCalculations = null;
    let leadQualified = false;
    let retryCount = 0; // Track consecutive retry attempts to prevent infinite loops

    // =========================================================================
    // ROBUSTNESS LAYER - Error Handling, Validation, Recovery, Rate Limiting
    // =========================================================================

    const RobustnessConfig = {
      maxRetries: 3,
      retryDelay: 1000,  // ms
      maxMessageLength: 5000,
      minMessageLength: 1,
      rateLimitMessages: 30,  // max messages per minute
      rateLimitWindow: 60000,  // 1 minute
      sessionTimeout: 30 * 60 * 1000,  // 30 minutes
      offlineQueueMax: 10,
      debugMode: false  // Set to true only for development
    };

    // =========================================================================
    // SECURITY: Production-Safe Logger (prevents info leakage in production)
    // =========================================================================

    /**
     * Production-safe logger that only outputs when debugMode is enabled.
     * SECURITY: Prevents sensitive debugging information from being exposed
     * in browser console in production environments.
     */
    const DevLogger = {
      log: function(...args) {
        if (RobustnessConfig.debugMode) {
          console.log('[DEV]', ...args);
        }
      },
      warn: function(...args) {
        if (RobustnessConfig.debugMode) {
          console.warn('[DEV]', ...args);
        }
      },
      error: function(...args) {
        // Always log errors, but redact sensitive data in production
        if (RobustnessConfig.debugMode) {
          console.error('[DEV]', ...args);
        } else {
          // In production, only log generic error without details
          console.error('An error occurred. Enable debugMode for details.');
        }
      },
      debug: function(...args) {
        if (RobustnessConfig.debugMode) {
          console.debug('[DEV]', ...args);
        }
      }
    };

    // =========================================================================
    // SECURITY: CSRF Protection
    // =========================================================================

    /**
     * Get CSRF token from cookie or meta tag.
     * @returns {string|null} The CSRF token or null if not found
     */
    function getCSRFToken() {
      // First try to get from cookie
      const cookies = document.cookie.split(';');
      for (const cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrf_token') {
          return decodeURIComponent(value);
        }
      }
      // Fallback to meta tag
      const metaTag = document.querySelector('meta[name="csrf-token"]');
      return metaTag ? metaTag.getAttribute('content') : null;
    }

    /**
     * Secure fetch wrapper that automatically includes CSRF token.
     * Use this for all POST/PUT/DELETE requests.
     * @param {string} url - The URL to fetch
     * @param {object} options - Fetch options
     * @returns {Promise<Response>}
     */
    async function secureFetch(url, options = {}) {
      const method = (options.method || 'GET').toUpperCase();

      // Add CSRF token for state-changing requests
      if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
        const csrfToken = getCSRFToken();
        if (csrfToken) {
          options.headers = {
            ...options.headers,
            'X-CSRF-Token': csrfToken
          };
        }
      }

      // Ensure credentials are included for cookie-based auth
      options.credentials = options.credentials || 'same-origin';

      return fetch(url, options);
    }

    // Rate limiting state
    const rateLimitState = {
      messages: [],
      blocked: false,
      blockUntil: null
    };

    // Offline message queue
    const offlineQueue = [];
    let isOnline = navigator.onLine;

    // Session recovery state
    let lastActivityTime = Date.now();
    let sessionRecoveryAttempted = false;

    // =========================================================================
    // DATA PROTECTION LAYER - Prevents race conditions and data overwrites
    // =========================================================================

    // Mutex for data operations - prevents concurrent modifications
    const dataMutex = {
      locked: false,
      queue: [],
      async acquire() {
        return new Promise(resolve => {
          if (!this.locked) {
            this.locked = true;
            resolve();
          } else {
            this.queue.push(resolve);
          }
        });
      },
      release() {
        if (this.queue.length > 0) {
          const next = this.queue.shift();
          next();
        } else {
          this.locked = false;
        }
      }
    };

    // Track user-confirmed data that should not be overwritten by AI
    const confirmedData = {
      fields: new Set(), // Set of field paths like 'tax_profile.filing_status'
      mark(fieldPath) {
        this.fields.add(fieldPath);
        DevLogger.log('Marked as confirmed:', fieldPath);
      },
      isConfirmed(fieldPath) {
        return this.fields.has(fieldPath);
      },
      clear() {
        this.fields.clear();
      }
    };

    // Deep merge that respects confirmed data and handles nested objects
    function safeDeepMerge(target, source, parentPath = '') {
      if (!source || typeof source !== 'object') return target;

      const result = { ...target };

      for (const key of Object.keys(source)) {
        const fieldPath = parentPath ? `${parentPath}.${key}` : key;
        const sourceValue = source[key];
        const targetValue = result[key];

        // Skip if this field is user-confirmed and has a value
        if (confirmedData.isConfirmed(fieldPath) && targetValue != null) {
          DevLogger.log(`Skipping confirmed field: ${fieldPath}`);
          continue;
        }

        // Skip null/undefined source values (don't overwrite with nothing)
        if (sourceValue == null) continue;

        // Deep merge nested objects (but not arrays)
        if (typeof sourceValue === 'object' && !Array.isArray(sourceValue) &&
            typeof targetValue === 'object' && !Array.isArray(targetValue)) {
          result[key] = safeDeepMerge(targetValue || {}, sourceValue, fieldPath);
        } else if (Array.isArray(sourceValue) && Array.isArray(targetValue)) {
          // For arrays, merge unique items
          const combined = [...targetValue];
          for (const item of sourceValue) {
            const exists = combined.some(existing =>
              JSON.stringify(existing) === JSON.stringify(item)
            );
            if (!exists) combined.push(item);
          }
          result[key] = combined;
        } else {
          // Simple value assignment
          result[key] = sourceValue;
        }
      }

      return result;
    }

    // Thread-safe data update function
    async function updateExtractedDataSafe(newData, source = 'unknown') {
      await dataMutex.acquire();
      try {
        DevLogger.log(`Updating extractedData from ${source}:`, newData);
        extractedData = safeDeepMerge(extractedData, newData);
        markUnsaved();
      } finally {
        dataMutex.release();
      }
    }

    // Helper to set a value AND mark it as user-confirmed (prevents AI overwriting)
    function setConfirmedValue(path, value) {
      const parts = path.split('.');
      let obj = extractedData;
      for (let i = 0; i < parts.length - 1; i++) {
        if (!obj[parts[i]]) obj[parts[i]] = {};
        obj = obj[parts[i]];
      }
      obj[parts[parts.length - 1]] = value;
      confirmedData.mark(path);
      markUnsaved();
    }

    // Batch confirm multiple values at once
    function setConfirmedValues(values) {
      for (const [path, value] of Object.entries(values)) {
        setConfirmedValue(path, value);
      }
    }

    // Queue processing mutex - prevents parallel queue processing
    let isProcessingQueue = false;

    // =========== INPUT VALIDATION & SANITIZATION ===========

    function sanitizeInput(input) {
      if (typeof input !== 'string') return '';

      // Remove potential XSS vectors
      let sanitized = input
        .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
        .replace(/<[^>]*>/g, '')  // Remove HTML tags
        .replace(/javascript:/gi, '')
        .replace(/on\w+\s*=/gi, '')  // Remove event handlers
        .trim();

      // Limit length
      if (sanitized.length > RobustnessConfig.maxMessageLength) {
        sanitized = sanitized.substring(0, RobustnessConfig.maxMessageLength);
      }

      return sanitized;
    }

    function validateMessage(message) {
      const errors = [];

      if (!message || typeof message !== 'string') {
        errors.push('Message must be a non-empty string');
      } else {
        if (message.length < RobustnessConfig.minMessageLength) {
          errors.push('Message is too short');
        }
        if (message.length > RobustnessConfig.maxMessageLength) {
          errors.push(`Message exceeds maximum length of ${RobustnessConfig.maxMessageLength} characters`);
        }
      }

      return {
        valid: errors.length === 0,
        errors: errors
      };
    }

    function validateNumericInput(value, min = 0, max = Infinity) {
      const num = parseFloat(value);
      if (isNaN(num)) return { valid: false, error: 'Must be a valid number' };
      if (num < min) return { valid: false, error: `Must be at least ${min}` };
      if (num > max) return { valid: false, error: `Must be no more than ${max}` };
      return { valid: true, value: num };
    }

    // =========== RATE LIMITING ===========

    function checkRateLimit() {
      const now = Date.now();

      // Check if currently blocked
      if (rateLimitState.blocked) {
        if (now < rateLimitState.blockUntil) {
          const waitSeconds = Math.ceil((rateLimitState.blockUntil - now) / 1000);
          return {
            allowed: false,
            reason: `Too many messages. Please wait ${waitSeconds} seconds.`
          };
        }
        // Block expired
        rateLimitState.blocked = false;
        rateLimitState.blockUntil = null;
      }

      // Remove old messages from tracking
      rateLimitState.messages = rateLimitState.messages.filter(
        time => now - time < RobustnessConfig.rateLimitWindow
      );

      // Check if over limit
      if (rateLimitState.messages.length >= RobustnessConfig.rateLimitMessages) {
        rateLimitState.blocked = true;
        rateLimitState.blockUntil = now + 30000; // Block for 30 seconds
        return {
          allowed: false,
          reason: 'You\'re sending messages too quickly. Please slow down.'
        };
      }

      // Record this message
      rateLimitState.messages.push(now);
      return { allowed: true };
    }

    // =========== NETWORK STATUS MONITORING ===========

    function initNetworkMonitoring() {
      window.addEventListener('online', handleOnline);
      window.addEventListener('offline', handleOffline);
    }

    function handleOnline() {
      isOnline = true;
      showToast('Connection restored', 'success');

      // Process queued messages
      processOfflineQueue();
    }

    function handleOffline() {
      isOnline = false;
      showToast('You\'re offline. Messages will be sent when connection is restored.', 'warning');
    }

    async function processOfflineQueue() {
      // Prevent concurrent queue processing
      if (isProcessingQueue) {
        DevLogger.log('Queue processing already in progress, skipping');
        return;
      }
      if (offlineQueue.length === 0) return;

      isProcessingQueue = true;
      try {
        showToast(`Sending ${offlineQueue.length} queued message(s)...`, 'info');

        while (offlineQueue.length > 0 && isOnline) {
          const message = offlineQueue.shift();
          try {
            await processAIResponse(message);
          } catch (error) {
            DevLogger.error('Failed to process queued message:', error);
            // Put it back if failed and still offline
            if (!isOnline) {
              offlineQueue.unshift(message);
              break;
            }
          }
        }
      } finally {
        isProcessingQueue = false;
      }
    }

    function queueOfflineMessage(message) {
      if (offlineQueue.length >= RobustnessConfig.offlineQueueMax) {
        showToast('Offline queue full. Please wait for connection.', 'error');
        return false;
      }
      offlineQueue.push(message);
      showToast(`Message queued. ${offlineQueue.length} message(s) waiting.`, 'info');
      return true;
    }

    // =========== API CALL WITH RETRY LOGIC ===========

    async function fetchWithRetryRobust(url, options = {}, retries = RobustnessConfig.maxRetries, timeoutMs = 30000) {
      let lastError;

      for (let attempt = 1; attempt <= retries; attempt++) {
        try {
          // Add timeout with AbortController
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

          // SECURITY: Add CSRF token for state-changing requests
          const method = (options.method || 'GET').toUpperCase();
          const headers = {
            'Content-Type': 'application/json',
            ...options.headers
          };

          if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
            const csrfToken = getCSRFToken();
            if (csrfToken) {
              headers['X-CSRF-Token'] = csrfToken;
            }
          }

          const response = await fetch(url, {
            ...options,
            signal: controller.signal,
            headers: headers,
            credentials: 'same-origin'
          });

          clearTimeout(timeoutId);

          if (!response.ok) {
            // Don't retry client errors (4xx)
            if (response.status >= 400 && response.status < 500) {
              const errorData = await response.json().catch(() => ({}));
              throw new Error(errorData.detail || `Request failed with status ${response.status}`);
            }
            throw new Error(`Server error: ${response.status}`);
          }

          return response;
        } catch (error) {
          lastError = error;

          // Handle timeout separately
          if (error.name === 'AbortError') {
            lastError = new Error('Request timeout - please try again');
          }

          if (RobustnessConfig.debugMode) {
            console.log(`Attempt ${attempt}/${retries} failed:`, error.message);
          }

          // Don't retry if it's a client error or last attempt
          if (attempt === retries || error.message.includes('400') || error.message.includes('401')) {
            break;
          }

          // Wait before retry (exponential backoff)
          await new Promise(resolve =>
            setTimeout(resolve, RobustnessConfig.retryDelay * Math.pow(2, attempt - 1))
          );
        }
      }

      throw lastError;
    }

    // =========== SESSION RECOVERY ===========

    function updateLastActivity() {
      lastActivityTime = Date.now();
      // SECURITY: Use sessionStorage for PII (clears when tab closes)
      sessionStorage.setItem('tax_advisor_last_activity', lastActivityTime.toString());
    }

    function checkSessionValidity() {
      const now = Date.now();
      const storedTime = parseInt(sessionStorage.getItem('tax_advisor_last_activity') || '0');

      if (storedTime && (now - storedTime) > RobustnessConfig.sessionTimeout) {
        return false; // Session expired
      }
      return true;
    }

    async function attemptSessionRecovery() {
      if (sessionRecoveryAttempted) return false;
      sessionRecoveryAttempted = true;

      const storedSessionId = sessionStorage.getItem('tax_session_id');
      const storedData = sessionStorage.getItem('tax_advisor_data');

      if (storedSessionId && storedData) {
        try {
          const savedData = JSON.parse(storedData);

          // Verify session still exists on server
          const response = await fetch(`/api/sessions/${storedSessionId}/restore`);
          if (response.ok) {
            sessionId = storedSessionId;

            // Restore extracted data using safe deep merge (prevents nested object loss)
            if (savedData.extractedData) {
              extractedData = safeDeepMerge(extractedData, savedData.extractedData);
              // Reset questioning state for restored sessions
              resetQuestioningState();
            }

            showToast('Previous session restored', 'success');
            return true;
          }
        } catch (error) {
          console.log('Session recovery failed:', error);
        }
      }

      // Allow retry on next page load
      sessionRecoveryAttempted = false;
      return false;
    }

    // Track localStorage quota usage
    let localStorageWarningShown = false;

    function saveSessionData() {
      try {
        const dataToSave = JSON.stringify({
          extractedData: extractedData,
          timestamp: Date.now()
        });

        // Check size before saving (5MB typical limit)
        const sizeInBytes = new Blob([dataToSave]).size;
        const maxSize = 4 * 1024 * 1024; // 4MB to leave buffer

        if (sizeInBytes > maxSize) {
          DevLogger.warn('Session data too large, trimming conversation history');
          // Trim data to fit
          const trimmedData = {
            extractedData: {
              ...extractedData,
              documents: extractedData.documents?.slice(-5) || [] // Keep only last 5 documents
            },
            timestamp: Date.now()
          };
          sessionStorage.setItem('tax_advisor_data', JSON.stringify(trimmedData));
        } else {
          sessionStorage.setItem('tax_advisor_data', dataToSave);
        }
        updateLastActivity();
        localStorageWarningShown = false;
      } catch (error) {
        // Handle QuotaExceededError
        if (error.name === 'QuotaExceededError' || error.code === 22) {
          if (!localStorageWarningShown) {
            showToast('Storage full - some data may not be saved locally', 'warning');
            localStorageWarningShown = true;
          }
          // Try to clear old data and retry
          try {
            sessionStorage.removeItem('tax_advisor_data');
            DevLogger.warn('Cleared old storage due to quota exceeded');
          } catch (e) {
            DevLogger.error('Failed to clear storage:', e);
          }
        } else {
          DevLogger.warn('Failed to save session data:', error);
        }
      }
    }

    // =========== COMPREHENSIVE ERROR HANDLER ===========

    function handleError(error, context = 'Unknown') {
      DevLogger.error(`Error in ${context}:`, error);

      // Determine error type and appropriate response
      let userMessage = '';
      let recoveryAction = null;

      if (!isOnline || error.message?.includes('network') || error.message?.includes('fetch')) {
        userMessage = 'Connection issue. Please check your internet and try again.';
        recoveryAction = 'retry';
      } else if (error.message?.includes('timeout')) {
        userMessage = 'The request took too long. Please try again.';
        recoveryAction = 'retry';
      } else if (error.message?.includes('401') || error.message?.includes('403')) {
        userMessage = 'Session expired. Please refresh the page.';
        recoveryAction = 'refresh';
      } else if (error.message?.includes('429')) {
        userMessage = 'Too many requests. Please wait a moment.';
        recoveryAction = 'wait';
      } else if (error.message?.includes('500') || error.message?.includes('502') || error.message?.includes('503')) {
        userMessage = 'Server is temporarily unavailable. Please try again.';
        recoveryAction = 'retry';
      } else {
        userMessage = 'Something went wrong. Let me try a different approach.';
        recoveryAction = 'fallback';
      }

      // Show error to user
      showToast(userMessage, 'error');

      // Return recovery info
      return {
        message: userMessage,
        action: recoveryAction,
        originalError: error
      };
    }

    // =========== FALLBACK RESPONSES ===========

    const FallbackResponses = {
      networkError: [
        "I'm having trouble connecting right now. Could you try again in a moment?",
        "Connection issues detected. Your data is safe - please try again shortly.",
        "Network hiccup! Don't worry, just click 'Retry' or try your message again."
      ],

      parseError: [
        "I didn't quite catch that. Could you rephrase your question?",
        "Let me make sure I understand - could you say that differently?",
        "I want to help, but I'm not sure what you mean. Can you clarify?"
      ],

      serverError: [
        "I'm experiencing some technical difficulties. Let me try a simpler approach.",
        "Something went wrong on my end. Let's continue with the basics.",
        "Technical issue detected. I'll work around it - please continue."
      ],

      unknown: [
        "I'm not sure how to respond to that. Let me ask you something instead.",
        "Interesting! Let's focus on your tax situation. What's your filing status?",
        "I want to help you save on taxes. Can you tell me about your income?"
      ],

      empty: [
        "I didn't receive your message. Please try typing again.",
        "It looks like your message was empty. What would you like to know?",
        "I'm ready to help! Just type your question or select an option above."
      ]
    };

    function getFallbackResponse(type = 'unknown') {
      const responses = FallbackResponses[type] || FallbackResponses.unknown;
      return responses[Math.floor(Math.random() * responses.length)];
    }

    // =========== GRACEFUL DEGRADATION ===========

    function attemptGracefulDegradation(originalRequest, error) {
      // If the main API fails, try simpler alternatives
      const degradedResponse = {
        success: false,
        message: getFallbackResponse('serverError'),
        quickActions: [
          { label: 'Tell me your filing status', value: 'filing_prompt' },
          { label: 'Enter your income', value: 'income_prompt' },
          { label: 'Start over', value: 'reset' }
        ]
      };

      return degradedResponse;
    }

    // =========== MESSAGE QUEUE MANAGEMENT ===========

    const messageQueue = [];
    // Reuses isProcessingQueue declared above (line ~4069)

    async function addToMessageQueue(message) {
      messageQueue.push({
        message: message,
        timestamp: Date.now(),
        retries: 0
      });

      if (!isProcessingQueue) {
        processMessageQueue();
      }
    }

    async function processMessageQueue() {
      if (isProcessingQueue || messageQueue.length === 0) return;

      isProcessingQueue = true;

      while (messageQueue.length > 0) {
        const item = messageQueue[0];

        try {
          await processAIResponse(item.message);
          messageQueue.shift(); // Remove processed message
        } catch (error) {
          item.retries++;

          if (item.retries >= RobustnessConfig.maxRetries) {
            messageQueue.shift(); // Give up after max retries
            addMessage('ai', getFallbackResponse('serverError'), [
              { label: 'Try again', value: 'retry_last' },
              { label: 'Start fresh', value: 'reset' }
            ]);
          } else {
            // Wait before retry
            await new Promise(r => setTimeout(r, RobustnessConfig.retryDelay * item.retries));
          }
        }
      }

      isProcessingQueue = false;
    }

    // =========== INITIALIZE ROBUSTNESS FEATURES ===========

    function initRobustnessFeatures() {
      initNetworkMonitoring();

      // Periodically save session data
      setInterval(saveSessionData, 30000);

      // Check for session recovery on load
      attemptSessionRecovery();

      // Log robustness initialization
      if (RobustnessConfig.debugMode) {
        DevLogger.log('Robustness features initialized:', {
          online: isOnline,
          sessionValid: checkSessionValidity(),
          queueSize: offlineQueue.length
        });
      }
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', initRobustnessFeatures);

    // =========================================================================
    // UX ENHANCEMENT LAYER - Celebrations, Voice, Streaming, Nudges, Emotions
    // =========================================================================

    // Celebration System
    const CelebrationSystem = {
      // Create confetti particles
      createConfetti(count = 100) {
        const overlay = document.createElement('div');
        overlay.className = 'celebration-overlay';
        document.body.appendChild(overlay);

        const colors = ['#1e3a5f', '#5387c1', '#10b981', '#14b8a6', '#f59e0b', '#34d399'];

        for (let i = 0; i < count; i++) {
          const confetti = document.createElement('div');
          confetti.className = 'confetti';
          confetti.style.left = Math.random() * 100 + '%';
          confetti.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
          confetti.style.animationDelay = Math.random() * 2 + 's';
          confetti.style.animationDuration = (2 + Math.random() * 2) + 's';
          overlay.appendChild(confetti);
        }

        setTimeout(() => overlay.remove(), 4000);
      },

      // Create money rain
      createMoneyRain(count = 50) {
        const overlay = document.createElement('div');
        overlay.className = 'celebration-overlay';
        document.body.appendChild(overlay);

        const moneyEmojis = ['💵', '💰', '🤑', '💲', '💎'];

        for (let i = 0; i < count; i++) {
          const money = document.createElement('div');
          money.className = 'money-particle';
          money.textContent = moneyEmojis[Math.floor(Math.random() * moneyEmojis.length)];
          money.style.left = Math.random() * 100 + '%';
          money.style.animationDelay = Math.random() * 1.5 + 's';
          overlay.appendChild(money);
        }

        setTimeout(() => overlay.remove(), 3500);
      },

      // Create sparkle effect at position
      createSparkles(x, y, count = 8) {
        for (let i = 0; i < count; i++) {
          const sparkle = document.createElement('div');
          sparkle.className = 'sparkle';
          sparkle.style.left = (x + (Math.random() - 0.5) * 100) + 'px';
          sparkle.style.top = (y + (Math.random() - 0.5) * 100) + 'px';
          sparkle.style.animationDelay = Math.random() * 0.3 + 's';
          document.body.appendChild(sparkle);
          setTimeout(() => sparkle.remove(), 1000);
        }
      },

      // Show celebration toast
      showCelebrationToast(emoji, title, subtitle, amount = null) {
        const toast = document.createElement('div');
        toast.className = 'celebration-toast';
        toast.innerHTML = `
          <span class="celebration-emoji">${emoji}</span>
          <div class="celebration-title">${title}</div>
          <div class="celebration-subtitle">${subtitle}</div>
          ${amount ? `<div class="celebration-amount">$${amount.toLocaleString()}</div>` : ''}
        `;
        document.body.appendChild(toast);

        setTimeout(() => {
          toast.style.animation = 'celebration-pop 0.3s ease reverse forwards';
          setTimeout(() => toast.remove(), 300);
        }, 3000);
      },

      // Celebrate profile completion
      celebrateProfileComplete() {
        this.createConfetti(150);
        this.showCelebrationToast('🎉', 'Amazing!', 'Your profile is complete!');
        this.playSound('success');
      },

      // Celebrate savings found
      celebrateSavingsFound(amount) {
        this.createMoneyRain(60);
        this.showCelebrationToast('💰', 'Savings Found!', 'Potential tax savings discovered', amount);
        this.playSound('money');
      },

      // Celebrate strategy unlock
      celebrateStrategyUnlock(strategyName) {
        this.createSparkles(window.innerWidth / 2, window.innerHeight / 2, 12);
        this.showCelebrationToast('⭐', 'Strategy Unlocked!', strategyName);
        this.playSound('unlock');
      },

      // Celebrate first milestone
      celebrateFirstMilestone() {
        this.showCelebrationToast('🚀', 'Great Start!', 'You\'re on your way to tax savings!');
      },

      // Play celebration sound (if enabled)
      playSound(type) {
        // Only play if user has interacted with page (browser requirement)
        if (!window.userHasInteracted) return;

        const sounds = {
          success: 'data:audio/wav;base64,UklGRl9vT19XQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgA',
          money: 'data:audio/wav;base64,UklGRl9vT19XQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgA',
          unlock: 'data:audio/wav;base64,UklGRl9vT19XQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgA'
        };

        // Note: In production, replace with actual sound files
        // For now, celebrations are visual only
      }
    };

    // Track user interaction for sound
    document.addEventListener('click', () => { window.userHasInteracted = true; }, { once: true });

    // Celebration triggers
    let previousSavings = 0;
    let previousCompleteness = 0;
    let celebratedMilestones = new Set();

    function checkForCelebration(data) {
      // Check for savings milestone
      const currentSavings = data.total_potential_savings || 0;
      if (currentSavings > previousSavings + 1000 && currentSavings >= 1000) {
        CelebrationSystem.celebrateSavingsFound(currentSavings);
        previousSavings = currentSavings;
      }

      // Check for profile completion
      const completeness = data.profile_completeness || 0;
      if (completeness >= 1.0 && previousCompleteness < 1.0) {
        CelebrationSystem.celebrateProfileComplete();
      } else if (completeness >= 0.5 && previousCompleteness < 0.5 && !celebratedMilestones.has('50')) {
        celebratedMilestones.add('50');
        CelebrationSystem.celebrateFirstMilestone();
      }
      previousCompleteness = completeness;

      // Check for first strategy
      if (data.strategies && data.strategies.length > 0 && !celebratedMilestones.has('first_strategy')) {
        celebratedMilestones.add('first_strategy');
        CelebrationSystem.celebrateStrategyUnlock(data.strategies[0].title);
      }
    }

    // Voice Input System
    const VoiceInputSystem = {
      recognition: null,
      isRecording: false,
      transcript: '',

      init() {
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
          DevLogger.log('Speech recognition not supported');
          return false;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.recognition = new SpeechRecognition();
        this.recognition.continuous = true;
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-US';

        this.recognition.onresult = (event) => {
          let interimTranscript = '';
          let finalTranscript = '';

          for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
              finalTranscript += transcript;
            } else {
              interimTranscript += transcript;
            }
          }

          this.transcript = finalTranscript || interimTranscript;
          this.updateTranscriptDisplay(this.transcript, !finalTranscript);
        };

        this.recognition.onerror = (event) => {
          DevLogger.error('Speech recognition error:', event.error);
          this.stopRecording();
          if (event.error === 'not-allowed') {
            showToast('Please allow microphone access to use voice input', 'warning');
          }
        };

        this.recognition.onend = () => {
          if (this.isRecording) {
            // Restart if still in recording mode (browser auto-stops)
            this.recognition.start();
          }
        };

        return true;
      },

      startRecording() {
        if (!this.recognition && !this.init()) {
          showToast('Voice input not supported in this browser', 'warning');
          return;
        }

        this.isRecording = true;
        this.transcript = '';
        this.recognition.start();
        this.showTranscriptPanel();

        const btn = document.getElementById('voiceInputBtn');
        if (btn) {
          btn.classList.add('recording');
          btn.innerHTML = '🔴';
        }
      },

      stopRecording() {
        this.isRecording = false;
        if (this.recognition) {
          this.recognition.stop();
        }

        const btn = document.getElementById('voiceInputBtn');
        if (btn) {
          btn.classList.remove('recording');
          btn.innerHTML = '🎤';
        }

        this.hideTranscriptPanel();

        // Send the transcript as a message
        if (this.transcript.trim()) {
          const input = document.getElementById('userInput');
          if (input) {
            input.value = this.transcript;
            sendMessage();
          }
        }
      },

      toggleRecording() {
        if (this.isRecording) {
          this.stopRecording();
        } else {
          this.startRecording();
        }
      },

      showTranscriptPanel() {
        let panel = document.getElementById('voiceTranscript');
        if (!panel) {
          panel = document.createElement('div');
          panel.id = 'voiceTranscript';
          panel.className = 'voice-transcript';
          panel.innerHTML = `
            <div class="voice-transcript-text" id="voiceTranscriptText">Listening...</div>
            <div class="voice-transcript-hint">🎤 Speak naturally. Click mic again to send.</div>
          `;
          const inputContainer = document.querySelector('.input-container');
          if (inputContainer) {
            inputContainer.style.position = 'relative';
            inputContainer.appendChild(panel);
          }
        }
        panel.classList.add('active');
      },

      hideTranscriptPanel() {
        const panel = document.getElementById('voiceTranscript');
        if (panel) {
          panel.classList.remove('active');
        }
      },

      updateTranscriptDisplay(text, isInterim) {
        const display = document.getElementById('voiceTranscriptText');
        if (display) {
          display.textContent = text || 'Listening...';
          display.style.opacity = isInterim ? '0.7' : '1';
        }
      }
    };

    // Smart Nudge System
    const SmartNudgeSystem = {
      lastActivityTime: Date.now(),
      nudgeTimeout: null,
      currentNudge: null,

      init() {
        // Track user activity
        ['mousemove', 'keydown', 'scroll', 'click'].forEach(event => {
          document.addEventListener(event, () => this.resetIdleTimer());
        });

        this.startIdleCheck();
      },

      resetIdleTimer() {
        this.lastActivityTime = Date.now();
      },

      startIdleCheck() {
        setInterval(() => {
          const idleTime = Date.now() - this.lastActivityTime;

          // Show nudge after 30 seconds of inactivity
          if (idleTime > 30000 && !this.currentNudge) {
            this.showIdleNudge();
          }
        }, 10000);
      },

      showIdleNudge() {
        const nudges = [
          {
            icon: '💡',
            title: 'Need help?',
            message: 'I noticed you paused. Would you like me to explain something differently?',
            primaryAction: { label: 'Yes, help me', value: 'help_me' },
            secondaryAction: { label: 'I\'m fine', value: 'dismiss' }
          },
          {
            icon: '🤔',
            title: 'Stuck on something?',
            message: 'Feel free to ask any question, or I can guide you step by step.',
            primaryAction: { label: 'Guide me', value: 'guide_me' },
            secondaryAction: { label: 'Just thinking', value: 'dismiss' }
          }
        ];

        const nudge = nudges[Math.floor(Math.random() * nudges.length)];
        this.showNudge(nudge);
      },

      showOpportunityNudge(opportunity) {
        this.showNudge({
          icon: '💰',
          title: 'Quick tip!',
          message: opportunity.message,
          primaryAction: { label: 'Tell me more', value: opportunity.action },
          secondaryAction: { label: 'Maybe later', value: 'dismiss' }
        });
      },

      showNudge(config) {
        // Remove existing nudge
        this.dismissNudge();

        const nudge = document.createElement('div');
        nudge.className = 'smart-nudge';
        nudge.id = 'smartNudge';
        nudge.innerHTML = `
          <button class="smart-nudge-close" onclick="SmartNudgeSystem.dismissNudge()">&times;</button>
          <div class="smart-nudge-icon">${config.icon}</div>
          <div class="smart-nudge-title">${config.title}</div>
          <div class="smart-nudge-message">${config.message}</div>
          <div class="smart-nudge-actions">
            <button class="smart-nudge-btn primary" onclick="SmartNudgeSystem.handleNudgeAction('${config.primaryAction.value}')">${config.primaryAction.label}</button>
            <button class="smart-nudge-btn secondary" onclick="SmartNudgeSystem.handleNudgeAction('${config.secondaryAction.value}')">${config.secondaryAction.label}</button>
          </div>
        `;

        document.body.appendChild(nudge);
        this.currentNudge = nudge;

        // Auto dismiss after 15 seconds
        this.nudgeTimeout = setTimeout(() => this.dismissNudge(), 15000);
      },

      dismissNudge() {
        if (this.currentNudge) {
          this.currentNudge.remove();
          this.currentNudge = null;
        }
        if (this.nudgeTimeout) {
          clearTimeout(this.nudgeTimeout);
        }
        this.lastActivityTime = Date.now();
      },

      handleNudgeAction(action) {
        this.dismissNudge();

        if (action === 'dismiss') return;

        // Trigger action in chat
        const actionMessages = {
          'help_me': 'I need help understanding this',
          'guide_me': 'Please guide me step by step'
        };

        const message = actionMessages[action] || action;
        const input = document.getElementById('userInput');
        if (input) {
          input.value = message;
          sendMessage();
        }
      }
    };

    // Emotion Detection System
    const EmotionDetector = {
      patterns: {
        frustrated: [
          /this (is |isn't |doesn't |does not )?(not |so )?work/i,
          /i('m| am) (so )?(confused|frustrated|lost|stuck)/i,
          /i don't (understand|get it|know)/i,
          /what(\?|!)+ *$/i,
          /ugh|argh|wtf|wth/i,
          /help!+/i
        ],
        confused: [
          /what does (that|this) mean/i,
          /i('m| am) not sure/i,
          /can you explain/i,
          /\?{2,}/,
          /huh\??/i
        ],
        anxious: [
          /worried|nervous|scared|afraid/i,
          /audit/i,
          /penalty|penalties/i,
          /am i (doing|getting) (this|it) right/i,
          /is this (correct|right|ok|okay)/i
        ],
        excited: [
          /wow|amazing|awesome|great|fantastic/i,
          /!{2,}/,
          /that's (so )?(cool|great|awesome)/i,
          /really\?!?/i
        ],
        rushed: [
          /quick(ly)?|fast|hurry|asap/i,
          /don't have (much )?time/i,
          /in a (rush|hurry)/i,
          /just (tell|give) me/i
        ]
      },

      detect(message) {
        for (const [emotion, patterns] of Object.entries(this.patterns)) {
          if (patterns.some(pattern => pattern.test(message))) {
            return emotion;
          }
        }
        return 'neutral';
      },

      getResponseModifier(emotion) {
        const modifiers = {
          frustrated: {
            prefix: "I completely understand - let me make this simpler. ",
            tone: "empathetic",
            style: "Use very simple language, be extra patient and supportive"
          },
          confused: {
            prefix: "Let me explain this more clearly. ",
            tone: "reassuring",
            style: "Break down into simple steps, use analogies"
          },
          anxious: {
            prefix: "Don't worry - you're doing great! ",
            tone: "reassuring",
            style: "Be calming, emphasize accuracy and safety"
          },
          excited: {
            prefix: "",
            tone: "encouraging",
            style: "Match their enthusiasm, celebrate with them"
          },
          rushed: {
            prefix: "Got it - here's the quick version: ",
            tone: "neutral",
            style: "Be concise, prioritize key information"
          },
          neutral: {
            prefix: "",
            tone: "neutral",
            style: "Normal helpful tone"
          }
        };
        return modifiers[emotion] || modifiers.neutral;
      }
    };

    // Streaming Response Simulator
    // (For real streaming, backend needs to support SSE/WebSocket)
    const StreamingDisplay = {
      async displayStreamingResponse(container, fullText, quickActions = []) {
        const bubble = container.querySelector('.bubble');
        if (!bubble) return;

        // Add streaming cursor
        const cursor = document.createElement('span');
        cursor.className = 'streaming-cursor';

        const textSpan = document.createElement('span');
        textSpan.className = 'streaming-text';

        // Clear existing content except copy button
        const copyBtn = bubble.querySelector('.copy-btn');
        const timestamp = bubble.querySelector('.message-time');
        bubble.innerHTML = '';
        bubble.appendChild(textSpan);
        bubble.appendChild(cursor);

        // Stream text character by character
        const words = fullText.split(' ');
        let currentText = '';

        for (let i = 0; i < words.length; i++) {
          currentText += (i > 0 ? ' ' : '') + words[i];
          textSpan.innerHTML = currentText;

          // Scroll to bottom
          const messages = document.getElementById('messages');
          if (messages) {
            messages.scrollTop = messages.scrollHeight;
          }

          // Variable delay for more natural feel
          await new Promise(resolve => setTimeout(resolve, 20 + Math.random() * 30));
        }

        // Remove cursor, restore full content
        cursor.remove();
        bubble.innerHTML = fullText;

        // Re-add copy button and timestamp
        if (copyBtn) bubble.appendChild(copyBtn);
        if (timestamp) bubble.appendChild(timestamp);

        // Add quick actions if any
        if (quickActions.length > 0) {
          // Quick actions will be added by the main addMessage function
        }
      }
    };

    // Live Savings Display
    const LiveSavingsDisplay = {
      currentAmount: 0,
      targetAmount: 0,
      displayElement: null,

      init() {
        // Create the floating display if it doesn't exist
        if (!document.getElementById('liveSavingsDisplay')) {
          const display = document.createElement('div');
          display.id = 'liveSavingsDisplay';
          display.className = 'live-savings-display';
          display.style.display = 'none';
          display.innerHTML = `
            <div class="live-savings-label">Potential Savings</div>
            <div class="live-savings-amount" id="liveSavingsAmount">$0</div>
          `;
          document.body.appendChild(display);
        }
        this.displayElement = document.getElementById('liveSavingsDisplay');
      },

      update(amount) {
        if (!this.displayElement) this.init();

        if (amount > 0) {
          this.displayElement.style.display = 'block';
          this.animateToAmount(amount);
        }
      },

      animateToAmount(target) {
        const amountEl = document.getElementById('liveSavingsAmount');
        if (!amountEl) return;

        const start = this.currentAmount;
        const diff = target - start;
        const duration = 1000;
        const startTime = performance.now();

        const animate = (currentTime) => {
          const elapsed = currentTime - startTime;
          const progress = Math.min(elapsed / duration, 1);

          // Ease out cubic
          const eased = 1 - Math.pow(1 - progress, 3);
          const current = Math.round(start + diff * eased);

          amountEl.textContent = '$' + current.toLocaleString();
          amountEl.classList.add('counting');

          if (progress < 1) {
            requestAnimationFrame(animate);
          } else {
            this.currentAmount = target;
            amountEl.classList.remove('counting');
          }
        };

        requestAnimationFrame(animate);
      }
    };

    // Photo Document Capture System
    const PhotoCapture = {
      stream: null,
      video: null,

      async open() {
        const modal = document.getElementById('photoCaptureModal');
        this.video = document.getElementById('cameraVideo');

        if (!modal || !this.video) return;

        try {
          this.stream = await navigator.mediaDevices.getUserMedia({
            video: {
              facingMode: 'environment', // Use back camera on mobile
              width: { ideal: 1920 },
              height: { ideal: 1080 }
            }
          });

          this.video.srcObject = this.stream;
          modal.classList.add('active');

        } catch (error) {
          DevLogger.error('Camera access error:', error);
          if (error.name === 'NotAllowedError') {
            showToast('Please allow camera access to capture documents', 'warning');
          } else {
            showToast('Unable to access camera. Please upload instead.', 'error');
          }
        }
      },

      close() {
        const modal = document.getElementById('photoCaptureModal');
        if (modal) {
          modal.classList.remove('active');
        }

        if (this.stream) {
          this.stream.getTracks().forEach(track => track.stop());
          this.stream = null;
        }
      },

      async capture() {
        if (!this.video) return;

        // Create canvas to capture frame
        const canvas = document.createElement('canvas');
        canvas.width = this.video.videoWidth;
        canvas.height = this.video.videoHeight;

        const ctx = canvas.getContext('2d');
        ctx.drawImage(this.video, 0, 0);

        // Convert to blob
        canvas.toBlob(async (blob) => {
          if (!blob) {
            showToast('Failed to capture image', 'error');
            return;
          }

          // Close camera
          this.close();

          // Show processing toast
          showToast('Processing document...', 'info');

          // Create form data and upload
          const formData = new FormData();
          formData.append('file', blob, 'captured_document.jpg');
          formData.append('session_id', sessionId || 'temp-session');

          try {
            // SECURITY: Use secureFetch for CSRF protection
            const response = await secureFetch('/api/advisor/upload-document', {
              method: 'POST',
              body: formData
            });

            const result = await response.json();

            if (result.success) {
              // Celebrate successful capture
              CelebrationSystem.createSparkles(window.innerWidth / 2, window.innerHeight / 2, 8);
              showToast('Document captured successfully!', 'success');

              // Add message about extracted data
              addMessage('ai', `📄 **Document Captured!**\n\nI detected a **${result.document_type || 'tax document'}** and extracted the following:\n\n${
                Object.entries(result.extracted_fields || {})
                  .slice(0, 5)
                  .map(([key, value]) => `• ${key}: **${value}**`)
                  .join('\n')
              }\n\nIs this information correct?`, [
                { label: '✓ Yes, looks good', value: 'document_confirmed' },
                { label: 'Make corrections', value: 'document_corrections' },
                { label: 'Capture another', value: 'capture_another' }
              ]);

            } else {
              showToast(result.message || 'Could not process document', 'warning');
              addMessage('ai', `I had trouble reading that document. Would you like to try again or enter the information manually?`, [
                { label: 'Try again', value: 'capture_another' },
                { label: 'Enter manually', value: 'enter_manually' }
              ]);
            }

          } catch (error) {
            DevLogger.error('Document upload error:', error);
            showToast('Failed to upload document', 'error');
          }

        }, 'image/jpeg', 0.9);
      }
    };

    // Initialize UX enhancements
    function initUXEnhancements() {
      SmartNudgeSystem.init();
      LiveSavingsDisplay.init();
      VoiceInputSystem.init();

      DevLogger.log('UX enhancements initialized');
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', initUXEnhancements);

    // Toast notification function for user feedback
    function showToast(message, type = 'info') {
      // Remove any existing toast
      const existingToast = document.querySelector('.toast-notification');
      if (existingToast) existingToast.remove();

      const toast = document.createElement('div');
      toast.className = 'toast-notification toast-' + type;
      toast.style.cssText = `
        position: fixed;
        bottom: 100px;
        left: 50%;
        transform: translateX(-50%);
        padding: 12px 24px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 10000;
        animation: slideUp 0.3s ease;
        max-width: 90%;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      `;

      // Style based on type
      if (type === 'error') {
        toast.style.background = '#ef4444';
      } else if (type === 'warning') {
        toast.style.background = '#f59e0b';
      } else if (type === 'success') {
        toast.style.background = '#10b981';
      } else {
        toast.style.background = '#5387c1';
      }

      toast.textContent = message;
      document.body.appendChild(toast);

      // Auto-remove after 4 seconds
      setTimeout(() => {
        toast.style.animation = 'slideDown 0.3s ease';
        setTimeout(() => toast.remove(), 300);
      }, 4000);
    }

    // Consent is now handled by the unified advisor consent modal (see top of file)

    // ============ CONNECTION STATUS ============
    function updateConnectionStatus(online) {
      const statusEl = document.getElementById('connectionStatus');
      const textEl = document.getElementById('connectionText');
      const dotEl = document.getElementById('connectionDot');

      if (online) {
        statusEl.classList.remove('offline');
        textEl.textContent = 'Connected';
        dotEl.style.background = 'var(--accent)';
      } else {
        statusEl.classList.add('offline');
        textEl.textContent = 'Offline';
        dotEl.style.background = '#ef4444';
        showToast('You appear to be offline. Messages will be sent when connection is restored.', 'warning');
      }
    }

    // Monitor connection status
    window.addEventListener('online', () => {
      updateConnectionStatus(true);
      hideOfflineBanner();
      showToast('Connection restored!', 'success');
    });

    window.addEventListener('offline', () => {
      updateConnectionStatus(false);
      showOfflineBanner();
    });

    // Periodic health check
    let healthCheckInterval = null;
    function startHealthCheck() {
      healthCheckInterval = setInterval(async () => {
        try {
          const response = await fetch('/api/health', {
            method: 'GET',
            cache: 'no-store',
            signal: AbortSignal.timeout(5000)
          });
          if (response.ok) {
            updateConnectionStatus(true);
          } else {
            updateConnectionStatus(false);
          }
        } catch (e) {
          // Don't mark as offline for network errors if we're still online per browser
          if (!navigator.onLine) {
            updateConnectionStatus(false);
          }
        }
      }, 30000); // Every 30 seconds
    }

    // ============ JOURNEY STEPPER MANAGEMENT ============
    let currentJourneyStep = 1;
    const journeySteps = {
      1: { name: 'Profile', icon: 'clipboard-document-list' },
      2: { name: 'Income', icon: 'currency-dollar' },
      3: { name: 'Analysis', icon: 'sparkles' },
      4: { name: 'Report', icon: 'chart-bar' }
    };

    function updateJourneyStep(stepNumber) {
      if (stepNumber < 1 || stepNumber > 4) return;

      currentJourneyStep = stepNumber;

      // Update all step indicators
      for (let i = 1; i <= 4; i++) {
        const stepEl = document.getElementById(`step-${i}`);
        if (!stepEl) continue;

        const stepIconEl = stepEl.querySelector('.step-icon');
        stepEl.classList.remove('active', 'completed');

        if (i < stepNumber) {
          // Completed steps show checkmark
          stepEl.classList.add('completed');
          stepIconEl.innerHTML = getIcon('check', 'md');
        } else if (i === stepNumber) {
          // Active step
          stepEl.classList.add('active');
          stepIconEl.innerHTML = getIcon(journeySteps[i].icon, 'md');
        } else {
          // Future steps show original icon
          stepIconEl.innerHTML = getIcon(journeySteps[i].icon, 'md');
        }
      }
    }

    function advanceJourneyBasedOnData() {
      // Determine step based on extracted data
      if (extractedData.lead_data.ready_for_cpa || taxCalculations) {
        updateJourneyStep(4);
      } else if (extractedData.tax_profile.total_income && extractedData.tax_profile.filing_status) {
        updateJourneyStep(3);
      } else if (extractedData.tax_profile.filing_status) {
        updateJourneyStep(2);
      } else {
        updateJourneyStep(1);
      }
    }

    // ============ LOADING OVERLAY MANAGEMENT ============
    function showLoadingOverlay(text = 'Analyzing your tax situation...', subtext = 'This may take a few moments') {
      const overlay = document.getElementById('loadingOverlay');
      const textEl = document.getElementById('loadingText');
      const subtextEl = document.getElementById('loadingSubtext');

      if (overlay) {
        textEl.textContent = text;
        subtextEl.textContent = subtext;
        overlay.classList.add('active');
      }
    }

    function hideLoadingOverlay() {
      const overlay = document.getElementById('loadingOverlay');
      if (overlay) {
        overlay.classList.remove('active');
      }
    }

    // ============ OFFLINE BANNER MANAGEMENT ============
    function showOfflineBanner() {
      const banner = document.getElementById('offlineBanner');
      if (banner) {
        banner.classList.add('active');
      }
    }

    function hideOfflineBanner() {
      const banner = document.getElementById('offlineBanner');
      if (banner) {
        banner.classList.remove('active');
      }
    }

    // ============ ERROR BANNER IN MESSAGES ============
    function showErrorBanner(title, message, retryAction = null) {
      const messages = document.getElementById('messages');
      if (!messages) return;

      const errorDiv = document.createElement('div');
      errorDiv.className = 'error-banner';
      errorDiv.id = 'currentErrorBanner';
      errorDiv.innerHTML = `
        <span class="error-icon">⚠️</span>
        <div class="error-content">
          <div class="error-title">${title}</div>
          <div class="error-message">${message}</div>
          ${retryAction ? `<button class="retry-btn" onclick="${retryAction}">Try Again</button>` : ''}
        </div>
      `;

      messages.appendChild(errorDiv);
      messages.scrollTop = messages.scrollHeight;
    }

    function clearErrorBanner() {
      const errorBanner = document.getElementById('currentErrorBanner');
      if (errorBanner) {
        errorBanner.remove();
      }
    }

    // ============ SUCCESS BANNER ============
    function showSuccessBanner(message) {
      const messages = document.getElementById('messages');
      if (!messages) return;

      const successDiv = document.createElement('div');
      successDiv.className = 'success-banner';
      successDiv.innerHTML = `<span>✅</span> <span>${message}</span>`;

      messages.appendChild(successDiv);
      messages.scrollTop = messages.scrollHeight;

      // Auto-remove after 5 seconds
      setTimeout(() => successDiv.remove(), 5000);
    }

    // ============ CLEAR CONVERSATION ============
    function clearConversation() {
      if (!confirm('Start a new conversation? This will clear your current session.')) {
        return;
      }

      // Clear session storage
      sessionStorage.removeItem('tax_session_id');
      sessionStorage.removeItem('tax_data_consent');
      sessionStorage.removeItem('tax_consent_timestamp');

      // Reload page to reset everything
      window.location.reload();
    }

    // Initialize session
    async function initializeSession() {
      DevLogger.log('initializeSession called');

      // Static greeting is already in HTML, just create session
      try {
        DevLogger.log('Creating session...');
        // SECURITY: Use secureFetch for CSRF protection
        const response = await secureFetch('/api/sessions/create-session', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workflow_type: 'intelligent_conversational',
            tax_year: 2025
          })
        });

        const data = await response.json();
        sessionId = data.session_id;
        sessionStorage.setItem('tax_session_id', sessionId);
        DevLogger.log('Session initialized:', sessionId);
      } catch (error) {
        DevLogger.error('Session initialization error:', error);
        // Continue without session - will be created on first message
      }
    }

    async function sendInitialGreeting() {
      DevLogger.log('sendInitialGreeting called');

      // Clean post-login greeting - leads to full robust chatbot
      addMessage('ai', `<div style="margin-bottom: var(--space-4);">
        <span style="font-size: var(--text-2xl); font-weight: var(--font-bold); color: var(--primary);">Welcome to Your Tax Advisory Session</span>
      </div>
      I'm your AI-powered tax strategist ready to help you <strong>maximize your savings</strong>.<br><br>
      <div style="display: grid; gap: var(--space-3); margin: var(--space-4) 0;">
        <div style="display: flex; align-items: center; gap: var(--space-2-5); padding: var(--space-3); background: rgba(26, 54, 93, 0.05); border-radius: var(--radius-lg);">
          ${getIcon('document-text', 'md')}
          <div>
            <strong>Upload Documents</strong> - I'll extract data from your W-2s, 1099s automatically
          </div>
        </div>
        <div style="display: flex; align-items: center; gap: var(--space-2-5); padding: var(--space-3); background: rgba(26, 54, 93, 0.05); border-radius: var(--radius-lg);">
          ${getIcon('chat-bubble-left-right', 'md')}
          <div>
            <strong>Answer Questions</strong> - Smart guided conversation with AI assistance
          </div>
        </div>
      </div>
      <strong>How would you like to start?</strong>`, [
        { label: getIcon('document-text', 'sm') + ' Upload My Documents', value: 'yes_upload', primary: true },
        { label: getIcon('chat-bubble-left-right', 'sm') + ' Answer Questions', value: 'no_manual' }
      ]);
      DevLogger.log('Initial greeting added');
    }

    // Calculate confidence level based on data completeness
    function getConfidenceLevel() {
      let score = 0;
      let maxScore = 100;

      if (extractedData.filing_status) score += 15;
      if (extractedData.income_range || extractedData.tax_profile?.total_income) score += 20;
      if (extractedData.deductions && extractedData.deductions.length > 0) score += 15;
      if (extractedData.credits && extractedData.credits.length > 0) score += 15;
      if (extractedData.contact?.name) score += 5;
      if (extractedData.documents && extractedData.documents.length > 0) score += 20;
      if (extractedData.focus_area) score += 10;

      const percentage = Math.round((score / maxScore) * 100);

      if (percentage >= 70) return { level: 'high', percentage, label: 'High confidence' };
      if (percentage >= 40) return { level: 'medium', percentage, label: 'Moderate confidence' };
      return { level: 'low', percentage, label: 'Limited data' };
    }

    // Generate confidence disclaimer for AI messages
    function getConfidenceDisclaimer(includeIRS = false) {
      const confidence = getConfidenceLevel();
      let disclaimer = '';

      if (confidence.level === 'high') {
        disclaimer = `<div class="confidence-indicator confidence-high">
          <span>${getIcon('check-circle', 'sm')} ${confidence.label} (${confidence.percentage}% data)</span>
          <span style="margin-left: auto; font-size: var(--text-2xs);">Verify with a tax professional before filing</span>
        </div>`;
      } else if (confidence.level === 'medium') {
        disclaimer = `<div class="confidence-indicator confidence-medium">
          <span>${getIcon('exclamation-triangle', 'sm')} ${confidence.label} (${confidence.percentage}% data)</span>
          <span style="margin-left: auto; font-size: var(--text-2xs);">Provide more details for better accuracy</span>
        </div>`;
      } else {
        disclaimer = `<div class="confidence-indicator confidence-low">
          <span>${getIcon('information-circle', 'sm')} ${confidence.label} (${confidence.percentage}% data)</span>
          <span style="margin-left: auto; font-size: var(--text-2xs);">General guidance only - more info needed</span>
        </div>`;
      }

      if (includeIRS) {
        disclaimer += `<div style="font-size: var(--text-2xs); color: var(--text-secondary); margin-top: var(--space-2);">
          ${getIcon('clipboard-document-list', 'sm')} Based on 2025 IRS guidelines. See <a href="https://www.irs.gov/forms-instructions" target="_blank" rel="noopener" style="color: var(--primary);">IRS.gov</a> for official forms.
        </div>`;
      }

      return disclaimer;
    }

    // Render confidence badge for API response-level confidence
    function renderConfidenceBadge(confidence, reason) {
      if (!confidence || confidence === 'high') {
        // Don't show badge for high confidence (default)
        return '';
      }

      const badges = {
        high: { label: 'High Confidence', className: 'high' },
        medium: { label: 'Moderate Confidence', className: 'medium' },
        low: { label: 'Limited Data', className: 'low' }
      };

      const badge = badges[confidence] || badges.medium;
      const tooltipAttr = reason ? ` title="${reason}"` : '';

      return `<div class="confidence-badge ${badge.className}"${tooltipAttr} style="margin-top: var(--space-3);">
        <span class="confidence-dot"></span>
        <span>${badge.label}</span>
        ${reason ? `<span style="font-size: 10px; opacity: 0.8; margin-left: var(--space-1);">${reason}</span>` : ''}
      </div>`;
    }

    function addMessage(type, text, quickActions = [], options = {}) {
      DevLogger.log('====== addMessage CALLED ======');
      DevLogger.log('Type:', type);
      DevLogger.log('Text preview:', text.substring(0, 50));
      DevLogger.log('Quick actions count:', quickActions.length);

      // Mark session as having unsaved changes when user sends a message
      if (type === 'user' && typeof markUnsaved === 'function') {
        markUnsaved();
      }

      const messages = document.getElementById('messages');
      DevLogger.log('Messages container found:', !!messages);

      if (!messages) {
        DevLogger.error('Messages container not found!');
        showToast('Error displaying message', 'error');
        return;
      }

      const messageDiv = document.createElement('div');
      messageDiv.className = `message ${type}`;
      messageDiv.setAttribute('role', 'article');
      messageDiv.setAttribute('aria-label', type === 'ai' ? 'AI assistant message' : 'Your message');

      const avatar = document.createElement('div');
      avatar.className = 'avatar';
      avatar.setAttribute('aria-hidden', 'true');
      avatar.innerHTML = type === 'ai' ? getIcon('briefcase', 'md') : getIcon('user', 'md');

      const bubble = document.createElement('div');
      bubble.className = 'bubble';

      // Only add confidence indicator when explicitly requested (not on every message)
      if (type === 'ai' && options.showConfidence === true) {
        const includeIRS = options.includeIRS || false;
        text += getConfidenceDisclaimer(includeIRS);
      }

      // Sanitize HTML to prevent XSS from API responses
      if (type === 'ai') {
        const sanitized = text
          .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
          .replace(/on\w+\s*=\s*["'][^"']*["']/gi, '')
          .replace(/javascript\s*:/gi, '')
          .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, '')
          .replace(/<object\b[^<]*(?:(?!<\/object>)<[^<]*)*<\/object>/gi, '')
          .replace(/<embed\b[^>]*>/gi, '')
          .replace(/<form\b[^<]*(?:(?!<\/form>)<[^<]*)*<\/form>/gi, '');
        bubble.innerHTML = sanitized;
      } else {
        bubble.textContent = text;
      }

      // Add copy button for AI messages
      if (type === 'ai') {
        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.innerHTML = getIcon('clipboard-document-list', 'sm') + ' Copy';
        copyBtn.setAttribute('aria-label', 'Copy this message');
        copyBtn.onclick = (e) => {
          e.stopPropagation();
          const textContent = bubble.innerText.replace(/\s*Copy$/, '').trim();
          navigator.clipboard.writeText(textContent).then(() => {
            copyBtn.innerHTML = getIcon('check', 'sm') + ' Copied';
            setTimeout(() => copyBtn.innerHTML = getIcon('clipboard-document-list', 'sm') + ' Copy', 2000);
          });
        };
        bubble.appendChild(copyBtn);
      }

      // Add timestamp
      const timestamp = document.createElement('span');
      timestamp.className = 'message-time';
      const now = new Date();
      const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      timestamp.textContent = timeStr;
      timestamp.setAttribute('aria-label', `Sent at ${timeStr}`);
      bubble.appendChild(timestamp);

      if (quickActions.length > 0) {
        // Check if this is a multi-select question
        const isMultiSelect = options.multiSelect === true;

        if (isMultiSelect) {
          // Render as checkboxes for multi-select
          const actionsDiv = document.createElement('div');
          actionsDiv.className = 'multi-select-actions';
          actionsDiv.setAttribute('role', 'group');
          actionsDiv.setAttribute('aria-label', 'Select all that apply');

          const selectedValues = new Set();

          quickActions.forEach((action, index) => {
            const optionDiv = document.createElement('div');
            optionDiv.className = 'multi-select-option';

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `multi-select-${index}`;
            checkbox.value = action.value;

            const label = document.createElement('label');
            label.htmlFor = `multi-select-${index}`;
            label.textContent = action.label;

            checkbox.onchange = () => {
              if (checkbox.checked) {
                selectedValues.add(action.value);
                optionDiv.classList.add('selected');
              } else {
                selectedValues.delete(action.value);
                optionDiv.classList.remove('selected');
              }
              // Enable/disable submit button
              const submitBtn = actionsDiv.querySelector('.submit-btn');
              if (submitBtn) {
                submitBtn.disabled = selectedValues.size === 0;
              }
            };

            optionDiv.onclick = (e) => {
              if (e.target !== checkbox) {
                checkbox.checked = !checkbox.checked;
                checkbox.dispatchEvent(new Event('change'));
              }
            };

            optionDiv.appendChild(checkbox);
            optionDiv.appendChild(label);
            actionsDiv.appendChild(optionDiv);
          });

          // Add submit and skip buttons
          const submitDiv = document.createElement('div');
          submitDiv.className = 'multi-select-submit';

          const submitBtn = document.createElement('button');
          submitBtn.className = 'submit-btn';
          submitBtn.textContent = 'Continue with Selected';
          submitBtn.disabled = true;
          submitBtn.onclick = () => {
            const selected = Array.from(selectedValues);
            if (selected.length > 0) {
              // Send all selected values as comma-separated
              const labels = quickActions
                .filter(a => selected.includes(a.value))
                .map(a => a.label);
              handleQuickAction(selected.join(','), labels.join(', '));
            }
          };

          const skipBtn = document.createElement('button');
          skipBtn.className = 'skip-btn';
          skipBtn.textContent = 'Skip';
          skipBtn.onclick = () => {
            handleQuickAction('skip_multi_select', 'None selected');
          };

          submitDiv.appendChild(submitBtn);
          submitDiv.appendChild(skipBtn);
          actionsDiv.appendChild(submitDiv);

          bubble.appendChild(actionsDiv);

        } else if (options.inputType === 'radio') {
          // Render as radio buttons for single-select with descriptions
          const actionsDiv = document.createElement('div');
          actionsDiv.className = 'radio-actions';
          actionsDiv.setAttribute('role', 'radiogroup');
          actionsDiv.setAttribute('aria-label', 'Select one option');

          const radioName = `radio-group-${Date.now()}`;
          let selectedValue = null;

          quickActions.forEach((action, index) => {
            const optionDiv = document.createElement('div');
            optionDiv.className = 'radio-option';

            const radio = document.createElement('input');
            radio.type = 'radio';
            radio.name = radioName;
            radio.id = `radio-${radioName}-${index}`;
            radio.value = action.value;

            const contentDiv = document.createElement('div');
            contentDiv.className = 'radio-content';

            const label = document.createElement('label');
            label.htmlFor = radio.id;
            label.textContent = action.label;
            contentDiv.appendChild(label);

            if (action.description) {
              const desc = document.createElement('div');
              desc.className = 'radio-description';
              desc.textContent = action.description;
              contentDiv.appendChild(desc);
            }

            radio.onchange = () => {
              // Remove selected from all options
              actionsDiv.querySelectorAll('.radio-option').forEach(opt => opt.classList.remove('selected'));
              optionDiv.classList.add('selected');
              selectedValue = action.value;
              // Auto-submit after selection (with brief delay for visual feedback)
              setTimeout(() => {
                handleQuickAction(action.value);
              }, 300);
            };

            optionDiv.onclick = (e) => {
              if (e.target !== radio) {
                radio.checked = true;
                radio.dispatchEvent(new Event('change'));
              }
            };

            optionDiv.appendChild(radio);
            optionDiv.appendChild(contentDiv);
            actionsDiv.appendChild(optionDiv);
          });

          bubble.appendChild(actionsDiv);

        } else if (options.inputType === 'dropdown') {
          // Render as dropdown for many options
          const actionsDiv = document.createElement('div');
          actionsDiv.className = 'dropdown-actions';

          const select = document.createElement('select');
          select.className = 'dropdown-select';
          select.setAttribute('aria-label', 'Select an option');

          // Add placeholder option
          const placeholder = document.createElement('option');
          placeholder.value = '';
          placeholder.textContent = options.placeholder || 'Select an option...';
          placeholder.disabled = true;
          placeholder.selected = true;
          select.appendChild(placeholder);

          // Group options if categories provided
          if (options.groups) {
            options.groups.forEach(group => {
              const optgroup = document.createElement('optgroup');
              optgroup.label = group.label;
              group.options.forEach(action => {
                const option = document.createElement('option');
                option.value = action.value;
                option.textContent = action.label;
                optgroup.appendChild(option);
              });
              select.appendChild(optgroup);
            });
          } else {
            quickActions.forEach(action => {
              const option = document.createElement('option');
              option.value = action.value;
              option.textContent = action.label;
              select.appendChild(option);
            });
          }

          actionsDiv.appendChild(select);

          // Add continue button
          const submitDiv = document.createElement('div');
          submitDiv.className = 'dropdown-submit';

          const submitBtn = document.createElement('button');
          submitBtn.textContent = 'Continue →';
          submitBtn.disabled = true;

          select.onchange = () => {
            submitBtn.disabled = !select.value;
          };

          submitBtn.onclick = () => {
            if (select.value) {
              const selectedOption = quickActions.find(a => a.value === select.value);
              handleQuickAction(select.value, selectedOption?.label);
            }
          };

          submitDiv.appendChild(submitBtn);
          actionsDiv.appendChild(submitDiv);

          bubble.appendChild(actionsDiv);

        } else if (options.inputType === 'currency') {
          // Currency input for exact amounts
          const currencyInput = createCurrencyInput(
            options.placeholder || 'Enter amount',
            (value) => {
              addMessage('user', '$' + value.toLocaleString());
              if (options.onSubmit) {
                options.onSubmit(value);
              } else if (options.field) {
                extractedData.tax_profile[options.field] = value;
                updateSavingsEstimate();
                startIntelligentQuestioning();
              }
            }
          );
          bubble.appendChild(currencyInput);

          // Add security notice for financial input
          bubble.appendChild(createSecurityNotice());

        } else if (options.inputType === 'slider') {
          // Slider for ranges
          const slider = createSliderInput(
            options.min || 0,
            options.max || 500000,
            options.step || 5000,
            options.default || (options.max / 2),
            (val) => '$' + val.toLocaleString(),
            (value) => {
              addMessage('user', '$' + value.toLocaleString());
              if (options.onSubmit) {
                options.onSubmit(value);
              } else if (options.field) {
                extractedData.tax_profile[options.field] = value;
                updateSavingsEstimate();
                startIntelligentQuestioning();
              }
            }
          );
          bubble.appendChild(slider);

        } else {
          // Regular single-select buttons (default)
          const actionsDiv = document.createElement('div');
          actionsDiv.className = 'quick-actions';
          actionsDiv.setAttribute('role', 'group');
          actionsDiv.setAttribute('aria-label', 'Quick response options');

          quickActions.forEach((action, index) => {
            const btn = document.createElement('button');
            btn.className = action.primary ? 'quick-action primary' : 'quick-action';
            btn.textContent = action.label;
            btn.setAttribute('aria-label', action.label.replace(/[^\w\s]/g, '').trim());
            btn.onclick = () => handleQuickAction(action.value);
            actionsDiv.appendChild(btn);
          });
          bubble.appendChild(actionsDiv);
        }
      }

      messageDiv.appendChild(avatar);
      messageDiv.appendChild(bubble);
      messages.appendChild(messageDiv);

      DevLogger.log('Message added successfully. Total messages now:', messages.children.length);

      messages.scrollTop = messages.scrollHeight;
      return messageDiv;
    }

    function showTyping() {
      const messages = document.getElementById('messages');
      const typing = document.createElement('div');
      typing.className = 'message ai';
      typing.id = 'typing-indicator';
      typing.setAttribute('role', 'status');
      typing.setAttribute('aria-live', 'polite');
      typing.setAttribute('aria-label', 'AI assistant is typing a response');
      typing.innerHTML = `
        <div class="avatar" aria-hidden="true">💼</div>
        <div class="bubble">
          <div class="typing-indicator" role="img" aria-label="Typing">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span class="sr-only">Please wait, the assistant is preparing a response...</span>
        </div>
      `;
      messages.appendChild(typing);
      messages.scrollTop = messages.scrollHeight;
    }

    function hideTyping() {
      const typing = document.getElementById('typing-indicator');
      if (typing) typing.remove();
    }

    async function sendMessage() {
      const input = document.getElementById('userInput');
      let text = input.value.trim();

      // Basic checks
      if (!text || isProcessing) return;

      // Sanitize input
      text = sanitizeInput(text);

      // Validate message
      const validation = validateMessage(text);
      if (!validation.valid) {
        showToast(validation.errors[0], 'warning');
        return;
      }

      // Check rate limit
      const rateCheck = checkRateLimit();
      if (!rateCheck.allowed) {
        showToast(rateCheck.reason, 'warning');
        return;
      }

      // Check network status
      if (!isOnline) {
        addMessage('user', text);
        queueOfflineMessage(text);
        input.value = '';
        input.style.height = 'auto';
        return;
      }

      // Process message
      addMessage('user', text);
      input.value = '';
      input.style.height = 'auto';

      // Update activity timestamp
      updateLastActivity();

      await processAIResponse(text);
    }

    // =========================================================================
    // UX ENHANCEMENT HELPERS
    // =========================================================================

    // Create tooltip with help text
    function createTooltip(text, helpText) {
      return `<span class="tooltip-trigger">${text}<span class="tooltip-icon">?</span><span class="tooltip-content">${helpText}</span></span>`;
    }

    // Update real-time savings estimate
    function updateSavingsEstimate() {
      const profile = extractedData.tax_profile || {};
      const income = profile.total_income || 0;

      // Remove existing estimate
      const existing = document.querySelector('.savings-estimate');
      if (existing) existing.remove();

      // Only show if we have some data
      if (!income && !extractedData.filing_status) return;

      // Calculate estimated savings based on profile
      let minSavings = 500;
      let maxSavings = 2000;
      let details = [];

      if (income > 0) {
        if (income > 200000) {
          minSavings = 5000; maxSavings = 25000;
          details.push('High-income strategies');
        } else if (income > 100000) {
          minSavings = 3000; maxSavings = 12000;
          details.push('Upper-bracket optimization');
        } else if (income > 50000) {
          minSavings = 1500; maxSavings = 6000;
          details.push('Middle-income deductions');
        }
      }

      if (profile.is_self_employed || profile.income_source === 'self_employed') {
        minSavings += 2000; maxSavings += 8000;
        details.push('Self-employment deductions');
      }

      if (profile.has_home_office) {
        minSavings += 500; maxSavings += 3000;
        details.push('Home office deduction');
      }

      if (profile.has_rental_income) {
        minSavings += 1000; maxSavings += 5000;
        details.push('Rental property benefits');
      }

      if (profile.dependents > 0) {
        minSavings += profile.dependents * 500;
        maxSavings += profile.dependents * 2000;
        details.push('Child/dependent credits');
      }

      // Create savings card
      const savingsCard = document.createElement('div');
      savingsCard.className = 'savings-estimate';
      savingsCard.innerHTML = `
        <div class="savings-estimate-label">Estimated Annual Savings</div>
        <div class="savings-estimate-amount">
          $${minSavings.toLocaleString()}<span class="range"> - $${maxSavings.toLocaleString()}</span>
        </div>
        ${details.length > 0 ? `<div class="savings-estimate-details">${details.slice(0, 2).join(' • ')}</div>` : ''}
      `;

      document.body.appendChild(savingsCard);
    }

    // Create currency input with formatting
    function createCurrencyInput(placeholder = 'Enter amount', onSubmit) {
      const wrapper = document.createElement('div');
      wrapper.className = 'currency-input-wrapper';
      wrapper.style.marginTop = '16px';

      const symbol = document.createElement('span');
      symbol.className = 'currency-symbol';
      symbol.textContent = '$';

      const input = document.createElement('input');
      input.type = 'text';
      input.className = 'currency-input';
      input.placeholder = placeholder;
      input.inputMode = 'numeric';

      // Format as user types
      input.addEventListener('input', (e) => {
        let value = e.target.value.replace(/[^\d]/g, '');
        if (value) {
          e.target.value = parseInt(value).toLocaleString();
        }
      });

      // Submit on Enter
      input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && input.value) {
          const numValue = parseInt(input.value.replace(/[^\d]/g, ''));
          if (onSubmit) onSubmit(numValue);
        }
      });

      wrapper.appendChild(symbol);
      wrapper.appendChild(input);

      // Add submit button
      const submitDiv = document.createElement('div');
      submitDiv.className = 'dropdown-submit';

      const submitBtn = document.createElement('button');
      submitBtn.textContent = 'Continue →';
      submitBtn.onclick = () => {
        if (input.value) {
          const numValue = parseInt(input.value.replace(/[^\d]/g, ''));
          if (onSubmit) onSubmit(numValue);
        }
      };

      submitDiv.appendChild(submitBtn);

      const container = document.createElement('div');
      container.appendChild(wrapper);
      container.appendChild(submitDiv);

      return container;
    }

    // Create slider input for ranges
    function createSliderInput(min, max, step, defaultValue, formatFn, onSubmit) {
      const wrapper = document.createElement('div');
      wrapper.className = 'slider-input-wrapper';

      const display = document.createElement('div');
      display.className = 'slider-value-display';
      display.textContent = formatFn(defaultValue);

      const slider = document.createElement('input');
      slider.type = 'range';
      slider.className = 'slider-input';
      slider.min = min;
      slider.max = max;
      slider.step = step;
      slider.value = defaultValue;

      slider.addEventListener('input', () => {
        display.textContent = formatFn(parseInt(slider.value));
      });

      const labels = document.createElement('div');
      labels.className = 'slider-labels';
      labels.innerHTML = `<span>${formatFn(min)}</span><span>${formatFn(max)}</span>`;

      wrapper.appendChild(display);
      wrapper.appendChild(slider);
      wrapper.appendChild(labels);

      // Add submit button
      const submitDiv = document.createElement('div');
      submitDiv.className = 'dropdown-submit';
      submitDiv.style.textAlign = 'center';

      const submitBtn = document.createElement('button');
      submitBtn.textContent = 'Confirm Amount →';
      submitBtn.onclick = () => {
        if (onSubmit) onSubmit(parseInt(slider.value));
      };

      submitDiv.appendChild(submitBtn);
      wrapper.appendChild(submitDiv);

      return wrapper;
    }

    // Create quick-edit panel for collected data
    function createQuickEditPanel() {
      const profile = extractedData.tax_profile || {};
      const items = [];

      if (extractedData.filing_status) {
        items.push({ label: 'Filing Status', value: extractedData.filing_status, field: 'filing_status' });
      }
      if (profile.total_income) {
        items.push({ label: 'Income', value: '$' + profile.total_income.toLocaleString(), field: 'total_income' });
      }
      if (profile.state) {
        items.push({ label: 'State', value: profile.state, field: 'state' });
      }
      if (profile.dependents !== undefined) {
        items.push({ label: 'Dependents', value: profile.dependents, field: 'dependents' });
      }

      if (items.length === 0) return null;

      const panel = document.createElement('div');
      panel.className = 'quick-edit-panel';

      let html = `
        <div class="quick-edit-header">
          <span class="quick-edit-title">📋 Your Information</span>
          <span class="quick-edit-toggle" onclick="toggleQuickEdit()">Edit</span>
        </div>
      `;

      items.forEach(item => {
        html += `
          <div class="quick-edit-item" onclick="editField('${item.field}')">
            <span class="quick-edit-label">${item.label}</span>
            <span class="quick-edit-value">
              ${item.value}
              <span class="edit-icon">✏️</span>
            </span>
          </div>
        `;
      });

      panel.innerHTML = html;
      return panel;
    }

    // Toggle quick edit panel between view and edit mode
    function toggleQuickEdit() {
      const panel = document.querySelector('.quick-edit-panel');
      if (!panel) return;

      const isEditing = panel.classList.contains('edit-mode');

      if (isEditing) {
        // Switch to view mode
        panel.classList.remove('edit-mode');
        const toggle = panel.querySelector('.quick-edit-toggle');
        if (toggle) toggle.textContent = 'Edit';
        // Re-enable items
        panel.querySelectorAll('.quick-edit-item').forEach(item => {
          item.style.pointerEvents = 'auto';
          item.style.opacity = '1';
        });
      } else {
        // Switch to edit mode
        panel.classList.add('edit-mode');
        const toggle = panel.querySelector('.quick-edit-toggle');
        if (toggle) toggle.textContent = 'Done';
        // Show edit hints
        showToast('Click any field to edit it', 'info');
      }
    }

    // Edit a specific field
    function editField(field) {
      const fieldLabels = {
        'filing_status': 'filing status',
        'total_income': 'income',
        'state': 'state',
        'dependents': 'number of dependents'
      };

      const message = `I'd like to change my ${fieldLabels[field] || field}`;
      addMessage('user', message);
      processAIResponse(message);
    }

    // Add keyboard navigation support
    function initKeyboardNavigation() {
      document.addEventListener('keydown', (e) => {
        // Focus input on any letter key if not already focused
        const input = document.getElementById('userInput');
        if (input && document.activeElement !== input) {
          if (e.key.length === 1 && e.key.match(/[a-z]/i) && !e.ctrlKey && !e.metaKey) {
            input.focus();
          }
        }

        // Number keys to select quick actions
        if (e.key >= '1' && e.key <= '9') {
          const actions = document.querySelectorAll('.quick-actions:last-of-type .quick-action, .radio-actions:last-of-type .radio-option, .multi-select-actions:last-of-type .multi-select-option');
          const index = parseInt(e.key) - 1;
          if (actions[index]) {
            actions[index].click();
          }
        }

        // Escape to clear input
        if (e.key === 'Escape' && input) {
          input.value = '';
          input.blur();
        }
      });
    }

    // Create trust/security badge
    function createSecurityNotice() {
      const notice = document.createElement('div');
      notice.className = 'security-notice';
      notice.innerHTML = `
        <span class="security-notice-icon">🔒</span>
        <span>Your data is encrypted and never shared. We follow IRS data protection guidelines.</span>
      `;
      return notice;
    }

    // Show success animation
    function showSuccessCheck(element) {
      const check = document.createElement('span');
      check.className = 'success-check';
      check.textContent = '✓';
      element.appendChild(check);
      setTimeout(() => check.remove(), 2000);
    }

    // Initialize keyboard navigation on page load
    document.addEventListener('DOMContentLoaded', initKeyboardNavigation);

    async function handleQuickAction(value, displayLabel = null) {
      DevLogger.log('====== handleQuickAction CALLED ======');
      DevLogger.log('Quick action clicked:', value);
      DevLogger.log('Display label:', displayLabel);
      DevLogger.log('Current extracted data:', extractedData);
      DevLogger.log('Messages container exists:', !!document.getElementById('messages'));

      // Handle multi-select skip
      if (value === 'skip_multi_select') {
        addMessage('user', 'None / Skip');
        await processAIResponse('none');
        return;
      }

      // Handle multi-select submission (comma-separated values)
      if (value.includes(',') && displayLabel) {
        addMessage('user', displayLabel);
        await processAIResponse(displayLabel);
        return;
      }

      // =========================================================================
      // UNIFIED GUIDED FLOW - Clean single mode (post-login)
      // =========================================================================

      if (value === 'guided_start') {
        addMessage('user', 'Answer Questions');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<strong>Let's get to know your tax situation.</strong><br><br>
          <div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 1 of 5</span>
          </div>
          <strong>What best describes your situation?</strong>`, [
            { label: getIcon('briefcase', 'sm') + ' W-2 Employee', value: 'guided_type_w2', primary: true },
            { label: getIcon('building-office', 'sm') + ' Self-Employed / 1099', value: 'guided_type_self' },
            { label: getIcon('chart-bar', 'sm') + ' Both W-2 + Self-Employed', value: 'guided_type_both' },
            { label: "🏖️ Retired / Other Income", value: 'guided_type_retired' }
          ]);
        }, 600);
        return;
      }

      // Guided - Select income type
      if (value.startsWith('guided_type_')) {
        const typeMap = {
          'w2': { source: 'w2', label: 'W-2 Employee' },
          'self': { source: 'self_employed', label: 'Self-Employed / 1099' },
          'both': { source: 'mixed', label: 'Both W-2 + Self-Employed' },
          'retired': { source: 'retirement', label: 'Retired / Other Income' }
        };
        const typeKey = value.replace('guided_type_', '');
        const info = typeMap[typeKey] || typeMap['w2'];
        extractedData.tax_profile.income_source = info.source;
        if (typeKey === 'self' || typeKey === 'both') {
          extractedData.tax_profile.is_self_employed = true;
        }
        addMessage('user', info.label);
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 2 of 5</span>
          </div>
          <strong>What's your filing status?</strong>`, [
            { label: "Single", value: 'guided_filing_single' },
            { label: "Married Filing Jointly", value: 'guided_filing_mfj' },
            { label: "Head of Household", value: 'guided_filing_hoh' },
            { label: "Married Filing Separately", value: 'guided_filing_mfs' }
          ]);
        }, 600);
        return;
      }

      // Guided - Filing status
      if (value.startsWith('guided_filing_')) {
        const statusMap = { 'single': 'Single', 'mfj': 'Married Filing Jointly', 'hoh': 'Head of Household', 'mfs': 'Married Filing Separately' };
        const statusKey = value.replace('guided_filing_', '');
        extractedData.tax_profile.filing_status = statusMap[statusKey] || 'Single';
        addMessage('user', statusMap[statusKey] || 'Single');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 3 of 5</span>
          </div>
          <strong>What's your approximate annual income?</strong>`, [
            { label: "Under $50k", value: 'guided_income_50k' },
            { label: "$50k - $100k", value: 'guided_income_100k' },
            { label: "$100k - $200k", value: 'guided_income_200k' },
            { label: "$200k+", value: 'guided_income_200kplus' }
          ]);
        }, 600);
        return;
      }

      // Guided - Income
      if (value.startsWith('guided_income_')) {
        const incomeMap = { '50k': 35000, '100k': 75000, '200k': 150000, '200kplus': 250000 };
        const labelMap = { '50k': 'Under $50k', '100k': '$50k - $100k', '200k': '$100k - $200k', '200kplus': '$200k+' };
        const incomeKey = value.replace('guided_income_', '');
        extractedData.tax_profile.total_income = incomeMap[incomeKey] || 75000;
        addMessage('user', labelMap[incomeKey]);
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 4 of 5</span>
          </div>
          <strong>Any dependents?</strong>`, [
            { label: "No dependents", value: 'guided_deps_0' },
            { label: "1 dependent", value: 'guided_deps_1' },
            { label: "2 dependents", value: 'guided_deps_2' },
            { label: "3+ dependents", value: 'guided_deps_3plus' }
          ]);
        }, 600);
        return;
      }

      // Guided - Dependents
      if (value.startsWith('guided_deps_')) {
        const depsMap = { '0': 0, '1': 1, '2': 2, '3plus': 3 };
        const labelMap = { '0': 'No dependents', '1': '1 dependent', '2': '2 dependents', '3plus': '3+ dependents' };
        const depsKey = value.replace('guided_deps_', '');
        extractedData.tax_profile.dependents = depsMap[depsKey] || 0;
        extractedData.tax_profile.qualifying_children_ctc = depsMap[depsKey] || 0;
        if (depsMap[depsKey] > 0) extractedData.tax_profile.has_dependents = true;
        addMessage('user', labelMap[depsKey]);
        showTyping();
        setTimeout(() => {
          hideTyping();
          // Show relevant deductions based on income source
          const isSelfEmployed = extractedData.tax_profile.is_self_employed;
          const deductionOptions = [
            { label: getIcon('home', 'sm') + ' Mortgage Interest', value: 'guided_ded_mortgage' },
            { label: getIcon('currency-dollar', 'sm') + ' 401k/IRA', value: 'guided_ded_retirement' },
            { label: getIcon('gift', 'sm') + ' Charitable Donations', value: 'guided_ded_charity' }
          ];
          if (isSelfEmployed) {
            deductionOptions.push({ label: getIcon('truck', 'sm') + ' Business Expenses', value: 'guided_ded_business' });
            deductionOptions.push({ label: getIcon('home', 'sm') + ' Home Office', value: 'guided_ded_homeoffice' });
          }
          deductionOptions.push({ label: getIcon('arrow-right', 'sm') + ' None - Get My Results', value: 'guided_ded_none' });

          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 5 of 5</span>
          </div>
          <strong>Any of these apply?</strong> <span style="color: var(--text-secondary);">(Select any that apply)</span>`, deductionOptions);
        }, 600);
        return;
      }

      // Guided - Deductions & Generate Report
      if (value.startsWith('guided_ded_')) {
        const ded = value.replace('guided_ded_', '');
        const dedLabels = {
          'mortgage': '🏠 Mortgage Interest',
          'retirement': '💰 401k/IRA',
          'charity': '🎁 Charitable Donations',
          'business': '🚗 Business Expenses',
          'homeoffice': '🏠 Home Office',
          'none': 'Get My Results'
        };

        if (ded === 'mortgage') extractedData.tax_items.has_mortgage = true;
        if (ded === 'retirement') extractedData.tax_items.has_retirement = true;
        if (ded === 'charity') extractedData.tax_items.charitable = true;
        if (ded === 'business') extractedData.tax_items.business_expenses = true;
        if (ded === 'homeoffice') extractedData.tax_items.home_office = true;

        addMessage('user', dedLabels[ded] || 'Get Results');
        showTyping();
        setTimeout(async () => {
          hideTyping();
          addMessage('ai', `<div style="text-align: center; padding: var(--space-5);">
            <div style="font-size: var(--text-5xl); margin-bottom: var(--space-4);">✅</div>
            <div style="font-size: var(--text-xl); font-weight: var(--font-bold); color: var(--primary); margin-bottom: var(--space-2);">Profile Complete!</div>
            <div style="color: var(--text-secondary); margin-bottom: var(--space-5);">Generating your personalized tax analysis...</div>
          </div>`, []);
          await performTaxCalculation();
        }, 800);
        return;
      }

      // Express W-2 Simple Flow (legacy - no longer accessible from UI)
      if (value.startsWith('express_filing_')) {
        const status = value.replace('express_filing_', '');
        const statusMap = { 'single': 'Single', 'married': 'Married Filing Jointly', 'hoh': 'Head of Household', 'mfs': 'Married Filing Separately' };
        extractedData.tax_profile.filing_status = statusMap[status] || 'Single';
        addMessage('user', statusMap[status] || 'Single');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 2 of 5</span>
          </div>
          <strong>What's your approximate annual income?</strong>`, [
            { label: "Under $50k", value: 'express_income_50k' },
            { label: "$50k - $100k", value: 'express_income_100k' },
            { label: "$100k - $200k", value: 'express_income_200k' },
            { label: "$200k+", value: 'express_income_200kplus' }
          ]);
        }, 600);
        return;
      }

      // Express Income Selection
      if (value.startsWith('express_income_')) {
        const incomeMap = { '50k': 35000, '100k': 75000, '200k': 150000, '200kplus': 250000 };
        const incomeKey = value.replace('express_income_', '');
        extractedData.tax_profile.total_income = incomeMap[incomeKey] || 75000;
        const labelMap = { '50k': 'Under $50k', '100k': '$50k - $100k', '200k': '$100k - $200k', '200kplus': '$200k+' };
        addMessage('user', labelMap[incomeKey]);
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 3 of 5</span>
          </div>
          <strong>Which state do you live in?</strong>`, [
            { label: "California", value: 'express_state_CA' },
            { label: "Texas", value: 'express_state_TX' },
            { label: "New York", value: 'express_state_NY' },
            { label: "Florida", value: 'express_state_FL' },
            { label: "Other State →", value: 'express_state_other' }
          ]);
        }, 600);
        return;
      }

      // Express State Selection
      if (value.startsWith('express_state_')) {
        const state = value.replace('express_state_', '');
        if (state === 'other') {
          // Show more states
          addMessage('user', 'Other State');
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Select your state:</strong>`, [
              { label: "Illinois", value: 'express_state_IL' },
              { label: "Pennsylvania", value: 'express_state_PA' },
              { label: "Ohio", value: 'express_state_OH' },
              { label: "Georgia", value: 'express_state_GA' },
              { label: "North Carolina", value: 'express_state_NC' },
              { label: "Michigan", value: 'express_state_MI' },
              { label: "New Jersey", value: 'express_state_NJ' },
              { label: "Washington", value: 'express_state_WA' },
              { label: "Arizona", value: 'express_state_AZ' },
              { label: "Colorado", value: 'express_state_CO' }
            ]);
          }, 400);
          return;
        }
        extractedData.tax_profile.state = state;
        addMessage('user', state);
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 4 of 5</span>
          </div>
          <strong>Any dependents (children, elderly parents)?</strong>`, [
            { label: "No dependents", value: 'express_deps_0' },
            { label: "1 dependent", value: 'express_deps_1' },
            { label: "2 dependents", value: 'express_deps_2' },
            { label: "3+ dependents", value: 'express_deps_3plus' }
          ]);
        }, 600);
        return;
      }

      // Express Dependents Selection
      if (value.startsWith('express_deps_')) {
        const depsMap = { '0': 0, '1': 1, '2': 2, '3plus': 3 };
        const depsKey = value.replace('express_deps_', '');
        extractedData.tax_profile.dependents = depsMap[depsKey] || 0;
        const labelMap = { '0': 'No dependents', '1': '1 dependent', '2': '2 dependents', '3plus': '3+ dependents' };
        addMessage('user', labelMap[depsKey]);
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 5 of 5</span>
          </div>
          <strong>Any of these deductions?</strong> <span style="color: var(--text-secondary);">(Select all that apply)</span>`, [
            { label: getIcon('home', 'sm') + ' Mortgage interest', value: 'express_ded_mortgage' },
            { label: getIcon('currency-dollar', 'sm') + ' 401k/IRA contributions', value: 'express_ded_retirement' },
            { label: getIcon('gift', 'sm') + ' Charitable donations', value: 'express_ded_charity' },
            { label: getIcon('academic-cap', 'sm') + ' Student loans', value: 'express_ded_student' },
            { label: getIcon('arrow-right', 'sm') + ' None / Skip to Report', value: 'express_ded_none' }
          ]);
        }, 600);
        return;
      }

      // Express Deduction Selection - Generate Report
      if (value.startsWith('express_ded_')) {
        const ded = value.replace('express_ded_', '');
        if (ded === 'mortgage') {
          extractedData.tax_items.has_mortgage = true;
          addMessage('user', '🏠 Mortgage interest');
        } else if (ded === 'retirement') {
          extractedData.tax_items.has_retirement = true;
          addMessage('user', '💰 401k/IRA contributions');
        } else if (ded === 'charity') {
          extractedData.tax_items.charitable = true;
          addMessage('user', '🎁 Charitable donations');
        } else if (ded === 'student') {
          extractedData.tax_items.student_loan_interest = true;
          addMessage('user', '📚 Student loans');
        } else {
          addMessage('user', 'Skip to Report');
        }

        // Now generate the report
        showTyping();
        setTimeout(async () => {
          hideTyping();
          // Show completion message
          addMessage('ai', `<div style="text-align: center; padding: var(--space-5);">
            <div style="font-size: var(--text-5xl); margin-bottom: var(--space-4);">✅</div>
            <div style="font-size: var(--text-xl); font-weight: var(--font-bold); color: var(--accent-light); margin-bottom: var(--space-2);">Profile Complete!</div>
            <div style="color: var(--text-secondary); margin-bottom: var(--space-5);">Generating your personalized tax analysis...</div>
          </div>`, []);

          // Calculate and show results
          await performTaxCalculation();
        }, 800);
        return;
      }

      // Express Family Flow - Kids count
      if (value.startsWith('express_fam_')) {
        const kidsMap = { '1kid': 1, '2kids': 2, '3kids': 3, '4plus': 4 };
        const kidsKey = value.replace('express_fam_', '');
        extractedData.tax_profile.dependents = kidsMap[kidsKey] || 1;
        extractedData.tax_profile.qualifying_children_ctc = kidsMap[kidsKey] || 1;
        const labelMap = { '1kid': '1 child', '2kids': '2 children', '3kids': '3 children', '4plus': '4+ children' };
        addMessage('user', labelMap[kidsKey]);
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 2 of 6</span>
          </div>
          <strong>Combined household income?</strong>`, [
            { label: "Under $75k", value: 'express_fam_inc_75k' },
            { label: "$75k - $150k", value: 'express_fam_inc_150k' },
            { label: "$150k - $250k", value: 'express_fam_inc_250k' },
            { label: "$250k+", value: 'express_fam_inc_250kplus' }
          ]);
        }, 600);
        return;
      }

      // Express Family - Income
      if (value.startsWith('express_fam_inc_')) {
        const incomeMap = { '75k': 50000, '150k': 112500, '250k': 200000, '250kplus': 350000 };
        const incKey = value.replace('express_fam_inc_', '');
        extractedData.tax_profile.total_income = incomeMap[incKey] || 112500;
        const labelMap = { '75k': 'Under $75k', '150k': '$75k - $150k', '250k': '$150k - $250k', '250kplus': '$250k+' };
        addMessage('user', labelMap[incKey]);
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 3 of 6</span>
          </div>
          <strong>Do you pay for childcare?</strong>`, [
            { label: "Yes, daycare/preschool", value: 'express_fam_care_yes' },
            { label: "Yes, after-school care", value: 'express_fam_care_after' },
            { label: "No childcare expenses", value: 'express_fam_care_no' }
          ]);
        }, 600);
        return;
      }

      // Express Family - Childcare
      if (value.startsWith('express_fam_care_')) {
        const care = value.replace('express_fam_care_', '');
        if (care === 'yes' || care === 'after') {
          extractedData.tax_profile.has_dependent_care = true;
          addMessage('user', care === 'yes' ? 'Yes, daycare/preschool' : 'Yes, after-school care');
        } else {
          addMessage('user', 'No childcare expenses');
        }
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 4 of 6</span>
          </div>
          <strong>Which state?</strong>`, [
            { label: "California", value: 'express_fam_state_CA' },
            { label: "Texas", value: 'express_fam_state_TX' },
            { label: "New York", value: 'express_fam_state_NY' },
            { label: "Florida", value: 'express_fam_state_FL' },
            { label: "Other →", value: 'express_fam_state_other' }
          ]);
        }, 600);
        return;
      }

      // Express Family - State
      if (value.startsWith('express_fam_state_')) {
        const state = value.replace('express_fam_state_', '');
        if (state === 'other') {
          addMessage('user', 'Other State');
          // Show more states
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Select your state:</strong>`, [
              { label: "Illinois", value: 'express_fam_state_IL' },
              { label: "Pennsylvania", value: 'express_fam_state_PA' },
              { label: "Ohio", value: 'express_fam_state_OH' },
              { label: "Georgia", value: 'express_fam_state_GA' },
              { label: "North Carolina", value: 'express_fam_state_NC' },
              { label: "New Jersey", value: 'express_fam_state_NJ' },
              { label: "Michigan", value: 'express_fam_state_MI' }
            ]);
          }, 400);
          return;
        }
        extractedData.tax_profile.state = state;
        addMessage('user', state);
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 5 of 6</span>
          </div>
          <strong>Do you own a home?</strong>`, [
            { label: "Yes, with mortgage", value: 'express_fam_home_yes' },
            { label: "Yes, paid off", value: 'express_fam_home_paid' },
            { label: "No, renting", value: 'express_fam_home_no' }
          ]);
        }, 600);
        return;
      }

      // Express Family - Home
      if (value.startsWith('express_fam_home_')) {
        const home = value.replace('express_fam_home_', '');
        if (home === 'yes') {
          extractedData.tax_items.has_mortgage = true;
          addMessage('user', 'Yes, with mortgage');
        } else if (home === 'paid') {
          addMessage('user', 'Yes, paid off');
        } else {
          addMessage('user', 'No, renting');
        }
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 6 of 6</span>
          </div>
          <strong>401k or retirement contributions?</strong>`, [
            { label: "Yes, contributing", value: 'express_fam_ret_yes' },
            { label: "No", value: 'express_fam_ret_no' }
          ]);
        }, 600);
        return;
      }

      // Express Family - Retirement (Final step)
      if (value.startsWith('express_fam_ret_')) {
        const ret = value.replace('express_fam_ret_', '');
        if (ret === 'yes') {
          extractedData.tax_items.has_retirement = true;
          addMessage('user', 'Yes, contributing');
        } else {
          addMessage('user', 'No');
        }
        showTyping();
        setTimeout(async () => {
          hideTyping();
          addMessage('ai', `<div style="text-align: center; padding: var(--space-5);">
            <div style="font-size: var(--text-5xl); margin-bottom: var(--space-4);">✅</div>
            <div style="font-size: var(--text-xl); font-weight: var(--font-bold); color: var(--accent-light); margin-bottom: var(--space-2);">Family Profile Complete!</div>
            <div style="color: var(--text-secondary); margin-bottom: var(--space-5);">Calculating your Child Tax Credits and deductions...</div>
          </div>`, []);
          await performTaxCalculation();
        }, 800);
        return;
      }

      // Express Self-Employed Flow
      if (value.startsWith('express_se_')) {
        const seKey = value.replace('express_se_', '');
        if (seKey === 'single' || seKey === 'married' || seKey === 'hoh') {
          const statusMap = { 'single': 'Single', 'married': 'Married Filing Jointly', 'hoh': 'Head of Household' };
          extractedData.tax_profile.filing_status = statusMap[seKey];
          addMessage('user', statusMap[seKey]);
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
              <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 2 of 7</span>
            </div>
            <strong>What type of self-employment?</strong>`, [
              { label: "Freelance/Consulting", value: 'express_se_type_freelance' },
              { label: "Small Business", value: 'express_se_type_business' },
              { label: "Gig Work (Uber, DoorDash)", value: 'express_se_type_gig' },
              { label: "Online Sales", value: 'express_se_type_online' }
            ]);
          }, 600);
          return;
        }
      }

      // Express SE Type
      if (value.startsWith('express_se_type_')) {
        const type = value.replace('express_se_type_', '');
        const typeMap = { 'freelance': 'Freelance/Consulting', 'business': 'Small Business', 'gig': 'Gig Work', 'online': 'Online Sales' };
        extractedData.business.type = typeMap[type];
        addMessage('user', typeMap[type]);
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 3 of 7</span>
          </div>
          <strong>Annual self-employment income?</strong>`, [
            { label: "Under $50k", value: 'express_se_inc_50k' },
            { label: "$50k - $100k", value: 'express_se_inc_100k' },
            { label: "$100k - $200k", value: 'express_se_inc_200k' },
            { label: "$200k+", value: 'express_se_inc_200kplus' }
          ]);
        }, 600);
        return;
      }

      // Express SE Income
      if (value.startsWith('express_se_inc_')) {
        const incMap = { '50k': 35000, '100k': 75000, '200k': 150000, '200kplus': 300000 };
        const incKey = value.replace('express_se_inc_', '');
        extractedData.tax_profile.total_income = incMap[incKey];
        extractedData.business.revenue = incMap[incKey];
        const labelMap = { '50k': 'Under $50k', '100k': '$50k - $100k', '200k': '$100k - $200k', '200kplus': '$200k+' };
        addMessage('user', labelMap[incKey]);
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 4 of 7</span>
          </div>
          <strong>Common business expenses?</strong> <span style="color: var(--text-secondary);">(Select all)</span>`, [
            { label: getIcon('home', 'sm') + ' Home office', value: 'express_se_exp_home' },
            { label: getIcon('truck', 'sm') + ' Vehicle/mileage', value: 'express_se_exp_vehicle' },
            { label: getIcon('cpu-chip', 'sm') + ' Equipment/software', value: 'express_se_exp_equip' },
            { label: "📱 Phone/internet", value: 'express_se_exp_phone' },
            { label: getIcon('arrow-right', 'sm') + ' Continue', value: 'express_se_exp_done' }
          ]);
        }, 600);
        return;
      }

      // Express SE Expenses
      if (value.startsWith('express_se_exp_')) {
        const exp = value.replace('express_se_exp_', '');
        if (exp === 'home') {
          extractedData.business.home_office = true;
          addMessage('user', '🏠 Home office');
          return; // Allow multiple selections
        } else if (exp === 'vehicle') {
          extractedData.business.vehicle = true;
          addMessage('user', '🚗 Vehicle/mileage');
          return;
        } else if (exp === 'equip') {
          extractedData.business.equipment = true;
          addMessage('user', '💻 Equipment/software');
          return;
        } else if (exp === 'phone') {
          extractedData.business.phone_internet = true;
          addMessage('user', '📱 Phone/internet');
          return;
        } else { // done
          addMessage('user', 'Continue');
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
              <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 5 of 7</span>
            </div>
            <strong>Which state?</strong>`, [
              { label: "California", value: 'express_se_state_CA' },
              { label: "Texas", value: 'express_se_state_TX' },
              { label: "New York", value: 'express_se_state_NY' },
              { label: "Florida", value: 'express_se_state_FL' },
              { label: "Other →", value: 'express_se_state_other' }
            ]);
          }, 600);
        }
        return;
      }

      // Express SE State
      if (value.startsWith('express_se_state_')) {
        const state = value.replace('express_se_state_', '');
        if (state === 'other') {
          addMessage('user', 'Other State');
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Select your state:</strong>`, [
              { label: "Illinois", value: 'express_se_state_IL' },
              { label: "Pennsylvania", value: 'express_se_state_PA' },
              { label: "Washington", value: 'express_se_state_WA' },
              { label: "Colorado", value: 'express_se_state_CO' },
              { label: "Georgia", value: 'express_se_state_GA' }
            ]);
          }, 400);
          return;
        }
        extractedData.tax_profile.state = state;
        addMessage('user', state);
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 6 of 7</span>
          </div>
          <strong>Do you pay quarterly estimated taxes?</strong>`, [
            { label: "Yes, I pay quarterly", value: 'express_se_est_yes' },
            { label: "No / Not sure", value: 'express_se_est_no' }
          ]);
        }, 600);
        return;
      }

      // Express SE Estimated Taxes
      if (value.startsWith('express_se_est_')) {
        const est = value.replace('express_se_est_', '');
        extractedData.tax_profile.pays_estimated = est === 'yes';
        addMessage('user', est === 'yes' ? 'Yes, I pay quarterly' : 'No / Not sure');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 7 of 7</span>
          </div>
          <strong>Any retirement contributions (SEP-IRA, Solo 401k)?</strong>`, [
            { label: "Yes", value: 'express_se_ret_yes' },
            { label: "No, but interested", value: 'express_se_ret_interested' },
            { label: "No", value: 'express_se_ret_no' }
          ]);
        }, 600);
        return;
      }

      // Express SE Retirement (Final)
      if (value.startsWith('express_se_ret_')) {
        const ret = value.replace('express_se_ret_', '');
        if (ret === 'yes') {
          extractedData.tax_items.has_retirement = true;
          addMessage('user', 'Yes');
        } else if (ret === 'interested') {
          extractedData.tax_profile.retirement_interested = true;
          addMessage('user', 'No, but interested');
        } else {
          addMessage('user', 'No');
        }
        showTyping();
        setTimeout(async () => {
          hideTyping();
          addMessage('ai', `<div style="text-align: center; padding: var(--space-5);">
            <div style="font-size: var(--text-5xl); margin-bottom: var(--space-4);">✅</div>
            <div style="font-size: var(--text-xl); font-weight: var(--font-bold); color: var(--accent-light); margin-bottom: var(--space-2);">Self-Employment Profile Complete!</div>
            <div style="color: var(--text-secondary); margin-bottom: var(--space-5);">Finding your QBI deduction and business write-offs...</div>
          </div>`, []);
          await performTaxCalculation();
        }, 800);
        return;
      }

      // Express Homeowner Flow
      if (value.startsWith('express_home_')) {
        const homeKey = value.replace('express_home_', '');
        if (homeKey === 'single' || homeKey === 'married' || homeKey === 'hoh') {
          const statusMap = { 'single': 'Single', 'married': 'Married Filing Jointly', 'hoh': 'Head of Household' };
          extractedData.tax_profile.filing_status = statusMap[homeKey];
          addMessage('user', statusMap[homeKey]);
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
              <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 2 of 6</span>
            </div>
            <strong>Annual household income?</strong>`, [
              { label: "Under $75k", value: 'express_hm_inc_75k' },
              { label: "$75k - $150k", value: 'express_hm_inc_150k' },
              { label: "$150k - $300k", value: 'express_hm_inc_300k' },
              { label: "$300k+", value: 'express_hm_inc_300kplus' }
            ]);
          }, 600);
          return;
        }
      }

      // Express Homeowner Income
      if (value.startsWith('express_hm_inc_')) {
        const incMap = { '75k': 50000, '150k': 112500, '300k': 225000, '300kplus': 400000 };
        const incKey = value.replace('express_hm_inc_', '');
        extractedData.tax_profile.total_income = incMap[incKey];
        const labelMap = { '75k': 'Under $75k', '150k': '$75k - $150k', '300k': '$150k - $300k', '300kplus': '$300k+' };
        addMessage('user', labelMap[incKey]);
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 3 of 6</span>
          </div>
          <strong>Annual mortgage interest paid?</strong>`, [
            { label: "Under $5,000", value: 'express_hm_mort_5k' },
            { label: "$5,000 - $15,000", value: 'express_hm_mort_15k' },
            { label: "$15,000 - $30,000", value: 'express_hm_mort_30k' },
            { label: "Over $30,000", value: 'express_hm_mort_30kplus' }
          ]);
        }, 600);
        return;
      }

      // Express Homeowner Mortgage
      if (value.startsWith('express_hm_mort_')) {
        const mortMap = { '5k': 3000, '15k': 10000, '30k': 22500, '30kplus': 40000 };
        const mortKey = value.replace('express_hm_mort_', '');
        extractedData.tax_items.mortgage_interest = mortMap[mortKey];
        extractedData.tax_items.has_mortgage = true;
        const labelMap = { '5k': 'Under $5,000', '15k': '$5,000 - $15,000', '30k': '$15,000 - $30,000', '30kplus': 'Over $30,000' };
        addMessage('user', labelMap[mortKey]);
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 4 of 6</span>
          </div>
          <strong>Annual property taxes paid?</strong>`, [
            { label: "Under $3,000", value: 'express_hm_prop_3k' },
            { label: "$3,000 - $8,000", value: 'express_hm_prop_8k' },
            { label: "$8,000 - $15,000", value: 'express_hm_prop_15k' },
            { label: "Over $15,000", value: 'express_hm_prop_15kplus' }
          ]);
        }, 600);
        return;
      }

      // Express Homeowner Property Tax
      if (value.startsWith('express_hm_prop_')) {
        const propMap = { '3k': 2000, '8k': 5500, '15k': 11500, '15kplus': 20000 };
        const propKey = value.replace('express_hm_prop_', '');
        extractedData.tax_items.property_tax = propMap[propKey];
        const labelMap = { '3k': 'Under $3,000', '8k': '$3,000 - $8,000', '15k': '$8,000 - $15,000', '15kplus': 'Over $15,000' };
        addMessage('user', labelMap[propKey]);
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 5 of 6</span>
          </div>
          <strong>Which state?</strong>`, [
            { label: "California", value: 'express_hm_state_CA' },
            { label: "Texas", value: 'express_hm_state_TX' },
            { label: "New York", value: 'express_hm_state_NY' },
            { label: "Florida", value: 'express_hm_state_FL' },
            { label: "New Jersey", value: 'express_hm_state_NJ' },
            { label: "Other →", value: 'express_hm_state_other' }
          ]);
        }, 600);
        return;
      }

      // Express Homeowner State
      if (value.startsWith('express_hm_state_')) {
        const state = value.replace('express_hm_state_', '');
        if (state === 'other') {
          addMessage('user', 'Other State');
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Select your state:</strong>`, [
              { label: "Illinois", value: 'express_hm_state_IL' },
              { label: "Pennsylvania", value: 'express_hm_state_PA' },
              { label: "Massachusetts", value: 'express_hm_state_MA' },
              { label: "Connecticut", value: 'express_hm_state_CT' },
              { label: "Maryland", value: 'express_hm_state_MD' },
              { label: "Virginia", value: 'express_hm_state_VA' }
            ]);
          }, 400);
          return;
        }
        extractedData.tax_profile.state = state;
        addMessage('user', state);
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Step 6 of 6</span>
          </div>
          <strong>Any dependents?</strong>`, [
            { label: "No dependents", value: 'express_hm_deps_0' },
            { label: "1-2 dependents", value: 'express_hm_deps_2' },
            { label: "3+ dependents", value: 'express_hm_deps_3plus' }
          ]);
        }, 600);
        return;
      }

      // Express Homeowner Dependents (Final)
      if (value.startsWith('express_hm_deps_')) {
        const depsMap = { '0': 0, '2': 2, '3plus': 3 };
        const depsKey = value.replace('express_hm_deps_', '');
        extractedData.tax_profile.dependents = depsMap[depsKey];
        const labelMap = { '0': 'No dependents', '2': '1-2 dependents', '3plus': '3+ dependents' };
        addMessage('user', labelMap[depsKey]);
        showTyping();
        setTimeout(async () => {
          hideTyping();
          addMessage('ai', `<div style="text-align: center; padding: var(--space-5);">
            <div style="font-size: var(--text-5xl); margin-bottom: var(--space-4);">✅</div>
            <div style="font-size: var(--text-xl); font-weight: var(--font-bold); color: var(--accent-light); margin-bottom: var(--space-2);">Homeowner Profile Complete!</div>
            <div style="color: var(--text-secondary); margin-bottom: var(--space-5);">Calculating your itemized deduction potential...</div>
          </div>`, []);
          await performTaxCalculation();
        }, 800);
        return;
      }

      // Lead capture - Name entry
      if (value === 'enter_name') {
        addMessage('user', 'I\'ll enter my name');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `Perfect! Please enter your full name below so I can personalize your tax advisory report.<br><br><input type="text" id="nameInput" placeholder="Your full name" style="width: 100%; padding: var(--space-3-5); margin: var(--space-3) 0; background: rgba(255,255,255,0.05); border: 2px solid var(--border); border-radius: var(--radius-lg); color: var(--text); font-size: var(--text-base);" onkeypress="if(event.key==='Enter') captureName()"><br><button onclick="captureName()" style="padding: var(--space-3) var(--space-8); background: var(--primary); color: white; border: none; border-radius: var(--radius-lg); cursor: pointer; font-weight: var(--font-semibold); margin-top: var(--space-2);">Continue →</button>`);
          setTimeout(() => document.getElementById('nameInput').focus(), 100);
        }, 1000);

      } else if (value === 'skip_name') {
        addMessage('user', 'I\'ll skip for now');
        extractedData.lead_data.score += 5; // Lower score for anonymous users
        proceedToDataGathering();

      } else if (value === 'enter_email') {
        addMessage('user', 'I\'ll enter my email');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `Great! Please enter your email address below.<br><br><input type="email" id="emailInput" placeholder="your.email@example.com" style="width: 100%; padding: var(--space-3-5); margin: var(--space-3) 0; background: rgba(255,255,255,0.05); border: 2px solid var(--border); border-radius: var(--radius-lg); color: var(--text); font-size: var(--text-base);" onkeypress="if(event.key==='Enter') captureEmail()"><br><button onclick="captureEmail()" style="padding: var(--space-3) var(--space-8); background: var(--primary); color: white; border: none; border-radius: var(--radius-lg); cursor: pointer; font-weight: var(--font-semibold); margin-top: var(--space-2);">Continue →</button>`);
          setTimeout(() => document.getElementById('emailInput').focus(), 100);
        }, 1000);

      } else if (value === 'skip_email') {
        addMessage('user', 'I\'ll skip for now');
        extractedData.lead_data.score += 10;
        proceedToDataGathering();

      } else if (value === 'upload_docs_qualified' || value === 'conversational_qualified' || value === 'hybrid_qualified') {
        const mode = value.replace('_qualified', '');
        addMessage('user', mode.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()));

        if (mode === 'upload_docs' || mode === 'hybrid') {
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Perfect! Let's use our Express Lane document analysis.</strong><br><br>📄 <strong>Upload any of these documents:</strong><br>• W-2 forms (employment income)<br>• 1099 forms (freelance, interest, dividends)<br>• Previous tax returns<br>• Business financial statements<br>• Receipts for deductions<br><br>I'll use advanced OCR and AI to extract all relevant information automatically.<br><br><div style="text-align: center; margin: var(--space-5) 0;"><button onclick="document.getElementById('fileInput').click()" style="padding: var(--space-4) var(--space-10); background: var(--gradient); color: white; border: none; border-radius: var(--radius-xl); cursor: pointer; font-weight: var(--font-bold); font-size: var(--text-lg);">📤 Upload Documents</button></div>Or <strong>drag and drop</strong> files anywhere on this page.`);
          }, 1000);
        } else {
          // Conversational mode - start smart Q&A
          startIntelligentQuestioning();
        }

      // Handle initial greeting responses
      } else if (value === 'yes_upload') {
        DevLogger.log('Processing yes_upload action');
        addMessage('user', 'Upload my documents');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div style="background: linear-gradient(135deg, rgba(33, 150, 243, 0.1), rgba(76, 175, 80, 0.1)); border-radius: var(--radius-xl); padding: var(--space-4); margin-bottom: var(--space-4);">
            <div style="font-size: var(--text-lg); font-weight: var(--font-semibold); margin-bottom: var(--space-2);">📄 Smart Document Analysis</div>
            <div style="font-size: var(--text-xs-plus); color: var(--text-secondary);">I'll extract all tax data automatically using AI</div>
          </div>
          <strong>Supported documents:</strong> W-2, 1099, 1098, Prior Tax Returns<br><br>
          <div style="text-align: center; margin: var(--space-4) 0;">
            <button onclick="document.getElementById('fileInput').click()" style="padding: var(--space-4) var(--space-8); background: var(--gradient); color: white; border: none; border-radius: var(--radius-xl); cursor: pointer; font-weight: var(--font-bold); font-size: var(--text-base);">
              📤 Select Files to Upload
            </button>
          </div>
          <div style="font-size: var(--text-xs); color: var(--text-secondary); text-align: center;">Or drag & drop files anywhere on this page</div>`, [
            { label: getIcon('chat-bubble-left-right', 'sm') + ' Skip upload, answer questions', value: 'no_manual' }
          ]);
        }, 800);

      } else if (value === 'no_manual') {
        addMessage('user', 'No, I\'d prefer to discuss my situation first');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `What's your filing status?`, [
            { label: 'Single', value: 'filing_single' },
            { label: 'Married Filing Jointly', value: 'filing_married' },
            { label: 'Head of Household', value: 'filing_hoh' },
            { label: 'Married Filing Separately', value: 'filing_mfs' },
            { label: 'Qualifying Surviving Spouse', value: 'filing_qss' }
          ]);
        }, 1500);

      } else if (value === 'what_docs') {
        addMessage('user', 'What kind of documents would help?');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `Great question! Here's what I typically review for a comprehensive tax advisory:<br><br><strong>📊 Income Documents:</strong><br>• W-2 forms (from employers)<br>• 1099 forms (interest, dividends, freelance income)<br>• Business income records<br>• Rental property income<br><br><strong>💰 Deduction & Credit Records:</strong><br>• Mortgage interest statements (1098)<br>• Property tax records<br>• Charitable contribution receipts<br>• Education expenses (1098-T)<br>• Medical expense receipts<br>• Retirement contributions<br><br><strong>📈 Investment Records:</strong><br>• Brokerage statements<br>• Cryptocurrency transactions<br>• Capital gains/losses<br><br>Don't worry if you don't have everything right now. <strong>What would you like to do next?</strong>`, [
            { label: getIcon('document-text', 'sm') + ' I have some documents ready', value: 'yes_upload' },
            { label: getIcon('chat-bubble-left-right', 'sm') + ' Let\'s discuss my situation', value: 'no_manual' }
          ]);
        }, 2000);

      } else if (value === 'upload_w2' || value === 'upload_1099' || value === 'upload_other') {
        addMessage('user', 'I want to upload a document');
        document.getElementById('fileInput').click();

      // Post-Upload Express Flow handlers
      } else if (value.startsWith('post_upload_filing_')) {
        const status = value.replace('post_upload_filing_', '');
        const statusMap = { 'single': 'Single', 'married': 'Married Filing Jointly', 'hoh': 'Head of Household', 'mfs': 'Married Filing Separately' };
        extractedData.tax_profile.filing_status = statusMap[status];
        addMessage('user', statusMap[status]);
        showTyping();
        setTimeout(() => {
          hideTyping();
          // Check if state is needed
          if (!extractedData.tax_profile.state) {
            addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
              <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Quick Question 2</span>
            </div>
            <strong>Which state?</strong>`, [
              { label: 'California', value: 'post_upload_state_CA' },
              { label: 'Texas', value: 'post_upload_state_TX' },
              { label: 'New York', value: 'post_upload_state_NY' },
              { label: 'Florida', value: 'post_upload_state_FL' },
              { label: 'Other →', value: 'post_upload_state_other' }
            ]);
          } else if (!extractedData.tax_profile.dependents && extractedData.tax_profile.dependents !== 0) {
            addMessage('ai', `<strong>Any dependents?</strong>`, [
              { label: 'No dependents', value: 'post_upload_deps_0' },
              { label: '1-2 dependents', value: 'post_upload_deps_2' },
              { label: '3+ dependents', value: 'post_upload_deps_3plus' }
            ]);
          } else {
            // All done - generate report
            addMessage('ai', `<div style="text-align: center; padding: var(--space-4);">
              <div style="font-size: 32px; margin-bottom: var(--space-3);">✅</div>
              <div style="font-size: var(--text-lg); font-weight: var(--font-semibold);">Ready to Generate Report!</div>
            </div>`, [
              { label: getIcon('chart-bar', 'sm') + ' Generate My Tax Report', value: 'generate_report', primary: true }
            ]);
          }
        }, 500);
        return;

      } else if (value.startsWith('post_upload_state_')) {
        const state = value.replace('post_upload_state_', '');
        if (state === 'other') {
          addMessage('user', 'Other State');
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Select your state:</strong>`, [
              { label: 'Illinois', value: 'post_upload_state_IL' },
              { label: 'Pennsylvania', value: 'post_upload_state_PA' },
              { label: 'Ohio', value: 'post_upload_state_OH' },
              { label: 'Georgia', value: 'post_upload_state_GA' },
              { label: 'Washington', value: 'post_upload_state_WA' },
              { label: 'Colorado', value: 'post_upload_state_CO' }
            ]);
          }, 300);
          return;
        }
        extractedData.tax_profile.state = state;
        addMessage('user', state);
        showTyping();
        setTimeout(() => {
          hideTyping();
          if (!extractedData.tax_profile.dependents && extractedData.tax_profile.dependents !== 0) {
            addMessage('ai', `<div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
              <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Last Question</span>
            </div>
            <strong>Any dependents?</strong>`, [
              { label: 'No dependents', value: 'post_upload_deps_0' },
              { label: '1-2 dependents', value: 'post_upload_deps_2' },
              { label: '3+ dependents', value: 'post_upload_deps_3plus' }
            ]);
          } else {
            addMessage('ai', `<div style="text-align: center; padding: var(--space-4);">
              <div style="font-size: 32px; margin-bottom: var(--space-3);">✅</div>
              <div style="font-size: var(--text-lg); font-weight: var(--font-semibold);">Ready to Generate Report!</div>
            </div>`, [
              { label: getIcon('chart-bar', 'sm') + ' Generate My Tax Report', value: 'generate_report', primary: true }
            ]);
          }
        }, 500);
        return;

      } else if (value.startsWith('post_upload_deps_')) {
        const depsMap = { '0': 0, '2': 2, '3plus': 3 };
        const depsKey = value.replace('post_upload_deps_', '');
        extractedData.tax_profile.dependents = depsMap[depsKey] || 0;
        const labelMap = { '0': 'No dependents', '2': '1-2 dependents', '3plus': '3+ dependents' };
        addMessage('user', labelMap[depsKey]);
        showTyping();
        setTimeout(async () => {
          hideTyping();
          addMessage('ai', `<div style="text-align: center; padding: var(--space-5);">
            <div style="font-size: var(--text-5xl); margin-bottom: var(--space-4);">✅</div>
            <div style="font-size: var(--text-xl); font-weight: var(--font-bold); color: var(--accent-light); margin-bottom: var(--space-2);">Profile Complete!</div>
            <div style="color: var(--text-secondary); margin-bottom: var(--space-5);">Generating your personalized tax analysis...</div>
          </div>`, []);
          await performTaxCalculation();
        }, 600);
        return;

      } else if (value.startsWith('filing_')) {
        const status = value.replace('filing_', '');
        const statusMap = {
          'single': 'Single',
          'married': 'Married Filing Jointly',
          'hoh': 'Head of Household',
          'mfs': 'Married Filing Separately',
          'qss': 'Qualifying Surviving Spouse'
        };
        const statusText = statusMap[status] || status;

        addMessage('user', statusText);
        // Mark as user-confirmed to prevent AI from overwriting
        setConfirmedValue('tax_profile.filing_status', statusText);
        extractedData.lead_data.score += 10;
        updateStats({ filing_status: statusText });
        calculateLeadScore();

        // Update savings estimate
        updateSavingsEstimate();

        // Ask about divorce for Single, HOH, or MFS (potential alimony/custody implications)
        if ((status === 'single' || status === 'hoh' || status === 'mfs') && !extractedData.tax_profile.divorce_explored) {
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Did your marital status change this year?</strong><br><small>Divorce can affect filing status, dependency claims, and alimony treatment.</small>`, [
              { label: 'Yes, recently divorced', value: 'divorce_recent' },
              { label: 'Yes, legally separated', value: 'divorce_separated' },
              { label: 'Widowed this year', value: 'divorce_widowed' },
              { label: 'No change', value: 'divorce_none' }
            ]);
          }, 800);
          return;
        }

        startIntelligentQuestioning();

      // Divorce Scenario Handlers
      } else if (value.startsWith('divorce_')) {
        const divorceType = value.replace('divorce_', '');
        const divorceLabels = {
          'recent': 'Recently divorced',
          'separated': 'Legally separated',
          'widowed': 'Widowed this year',
          'none': 'No change'
        };
        addMessage('user', divorceLabels[divorceType] || divorceType);
        extractedData.tax_profile.divorce_explored = true;
        extractedData.tax_profile.marital_change = divorceType;

        if (divorceType === 'recent') {
          // Ask about alimony (pre-2019 vs post-2019 divorce)
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>When was your divorce finalized?</strong><br><small>Alimony tax treatment changed for divorces after Dec 31, 2018.</small>`, [
              { label: 'Before 2019', value: 'divorce_year_pre2019' },
              { label: '2019 or later', value: 'divorce_year_post2019' }
            ]);
          }, 800);
          return;
        } else if (divorceType === 'separated') {
          extractedData.tax_profile.is_separated = true;
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Are you living apart from your spouse?</strong><br><small>This may affect whether you can file as Head of Household.</small>`, [
              { label: 'Yes, we live separately', value: 'separated_live_apart' },
              { label: 'No, still living together', value: 'separated_same_home' }
            ]);
          }, 800);
          return;
        } else if (divorceType === 'widowed') {
          extractedData.tax_profile.is_widowed = true;
          // May qualify for Qualifying Surviving Spouse status
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `I'm sorry for your loss. <strong>Do you have dependent children living with you?</strong><br><small>You may qualify for Qualifying Surviving Spouse status (same tax rates as Married Filing Jointly) for up to 2 years.</small>`, [
              { label: 'Yes, dependents in my home', value: 'widowed_with_deps' },
              { label: 'No dependents', value: 'widowed_no_deps' }
            ]);
          }, 800);
          return;
        }
        startIntelligentQuestioning();

      // Divorce Year Handler (affects alimony treatment)
      } else if (value.startsWith('divorce_year_')) {
        const yearType = value.replace('divorce_year_', '');
        addMessage('user', yearType === 'pre2019' ? 'Before 2019' : '2019 or later');
        extractedData.tax_profile.divorce_year_type = yearType;

        if (yearType === 'pre2019') {
          // Ask about alimony paid/received (deductible for payer, taxable for recipient)
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Did you pay or receive alimony this year?</strong><br><small>Pre-2019 divorces: Alimony is deductible for the payer and taxable income for the recipient.</small>`, [
              { label: 'I paid alimony', value: 'alimony_paid' },
              { label: 'I received alimony', value: 'alimony_received' },
              { label: 'No alimony', value: 'alimony_none' }
            ]);
          }, 800);
          return;
        } else {
          // Post-2018 divorces: alimony not deductible/taxable
          extractedData.tax_profile.alimony_taxable = false;
          // Ask about child support and custody
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Do you have children from this marriage?</strong><br><small>Understanding custody arrangements helps determine who can claim dependents.</small>`, [
              { label: 'Yes, I have primary custody', value: 'custody_primary' },
              { label: 'Yes, shared custody', value: 'custody_shared' },
              { label: 'Yes, ex has primary custody', value: 'custody_ex' },
              { label: 'No children', value: 'custody_none' }
            ]);
          }, 800);
          return;
        }

      // Alimony Handlers (pre-2019 divorces)
      } else if (value.startsWith('alimony_')) {
        const alimonyType = value.replace('alimony_', '');
        const alimonyLabels = { 'paid': 'I paid alimony', 'received': 'I received alimony', 'none': 'No alimony' };
        addMessage('user', alimonyLabels[alimonyType] || alimonyType);
        extractedData.tax_profile.alimony_type = alimonyType;

        if (alimonyType === 'paid' || alimonyType === 'received') {
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>How much alimony did you ${alimonyType === 'paid' ? 'pay' : 'receive'} this year?</strong>`, [
              { label: 'Under $10,000', value: `alimony_amt_${alimonyType}_under10k` },
              { label: '$10,000 - $25,000', value: `alimony_amt_${alimonyType}_10_25k` },
              { label: '$25,000 - $50,000', value: `alimony_amt_${alimonyType}_25_50k` },
              { label: 'Over $50,000', value: `alimony_amt_${alimonyType}_over50k` }
            ]);
          }, 800);
          return;
        }
        startIntelligentQuestioning();

      // Alimony Amount Handlers
      } else if (value.startsWith('alimony_amt_')) {
        const parts = value.replace('alimony_amt_', '').split('_');
        const type = parts[0]; // 'paid' or 'received'
        const amtKey = parts.slice(1).join('_');
        const amtLabels = { 'under10k': 'Under $10,000', '10_25k': '$10,000-$25,000', '25_50k': '$25,000-$50,000', 'over50k': 'Over $50,000' };
        const amtValues = { 'under10k': 5000, '10_25k': 17500, '25_50k': 37500, 'over50k': 75000 };
        addMessage('user', amtLabels[amtKey] || amtKey);

        if (type === 'paid') {
          extractedData.tax_profile.alimony_paid = amtValues[amtKey] || 10000;
          extractedData.tax_profile.alimony_deduction = extractedData.tax_profile.alimony_paid;
        } else {
          extractedData.tax_profile.alimony_received = amtValues[amtKey] || 10000;
          extractedData.tax_profile.alimony_income = extractedData.tax_profile.alimony_received;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // Custody Handlers
      } else if (value.startsWith('custody_')) {
        const custodyType = value.replace('custody_', '');
        const custodyLabels = { 'primary': 'Primary custody', 'shared': 'Shared custody', 'ex': 'Ex has primary custody', 'none': 'No children' };
        addMessage('user', custodyLabels[custodyType] || custodyType);
        extractedData.tax_profile.custody_arrangement = custodyType;

        if (custodyType === 'primary' || custodyType === 'shared') {
          // Ask about Form 8332 (release of claim to exemption)
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Did you sign Form 8332 to release your claim to the child's exemption?</strong><br><small>The custodial parent typically claims the child, but can release this right to the other parent.</small>`, [
              { label: 'Yes, I signed Form 8332', value: 'form8332_signed' },
              { label: 'No, I will claim my children', value: 'form8332_no' },
              { label: 'We alternate years', value: 'form8332_alternate' },
              { label: 'Not sure', value: 'form8332_unsure' }
            ]);
          }, 800);
          return;
        }
        startIntelligentQuestioning();

      // Form 8332 Handlers
      } else if (value.startsWith('form8332_')) {
        const f8332Type = value.replace('form8332_', '');
        const f8332Labels = { 'signed': 'Signed Form 8332', 'no': 'I will claim my children', 'alternate': 'We alternate years', 'unsure': 'Not sure' };
        addMessage('user', f8332Labels[f8332Type] || f8332Type);
        extractedData.tax_profile.form_8332_status = f8332Type;

        if (f8332Type === 'signed') {
          extractedData.tax_profile.released_dependency_claim = true;
        } else if (f8332Type === 'alternate') {
          extractedData.tax_profile.alternates_dependency_claim = true;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // Separated Living Handlers
      } else if (value.startsWith('separated_')) {
        const sepType = value.replace('separated_', '');
        addMessage('user', sepType === 'live_apart' ? 'Living separately' : 'Same home');
        extractedData.tax_profile.separated_living_apart = (sepType === 'live_apart');

        if (sepType === 'live_apart') {
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Have you lived apart for the last 6 months of the year?</strong><br><small>This is one requirement for filing as Head of Household while married.</small>`, [
              { label: 'Yes, 6+ months apart', value: 'apart_6months_yes' },
              { label: 'No, less than 6 months', value: 'apart_6months_no' }
            ]);
          }, 800);
          return;
        }
        startIntelligentQuestioning();

      // 6 Months Apart Handler
      } else if (value.startsWith('apart_6months_')) {
        const apart = value.replace('apart_6months_', '');
        addMessage('user', apart === 'yes' ? '6+ months apart' : 'Less than 6 months');
        extractedData.tax_profile.apart_6_months = (apart === 'yes');

        if (apart === 'yes') {
          extractedData.tax_profile.may_qualify_hoh = true;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // Widowed Handlers
      } else if (value.startsWith('widowed_')) {
        const widowedType = value.replace('widowed_', '');
        addMessage('user', widowedType === 'with_deps' ? 'Dependents in my home' : 'No dependents');

        if (widowedType === 'with_deps') {
          extractedData.tax_profile.qualifies_qss = true;
          extractedData.tax_profile.filing_status = 'Qualifying Surviving Spouse';
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `You may qualify for <strong>Qualifying Surviving Spouse</strong> status, which provides the same tax rates as Married Filing Jointly for up to 2 years after your spouse's passing. This can result in significant tax savings.<br><br>Let's continue gathering your information.`);
            setTimeout(() => startIntelligentQuestioning(), 1500);
          }, 800);
          return;
        }
        startIntelligentQuestioning();

      } else if (value.startsWith('income_')) {
        let incomeText = '';
        let incomeAmount = 0;

        if (value === 'income_custom') {
          addMessage('user', 'I\'ll type my exact income');
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `Please enter your total annual income for 2025:<br><br><input type="number" id="incomeInput" placeholder="Enter amount" style="width: 100%; padding: var(--space-3-5); margin: var(--space-3) 0; background: rgba(255,255,255,0.05); border: 2px solid var(--border); border-radius: var(--radius-lg); color: var(--text); font-size: var(--text-base);" onkeypress="if(event.key==='Enter') captureIncome()"><br><button onclick="captureIncome()" style="padding: var(--space-3) var(--space-8); background: var(--primary); color: white; border: none; border-radius: var(--radius-lg); cursor: pointer; font-weight: var(--font-semibold); margin-top: var(--space-2);">Continue →</button>`);
            setTimeout(() => document.getElementById('incomeInput').focus(), 100);
          }, 1000);
          return;
        } else if (value === 'income_0_50k') {
          incomeText = '$0 - $50,000';
          incomeAmount = 35000;
        } else if (value === 'income_50_100k') {
          incomeText = '$50,000 - $100,000';
          incomeAmount = 75000;
        } else if (value === 'income_100_200k') {
          incomeText = '$100,000 - $200,000';
          incomeAmount = 150000;
        } else if (value === 'income_200_500k') {
          incomeText = '$200,000 - $500,000';
          incomeAmount = 350000;
        } else if (value === 'income_500k_plus') {
          incomeText = 'Over $500,000';
          incomeAmount = 750000;
        }

        addMessage('user', incomeText);
        // Mark as user-confirmed to prevent AI from overwriting
        setConfirmedValues({
          'tax_profile.total_income': incomeAmount,
          'tax_profile.w2_income': incomeAmount // Assume W2 unless told otherwise
        });
        extractedData.lead_data.score += 15;
        updateStats({ total_income: incomeAmount });
        calculateLeadScore();

        // Update savings estimate
        updateSavingsEstimate();

        startIntelligentQuestioning();

      } else if (value.startsWith('dependents_')) {
        const depCount = value.replace('dependents_', '');
        const depNum = depCount === '3plus' ? 3 : parseInt(depCount);
        const depText = depNum === 0 ? 'No dependents' : depNum === 1 ? '1 dependent' : `${depNum}+ dependents`;

        addMessage('user', depText);
        // Mark as user-confirmed to prevent AI from overwriting
        setConfirmedValue('tax_profile.dependents', depNum);
        extractedData.lead_data.score += 10;
        calculateLeadScore();

        startIntelligentQuestioning();

      // State selection handlers
      } else if (value.startsWith('state_')) {
        const stateCode = value.replace('state_', '');
        const stateLabels = {
          'CA': 'California',
          'NY': 'New York',
          'TX': 'Texas',
          'FL': 'Florida',
          'other': 'Other state'
        };
        const stateText = stateLabels[stateCode] || stateCode;

        addMessage('user', stateText);
        // Use 'OTHER' for other states so the flow continues (not empty string)
        // Mark as user-confirmed to prevent AI from overwriting
        setConfirmedValue('tax_profile.state', stateCode === 'other' ? 'OTHER' : stateCode);
        extractedData.lead_data.score += 5;
        calculateLeadScore();

        // States with significant local/city taxes - ask follow-up questions
        const statesWithLocalTax = {
          'NY': { name: 'New York', cities: ['New York City', 'Yonkers', 'Other NY area'], question: 'Do you live or work in a city with local income tax?' },
          'OH': { name: 'Ohio', cities: ['Columbus', 'Cleveland', 'Cincinnati', 'Toledo', 'Other OH city'], question: 'Most Ohio cities have their own income tax. Which city do you live in?' },
          'PA': { name: 'Pennsylvania', cities: ['Philadelphia', 'Pittsburgh', 'Other PA city', 'None (rural)'], question: 'Pennsylvania has local earned income taxes. Do you live in a city with additional taxes?' },
          'MD': { name: 'Maryland', cities: ['Baltimore City', 'Montgomery County', 'Prince George\'s County', 'Other MD county'], question: 'Maryland counties have varying tax rates. Which county do you live in?' },
          'IN': { name: 'Indiana', cities: ['Indianapolis/Marion', 'Fort Wayne', 'Other IN county'], question: 'Indiana has county income taxes. Which county do you live in?' },
          'KY': { name: 'Kentucky', cities: ['Louisville', 'Lexington', 'Other KY city'], question: 'Kentucky has local occupational taxes. Do you live or work in a major city?' }
        };

        if (statesWithLocalTax[stateCode] && !extractedData.tax_profile.local_tax_explored) {
          const stateInfo = statesWithLocalTax[stateCode];
          showTyping();
          setTimeout(() => {
            hideTyping();
            const cityOptions = stateInfo.cities.map((city, idx) => ({
              label: city,
              value: `localtax_${stateCode}_${idx}`
            }));
            cityOptions.push({ label: 'Not sure', value: `localtax_${stateCode}_unsure` });
            addMessage('ai', `<strong>${stateInfo.question}</strong><br><small>This helps calculate your total state and local tax obligation.</small>`, cityOptions);
          }, 800);
          return;
        }

        // No income tax states - note this benefit
        const noIncomeTaxStates = ['AK', 'FL', 'NV', 'SD', 'TN', 'TX', 'WA', 'WY', 'NH'];
        if (noIncomeTaxStates.includes(stateCode)) {
          extractedData.tax_profile.no_state_income_tax = true;
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `Great! ${stateText} has <strong>no state income tax</strong>, which is a nice advantage. Let's continue.`);
            setTimeout(() => startIntelligentQuestioning(), 1000);
          }, 800);
          return;
        }

        // High tax states - note potential SALT cap impact
        const highTaxStates = ['CA', 'NY', 'NJ', 'CT', 'MA', 'OR', 'MN', 'HI'];
        if (highTaxStates.includes(stateCode)) {
          extractedData.tax_profile.high_tax_state = true;
        }

        startIntelligentQuestioning();

      // Local Tax Handlers
      } else if (value.startsWith('localtax_')) {
        const parts = value.replace('localtax_', '').split('_');
        const stateCode = parts[0];
        const cityIdx = parts[1];
        extractedData.tax_profile.local_tax_explored = true;

        const localTaxInfo = {
          'NY': { cities: ['New York City', 'Yonkers', 'Other NY area'], rates: [3.876, 1.5, 0] },
          'OH': { cities: ['Columbus', 'Cleveland', 'Cincinnati', 'Toledo', 'Other OH city'], rates: [2.5, 2.5, 2.1, 2.25, 1.5] },
          'PA': { cities: ['Philadelphia', 'Pittsburgh', 'Other PA city', 'None'], rates: [3.79, 3.0, 1.0, 0] },
          'MD': { cities: ['Baltimore City', 'Montgomery County', 'Prince George\'s County', 'Other MD county'], rates: [3.2, 3.2, 3.2, 2.5] },
          'IN': { cities: ['Indianapolis/Marion', 'Fort Wayne', 'Other IN county'], rates: [2.02, 1.35, 1.5] },
          'KY': { cities: ['Louisville', 'Lexington', 'Other KY city'], rates: [2.2, 2.25, 1.5] }
        };

        if (cityIdx === 'unsure') {
          addMessage('user', 'Not sure about local taxes');
          extractedData.tax_profile.local_tax_city = 'unknown';
        } else {
          const info = localTaxInfo[stateCode];
          const idx = parseInt(cityIdx);
          if (info && info.cities[idx]) {
            addMessage('user', info.cities[idx]);
            extractedData.tax_profile.local_tax_city = info.cities[idx];
            extractedData.tax_profile.local_tax_rate = info.rates[idx];

            if (info.rates[idx] > 0) {
              showTyping();
              setTimeout(() => {
                hideTyping();
                addMessage('ai', `Got it. ${info.cities[idx]} has a local income tax rate of approximately <strong>${info.rates[idx]}%</strong>. This will be factored into your tax estimate.`);
                setTimeout(() => startIntelligentQuestioning(), 1000);
              }, 800);
              return;
            }
          }
        }
        startIntelligentQuestioning();

      // Income source handlers
      } else if (value.startsWith('source_')) {
        const source = value.replace('source_', '');
        const sourceLabels = {
          'w2': 'W-2 Employee',
          'self_employed': 'Self-Employed / 1099',
          'business': 'Business Owner',
          'investments': 'Investments / Retirement',
          'multiple': 'Multiple sources'
        };
        const sourceText = sourceLabels[source] || source;

        addMessage('user', sourceText);
        extractedData.tax_profile.income_source = sourceText;
        if (source === 'self_employed' || source === 'business') {
          extractedData.tax_profile.is_self_employed = true;
        }
        extractedData.lead_data.score += 10;
        calculateLeadScore();

        // For retirement income, ask about Social Security and pension
        if (source === 'investments') {
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>What types of retirement income do you have?</strong>`, [
              { label: 'Social Security benefits', value: 'retire_income_ss' },
              { label: 'Pension income', value: 'retire_income_pension' },
              { label: 'IRA/401k withdrawals', value: 'retire_income_ira' },
              { label: 'Investment dividends/interest', value: 'retire_income_invest' },
              { label: 'Multiple types', value: 'retire_income_multiple' }
            ]);
          }, 800);
          return;
        }

        startIntelligentQuestioning();

      // Retirement Income Type Handlers
      } else if (value.startsWith('retire_income_')) {
        const retireType = value.replace('retire_income_', '');
        const retireLabels = { 'ss': 'Social Security', 'pension': 'Pension', 'ira': 'IRA/401k withdrawals', 'invest': 'Investment income', 'multiple': 'Multiple types' };
        addMessage('user', retireLabels[retireType] || retireType);
        extractedData.tax_profile.retirement_income_type = retireType;

        if (retireType === 'ss' || retireType === 'multiple') {
          extractedData.tax_profile.has_social_security = true;
          // Ask about SS taxation
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>What's your approximate annual Social Security benefit?</strong><br><small>Up to 85% of SS may be taxable depending on total income.</small>`, [
              { label: 'Under $20,000', value: 'ss_amt_under20k' },
              { label: '$20,000 - $35,000', value: 'ss_amt_20_35k' },
              { label: '$35,000 - $50,000', value: 'ss_amt_35_50k' },
              { label: 'Over $50,000', value: 'ss_amt_over50k' }
            ]);
          }, 800);
          return;
        } else if (retireType === 'pension') {
          extractedData.tax_profile.has_pension = true;
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>What's your approximate annual pension income?</strong>`, [
              { label: 'Under $25,000', value: 'pension_amt_under25k' },
              { label: '$25,000 - $50,000', value: 'pension_amt_25_50k' },
              { label: '$50,000 - $100,000', value: 'pension_amt_50_100k' },
              { label: 'Over $100,000', value: 'pension_amt_over100k' }
            ]);
          }, 800);
          return;
        } else if (retireType === 'ira') {
          extractedData.tax_profile.has_ira_withdrawals = true;
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Are you 73 or older (required to take RMDs)?</strong><br><small>Required Minimum Distributions must be taken from traditional IRAs/401ks.</small>`, [
              { label: 'Yes, I take RMDs', value: 'rmd_yes' },
              { label: 'No, not yet 73', value: 'rmd_no' },
              { label: 'I\'m close to RMD age', value: 'rmd_soon' }
            ]);
          }, 800);
          return;
        }
        startIntelligentQuestioning();

      // Social Security Amount Handlers
      } else if (value.startsWith('ss_amt_')) {
        const ssAmt = value.replace('ss_amt_', '');
        const ssAmounts = { 'under20k': 15000, '20_35k': 27500, '35_50k': 42500, 'over50k': 60000 };
        const ssLabels = { 'under20k': 'Under $20,000', '20_35k': '$20,000-$35,000', '35_50k': '$35,000-$50,000', 'over50k': 'Over $50,000' };
        addMessage('user', ssLabels[ssAmt] || ssAmt);
        extractedData.tax_profile.social_security_amount = ssAmounts[ssAmt] || 27500;

        // Calculate potential SS taxation (depends on provisional income)
        const ssAmount = ssAmounts[ssAmt] || 27500;
        const otherIncome = extractedData.tax_profile.total_income || 50000;
        const provisionalIncome = otherIncome + (ssAmount / 2);
        const filingStatus = extractedData.tax_profile.filing_status;
        const threshold1 = filingStatus === 'Married Filing Jointly' ? 32000 : 25000;
        const threshold2 = filingStatus === 'Married Filing Jointly' ? 44000 : 34000;

        let taxablePct = 0;
        if (provisionalIncome > threshold2) {
          taxablePct = 0.85;
        } else if (provisionalIncome > threshold1) {
          taxablePct = 0.50;
        }
        extractedData.tax_profile.ss_taxable_percentage = taxablePct;
        extractedData.tax_profile.ss_taxable_amount = Math.round(ssAmount * taxablePct);

        if (taxablePct > 0) {
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `Based on your income, approximately <strong>${Math.round(taxablePct * 100)}% of your Social Security</strong> (~$${extractedData.tax_profile.ss_taxable_amount.toLocaleString()}) may be taxable.<br><br>Would you like strategies to reduce this?`, [
              { label: 'Yes, show me strategies', value: 'ss_strategy_yes' },
              { label: 'No, continue with assessment', value: 'ss_strategy_no' }
            ]);
          }, 1000);
          return;
        }
        startIntelligentQuestioning();

      // SS Strategy Response Handlers
      } else if (value === 'ss_strategy_yes' || value === 'ss_strategy_no') {
        addMessage('user', value === 'ss_strategy_yes' ? 'Show me strategies' : 'Continue');
        if (value === 'ss_strategy_yes') {
          extractedData.tax_profile.wants_ss_strategies = true;
        }
        startIntelligentQuestioning();

      // Pension Amount Handlers
      } else if (value.startsWith('pension_amt_')) {
        const pensionAmt = value.replace('pension_amt_', '');
        const pensionAmounts = { 'under25k': 15000, '25_50k': 37500, '50_100k': 75000, 'over100k': 125000 };
        addMessage('user', `$${(pensionAmounts[pensionAmt] || 37500).toLocaleString()}`);
        extractedData.tax_profile.pension_amount = pensionAmounts[pensionAmt] || 37500;
        startIntelligentQuestioning();

      // RMD (Required Minimum Distribution) Handlers
      } else if (value.startsWith('rmd_')) {
        const rmdStatus = value.replace('rmd_', '');
        const rmdLabels = { 'yes': 'Yes, I take RMDs', 'no': 'Not yet 73', 'soon': 'Close to RMD age' };
        addMessage('user', rmdLabels[rmdStatus] || rmdStatus);
        extractedData.tax_profile.rmd_status = rmdStatus;

        if (rmdStatus === 'yes') {
          extractedData.tax_profile.takes_rmds = true;
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>What's your approximate annual RMD amount?</strong>`, [
              { label: 'Under $10,000', value: 'rmd_amt_under10k' },
              { label: '$10,000 - $30,000', value: 'rmd_amt_10_30k' },
              { label: '$30,000 - $75,000', value: 'rmd_amt_30_75k' },
              { label: 'Over $75,000', value: 'rmd_amt_over75k' }
            ]);
          }, 800);
          return;
        } else if (rmdStatus === 'soon') {
          extractedData.tax_profile.approaching_rmd_age = true;
        }
        startIntelligentQuestioning();

      // RMD Amount Handlers
      } else if (value.startsWith('rmd_amt_')) {
        const rmdAmt = value.replace('rmd_amt_', '');
        const rmdAmounts = { 'under10k': 7500, '10_30k': 20000, '30_75k': 52500, 'over75k': 100000 };
        addMessage('user', `$${(rmdAmounts[rmdAmt] || 20000).toLocaleString()}`);
        extractedData.tax_profile.rmd_amount = rmdAmounts[rmdAmt] || 20000;
        startIntelligentQuestioning();

      // Deduction exploration handlers
      } else if (value.startsWith('deduction_')) {
        const deduction = value.replace('deduction_', '');
        if (deduction === 'none') {
          addMessage('user', 'None of these apply');
          extractedData.tax_profile.deductions_explored = true;
          calculateLeadScore();
          startIntelligentQuestioning();
        } else {
          const deductionLabels = {
            'mortgage': 'Own a home',
            'charity': 'Make charitable donations',
            'medical': 'Have high medical expenses',
            'retirement': 'Contribute to retirement'
          };
          addMessage('user', deductionLabels[deduction] || deduction);

          // Prevent duplicate deductions
          extractedData.deductions = extractedData.deductions || [];
          if (!extractedData.deductions.includes(deduction)) {
            extractedData.deductions.push(deduction);
            extractedData.lead_data.score += 5;
          }

          // Set flags for deductions - amounts will be asked in follow-ups
          if (deduction === 'retirement') {
            extractedData.tax_profile.has_retirement_contributions = true;
          }
          if (deduction === 'investment_loss') {
            extractedData.tax_profile.has_investment_losses = true;
            extractedData.lead_data.score += 5;
          }

          // Mortgage - ask for amount and property tax
          if (deduction === 'mortgage') {
            extractedData.tax_profile.has_mortgage = true;
            extractedData.tax_profile.owns_home = true;
            showTyping();
            setTimeout(() => {
              hideTyping();
              addMessage('ai', `Great! Mortgage interest is a valuable deduction. <strong>What's your approximate annual mortgage interest?</strong>`, [
                { label: 'Under $5,000', value: 'mortgageamt_under5k' },
                { label: '$5,000 - $15,000', value: 'mortgageamt_5_15k' },
                { label: '$15,000 - $30,000', value: 'mortgageamt_15_30k' },
                { label: 'Over $30,000', value: 'mortgageamt_over30k' }
              ]);
            }, 800);
            return;
          }

          // Charitable donations - ask for amount
          if (deduction === 'charity') {
            extractedData.tax_profile.has_charitable = true;
            showTyping();
            setTimeout(() => {
              hideTyping();
              addMessage('ai', `<strong>How much do you typically donate to charity annually?</strong>`, [
                { label: 'Under $500', value: 'charityamt_under500' },
                { label: '$500 - $2,500', value: 'charityamt_500_2500' },
                { label: '$2,500 - $10,000', value: 'charityamt_2500_10k' },
                { label: 'Over $10,000', value: 'charityamt_over10k' }
              ]);
            }, 800);
            return;
          }

          // Medical expenses - ask for amount
          if (deduction === 'medical') {
            showTyping();
            setTimeout(() => {
              hideTyping();
              addMessage('ai', `Medical expenses can potentially be deducted if they exceed 7.5% of your income. <strong>What's your estimated annual medical expense?</strong>`, [
                { label: 'Under $5,000', value: 'medical_amount_low' },
                { label: '$5,000 - $15,000', value: 'medical_amount_medium' },
                { label: '$15,000 - $30,000', value: 'medical_amount_high' },
                { label: 'Over $30,000', value: 'medical_amount_very_high' }
              ]);
            }, 800);
            return;
          }

          extractedData.tax_profile.deductions_explored = true;
          calculateLeadScore();
          startIntelligentQuestioning();
        }

      // Mortgage amount handlers
      } else if (value.startsWith('mortgageamt_')) {
        const amt = value.replace('mortgageamt_', '');
        const amounts = { 'under5k': 3000, '5_15k': 10000, '15_30k': 22500, 'over30k': 40000 };
        const labels = { 'under5k': 'Under $5,000', '5_15k': '$5,000-$15,000', '15_30k': '$15,000-$30,000', 'over30k': 'Over $30,000' };
        addMessage('user', labels[amt] || amt);
        extractedData.tax_items.mortgage_interest = amounts[amt] || 10000;

        // Follow up with property tax question
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<strong>What's your approximate annual property tax?</strong>`, [
            { label: 'Under $3,000', value: 'proptaxamt_under3k' },
            { label: '$3,000 - $8,000', value: 'proptaxamt_3_8k' },
            { label: '$8,000 - $15,000', value: 'proptaxamt_8_15k' },
            { label: 'Over $15,000', value: 'proptaxamt_over15k' }
          ]);
        }, 800);

      } else if (value.startsWith('proptaxamt_')) {
        const amt = value.replace('proptaxamt_', '');
        const amounts = { 'under3k': 2000, '3_8k': 5500, '8_15k': 11500, 'over15k': 20000 };
        const labels = { 'under3k': 'Under $3,000', '3_8k': '$3,000-$8,000', '8_15k': '$8,000-$15,000', 'over15k': 'Over $15,000' };
        addMessage('user', labels[amt] || amt);
        extractedData.tax_items.property_tax = amounts[amt] || 5500;
        // Note: SALT cap is $10,000
        extractedData.tax_profile.deductions_explored = true;
        calculateLeadScore();
        startIntelligentQuestioning();

      // Charitable donation amount handlers
      } else if (value.startsWith('charityamt_')) {
        const amt = value.replace('charityamt_', '');
        const amounts = { 'under500': 250, '500_2500': 1500, '2500_10k': 6000, 'over10k': 15000 };
        const labels = { 'under500': 'Under $500', '500_2500': '$500-$2,500', '2500_10k': '$2,500-$10,000', 'over10k': 'Over $10,000' };
        addMessage('user', labels[amt] || amt);
        extractedData.tax_items.charitable = amounts[amt] || 1500;
        extractedData.tax_profile.deductions_explored = true;
        calculateLeadScore();
        startIntelligentQuestioning();

      // Medical expense amount handlers
      } else if (value.startsWith('medical_amount_')) {
        const medicalLevel = value.replace('medical_amount_', '');
        const medicalAmounts = {
          'low': 2500,
          'medium': 10000,
          'high': 22500,
          'very_high': 40000
        };
        const medicalLabels = {
          'low': 'Under $5,000',
          'medium': '$5,000 - $15,000',
          'high': '$15,000 - $30,000',
          'very_high': 'Over $30,000'
        };
        const amount = medicalAmounts[medicalLevel] || 10000;
        addMessage('user', medicalLabels[medicalLevel] || `$${amount.toLocaleString()}`);
        extractedData.tax_items.medical = amount;
        extractedData.tax_profile.deductions_explored = true;
        calculateLeadScore();
        startIntelligentQuestioning();

      // Medical amount skip handler
      } else if (value === 'medical_amt_skip') {
        addMessage('user', 'Skip medical expenses');
        extractedData.tax_profile.medical_explored = true;
        continueToDeductionsFromFocus();

      // Tax goal handlers
      } else if (value.startsWith('goal_')) {
        const goal = value.replace('goal_', '');
        const goalLabels = {
          'reduce_taxes': 'Reduce my current tax bill',
          'retirement': 'Maximize retirement savings',
          'life_event': 'Plan for a major life event',
          'wealth': 'Build long-term wealth tax-efficiently',
          'optimize': 'General tax optimization'
        };
        addMessage('user', goalLabels[goal] || goal);
        extractedData.tax_profile.primary_goal = goal;
        extractedData.tax_profile.goals_explored = true;
        extractedData.lead_data.score += 10;
        calculateLeadScore();
        startIntelligentQuestioning();

      // =====================================================================
      // W-4 WITHHOLDING HANDLERS
      // =====================================================================

      } else if (value.startsWith('withhold_')) {
        const withholdType = value.replace('withhold_', '');
        const withholdLabels = {
          'strategic': 'Yes, I adjust it strategically',
          'default': 'No, I use the default settings',
          'large_refund': 'I usually get a large refund',
          'owe': 'I usually owe taxes',
          'skip': 'Skip'
        };
        addMessage('user', withholdLabels[withholdType] || withholdType);
        extractedData.tax_profile.withholding_explored = true;
        extractedData.tax_profile.withholding_status = withholdType;

        if (withholdType === 'large_refund') {
          extractedData.tax_profile.may_need_w4_adjustment = true;
          // Large refund means overwithholding - opportunity for adjustment
        }
        if (withholdType === 'owe') {
          extractedData.tax_profile.may_need_w4_adjustment = true;
          extractedData.tax_profile.possible_underpayment_penalty = true;
        }
        extractedData.lead_data.score += 5;
        calculateLeadScore();
        startIntelligentQuestioning();

      // =====================================================================
      // PRIOR YEAR TAX SITUATION HANDLERS
      // =====================================================================

      } else if (value.startsWith('prior_')) {
        const priorType = value.replace('prior_', '');
        const priorLabels = {
          'large_refund': 'Got a large refund (over $2,000)',
          'small_refund': 'Got a small refund (under $2,000)',
          'owed': 'Owed money to the IRS',
          'breakeven': 'About break-even',
          'skip': 'First time filing / Skip'
        };
        addMessage('user', priorLabels[priorType] || priorType);
        extractedData.tax_profile.prior_year_explored = true;
        extractedData.tax_profile.prior_year_result = priorType;

        if (priorType === 'large_refund') {
          extractedData.tax_profile.prior_had_large_refund = true;
        }
        if (priorType === 'owed') {
          extractedData.tax_profile.prior_owed_taxes = true;
        }
        extractedData.lead_data.score += 5;
        calculateLeadScore();
        startIntelligentQuestioning();

      // =====================================================================
      // SPOUSE INCOME HANDLERS (for MFJ)
      // =====================================================================

      } else if (value.startsWith('spouse_')) {
        const spouseType = value.replace('spouse_', '');
        const spouseLabels = {
          'w2': 'Yes, W-2 employment',
          'self_employed': 'Yes, self-employed',
          'both': 'Yes, both W-2 and self-employed',
          'none': 'No, spouse doesn\'t work',
          'skip': 'Skip'
        };
        addMessage('user', spouseLabels[spouseType] || spouseType);
        extractedData.tax_profile.spouse_income_explored = true;
        extractedData.tax_profile.spouse_income_type = spouseType;

        if (spouseType === 'w2' || spouseType === 'both') {
          extractedData.tax_profile.spouse_has_w2 = true;
        }
        if (spouseType === 'self_employed' || spouseType === 'both') {
          extractedData.tax_profile.spouse_is_self_employed = true;
          extractedData.lead_data.complexity = 'complex';
        }
        extractedData.lead_data.score += 5;
        calculateLeadScore();
        startIntelligentQuestioning();

      // =====================================================================
      // BUSINESS & SELF-EMPLOYMENT HANDLERS
      // =====================================================================

      // Flow A business TYPE handlers (industry/category - different from entity structure)
      } else if (value === 'biz_professional' || value === 'biz_retail' ||
                 value === 'biz_realestate' || value === 'biz_tech' || value === 'biz_service' || value === 'biz_farm') {
        const bizType = value.replace('biz_', '');
        const bizLabels = {
          'professional': 'Professional Services',
          'retail': 'Retail / E-commerce',
          'realestate': 'Real Estate',
          'tech': 'Tech / Software',
          'service': 'Other Service Business',
          'farm': 'Farming / Agriculture'
        };
        addMessage('user', bizLabels[bizType] || bizType);
        extractedData.tax_profile.business_type = bizType;
        extractedData.lead_data.score += 5;

        // Farm income uses Schedule F instead of Schedule C
        if (bizType === 'farm') {
          extractedData.tax_profile.uses_schedule_f = true;
          extractedData.lead_data.complexity = 'complex';
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>What type of farming operation?</strong><br><small>Farm income is reported on Schedule F with special provisions.</small>`, [
              { label: 'Crop production', value: 'farm_type_crops' },
              { label: 'Livestock', value: 'farm_type_livestock' },
              { label: 'Dairy', value: 'farm_type_dairy' },
              { label: 'Mixed farming', value: 'farm_type_mixed' },
              { label: 'Timber/forestry', value: 'farm_type_timber' }
            ]);
          }, 800);
          return;
        }

        calculateLeadScore();
        startIntelligentQuestioning();

      // Farm Type Handlers
      } else if (value.startsWith('farm_type_')) {
        const farmType = value.replace('farm_type_', '');
        const farmLabels = { 'crops': 'Crop production', 'livestock': 'Livestock', 'dairy': 'Dairy', 'mixed': 'Mixed farming', 'timber': 'Timber/forestry' };
        addMessage('user', farmLabels[farmType] || farmType);
        extractedData.tax_profile.farm_type = farmType;

        // Ask about farm income
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<strong>What's your approximate gross farm income for the year?</strong>`, [
            { label: 'Under $50,000', value: 'farm_income_under50k' },
            { label: '$50,000 - $150,000', value: 'farm_income_50_150k' },
            { label: '$150,000 - $500,000', value: 'farm_income_150_500k' },
            { label: 'Over $500,000', value: 'farm_income_over500k' }
          ]);
        }, 800);

      // Farm Income Handlers
      } else if (value.startsWith('farm_income_')) {
        const farmIncome = value.replace('farm_income_', '');
        const incomeAmounts = { 'under50k': 35000, '50_150k': 100000, '150_500k': 325000, 'over500k': 750000 };
        addMessage('user', `$${(incomeAmounts[farmIncome] || 100000).toLocaleString()}`);
        extractedData.tax_profile.farm_gross_income = incomeAmounts[farmIncome] || 100000;

        // Ask about farm expenses - MULTI-SELECT
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<strong>What are your major farm expense categories?</strong> (Select all that apply)`, [
            { label: '🌾 Seeds, feed, fertilizer', value: 'farm_exp_supplies' },
            { label: '🚜 Equipment & machinery', value: 'farm_exp_equipment' },
            { label: '👷 Labor costs', value: 'farm_exp_labor' },
            { label: '🏞️ Land rent/lease', value: 'farm_exp_land' },
            { label: '⛽ Fuel & utilities', value: 'farm_exp_fuel' }
          ], { multiSelect: true });
        }, 800);

      // Farm Expense Handlers - Multi-select
      } else if (value.includes('farm_exp_') && value.includes(',')) {
        const expTypes = value.split(',').map(v => v.replace('farm_exp_', '').trim());
        extractedData.tax_profile.farm_expense_types = expTypes;
        extractedData.lead_data.score += expTypes.length * 2;
        calculateLeadScore();
        startIntelligentQuestioning();

      // Farm Expense Handlers - Single select
      } else if (value.startsWith('farm_exp_')) {
        const farmExp = value.replace('farm_exp_', '');
        const expLabels = { 'supplies': 'Seeds/feed/fertilizer', 'equipment': 'Equipment', 'labor': 'Labor', 'land': 'Land rent', 'fuel': 'Fuel & utilities' };
        addMessage('user', expLabels[farmExp] || farmExp);
        extractedData.tax_profile.farm_expense_type = farmExp;
        calculateLeadScore();
        startIntelligentQuestioning();

      } else if (value.startsWith('entity_')) {
        const entityType = value.replace('entity_', '');
        const entityLabels = {
          'sole': 'Sole Proprietorship',
          'llc_single': 'Single-Member LLC',
          'llc_multi': 'Multi-Member LLC / Partnership',
          'scorp': 'S-Corporation',
          'ccorp': 'C-Corporation'
        };
        addMessage('user', entityLabels[entityType] || entityType);
        extractedData.tax_profile.entity_type = entityType;
        extractedData.lead_data.score += 5;
        // S-Corp or C-Corp indicates more sophisticated tax planning
        if (entityType === 'scorp' || entityType === 'ccorp') {
          extractedData.lead_data.complexity = 'complex';
          extractedData.lead_data.score += 10;
        }
        calculateLeadScore();

        // S-Corp requires reasonable salary - critical IRS requirement
        if (entityType === 'scorp') {
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>As an S-Corp owner, do you pay yourself a W-2 salary?</strong><br><small>IRS requires S-Corp owners to take "reasonable compensation" as W-2 wages before distributions.</small>`, [
              { label: 'Yes, I take a W-2 salary', value: 'scorp_salary_yes' },
              { label: 'No, only distributions', value: 'scorp_salary_no' },
              { label: 'Not sure', value: 'scorp_salary_unsure' }
            ]);
          }, 800);
          return;
        }
        startIntelligentQuestioning();

      // S-Corp Reasonable Salary Handlers
      } else if (value.startsWith('scorp_salary_')) {
        const salaryStatus = value.replace('scorp_salary_', '');
        const salaryLabels = { 'yes': 'Yes, I take a W-2 salary', 'no': 'Only distributions', 'unsure': 'Not sure' };
        addMessage('user', salaryLabels[salaryStatus] || salaryStatus);
        extractedData.tax_profile.scorp_salary_status = salaryStatus;

        if (salaryStatus === 'no') {
          extractedData.tax_profile.scorp_compliance_risk = true;
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `${getIcon('exclamation-triangle', 'sm')} <strong>Important:</strong> IRS requires S-Corp owner-employees to receive reasonable compensation. Taking only distributions may trigger reclassification and payroll tax penalties.<br><br><strong>What's your approximate annual distributions/draws?</strong>`, [
              { label: 'Under $50,000', value: 'scorp_dist_under50k' },
              { label: '$50,000 - $100,000', value: 'scorp_dist_50_100k' },
              { label: '$100,000 - $200,000', value: 'scorp_dist_100_200k' },
              { label: 'Over $200,000', value: 'scorp_dist_over200k' }
            ]);
          }, 1000);
          return;
        } else if (salaryStatus === 'yes') {
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>What's your approximate annual W-2 salary from the S-Corp?</strong>`, [
              { label: 'Under $50,000', value: 'scorp_w2_under50k' },
              { label: '$50,000 - $80,000', value: 'scorp_w2_50_80k' },
              { label: '$80,000 - $120,000', value: 'scorp_w2_80_120k' },
              { label: '$120,000 - $160,000', value: 'scorp_w2_120_160k' },
              { label: 'Over $160,000', value: 'scorp_w2_over160k' }
            ]);
          }, 800);
          return;
        }
        startIntelligentQuestioning();

      // S-Corp W-2 Salary Amount Handlers
      } else if (value.startsWith('scorp_w2_') || value.startsWith('scorp_dist_')) {
        const isW2 = value.startsWith('scorp_w2_');
        const amt = value.replace(isW2 ? 'scorp_w2_' : 'scorp_dist_', '');
        const amounts = { 'under50k': 35000, '50_80k': 65000, '50_100k': 75000, '80_120k': 100000, '100_200k': 150000, '120_160k': 140000, 'over160k': 200000, 'over200k': 250000 };
        addMessage('user', `$${(amounts[amt] || 50000).toLocaleString()}`);

        if (isW2) {
          extractedData.tax_profile.scorp_w2_salary = amounts[amt] || 50000;
        } else {
          extractedData.tax_profile.scorp_distributions = amounts[amt] || 50000;
          // Flag if distributions significantly exceed what salary should be
          extractedData.tax_profile.needs_salary_review = true;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      } else if (value.startsWith('revenue_')) {
        const revenueRange = value.replace('revenue_', '');
        const revenueLabels = {
          'under50k': 'Under $50,000',
          '50_100k': '$50,000 - $100,000',
          '100_250k': '$100,000 - $250,000',
          '250_500k': '$250,000 - $500,000',
          'over500k': 'Over $500,000'
        };
        const revenueAmounts = {
          'under50k': 35000,
          '50_100k': 75000,
          '100_250k': 175000,
          '250_500k': 375000,
          'over500k': 750000
        };
        addMessage('user', revenueLabels[revenueRange] || revenueRange);
        extractedData.tax_profile.business_revenue = revenueAmounts[revenueRange] || 100000;
        extractedData.lead_data.score += 10;
        if (revenueAmounts[revenueRange] >= 250000) {
          extractedData.lead_data.complexity = 'complex';
        }
        calculateLeadScore();

        // For retail/e-commerce, ask about Cost of Goods Sold (COGS)
        const isRetail = extractedData.tax_profile.business_type === 'retail';
        if (isRetail) {
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Do you have Cost of Goods Sold (inventory purchases)?</strong><br><small>COGS is deducted from revenue before calculating profit.</small>`, [
              { label: 'Yes, significant inventory costs', value: 'cogs_yes_high' },
              { label: 'Yes, moderate inventory', value: 'cogs_yes_moderate' },
              { label: 'Minimal (mostly services/digital)', value: 'cogs_minimal' },
              { label: 'No inventory costs', value: 'cogs_none' }
            ]);
          }, 800);
          return;
        }
        startIntelligentQuestioning();

      // COGS (Cost of Goods Sold) Handlers
      } else if (value.startsWith('cogs_')) {
        const cogsLevel = value.replace('cogs_', '');
        const cogsLabels = { 'yes_high': 'Significant inventory', 'yes_moderate': 'Moderate inventory', 'minimal': 'Minimal', 'none': 'No inventory' };
        addMessage('user', cogsLabels[cogsLevel] || cogsLevel);
        extractedData.tax_profile.cogs_status = cogsLevel;

        if (cogsLevel === 'yes_high' || cogsLevel === 'yes_moderate') {
          extractedData.tax_profile.has_cogs = true;
          // Ask for COGS percentage
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>What percentage of your revenue goes to inventory/COGS?</strong>`, [
              { label: 'Under 25%', value: 'cogs_pct_under25' },
              { label: '25-40% (typical retail)', value: 'cogs_pct_25_40' },
              { label: '40-60% (product-heavy)', value: 'cogs_pct_40_60' },
              { label: 'Over 60%', value: 'cogs_pct_over60' }
            ]);
          }, 800);
          return;
        }
        startIntelligentQuestioning();

      // COGS Percentage Handlers
      } else if (value.startsWith('cogs_pct_')) {
        const cogsPct = value.replace('cogs_pct_', '');
        const pctAmounts = { 'under25': 0.20, '25_40': 0.325, '40_60': 0.50, 'over60': 0.70 };
        const pctLabels = { 'under25': 'Under 25%', '25_40': '25-40%', '40_60': '40-60%', 'over60': 'Over 60%' };
        addMessage('user', pctLabels[cogsPct] || cogsPct);
        extractedData.tax_profile.cogs_percentage = pctAmounts[cogsPct] || 0.325;
        // Calculate estimated COGS
        const revenue = extractedData.tax_profile.business_revenue || 100000;
        extractedData.tax_profile.estimated_cogs = Math.round(revenue * (pctAmounts[cogsPct] || 0.325));
        extractedData.tax_profile.gross_profit = revenue - extractedData.tax_profile.estimated_cogs;
        calculateLeadScore();
        startIntelligentQuestioning();

      // =====================================================================
      // BUSINESS EXPENSE HANDLERS
      // =====================================================================

      // Handle multi-select business expenses (comma-separated values)
      } else if (value.includes('bizexp_') && value.includes(',')) {
        const expTypes = value.split(',').map(v => v.replace('bizexp_', '').trim());
        const expLabels = {
          'home_office': 'Home Office',
          'vehicle': 'Vehicle / Mileage',
          'equipment': 'Equipment & Software',
          'marketing': 'Marketing & Advertising',
          'supplies': 'Supplies & Materials',
          'training': 'Training & Education'
        };

        // Store all selected expense types
        extractedData.tax_profile.business_expenses = expTypes;
        extractedData.lead_data.score += expTypes.length * 3;

        // Check which specific expense types were selected for follow-ups
        extractedData.tax_profile.has_home_office = expTypes.includes('home_office');
        extractedData.tax_profile.has_vehicle_expenses = expTypes.includes('vehicle');

        showTyping();
        setTimeout(() => {
          hideTyping();
          // If home office was selected, ask about it first
          if (expTypes.includes('home_office')) {
            addMessage('ai', `Great, you selected multiple expense categories! Let's start with your <strong>home office</strong>.\n\nWhat's the approximate square footage of your home office?`, [
              { label: 'Under 100 sq ft', value: 'homeoffice_under100' },
              { label: '100-300 sq ft', value: 'homeoffice_100_300' },
              { label: '300-500 sq ft', value: 'homeoffice_300_500' },
              { label: 'Over 500 sq ft', value: 'homeoffice_over500' }
            ]);
          } else if (expTypes.includes('vehicle')) {
            addMessage('ai', `Let's start with your <strong>vehicle expenses</strong>.\n\nApproximately how many business miles do you drive per year?`, [
              { label: 'Under 5,000 miles', value: 'vehicle_under5k' },
              { label: '5,000 - 15,000 miles', value: 'vehicle_5_15k' },
              { label: '15,000 - 30,000 miles', value: 'vehicle_15_30k' },
              { label: 'Over 30,000 miles', value: 'vehicle_over30k' }
            ]);
          } else {
            // Skip to summary if no home office or vehicle
            extractedData.tax_profile.business_expenses_explored = true;
            calculateLeadScore();
            startIntelligentQuestioning();
          }
        }, 800);

      } else if (value.startsWith('bizexp_')) {
        const expType = value.replace('bizexp_', '');
        const expLabels = {
          'home_office': 'Home Office',
          'vehicle': 'Vehicle / Mileage',
          'equipment': 'Equipment & Software',
          'marketing': 'Marketing & Advertising',
          'supplies': 'Supplies & Materials',
          'training': 'Training & Education',
          'skip': 'Continue without specifying'
        };
        addMessage('user', expLabels[expType] || expType);

        if (expType !== 'skip') {
          extractedData.tax_profile.business_expenses = extractedData.tax_profile.business_expenses || [];
          extractedData.tax_profile.business_expenses.push(expType);
          extractedData.lead_data.score += 5;

          // Ask for amount based on expense type
          showTyping();
          setTimeout(() => {
            hideTyping();
            if (expType === 'home_office') {
              extractedData.tax_profile.has_home_office = true;
              addMessage('ai', `<strong>What's the approximate square footage of your home office?</strong>`, [
                { label: 'Under 100 sq ft', value: 'homeoffice_under100' },
                { label: '100-300 sq ft', value: 'homeoffice_100_300' },
                { label: '300-500 sq ft', value: 'homeoffice_300_500' },
                { label: 'Over 500 sq ft', value: 'homeoffice_over500' }
              ]);
            } else if (expType === 'vehicle') {
              extractedData.tax_profile.has_vehicle_expenses = true;
              addMessage('ai', `<strong>Approximately how many business miles do you drive per year?</strong>`, [
                { label: 'Under 5,000 miles', value: 'vehicle_under5k' },
                { label: '5,000 - 15,000 miles', value: 'vehicle_5_15k' },
                { label: '15,000 - 30,000 miles', value: 'vehicle_15_30k' },
                { label: 'Over 30,000 miles', value: 'vehicle_over30k' }
              ]);
            } else if (expType === 'equipment') {
              addMessage('ai', `<strong>How much did you spend on equipment & software this year?</strong>`, [
                { label: 'Under $2,500', value: 'equipment_under2500' },
                { label: '$2,500 - $10,000', value: 'equipment_2500_10k' },
                { label: '$10,000 - $50,000', value: 'equipment_10_50k' },
                { label: 'Over $50,000', value: 'equipment_over50k' }
              ]);
            } else if (expType === 'marketing') {
              addMessage('ai', `<strong>How much do you spend on marketing & advertising annually?</strong>`, [
                { label: 'Under $1,000', value: 'marketing_under1k' },
                { label: '$1,000 - $5,000', value: 'marketing_1_5k' },
                { label: '$5,000 - $20,000', value: 'marketing_5_20k' },
                { label: 'Over $20,000', value: 'marketing_over20k' }
              ]);
            }
          }, 800);
        } else {
          extractedData.tax_profile.business_expenses_explored = true;
          calculateLeadScore();
          startIntelligentQuestioning();
        }

      // Business expense amount handlers
      } else if (value.startsWith('homeoffice_')) {
        const size = value.replace('homeoffice_', '');
        const sizeAmounts = { 'under100': 75, '100_300': 200, '300_500': 400, 'over500': 600 };
        const sizeLabels = { 'under100': 'Under 100 sq ft', '100_300': '100-300 sq ft', '300_500': '300-500 sq ft', 'over500': 'Over 500 sq ft' };
        addMessage('user', sizeLabels[size] || size);
        // Simplified method: $5 per sq ft
        extractedData.tax_items.home_office_sqft = sizeAmounts[size] || 200;
        extractedData.tax_items.home_office_deduction = (sizeAmounts[size] || 200) * 5;
        extractedData.tax_profile.business_expenses_explored = true;
        calculateLeadScore();
        startIntelligentQuestioning();

      } else if (value.startsWith('vehicle_')) {
        const miles = value.replace('vehicle_', '');
        const mileAmounts = { 'under5k': 3000, '5_15k': 10000, '15_30k': 22500, 'over30k': 40000 };
        const mileLabels = { 'under5k': 'Under 5,000 miles', '5_15k': '5,000-15,000 miles', '15_30k': '15,000-30,000 miles', 'over30k': 'Over 30,000 miles' };
        addMessage('user', mileLabels[miles] || miles);
        extractedData.tax_items.business_miles = mileAmounts[miles] || 10000;
        // 2024 IRS rate: $0.67 per mile
        extractedData.tax_items.vehicle_deduction = (mileAmounts[miles] || 10000) * 0.67;
        extractedData.tax_profile.business_expenses_explored = true;
        calculateLeadScore();
        startIntelligentQuestioning();

      } else if (value.startsWith('equipment_')) {
        const amt = value.replace('equipment_', '');
        const equipAmounts = { 'under2500': 1500, '2500_10k': 6000, '10_50k': 30000, 'over50k': 75000 };
        const equipLabels = { 'under2500': 'Under $2,500', '2500_10k': '$2,500-$10,000', '10_50k': '$10,000-$50,000', 'over50k': 'Over $50,000' };
        addMessage('user', equipLabels[amt] || amt);
        extractedData.tax_items.equipment_expense = equipAmounts[amt] || 6000;
        extractedData.tax_profile.business_expenses_explored = true;
        calculateLeadScore();
        startIntelligentQuestioning();

      } else if (value.startsWith('marketing_')) {
        const amt = value.replace('marketing_', '');
        const marketAmounts = { 'under1k': 500, '1_5k': 3000, '5_20k': 12500, 'over20k': 30000 };
        const marketLabels = { 'under1k': 'Under $1,000', '1_5k': '$1,000-$5,000', '5_20k': '$5,000-$20,000', 'over20k': 'Over $20,000' };
        addMessage('user', marketLabels[amt] || amt);
        extractedData.tax_items.marketing_expense = marketAmounts[amt] || 3000;
        extractedData.tax_profile.business_expenses_explored = true;
        calculateLeadScore();
        startIntelligentQuestioning();

      // =====================================================================
      // MULTIPLE INCOME SOURCES HANDLERS
      // =====================================================================

      } else if (value.startsWith('multi_')) {
        const multiType = value.replace('multi_', '');
        const multiLabels = {
          'w2_biz': 'W-2 Employment + Side Business',
          'w2_invest': 'W-2 Employment + Investments',
          'self_rental': 'Self-Employment + Rental Income',
          'retire_work': 'Retirement Income + Part-time Work',
          'other': 'Other combination'
        };
        addMessage('user', multiLabels[multiType] || multiType);
        extractedData.tax_profile.income_sources_detailed = multiType;
        extractedData.lead_data.complexity = 'moderate';
        extractedData.lead_data.score += 10;

        // Set flags based on selection
        if (multiType === 'w2_biz' || multiType === 'self_rental') {
          extractedData.tax_profile.is_self_employed = true;
        }
        if (multiType === 'self_rental') {
          extractedData.tax_profile.has_rental_income = true;
        }
        if (multiType === 'w2_invest') {
          extractedData.tax_profile.has_investment_income = true;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // =====================================================================
      // INVESTMENT INCOME HANDLERS
      // =====================================================================

      // Multi-select investment types
      } else if (value.includes('invest_') && value.includes(',')) {
        const investTypes = value.split(',').map(v => v.replace('invest_', '').trim());
        const investLabels = {
          'stocks': 'Stocks & capital gains',
          'rental': 'Rental income',
          'interest': 'Interest income',
          'k1': 'K-1 income',
          'crypto': 'Cryptocurrency'
        };

        extractedData.tax_profile.investment_types = investTypes;
        extractedData.tax_profile.investment_explored = true;
        extractedData.tax_profile.has_investment_income = true;

        // Set flags based on selections
        if (investTypes.includes('rental')) {
          extractedData.tax_profile.has_rental_income = true;
        }
        if (investTypes.includes('k1')) {
          extractedData.lead_data.complexity = 'complex';
          extractedData.lead_data.score += 15;
        }
        if (investTypes.includes('crypto')) {
          extractedData.tax_profile.has_crypto = true;
          extractedData.lead_data.score += 10;
        }

        extractedData.lead_data.score += investTypes.length * 5;
        calculateLeadScore();
        startIntelligentQuestioning();

      // Single invest type
      } else if (value.startsWith('invest_')) {
        const investType = value.replace('invest_', '');
        const investLabels = {
          'stocks': 'Stock dividends & capital gains',
          'rental': 'Rental property income',
          'interest': 'Interest income',
          'k1': 'Partnership/K-1 income',
          'crypto': 'Cryptocurrency',
          'multiple': 'Multiple investment types'
        };
        addMessage('user', investLabels[investType] || investType);
        extractedData.tax_profile.investment_type = investType;
        extractedData.tax_profile.investment_explored = true;
        extractedData.tax_profile.has_investment_income = true;

        if (investType === 'rental') {
          extractedData.tax_profile.has_rental_income = true;
        }
        if (investType === 'k1') {
          extractedData.lead_data.complexity = 'complex';
          extractedData.lead_data.score += 15;
        }
        extractedData.lead_data.score += 10;
        calculateLeadScore();
        startIntelligentQuestioning();

      } else if (value.startsWith('rental_')) {
        const rentalCount = value.replace('rental_', '');
        const rentalLabels = {
          '1': '1 property',
          '2_4': '2-4 properties',
          '5plus': '5+ properties'
        };
        addMessage('user', rentalLabels[rentalCount] || rentalCount);
        extractedData.tax_profile.rental_property_count = rentalCount;
        extractedData.tax_profile.rental_explored = true;

        if (rentalCount === '5plus') {
          extractedData.lead_data.complexity = 'complex';
          extractedData.lead_data.score += 20;
        } else if (rentalCount === '2_4') {
          extractedData.lead_data.score += 10;
        }
        calculateLeadScore();

        // Ask about rental property depreciation - critical for Schedule E
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<strong>Do you claim depreciation on your rental properties?</strong><br><small>Depreciation is a major tax benefit - typically deducting the building cost over 27.5 years.</small>`, [
            { label: 'Yes, I claim depreciation', value: 'rental_deprec_yes' },
            { label: 'No, I don\'t claim it', value: 'rental_deprec_no' },
            { label: 'My CPA handles this', value: 'rental_deprec_cpa' },
            { label: 'Not sure', value: 'rental_deprec_unsure' }
          ]);
        }, 800);

      // Rental Property Depreciation Handlers
      } else if (value.startsWith('rental_deprec_')) {
        const deprecStatus = value.replace('rental_deprec_', '');
        const deprecLabels = { 'yes': 'Yes, I claim depreciation', 'no': 'No depreciation', 'cpa': 'CPA handles it', 'unsure': 'Not sure' };
        addMessage('user', deprecLabels[deprecStatus] || deprecStatus);
        extractedData.tax_profile.rental_depreciation_status = deprecStatus;

        if (deprecStatus === 'yes' || deprecStatus === 'cpa') {
          extractedData.tax_profile.claims_rental_depreciation = true;
          // Ask about property basis for depreciation recapture planning
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>What's the approximate total cost basis of your rental properties (purchase price + improvements)?</strong><br><small>Important for depreciation and future sale planning.</small>`, [
              { label: 'Under $200,000', value: 'rental_basis_under200k' },
              { label: '$200,000 - $500,000', value: 'rental_basis_200_500k' },
              { label: '$500,000 - $1,000,000', value: 'rental_basis_500k_1m' },
              { label: 'Over $1,000,000', value: 'rental_basis_over1m' }
            ]);
          }, 800);
          return;
        } else if (deprecStatus === 'no') {
          // They may be missing out on deductions
          extractedData.tax_profile.missing_depreciation_deduction = true;
        }
        startIntelligentQuestioning();

      // Rental Property Basis Handlers
      } else if (value.startsWith('rental_basis_')) {
        const basis = value.replace('rental_basis_', '');
        const basisAmounts = { 'under200k': 150000, '200_500k': 350000, '500k_1m': 750000, 'over1m': 1500000 };
        const basisLabels = { 'under200k': 'Under $200,000', '200_500k': '$200,000-$500,000', '500k_1m': '$500,000-$1M', 'over1m': 'Over $1,000,000' };
        addMessage('user', basisLabels[basis] || basis);
        extractedData.tax_profile.rental_property_basis = basisAmounts[basis] || 350000;

        // Estimate annual depreciation (building is ~80% of basis, 27.5 year life)
        const buildingValue = (basisAmounts[basis] || 350000) * 0.80;
        const annualDepreciation = Math.round(buildingValue / 27.5);
        extractedData.tax_profile.estimated_annual_depreciation = annualDepreciation;

        // Ask about rental expenses for complete Schedule E picture
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<strong>What are your approximate annual rental expenses?</strong><br><small>Include repairs, insurance, property management, utilities paid by you.</small>`, [
            { label: 'Under $5,000', value: 'rental_exp_under5k' },
            { label: '$5,000 - $15,000', value: 'rental_exp_5_15k' },
            { label: '$15,000 - $30,000', value: 'rental_exp_15_30k' },
            { label: 'Over $30,000', value: 'rental_exp_over30k' }
          ]);
        }, 800);

      // Rental Expense Handlers
      } else if (value.startsWith('rental_exp_')) {
        const exp = value.replace('rental_exp_', '');
        const expAmounts = { 'under5k': 3000, '5_15k': 10000, '15_30k': 22500, 'over30k': 40000 };
        const expLabels = { 'under5k': 'Under $5,000', '5_15k': '$5,000-$15,000', '15_30k': '$15,000-$30,000', 'over30k': 'Over $30,000' };
        addMessage('user', expLabels[exp] || exp);
        extractedData.tax_profile.rental_expenses = expAmounts[exp] || 10000;
        calculateLeadScore();
        startIntelligentQuestioning();

      // =====================================================================
      // CAPITAL GAINS/LOSSES HANDLERS
      // =====================================================================

      } else if (value.startsWith('capgain_')) {
        const gainType = value.replace('capgain_', '');
        const gainLabels = {
          'gains': 'Yes, net gains (profit)',
          'losses': 'Yes, net losses',
          'even': 'About break-even',
          'none': 'Haven\'t sold anything'
        };
        addMessage('user', gainLabels[gainType] || gainType);
        extractedData.tax_profile.capital_gains_explored = true;

        if (gainType === 'gains') {
          extractedData.tax_profile.has_capital_gains = true;
        }
        if (gainType === 'losses') {
          extractedData.tax_profile.has_capital_losses = true;
        }
        extractedData.lead_data.score += 5;
        calculateLeadScore();
        startIntelligentQuestioning();

      } else if (value.startsWith('capgainamt_')) {
        const amt = value.replace('capgainamt_', '');
        const amounts = { 'under10k': 5000, '10_50k': 30000, '50_100k': 75000, 'over100k': 150000 };
        const labels = { 'under10k': 'Under $10,000', '10_50k': '$10,000-$50,000', '50_100k': '$50,000-$100,000', 'over100k': 'Over $100,000' };
        addMessage('user', labels[amt] || amt);
        extractedData.tax_profile.capital_gains_amount = amounts[amt] || 30000;
        extractedData.tax_profile.capital_gains_amount_explored = true;
        extractedData.lead_data.score += 10;
        calculateLeadScore();

        // Ask about holding period (long-term vs short-term) - critical for tax rate
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<strong>Were these primarily long-term (held > 1 year) or short-term gains?</strong><br><small>Long-term gains are taxed at lower rates (0-20%).</small>`, [
            { label: 'Mostly long-term (held > 1 year)', value: 'capgain_longterm' },
            { label: 'Mostly short-term (held < 1 year)', value: 'capgain_shortterm' },
            { label: 'Mix of both', value: 'capgain_mixed' },
            { label: 'Not sure', value: 'capgain_unsure' }
          ]);
        }, 800);

      // Capital Gains Holding Period Handlers
      } else if (value.startsWith('capgain_longterm') || value.startsWith('capgain_shortterm') || value.startsWith('capgain_mixed') || value === 'capgain_unsure') {
        const holdingLabels = {
          'capgain_longterm': 'Mostly long-term (held > 1 year)',
          'capgain_shortterm': 'Mostly short-term (held < 1 year)',
          'capgain_mixed': 'Mix of both',
          'capgain_unsure': 'Not sure'
        };
        addMessage('user', holdingLabels[value] || value);
        extractedData.tax_profile.capital_gains_holding = value.replace('capgain_', '');

        // Flag if short-term - taxed as ordinary income
        if (value === 'capgain_shortterm') {
          extractedData.tax_profile.has_short_term_gains = true;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      } else if (value.startsWith('caplossamt_')) {
        const amt = value.replace('caplossamt_', '');
        const amounts = { 'under3k': 1500, '3_10k': 6500, 'over10k': 15000 };
        const labels = { 'under3k': 'Under $3,000', '3_10k': '$3,000-$10,000', 'over10k': 'Over $10,000' };
        addMessage('user', labels[amt] || amt);
        extractedData.tax_profile.capital_losses_amount = amounts[amt] || 3000;
        extractedData.tax_profile.capital_losses_amount_explored = true;
        extractedData.lead_data.score += 5;

        // Ask about wash sales - critical for loss deduction
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<strong>Did you repurchase any of these securities within 30 days of selling at a loss?</strong><br><small>The IRS "wash sale" rule disallows losses if you buy back within 30 days.</small>`, [
            { label: 'Yes, I repurchased some', value: 'washsale_yes' },
            { label: 'No, did not repurchase', value: 'washsale_no' },
            { label: 'Not sure', value: 'washsale_unsure' }
          ]);
        }, 800);

      // Wash Sale Handlers
      } else if (value.startsWith('washsale_')) {
        const washStatus = value.replace('washsale_', '');
        const washLabels = { 'yes': 'Yes, repurchased some', 'no': 'No, did not repurchase', 'unsure': 'Not sure' };
        addMessage('user', washLabels[washStatus] || washStatus);
        extractedData.tax_profile.washsale_status = washStatus;

        if (washStatus === 'yes') {
          extractedData.tax_profile.has_wash_sales = true;
          // Losses may be disallowed
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Approximately what percentage of your losses were wash sales?</strong><br><small>These losses are deferred, not permanently lost - they add to your cost basis.</small>`, [
              { label: 'Under 25% of losses', value: 'washsale_pct_under25' },
              { label: '25-50% of losses', value: 'washsale_pct_25_50' },
              { label: 'Over 50% of losses', value: 'washsale_pct_over50' },
              { label: 'Not sure', value: 'washsale_pct_unsure' }
            ]);
          }, 800);
          return;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // Wash Sale Percentage Handlers
      } else if (value.startsWith('washsale_pct_')) {
        const washPct = value.replace('washsale_pct_', '');
        const washLabels = { 'under25': 'Under 25%', '25_50': '25-50%', 'over50': 'Over 50%', 'unsure': 'Not sure' };
        const washAmounts = { 'under25': 0.15, '25_50': 0.375, 'over50': 0.60, 'unsure': 0.25 };
        addMessage('user', washLabels[washPct] || washPct);
        extractedData.tax_profile.washsale_percentage = washAmounts[washPct] || 0.25;
        // Adjust deductible losses
        const totalLosses = extractedData.tax_profile.capital_losses_amount || 0;
        const disallowedLosses = Math.round(totalLosses * (washAmounts[washPct] || 0.25));
        extractedData.tax_profile.washsale_disallowed = disallowedLosses;
        extractedData.tax_profile.deductible_losses = totalLosses - disallowedLosses;
        calculateLeadScore();
        startIntelligentQuestioning();

      // =====================================================================
      // DEPENDENT & FAMILY HANDLERS
      // =====================================================================

      } else if (value.startsWith('dep_age_')) {
        const ageGroup = value.replace('dep_age_', '');
        const ageLabels = {
          'under6': 'All under 6 years old',
          '6_17': 'Children 6-17 years old',
          'college': 'College students (18-24)',
          'adult': 'Adult dependents / elderly parents',
          'mixed': 'Mix of ages'
        };
        addMessage('user', ageLabels[ageGroup] || ageGroup);
        extractedData.tax_profile.dependent_ages = ageGroup;
        extractedData.tax_profile.dependent_ages_explored = true;

        // Set flags for credit eligibility
        if (ageGroup === 'under6' || ageGroup === 'mixed') {
          extractedData.tax_profile.has_young_children = true;
        }
        if (ageGroup === 'college') {
          extractedData.tax_profile.has_college_students = true;
        }

        // Calculate Child Tax Credit for children under 17
        const hasChildrenUnder17 = ageGroup === 'under6' || ageGroup === '6_17' || ageGroup === 'mixed';
        if (hasChildrenUnder17) {
          const numDependents = extractedData.tax_profile.dependents || 1;
          // Estimate qualifying children (assume all if under6 or 6_17, half if mixed)
          const qualifyingChildren = ageGroup === 'mixed' ? Math.ceil(numDependents / 2) : numDependents;
          const ctcPerChild = 2000; // 2025 CTC amount
          const income = extractedData.tax_profile.total_income || 0;
          const filingStatus = extractedData.tax_profile.filing_status;

          // Phase-out thresholds (2025)
          const phaseOutStart = (filingStatus === 'Married Filing Jointly') ? 400000 : 200000;

          let estimatedCTC = qualifyingChildren * ctcPerChild;

          // Apply phase-out ($50 reduction per $1,000 over threshold)
          if (income > phaseOutStart) {
            const reduction = Math.floor((income - phaseOutStart) / 1000) * 50;
            estimatedCTC = Math.max(0, estimatedCTC - reduction);
          }

          extractedData.tax_profile.qualifying_children_ctc = qualifyingChildren;
          extractedData.tax_profile.estimated_child_tax_credit = estimatedCTC;
          extractedData.tax_profile.has_child_tax_credit = estimatedCTC > 0;

          DevLogger.log(`Estimated Child Tax Credit: $${estimatedCTC} for ${qualifyingChildren} qualifying children`);
        }

        extractedData.lead_data.score += 5;
        calculateLeadScore();

        // Ask about kiddie tax for children with investment income
        const hasMinorChildren = ageGroup === 'under6' || ageGroup === '6_17' || ageGroup === 'mixed';
        if (hasMinorChildren) {
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Do any of your children have investment income?</strong><br><small>Children's unearned income over $2,500 may be taxed at parent's rate ("kiddie tax").</small>`, [
              { label: 'Yes, child has investment/interest income', value: 'kiddie_yes' },
              { label: 'Yes, child has trust income', value: 'kiddie_trust' },
              { label: 'No unearned income', value: 'kiddie_no' }
            ]);
          }, 800);
          return;
        }
        startIntelligentQuestioning();

      // Kiddie Tax Handlers
      } else if (value.startsWith('kiddie_')) {
        const kiddieStatus = value.replace('kiddie_', '');
        const kiddieLabels = { 'yes': 'Child has investment income', 'trust': 'Child has trust income', 'no': 'No unearned income' };
        addMessage('user', kiddieLabels[kiddieStatus] || kiddieStatus);
        extractedData.tax_profile.kiddie_tax_status = kiddieStatus;

        if (kiddieStatus === 'yes' || kiddieStatus === 'trust') {
          extractedData.tax_profile.has_kiddie_tax_situation = true;
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>What's the child's approximate unearned income?</strong><br><small>First $1,250 tax-free, next $1,250 at child's rate, above $2,500 at parent's rate.</small>`, [
              { label: 'Under $1,250 (tax-free)', value: 'kiddie_amt_under1250' },
              { label: '$1,250 - $2,500 (child\'s rate)', value: 'kiddie_amt_1250_2500' },
              { label: '$2,500 - $10,000 (kiddie tax applies)', value: 'kiddie_amt_2500_10k' },
              { label: 'Over $10,000', value: 'kiddie_amt_over10k' }
            ]);
          }, 800);
          return;
        }
        startIntelligentQuestioning();

      // Kiddie Tax Amount Handlers
      } else if (value.startsWith('kiddie_amt_')) {
        const kiddieAmt = value.replace('kiddie_amt_', '');
        const amtAmounts = { 'under1250': 750, '1250_2500': 1875, '2500_10k': 6000, 'over10k': 15000 };
        const amtLabels = { 'under1250': 'Under $1,250', '1250_2500': '$1,250-$2,500', '2500_10k': '$2,500-$10,000', 'over10k': 'Over $10,000' };
        addMessage('user', amtLabels[kiddieAmt] || kiddieAmt);
        extractedData.tax_profile.child_unearned_income = amtAmounts[kiddieAmt] || 3000;

        // Flag if kiddie tax will apply
        if (kiddieAmt === '2500_10k' || kiddieAmt === 'over10k') {
          extractedData.tax_profile.kiddie_tax_applies = true;
          // Estimate additional tax at parent's rate
          const excessIncome = (amtAmounts[kiddieAmt] || 6000) - 2500;
          const parentRate = (extractedData.tax_profile.total_income || 100000) > 200000 ? 0.32 : 0.22;
          extractedData.tax_profile.estimated_kiddie_tax = Math.round(excessIncome * parentRate);
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      } else if (value.startsWith('childcare_')) {
        const childcareLevel = value.replace('childcare_', '');
        const childcareLabels = {
          'high': 'Yes, over $5,000/year',
          'low': 'Yes, under $5,000/year',
          'none': 'No childcare expenses'
        };
        const childcareAmounts = { 'high': 8000, 'low': 3000, 'none': 0 };
        addMessage('user', childcareLabels[childcareLevel] || childcareLevel);
        extractedData.tax_items.childcare = childcareAmounts[childcareLevel] || 0;
        extractedData.tax_profile.childcare_explored = true;

        // Calculate Child and Dependent Care Credit (Form 2441)
        if (childcareLevel !== 'none') {
          const income = extractedData.tax_profile.total_income || 0;
          const expenses = childcareAmounts[childcareLevel];
          const numChildren = Math.min(extractedData.tax_profile.dependents || 1, 2); // Max 2 for credit
          const expenseLimit = numChildren === 1 ? 3000 : 6000; // IRS limits
          const qualifyingExpenses = Math.min(expenses, expenseLimit);

          // Credit percentage based on AGI (20-35%)
          let creditPct = 0.20;
          if (income <= 15000) creditPct = 0.35;
          else if (income <= 17000) creditPct = 0.34;
          else if (income <= 19000) creditPct = 0.33;
          else if (income <= 21000) creditPct = 0.32;
          else if (income <= 23000) creditPct = 0.31;
          else if (income <= 25000) creditPct = 0.30;
          else if (income <= 43000) creditPct = 0.20 + (43000 - income) / 2000 * 0.01;

          const estimatedCredit = Math.round(qualifyingExpenses * creditPct);
          extractedData.tax_profile.dependent_care_credit = estimatedCredit;
          extractedData.tax_profile.has_dependent_care_credit = true;

          DevLogger.log(`Estimated Dependent Care Credit: $${estimatedCredit}`);
        }

        extractedData.lead_data.score += 5;
        calculateLeadScore();
        startIntelligentQuestioning();

      // =====================================================================
      // RETIREMENT CONTRIBUTION HANDLERS
      // =====================================================================

      } else if (value.startsWith('retire_')) {
        const retireType = value.replace('retire_', '');
        const retireLabels = {
          '401k': '401(k) through employer',
          'trad_ira': 'Traditional IRA',
          'roth_ira': 'Roth IRA',
          'both': '401(k) and IRA',
          'sep': 'SEP-IRA or Solo 401(k)'
        };
        addMessage('user', retireLabels[retireType] || retireType);
        extractedData.tax_profile.retirement_type = retireType;
        extractedData.tax_profile.retirement_detailed = true;

        if (retireType === '401k' || retireType === 'both') {
          extractedData.tax_profile.has_401k = true;
        }
        if (retireType === 'sep') {
          extractedData.lead_data.score += 10; // Self-employed retirement
        }
        extractedData.lead_data.score += 5;
        calculateLeadScore();
        startIntelligentQuestioning();

      } else if (value.startsWith('401k_')) {
        const amount = value.replace('401k_', '');
        const amountLabels = {
          'under10k': 'Less than $10,000',
          '10_15k': '$10,000 - $15,000',
          '15_23k': '$15,000 - $23,000',
          'max': 'Maxing out ($23,500)',
          'unsure': 'Not sure'
        };
        const amountValues = {
          'under10k': 7500,
          '10_15k': 12500,
          '15_23k': 19000,
          'max': 23500,
          'unsure': 15000
        };
        addMessage('user', amountLabels[amount] || amount);
        extractedData.tax_profile.retirement_401k = amountValues[amount] || 15000;
        extractedData.lead_data.score += 5;
        calculateLeadScore();
        startIntelligentQuestioning();

      // =====================================================================
      // HSA CONTRIBUTION HANDLERS
      // =====================================================================

      } else if (value.startsWith('hsa_')) {
        const hsaType = value.replace('hsa_', '');
        const hsaLabels = { 'yes': 'Yes, I contribute to an HSA', 'no': 'No HSA', 'unsure': 'Not sure' };
        addMessage('user', hsaLabels[hsaType] || hsaType);
        extractedData.tax_profile.hsa_explored = true;

        if (hsaType === 'yes') {
          extractedData.tax_profile.has_hsa = true;
          extractedData.lead_data.score += 5;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      } else if (value.startsWith('hsaamt_')) {
        const amt = value.replace('hsaamt_', '');
        const amounts = { 'under2k': 1500, '2_4k': 3000, 'max': 4150, 'unsure': 2500 };
        const labels = { 'under2k': 'Under $2,000', '2_4k': '$2,000-$4,000', 'max': 'Maxing out', 'unsure': 'Not sure' };
        addMessage('user', labels[amt] || amt);
        extractedData.tax_items.hsa_contributions = amounts[amt] || 2500;
        extractedData.tax_profile.hsa_amount_explored = true;
        extractedData.lead_data.score += 5;
        calculateLeadScore();
        startIntelligentQuestioning();

      // =====================================================================
      // STUDENT LOAN INTEREST HANDLERS
      // =====================================================================

      } else if (value.startsWith('studentloan_')) {
        const loanType = value.replace('studentloan_', '');
        const loanLabels = { 'yes': 'Yes, I pay student loan interest', 'no': 'No student loans' };
        addMessage('user', loanLabels[loanType] || loanType);
        extractedData.tax_profile.student_loan_explored = true;

        if (loanType === 'yes') {
          extractedData.tax_profile.has_student_loans = true;
          extractedData.lead_data.score += 5;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      } else if (value.startsWith('studentloanamt_')) {
        const amt = value.replace('studentloanamt_', '');
        const amounts = { 'under1k': 500, '1_2500': 1750, 'over2500': 2500 };
        const labels = { 'under1k': 'Under $1,000', '1_2500': '$1,000-$2,500', 'over2500': 'Over $2,500' };
        addMessage('user', labels[amt] || amt);
        // Max deductible is $2,500
        extractedData.tax_items.student_loan_interest = Math.min(amounts[amt] || 1750, 2500);
        extractedData.tax_profile.student_loan_amount_explored = true;
        extractedData.lead_data.score += 5;
        calculateLeadScore();
        startIntelligentQuestioning();

      // =====================================================================
      // ENERGY CREDIT HANDLERS
      // =====================================================================

      } else if (value.startsWith('energy_')) {
        const energyType = value.replace('energy_', '');
        const energyLabels = {
          'solar': 'Solar panels installed',
          'ev': 'Electric vehicle purchased',
          'hvac': 'Heat pump / HVAC upgrade',
          'home_improve': 'Windows / insulation / doors',
          'none': 'None of these'
        };
        addMessage('user', energyLabels[energyType] || energyType);
        extractedData.tax_profile.energy_explored = true;

        if (energyType !== 'none') {
          extractedData.tax_profile.has_energy_credits = true;
          extractedData.tax_profile.energy_credit_type = energyType;
          extractedData.lead_data.score += 10;

          // Solar gets significant credit (30% of cost)
          if (energyType === 'solar') {
            extractedData.tax_profile.has_solar_credit = true;
            extractedData.lead_data.complexity = 'moderate';
          }
          // EV credit up to $7,500
          if (energyType === 'ev') {
            extractedData.tax_profile.has_ev_credit = true;
          }
          // Home improvements get smaller credits
          if (energyType === 'hvac' || energyType === 'home_improve') {
            extractedData.tax_profile.has_home_energy_credit = true;
          }
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // =====================================================================
      // LIFE EVENT HANDLERS
      // =====================================================================

      } else if (value.startsWith('event_')) {
        const eventType = value.replace('event_', '');
        const eventLabels = {
          'marriage': 'Getting married',
          'baby': 'Having a baby',
          'home': 'Buying a home',
          'business': 'Starting a business',
          'retirement': 'Retiring soon',
          'sale': 'Selling a home or major asset'
        };
        addMessage('user', eventLabels[eventType] || eventType);
        extractedData.tax_profile.life_event_type = eventType;
        extractedData.lead_data.score += 10;

        // Increase complexity for certain events
        if (eventType === 'business' || eventType === 'sale') {
          extractedData.lead_data.complexity = 'complex';
          extractedData.lead_data.score += 10;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // =====================================================================
      // ADVANCED STRATEGIES HANDLERS (HIGH EARNERS)
      // =====================================================================

      } else if (value.startsWith('adv_')) {
        const advType = value.replace('adv_', '');
        const advLabels = {
          'backdoor': 'Backdoor Roth IRA strategies',
          'charitable': 'Charitable giving optimization',
          'deferred': 'Deferred compensation plans',
          'estate': 'Estate planning considerations',
          'all': 'Show all tax-saving opportunities'
        };
        addMessage('user', advLabels[advType] || advType);
        extractedData.tax_profile.advanced_interest = advType;
        extractedData.tax_profile.advanced_explored = true;
        extractedData.lead_data.complexity = 'complex';
        extractedData.lead_data.score += 15;
        calculateLeadScore();
        startIntelligentQuestioning();

      // =====================================================================
      // CRYPTOCURRENCY HANDLERS
      // =====================================================================

      } else if (value.startsWith('crypto_')) {
        const cryptoType = value.replace('crypto_', '');
        const cryptoLabels = {
          'hold': 'Yes, I hold crypto but haven\'t sold',
          'sold': 'Yes, I sold/traded crypto',
          'earned': 'Yes, I earned crypto',
          'none': 'No cryptocurrency'
        };
        addMessage('user', cryptoLabels[cryptoType] || cryptoType);
        extractedData.tax_profile.crypto_explored = true;

        if (cryptoType !== 'none') {
          extractedData.tax_profile.has_crypto = true;
          extractedData.tax_profile.crypto_activity = cryptoType;
          extractedData.lead_data.score += 10;

          if (cryptoType === 'sold') {
            extractedData.tax_profile.has_crypto_gains = true;
            extractedData.lead_data.complexity = 'complex';
            // Ask detailed crypto trading questions
            showTyping();
            setTimeout(() => {
              hideTyping();
              addMessage('ai', `<strong>Approximately how many crypto transactions did you have this year?</strong><br><small>Each trade (including crypto-to-crypto swaps) is a taxable event.</small>`, [
                { label: 'Under 10 trades', value: 'crypto_trades_under10' },
                { label: '10-50 trades', value: 'crypto_trades_10_50' },
                { label: '50-200 trades', value: 'crypto_trades_50_200' },
                { label: 'Over 200 trades (active trader)', value: 'crypto_trades_over200' }
              ]);
            }, 800);
            return;
          } else if (cryptoType === 'earned') {
            extractedData.tax_profile.has_crypto_income = true;
            extractedData.lead_data.complexity = 'complex';
            // Ask about crypto income type
            showTyping();
            setTimeout(() => {
              hideTyping();
              addMessage('ai', `<strong>How did you earn cryptocurrency?</strong><br><small>Different earning methods have different tax treatments.</small>`, [
                { label: 'Mining', value: 'crypto_earn_mining' },
                { label: 'Staking rewards', value: 'crypto_earn_staking' },
                { label: 'DeFi yield farming', value: 'crypto_earn_defi' },
                { label: 'Airdrops/rewards', value: 'crypto_earn_airdrops' },
                { label: 'Payment for services', value: 'crypto_earn_payment' }
              ]);
            }, 800);
            return;
          }
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // Crypto Trade Count Handlers
      } else if (value.startsWith('crypto_trades_')) {
        const tradeCount = value.replace('crypto_trades_', '');
        const tradeLabels = { 'under10': 'Under 10 trades', '10_50': '10-50 trades', '50_200': '50-200 trades', 'over200': 'Over 200 trades' };
        addMessage('user', tradeLabels[tradeCount] || tradeCount);
        extractedData.tax_profile.crypto_trade_count = tradeCount;

        if (tradeCount === 'over200' || tradeCount === '50_200') {
          extractedData.tax_profile.needs_crypto_software = true;
        }

        // Ask about crypto gain/loss amount
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<strong>What's your approximate net crypto gain or loss this year?</strong>`, [
            { label: 'Net gain under $5,000', value: 'crypto_gl_gain_under5k' },
            { label: 'Net gain $5,000-$25,000', value: 'crypto_gl_gain_5_25k' },
            { label: 'Net gain over $25,000', value: 'crypto_gl_gain_over25k' },
            { label: 'Net loss under $10,000', value: 'crypto_gl_loss_under10k' },
            { label: 'Net loss over $10,000', value: 'crypto_gl_loss_over10k' },
            { label: 'About break-even', value: 'crypto_gl_even' }
          ]);
        }, 800);

      // Crypto Gain/Loss Handlers
      } else if (value.startsWith('crypto_gl_')) {
        const glType = value.replace('crypto_gl_', '');
        const glLabels = {
          'gain_under5k': 'Net gain under $5,000', 'gain_5_25k': 'Net gain $5,000-$25,000', 'gain_over25k': 'Net gain over $25,000',
          'loss_under10k': 'Net loss under $10,000', 'loss_over10k': 'Net loss over $10,000', 'even': 'About break-even'
        };
        const glAmounts = { 'gain_under5k': 2500, 'gain_5_25k': 15000, 'gain_over25k': 50000, 'loss_under10k': -5000, 'loss_over10k': -15000, 'even': 0 };
        addMessage('user', glLabels[glType] || glType);
        extractedData.tax_profile.crypto_gain_loss = glAmounts[glType] || 0;

        if (glType.startsWith('loss_')) {
          extractedData.tax_profile.has_crypto_losses = true;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // Crypto Earning Type Handlers
      } else if (value.startsWith('crypto_earn_')) {
        const earnType = value.replace('crypto_earn_', '');
        const earnLabels = { 'mining': 'Mining', 'staking': 'Staking rewards', 'defi': 'DeFi yield farming', 'airdrops': 'Airdrops/rewards', 'payment': 'Payment for services' };
        addMessage('user', earnLabels[earnType] || earnType);
        extractedData.tax_profile.crypto_earning_type = earnType;

        // Mining and staking may have self-employment implications
        if (earnType === 'mining') {
          extractedData.tax_profile.crypto_mining_se_tax = true;
        }

        // Ask about earned crypto value
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<strong>What's the approximate fair market value of crypto you earned this year?</strong><br><small>This is taxed as ordinary income when received.</small>`, [
            { label: 'Under $1,000', value: 'crypto_earned_under1k' },
            { label: '$1,000 - $5,000', value: 'crypto_earned_1_5k' },
            { label: '$5,000 - $20,000', value: 'crypto_earned_5_20k' },
            { label: 'Over $20,000', value: 'crypto_earned_over20k' }
          ]);
        }, 800);

      // Crypto Earned Value Handlers
      } else if (value.startsWith('crypto_earned_')) {
        const earnedAmt = value.replace('crypto_earned_', '');
        const earnedAmounts = { 'under1k': 500, '1_5k': 3000, '5_20k': 12500, 'over20k': 35000 };
        const earnedLabels = { 'under1k': 'Under $1,000', '1_5k': '$1,000-$5,000', '5_20k': '$5,000-$20,000', 'over20k': 'Over $20,000' };
        addMessage('user', earnedLabels[earnedAmt] || earnedAmt);
        extractedData.tax_profile.crypto_earned_value = earnedAmounts[earnedAmt] || 5000;
        calculateLeadScore();
        startIntelligentQuestioning();

      // =====================================================================
      // STOCK OPTIONS & EQUITY COMPENSATION HANDLERS
      // =====================================================================

      } else if (value.startsWith('options_')) {
        const optionType = value.replace('options_', '');
        const optionLabels = {
          'iso': 'Yes, I have ISOs',
          'nso': 'Yes, I have NSOs',
          'rsu': 'Yes, I have RSUs',
          'espp': 'Yes, I have ESPP',
          'none': 'No equity compensation'
        };
        addMessage('user', optionLabels[optionType] || optionType);
        extractedData.tax_profile.stock_options_explored = true;

        if (optionType !== 'none') {
          extractedData.tax_profile.has_equity_compensation = true;
          extractedData.tax_profile.equity_type = optionType;
          extractedData.lead_data.score += 10;
          extractedData.lead_data.complexity = 'complex';

          // ISOs have special AMT implications - ask detailed questions
          if (optionType === 'iso') {
            extractedData.tax_profile.has_iso = true;
            extractedData.tax_profile.may_have_amt = true;
            showTyping();
            setTimeout(() => {
              hideTyping();
              addMessage('ai', `<strong>Did you exercise any ISOs this year?</strong><br><small>ISO exercises can trigger Alternative Minimum Tax (AMT).</small>`, [
                { label: 'Yes, I exercised ISOs', value: 'iso_exercised_yes' },
                { label: 'No, haven\'t exercised yet', value: 'iso_exercised_no' },
                { label: 'Planning to exercise soon', value: 'iso_exercised_planning' }
              ]);
            }, 800);
            return;
          } else if (optionType === 'nso' || optionType === 'rsu') {
            // NSOs and RSUs - ask about vesting/exercise
            showTyping();
            setTimeout(() => {
              hideTyping();
              addMessage('ai', `<strong>What's the approximate value of ${optionType === 'nso' ? 'NSOs exercised' : 'RSUs vested'} this year?</strong><br><small>${optionType === 'nso' ? 'The bargain element is taxed as ordinary income.' : 'RSU value at vesting is taxed as ordinary income.'}</small>`, [
                { label: 'Under $25,000', value: `${optionType}_value_under25k` },
                { label: '$25,000 - $100,000', value: `${optionType}_value_25_100k` },
                { label: '$100,000 - $250,000', value: `${optionType}_value_100_250k` },
                { label: 'Over $250,000', value: `${optionType}_value_over250k` }
              ]);
            }, 800);
            return;
          }
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // ISO Exercise Handlers (AMT triggers)
      } else if (value.startsWith('iso_exercised_')) {
        const exerciseStatus = value.replace('iso_exercised_', '');
        const exerciseLabels = { 'yes': 'Yes, exercised ISOs', 'no': 'Haven\'t exercised', 'planning': 'Planning to exercise' };
        addMessage('user', exerciseLabels[exerciseStatus] || exerciseStatus);
        extractedData.tax_profile.iso_exercise_status = exerciseStatus;

        if (exerciseStatus === 'yes') {
          // Ask about ISO bargain element (spread) - this is the AMT preference item
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>What's the approximate "spread" (difference between FMV and exercise price)?</strong><br><small>This spread is an AMT preference item that may trigger AMT liability.</small>`, [
              { label: 'Under $50,000 spread', value: 'iso_spread_under50k' },
              { label: '$50,000 - $150,000 spread', value: 'iso_spread_50_150k' },
              { label: '$150,000 - $500,000 spread', value: 'iso_spread_150_500k' },
              { label: 'Over $500,000 spread', value: 'iso_spread_over500k' }
            ]);
          }, 800);
          return;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // ISO Spread (AMT Preference Item) Handlers
      } else if (value.startsWith('iso_spread_')) {
        const spreadAmt = value.replace('iso_spread_', '');
        const spreadAmounts = { 'under50k': 25000, '50_150k': 100000, '150_500k': 325000, 'over500k': 750000 };
        const spreadLabels = { 'under50k': 'Under $50,000', '50_150k': '$50,000-$150,000', '150_500k': '$150,000-$500,000', 'over500k': 'Over $500,000' };
        addMessage('user', spreadLabels[spreadAmt] || spreadAmt);
        extractedData.tax_profile.iso_spread = spreadAmounts[spreadAmt] || 100000;

        // Calculate potential AMT liability estimate
        const spread = spreadAmounts[spreadAmt] || 100000;
        const potentialAMT = Math.round(spread * 0.28); // AMT rate is 26-28%
        extractedData.tax_profile.potential_amt_liability = potentialAMT;

        if (spread >= 150000) {
          extractedData.tax_profile.high_amt_risk = true;
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `${getIcon('exclamation-triangle', 'sm')} <strong>High AMT Risk Alert:</strong> With a $${spread.toLocaleString()} spread, you may owe significant AMT (potentially $${potentialAMT.toLocaleString()}).<br><br><strong>Did you already make estimated tax payments for AMT?</strong>`, [
              { label: 'Yes, made AMT estimated payments', value: 'amt_estimated_yes' },
              { label: 'No, need to plan for this', value: 'amt_estimated_no' },
              { label: 'My CPA is handling this', value: 'amt_estimated_cpa' }
            ]);
          }, 1000);
          return;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // AMT Estimated Payment Handlers
      } else if (value.startsWith('amt_estimated_')) {
        const amtStatus = value.replace('amt_estimated_', '');
        const amtLabels = { 'yes': 'Yes, made AMT payments', 'no': 'Need to plan for this', 'cpa': 'CPA handling it' };
        addMessage('user', amtLabels[amtStatus] || amtStatus);
        extractedData.tax_profile.amt_estimated_status = amtStatus;
        if (amtStatus === 'no') {
          extractedData.tax_profile.needs_amt_planning = true;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // NSO/RSU Value Handlers
      } else if (value.match(/^(nso|rsu)_value_/)) {
        const parts = value.split('_value_');
        const equityType = parts[0];
        const valueAmt = parts[1];
        const valueAmounts = { 'under25k': 15000, '25_100k': 62500, '100_250k': 175000, 'over250k': 400000 };
        const valueLabels = { 'under25k': 'Under $25,000', '25_100k': '$25,000-$100,000', '100_250k': '$100,000-$250,000', 'over250k': 'Over $250,000' };
        addMessage('user', valueLabels[valueAmt] || valueAmt);
        extractedData.tax_profile[`${equityType}_value`] = valueAmounts[valueAmt] || 62500;
        // This is ordinary income, will be on W-2
        extractedData.tax_profile.equity_income = valueAmounts[valueAmt] || 62500;
        calculateLeadScore();
        startIntelligentQuestioning();

      // =====================================================================
      // ESTIMATED TAX PAYMENTS HANDLERS
      // =====================================================================

      } else if (value.startsWith('estimated_')) {
        const estimatedType = value.replace('estimated_', '');
        const estimatedLabels = {
          'yes': 'Yes, I make regular estimated payments',
          'sometimes': 'Sometimes, but not consistently',
          'no': 'No, I don\'t make estimated payments',
          'unsure': 'Not sure if I should be'
        };
        addMessage('user', estimatedLabels[estimatedType] || estimatedType);
        extractedData.tax_profile.estimated_explored = true;
        extractedData.tax_profile.makes_estimated_payments = (estimatedType === 'yes');
        extractedData.tax_profile.estimated_payment_status = estimatedType;

        // Flag potential underpayment penalty risk
        if (estimatedType === 'no' || estimatedType === 'unsure') {
          const profile = extractedData.tax_profile;
          if (profile.is_self_employed || profile.has_rental_income ||
              profile.has_crypto_gains || profile.has_investment_income) {
            extractedData.tax_profile.possible_underpayment_penalty = true;
          }
          calculateLeadScore();
          startIntelligentQuestioning();
        } else if (estimatedType === 'yes' || estimatedType === 'sometimes') {
          // Ask for estimated payment amounts to calculate refund/owed accurately
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>What's your approximate total estimated tax payments so far this year?</strong><br><small>This helps us calculate if you'll owe or get a refund.</small>`, [
              { label: 'Under $5,000', value: 'estamt_under5k' },
              { label: '$5,000 - $15,000', value: 'estamt_5_15k' },
              { label: '$15,000 - $30,000', value: 'estamt_15_30k' },
              { label: '$30,000 - $50,000', value: 'estamt_30_50k' },
              { label: 'Over $50,000', value: 'estamt_over50k' },
              { label: 'Skip - I\'ll check later', value: 'estamt_skip' }
            ]);
          }, 800);
        } else {
          calculateLeadScore();
          startIntelligentQuestioning();
        }

      // Estimated Payment Amount Handlers
      } else if (value.startsWith('estamt_')) {
        const amt = value.replace('estamt_', '');
        const amounts = { 'under5k': 2500, '5_15k': 10000, '15_30k': 22500, '30_50k': 40000, 'over50k': 75000, 'skip': 0 };
        const labels = { 'under5k': 'Under $5,000', '5_15k': '$5,000-$15,000', '15_30k': '$15,000-$30,000', '30_50k': '$30,000-$50,000', 'over50k': 'Over $50,000', 'skip': 'Skip for now' };
        addMessage('user', labels[amt] || amt);
        extractedData.tax_profile.estimated_payments_amount = amounts[amt] || 0;
        extractedData.tax_profile.estimated_amount_explored = true;
        calculateLeadScore();
        startIntelligentQuestioning();

      // Net Business Income Handlers
      } else if (value.startsWith('netincome_')) {
        const amt = value.replace('netincome_', '');
        const amounts = { 'under25k': 15000, '25_75k': 50000, '75_150k': 112500, '150_250k': 200000, 'over250k': 350000 };
        const labels = { 'under25k': 'Under $25,000', '25_75k': '$25,000-$75,000', '75_150k': '$75,000-$150,000', '150_250k': '$150,000-$250,000', 'over250k': 'Over $250,000' };
        addMessage('user', labels[amt] || amt);
        extractedData.tax_profile.net_business_income = amounts[amt] || 50000;
        extractedData.tax_profile.net_income_explored = true;

        // Calculate estimated self-employment tax (15.3% on 92.35% of net income)
        const netIncome = amounts[amt] || 50000;
        const seTax = Math.round(netIncome * 0.9235 * 0.153);
        extractedData.tax_profile.estimated_se_tax = seTax;

        calculateLeadScore();
        startIntelligentQuestioning();

      // QBI Deduction Handlers
      } else if (value.startsWith('qbi_')) {
        const qbiStatus = value.replace('qbi_', '');
        const qbiLabels = {
          'yes': 'Yes, I claim QBI deduction',
          'learn': 'No, I want to learn more',
          'cpa': 'My CPA handles this',
          'unsure': 'Not sure if I qualify'
        };
        addMessage('user', qbiLabels[qbiStatus] || qbiStatus);
        extractedData.tax_profile.qbi_explored = true;
        extractedData.tax_profile.qbi_status = qbiStatus;

        if (qbiStatus === 'yes') {
          extractedData.tax_profile.claims_qbi = true;
          // Estimate QBI deduction (20% of net business income, subject to limits)
          const netIncome = extractedData.tax_profile.net_business_income || 0;
          const qbiDeduction = Math.min(netIncome * 0.20, 50000); // Simplified estimate
          extractedData.tax_profile.estimated_qbi_deduction = qbiDeduction;
        }

        if (qbiStatus === 'learn') {
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>QBI Deduction Explained:</strong><br><br>The Qualified Business Income (QBI) deduction lets you deduct up to <strong>20% of your net business income</strong> from your taxes.<br><br>${getIcon('check-circle', 'sm')} <strong>You may qualify if:</strong><br>• You're self-employed or own a pass-through business<br>• Your income is below $${extractedData.tax_profile.filing_status === 'Married Filing Jointly' ? '364,200' : '182,100'} (full deduction)<br>• Higher incomes may still qualify for partial deduction<br><br>This is one of the biggest tax savings opportunities for business owners!`, [
              { label: 'I\'ll look into this', value: 'qbi_noted' },
              { label: 'My CPA can help', value: 'qbi_cpa_help' }
            ]);
          }, 1000);
          return;
        }

        calculateLeadScore();
        startIntelligentQuestioning();

      } else if (value === 'qbi_noted' || value === 'qbi_cpa_help') {
        addMessage('user', value === 'qbi_noted' ? 'I\'ll look into this' : 'My CPA can help');
        extractedData.tax_profile.qbi_interest = true;
        calculateLeadScore();
        startIntelligentQuestioning();

      // Education Credits Handlers
      } else if (value.startsWith('educredit_')) {
        const creditType = value.replace('educredit_', '');
        const creditLabels = {
          'dependents': 'College tuition for dependents',
          'self': 'Education for myself',
          '529': 'I contribute to a 529 plan',
          'none': 'No education expenses'
        };
        addMessage('user', creditLabels[creditType] || creditType);
        extractedData.tax_profile.education_credits_explored = true;

        if (creditType === 'dependents') {
          extractedData.tax_profile.has_education_expenses = true;
          extractedData.tax_profile.education_type = 'dependents';
          // Ask about AOTC eligibility
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>How many students are you paying college tuition for?</strong><br><small>AOTC credit: up to $2,500 per student (first 4 years).</small>`, [
              { label: '1 student', value: 'students_1' },
              { label: '2 students', value: 'students_2' },
              { label: '3+ students', value: 'students_3plus' }
            ]);
          }, 800);
          return;
        } else if (creditType === 'self') {
          extractedData.tax_profile.has_education_expenses = true;
          extractedData.tax_profile.education_type = 'self';
          // Lifetime Learning Credit for self
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>What type of education?</strong><br><small>Lifetime Learning Credit: up to $2,000 for any level of education.</small>`, [
              { label: 'College degree program', value: 'selfed_degree' },
              { label: 'Graduate school', value: 'selfed_graduate' },
              { label: 'Professional certifications', value: 'selfed_cert' },
              { label: 'Job-related courses', value: 'selfed_courses' }
            ]);
          }, 800);
          return;
        } else if (creditType === '529') {
          extractedData.tax_profile.has_529 = true;
          extractedData.tax_items.has_529 = true;
          // Ask about 529 contribution amount
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>How much did you contribute to 529 plans this year?</strong><br><small>Many states offer tax deductions for 529 contributions.</small>`, [
              { label: 'Under $5,000', value: '529amt_under5k' },
              { label: '$5,000 - $15,000', value: '529amt_5_15k' },
              { label: 'Over $15,000', value: '529amt_over15k' }
            ]);
          }, 800);
          return;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // Education student count handlers
      } else if (value.startsWith('students_')) {
        const count = value.replace('students_', '');
        const countLabels = { '1': '1 student', '2': '2 students', '3plus': '3+ students' };
        addMessage('user', countLabels[count] || count);
        extractedData.tax_profile.college_students = count === '3plus' ? 3 : parseInt(count);
        // Estimate AOTC credit ($2,500 per student)
        const numStudents = count === '3plus' ? 3 : parseInt(count);
        extractedData.tax_profile.potential_aotc = numStudents * 2500;
        calculateLeadScore();
        startIntelligentQuestioning();

      // Self education type handlers
      } else if (value.startsWith('selfed_')) {
        const edType = value.replace('selfed_', '');
        const edLabels = { 'degree': 'College degree', 'graduate': 'Graduate school', 'cert': 'Professional certifications', 'courses': 'Job-related courses' };
        addMessage('user', edLabels[edType] || edType);
        extractedData.tax_profile.self_education_type = edType;
        // Lifetime Learning Credit estimate ($2,000 max)
        extractedData.tax_profile.potential_llc = 2000;
        calculateLeadScore();
        startIntelligentQuestioning();

      // 529 amount handlers
      } else if (value.startsWith('529amt_')) {
        const amt = value.replace('529amt_', '');
        const amounts = { 'under5k': 2500, '5_15k': 10000, 'over15k': 20000 };
        const labels = { 'under5k': 'Under $5,000', '5_15k': '$5,000-$15,000', 'over15k': 'Over $15,000' };
        addMessage('user', labels[amt] || amt);
        extractedData.tax_profile.contribution_529 = amounts[amt] || 5000;
        calculateLeadScore();
        startIntelligentQuestioning();

      // Standard Deduction vs Itemized Handlers
      } else if (value.startsWith('itemize_')) {
        const itemizeChoice = value.replace('itemize_', '');
        const itemizeLabels = {
          'yes': 'I itemize deductions',
          'standard': 'I take the standard deduction',
          'cpa': 'My CPA decides',
          'unsure': 'Not sure'
        };
        addMessage('user', itemizeLabels[itemizeChoice] || itemizeChoice);
        extractedData.tax_profile.itemize_decision_explored = true;
        extractedData.tax_profile.itemize_choice = itemizeChoice;

        if (itemizeChoice === 'yes') {
          extractedData.tax_profile.itemizes_deductions = true;
        } else if (itemizeChoice === 'standard') {
          extractedData.tax_profile.itemizes_deductions = false;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // Foreign Income/FBAR Handlers
      } else if (value.startsWith('foreign_')) {
        const foreignType = value.replace('foreign_', '');
        const foreignLabels = {
          'income': 'Yes, I have foreign income',
          'accounts': 'Yes, foreign bank accounts only',
          'both': 'Both foreign income and accounts',
          'none': 'No foreign income or accounts'
        };
        addMessage('user', foreignLabels[foreignType] || foreignType);
        extractedData.tax_profile.foreign_explored = true;

        if (foreignType !== 'none') {
          extractedData.tax_profile.has_foreign_income = (foreignType === 'income' || foreignType === 'both');
          extractedData.tax_profile.has_foreign_accounts = (foreignType === 'accounts' || foreignType === 'both');
          extractedData.tax_profile.may_need_fbar = true;
          extractedData.lead_data.complexity = 'complex';

          // Ask detailed foreign income questions
          if (foreignType === 'income' || foreignType === 'both') {
            showTyping();
            setTimeout(() => {
              hideTyping();
              addMessage('ai', `<strong>What type of foreign income do you have?</strong><br><small>Different types qualify for different exclusions/credits.</small>`, [
                { label: 'Wages from foreign employer', value: 'foreign_type_wages' },
                { label: 'Self-employment abroad', value: 'foreign_type_self' },
                { label: 'Foreign rental property', value: 'foreign_type_rental' },
                { label: 'Foreign investments/dividends', value: 'foreign_type_invest' },
                { label: 'Foreign pension', value: 'foreign_type_pension' }
              ]);
            }, 800);
            return;
          } else if (foreignType === 'accounts') {
            // Ask about FBAR threshold
            showTyping();
            setTimeout(() => {
              hideTyping();
              addMessage('ai', `<strong>What's the highest aggregate balance of all foreign accounts this year?</strong><br><small>FBAR filing required if > $10,000 at any time.</small>`, [
                { label: 'Under $10,000', value: 'fbar_under10k' },
                { label: '$10,000 - $50,000', value: 'fbar_10_50k' },
                { label: '$50,000 - $200,000', value: 'fbar_50_200k' },
                { label: 'Over $200,000', value: 'fbar_over200k' }
              ]);
            }, 800);
            return;
          }
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // Foreign Income Type Handlers
      } else if (value.startsWith('foreign_type_')) {
        const incomeType = value.replace('foreign_type_', '');
        const typeLabels = { 'wages': 'Foreign wages', 'self': 'Self-employment abroad', 'rental': 'Foreign rental', 'invest': 'Foreign investments', 'pension': 'Foreign pension' };
        addMessage('user', typeLabels[incomeType] || incomeType);
        extractedData.tax_profile.foreign_income_type = incomeType;

        // Earned income (wages/self-employment) may qualify for FEIE
        if (incomeType === 'wages' || incomeType === 'self') {
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Did you live outside the US for most of the year?</strong><br><small>You may qualify for the Foreign Earned Income Exclusion (up to $126,500 in 2024).</small>`, [
              { label: 'Yes, lived abroad full year', value: 'feie_full_year' },
              { label: 'Yes, 330+ days abroad', value: 'feie_330_days' },
              { label: 'Partial year abroad', value: 'feie_partial' },
              { label: 'No, worked remotely from US', value: 'feie_remote_us' }
            ]);
          }, 800);
          return;
        } else {
          // Ask about foreign tax paid for Foreign Tax Credit
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Did you pay foreign taxes on this income?</strong><br><small>You may claim a Foreign Tax Credit to avoid double taxation.</small>`, [
              { label: 'Yes, taxes withheld/paid', value: 'ftc_yes' },
              { label: 'No foreign taxes paid', value: 'ftc_no' },
              { label: 'Not sure', value: 'ftc_unsure' }
            ]);
          }, 800);
          return;
        }

      // FEIE (Foreign Earned Income Exclusion) Handlers
      } else if (value.startsWith('feie_')) {
        const feieStatus = value.replace('feie_', '');
        const feieLabels = { 'full_year': 'Lived abroad full year', '330_days': '330+ days abroad', 'partial': 'Partial year abroad', 'remote_us': 'Worked remotely from US' };
        addMessage('user', feieLabels[feieStatus] || feieStatus);
        extractedData.tax_profile.feie_status = feieStatus;

        if (feieStatus === 'full_year' || feieStatus === '330_days') {
          extractedData.tax_profile.qualifies_feie = true;
          extractedData.tax_profile.feie_exclusion = 126500; // 2024 limit
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>What's your approximate foreign earned income?</strong><br><small>Up to $126,500 may be excluded from US taxes.</small>`, [
              { label: 'Under $50,000', value: 'foreign_earned_under50k' },
              { label: '$50,000 - $100,000', value: 'foreign_earned_50_100k' },
              { label: '$100,000 - $126,500', value: 'foreign_earned_100_126k' },
              { label: 'Over $126,500', value: 'foreign_earned_over126k' }
            ]);
          }, 800);
          return;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // Foreign Earned Income Amount Handlers
      } else if (value.startsWith('foreign_earned_')) {
        const earnedAmt = value.replace('foreign_earned_', '');
        const earnedAmounts = { 'under50k': 35000, '50_100k': 75000, '100_126k': 113000, 'over126k': 175000 };
        addMessage('user', `$${(earnedAmounts[earnedAmt] || 75000).toLocaleString()}`);
        extractedData.tax_profile.foreign_earned_income = earnedAmounts[earnedAmt] || 75000;

        // If over exclusion limit, ask about foreign housing deduction
        if (earnedAmt === 'over126k') {
          extractedData.tax_profile.excess_foreign_income = true;
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `Since your income exceeds the FEIE limit, you may also qualify for the <strong>Foreign Housing Exclusion</strong>.<br><br><strong>What's your annual housing expense abroad?</strong>`, [
              { label: 'Under $20,000', value: 'foreign_housing_under20k' },
              { label: '$20,000 - $40,000', value: 'foreign_housing_20_40k' },
              { label: 'Over $40,000', value: 'foreign_housing_over40k' }
            ]);
          }, 800);
          return;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // Foreign Housing Handlers
      } else if (value.startsWith('foreign_housing_')) {
        const housingAmt = value.replace('foreign_housing_', '');
        const housingAmounts = { 'under20k': 15000, '20_40k': 30000, 'over40k': 50000 };
        addMessage('user', `$${(housingAmounts[housingAmt] || 30000).toLocaleString()}`);
        extractedData.tax_profile.foreign_housing_expense = housingAmounts[housingAmt] || 30000;
        calculateLeadScore();
        startIntelligentQuestioning();

      // Foreign Tax Credit Handlers
      } else if (value.startsWith('ftc_')) {
        const ftcStatus = value.replace('ftc_', '');
        const ftcLabels = { 'yes': 'Yes, taxes withheld/paid', 'no': 'No foreign taxes', 'unsure': 'Not sure' };
        addMessage('user', ftcLabels[ftcStatus] || ftcStatus);
        extractedData.tax_profile.ftc_status = ftcStatus;

        if (ftcStatus === 'yes') {
          extractedData.tax_profile.has_foreign_tax_credit = true;
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Approximately how much foreign tax did you pay?</strong>`, [
              { label: 'Under $1,000', value: 'ftc_amt_under1k' },
              { label: '$1,000 - $5,000', value: 'ftc_amt_1_5k' },
              { label: '$5,000 - $20,000', value: 'ftc_amt_5_20k' },
              { label: 'Over $20,000', value: 'ftc_amt_over20k' }
            ]);
          }, 800);
          return;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // Foreign Tax Credit Amount Handlers
      } else if (value.startsWith('ftc_amt_')) {
        const ftcAmt = value.replace('ftc_amt_', '');
        const ftcAmounts = { 'under1k': 500, '1_5k': 3000, '5_20k': 12500, 'over20k': 35000 };
        addMessage('user', `$${(ftcAmounts[ftcAmt] || 3000).toLocaleString()}`);
        extractedData.tax_profile.foreign_tax_paid = ftcAmounts[ftcAmt] || 3000;
        calculateLeadScore();
        startIntelligentQuestioning();

      // FBAR Balance Handlers
      } else if (value.startsWith('fbar_')) {
        const fbarAmt = value.replace('fbar_', '');
        const fbarLabels = { 'under10k': 'Under $10,000', '10_50k': '$10,000-$50,000', '50_200k': '$50,000-$200,000', 'over200k': 'Over $200,000' };
        addMessage('user', fbarLabels[fbarAmt] || fbarAmt);
        extractedData.tax_profile.fbar_balance_range = fbarAmt;

        if (fbarAmt !== 'under10k') {
          extractedData.tax_profile.fbar_required = true;
          // Check for FATCA Form 8938 requirement (higher thresholds)
          if (fbarAmt === '50_200k' || fbarAmt === 'over200k') {
            extractedData.tax_profile.fatca_8938_may_apply = true;
          }
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // Multi-State Filing Handlers
      } else if (value.startsWith('multistate_')) {
        const multiType = value.replace('multistate_', '');
        const multiLabels = { 'no': 'Just one state', 'work': 'Worked in another state', 'moved': 'Moved to a new state', 'remote': 'Multiple states (remote)' };
        addMessage('user', multiLabels[multiType] || multiType);
        extractedData.tax_profile.multistate_status = multiType;

        if (multiType !== 'no') {
          extractedData.tax_profile.is_multistate_filer = true;
          extractedData.lead_data.complexity = 'complex';

          // Ask for the additional state(s)
          showTyping();
          setTimeout(() => {
            hideTyping();
            if (multiType === 'moved') {
              addMessage('ai', `<strong>When did you move?</strong><br><small>This affects your part-year resident status.</small>`, [
                { label: 'January - March', value: 'moved_q1' },
                { label: 'April - June', value: 'moved_q2' },
                { label: 'July - September', value: 'moved_q3' },
                { label: 'October - December', value: 'moved_q4' }
              ]);
            } else if (multiType === 'work') {
              addMessage('ai', `<strong>How many days did you work in the other state?</strong><br><small>Many states require filing if you work there 10+ days.</small>`, [
                { label: 'Under 10 days', value: 'workdays_under10' },
                { label: '10-30 days', value: 'workdays_10_30' },
                { label: '30-60 days', value: 'workdays_30_60' },
                { label: 'Over 60 days', value: 'workdays_over60' }
              ]);
            } else if (multiType === 'remote') {
              addMessage('ai', `<strong>How many states did you work from remotely?</strong>`, [
                { label: '2 states', value: 'remote_states_2' },
                { label: '3 states', value: 'remote_states_3' },
                { label: '4+ states', value: 'remote_states_4plus' }
              ]);
            }
          }, 800);
          return;
        }
        startIntelligentQuestioning();

      // Move Date Handlers
      } else if (value.startsWith('moved_')) {
        const moveQuarter = value.replace('moved_', '');
        const moveLabels = { 'q1': 'January-March', 'q2': 'April-June', 'q3': 'July-September', 'q4': 'October-December' };
        addMessage('user', moveLabels[moveQuarter] || moveQuarter);
        extractedData.tax_profile.move_quarter = moveQuarter;
        // Calculate approximate days in each state
        const daysInOldState = { 'q1': 75, 'q2': 150, 'q3': 225, 'q4': 300 };
        extractedData.tax_profile.days_in_old_state = daysInOldState[moveQuarter] || 180;
        extractedData.tax_profile.days_in_new_state = 365 - (daysInOldState[moveQuarter] || 180);
        calculateLeadScore();
        startIntelligentQuestioning();

      // Work Days in Other State Handlers
      } else if (value.startsWith('workdays_')) {
        const workdays = value.replace('workdays_', '');
        const workdayLabels = { 'under10': 'Under 10 days', '10_30': '10-30 days', '30_60': '30-60 days', 'over60': 'Over 60 days' };
        const workdayAmounts = { 'under10': 5, '10_30': 20, '30_60': 45, 'over60': 90 };
        addMessage('user', workdayLabels[workdays] || workdays);
        extractedData.tax_profile.workdays_other_state = workdayAmounts[workdays] || 20;

        // Flag if likely need to file in other state
        if (workdays !== 'under10') {
          extractedData.tax_profile.likely_need_nonresident_return = true;
        }
        calculateLeadScore();
        startIntelligentQuestioning();

      // Remote States Count Handlers
      } else if (value.startsWith('remote_states_')) {
        const stateCount = value.replace('remote_states_', '');
        const countLabels = { '2': '2 states', '3': '3 states', '4plus': '4+ states' };
        const countAmounts = { '2': 2, '3': 3, '4plus': 5 };
        addMessage('user', countLabels[stateCount] || stateCount);
        extractedData.tax_profile.remote_work_states = countAmounts[stateCount] || 2;
        extractedData.tax_profile.needs_multistate_planning = true;
        calculateLeadScore();
        startIntelligentQuestioning();

      // Run full analysis
      } else if (value === 'run_full_analysis') {
        addMessage('user', 'Run full analysis');
        performTaxCalculation();

      // Edit profile
      } else if (value === 'edit_profile') {
        addMessage('user', 'I want to edit my information');
        // Reset the flags to allow re-asking questions
        extractedData.tax_profile.deductions_explored = false;
        extractedData.tax_profile.goals_explored = false;
        addMessage('ai', 'No problem! What would you like to change?', [
          { label: 'Change filing status', value: 'edit_filing' },
          { label: 'Change income', value: 'edit_income' },
          { label: 'Change state', value: 'edit_state' },
          { label: 'Continue with analysis', value: 'run_full_analysis', primary: true }
        ]);

      } else if (value === 'edit_filing') {
        extractedData.tax_profile.filing_status = null;
        startIntelligentQuestioning();

      } else if (value === 'edit_income') {
        extractedData.tax_profile.total_income = null;
        startIntelligentQuestioning();

      } else if (value === 'edit_state') {
        extractedData.tax_profile.state = null;
        startIntelligentQuestioning();

      } else if (value === 'analyze_deductions') {
        addMessage('user', 'Yes, find more savings');
        analyzeDeductions();

      } else if (value === 'show_all_strategies') {
        addMessage('user', 'Show me all strategies');
        showAllStrategies();

      } else if (value === 'explore_strategies') {
        addMessage('user', 'Yes, show me the strategies');
        currentStrategyIndex = 0;
        showNextStrategy();

      } else if (value === 'quick_summary') {
        addMessage('user', 'Skip to summary');
        showStrategySummary();

      } else if (value === 'next_strategy') {
        currentStrategyIndex++;
        showNextStrategy();

      } else if (value === 'previous_strategy') {
        currentStrategyIndex = Math.max(0, currentStrategyIndex - 1);
        showNextStrategy();

      } else if (value === 'finish_strategies') {
        addMessage('user', 'I\'ve reviewed all strategies');
        showStrategySummary();

      // Deduction selection handlers
      } else if (value.startsWith('has_')) {
        const deductionType = value.replace('has_', '');
        const deductionLabels = {
          'mortgage': 'Mortgage interest',
          'charity': 'Charitable donations',
          'medical': 'Medical expenses',
          'education': 'Education expenses',
          'business': 'Business expenses',
          'retirement': 'Retirement contributions'
        };
        const label = deductionLabels[deductionType] || deductionType;
        addMessage('user', label);

        extractedData.deductions = extractedData.deductions || [];
        extractedData.deductions.push(deductionType);
        extractedData.lead_data.score += 5;
        calculateLeadScore();

        // Ask for amount
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `Approximately how much in ${label.toLowerCase()} for 2025?`, [
            { label: 'Under $5,000', value: `amount_${deductionType}_low` },
            { label: '$5,000 - $15,000', value: `amount_${deductionType}_mid` },
            { label: 'Over $15,000', value: `amount_${deductionType}_high` },
            { label: 'Skip this', value: 'deduction_next' }
          ]);
        }, 800);

      } else if (value.startsWith('amount_')) {
        // Handle deduction amount selection
        const parts = value.split('_');
        const level = parts[parts.length - 1];
        const amountMap = { 'low': '$2,500', 'mid': '$10,000', 'high': '$20,000+' };
        addMessage('user', amountMap[level] || 'Estimated');

        // Continue to next deduction or credits
        showTyping();
        setTimeout(() => {
          hideTyping();
          askNextDeductionOrCredits();
        }, 800);

      } else if (value === 'deduction_next') {
        addMessage('user', 'Skip');
        showTyping();
        setTimeout(() => {
          hideTyping();
          askNextDeductionOrCredits();
        }, 500);

      } else if (value === 'deductions_done') {
        addMessage('user', 'Continue');
        showTyping();
        setTimeout(() => {
          hideTyping();
          // Move to credits or generate report
          addMessage('ai', `Got it! Now let's check for tax credits you might qualify for.`, [
            { label: 'Child Tax Credit', value: 'credit_child' },
            { label: 'Education Credits', value: 'credit_education' },
            { label: 'Energy Credits', value: 'credit_energy' },
            { label: 'Skip to report →', value: 'generate_report' }
          ]);
        }, 800);

      // CPA scheduling handlers
      } else if (value === 'schedule_time') {
        addMessage('user', 'Schedule a consultation');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `Great! Our CPA team will reach out within 24 hours to schedule at your convenience.<br><br>In the meantime, would you like your detailed tax report?`, [
            { label: 'Yes, generate my report →', value: 'generate_report' },
            { label: "I'll wait for the CPA call", value: 'finish_satisfied' }
          ]);
        }, 1000);

      } else if (value === 'email_only') {
        addMessage('user', 'Just email me');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `Perfect! We'll send your tax analysis summary to your email.<br><br>Would you also like your full advisory report?`, [
            { label: 'Yes, generate full report →', value: 'generate_report' },
            { label: "Email summary is enough", value: 'finish_satisfied' }
          ]);
        }, 1000);

      } else if (value === 'generate_report_early') {
        addMessage('user', 'Generate my full report');
        updateProgress(90);
        // Generate actual advisory report
        value = 'generate_report'; // Fall through to existing handler

      } else if (value === 'request_cpa_early') {
        addMessage('user', 'I want to speak with a CPA');
        requestCPAConnection();

      // Consolidated status handler - redirects to main flow via startIntelligentQuestioning
      } else if (value.startsWith('status_')) {
        const status = value.replace('status_', '').replace('_', ' ');
        const statusMap = {
          'single': 'Single',
          'married filing jointly': 'Married Filing Jointly',
          'married_filing_jointly': 'Married Filing Jointly',
          'head of household': 'Head of Household',
          'married filing separately': 'Married Filing Separately',
          'qualifying surviving spouse': 'Qualifying Surviving Spouse'
        };
        const displayStatus = statusMap[status] || status.charAt(0).toUpperCase() + status.slice(1);
        addMessage('user', displayStatus);
        extractedData.tax_profile.filing_status = displayStatus;
        updateStats({ filing_status: displayStatus });
        updateProgress(15);
        extractedData.lead_data.score += 10;
        calculateLeadScore();

        // Use consolidated main flow instead of separate inline flow
        startIntelligentQuestioning();

      } else if (value.startsWith('focus_')) {
        const focus = value.replace('focus_', '').replace('_', ' ');
        addMessage('user', focus.charAt(0).toUpperCase() + focus.slice(1));
        extractedData.focus_area = focus;
        updateProgress(45);

        showTyping();
        setTimeout(() => {
          hideTyping();

          // Provide tailored responses based on focus area
          if (value === 'focus_real_estate') {
            addMessage('ai', `Excellent choice! Real estate offers significant tax advantages. Let me understand your situation better.<br><br><strong>Do you own your primary residence?</strong>`, [
              { label: 'Yes, I own my home', value: 'homeowner_yes' },
              { label: 'No, I rent', value: 'homeowner_no' },
              { label: 'I own rental properties', value: 'homeowner_rental' }
            ]);
          } else if (value === 'focus_education') {
            addMessage('ai', `Education expenses can provide valuable tax benefits. Let's explore your situation.<br><br><strong>Are you currently paying for education expenses?</strong>`, [
              { label: 'Yes, for myself', value: 'edu_self' },
              { label: 'Yes, for dependents', value: 'edu_dependents' },
              { label: 'I have student loan interest', value: 'edu_loans' },
              { label: 'Multiple of these', value: 'edu_multiple' }
            ]);
          } else if (value === 'focus_business') {
            addMessage('ai', `Self-employment and business income create unique opportunities for tax optimization. Tell me more.<br><br><strong>What's your business structure?</strong>`, [
              { label: 'Sole Proprietor / Freelancer', value: 'biz_sole' },
              { label: 'LLC / Partnership', value: 'biz_llc' },
              { label: 'S-Corp / C-Corp', value: 'biz_corp' },
              { label: 'Side business / Gig work', value: 'biz_side' }
            ]);
          } else if (value === 'focus_healthcare') {
            addMessage('ai', `Healthcare expenses can add up, but there are ways to reduce your tax burden. Let's review your situation.<br><br><strong>Do you have significant medical expenses?</strong>`, [
              { label: 'Yes, over $5,000 annually', value: 'medical_high' },
              { label: 'Moderate expenses', value: 'medical_moderate' },
              { label: 'I have an HSA', value: 'medical_hsa' },
              { label: 'Long-term care expenses', value: 'medical_ltc' }
            ]);
          } else if (value === 'focus_investments') {
            addMessage('ai', `Investment and retirement planning are crucial for long-term tax efficiency. Let's dive in.<br><br><strong>What types of investment accounts do you have?</strong>`, [
              { label: '401(k) / Traditional IRA', value: 'inv_traditional' },
              { label: 'Roth IRA', value: 'inv_roth' },
              { label: 'Brokerage / Taxable accounts', value: 'inv_brokerage' },
              { label: 'Multiple account types', value: 'inv_multiple' }
            ]);
          }
        }, 1500);

      // =====================================================================
      // FOCUS-BASED FLOW HANDLERS (with specific follow-ups)
      // =====================================================================

      // Homeowner/Real Estate handlers
      } else if (value.startsWith('homeowner_')) {
        const homeType = value.replace('homeowner_', '');
        const homeLabels = {
          'yes': 'Yes, I own my home',
          'no': 'No, I rent',
          'rental': 'I own rental properties'
        };
        addMessage('user', homeLabels[homeType] || homeType);
        extractedData.details = extractedData.details || {};
        extractedData.details[value] = true;

        showTyping();
        setTimeout(() => {
          hideTyping();
          if (homeType === 'yes') {
            // Primary residence - ask about mortgage and property tax
            addMessage('ai', `Homeownership offers great tax benefits! Let me understand your situation better.<br><br><strong>What's your approximate annual mortgage interest?</strong>`, [
              { label: 'Under $5,000', value: 'mortgage_under5k' },
              { label: '$5,000 - $15,000', value: 'mortgage_5_15k' },
              { label: '$15,000 - $30,000', value: 'mortgage_15_30k' },
              { label: 'Over $30,000', value: 'mortgage_over30k' },
              { label: 'No mortgage / Paid off', value: 'mortgage_none' }
            ]);
          } else if (homeType === 'rental') {
            // Rental property owner - ask about rental details
            addMessage('ai', `Rental properties can provide significant tax advantages. Let me learn more.<br><br><strong>How many rental properties do you own?</strong>`, [
              { label: '1 property', value: 'rental_props_1' },
              { label: '2-4 properties', value: 'rental_props_2_4' },
              { label: '5+ properties', value: 'rental_props_5plus' }
            ]);
          } else {
            // Renter - continue to next section
            continueToDeductionsFromFocus();
          }
        }, 1000);

      // Mortgage amount handlers
      } else if (value.startsWith('mortgage_')) {
        const mortgageLevel = value.replace('mortgage_', '');
        const mortgageAmounts = {
          'under5k': 2500, '5_15k': 10000, '15_30k': 22500, 'over30k': 40000, 'none': 0
        };
        const mortgageLabels = {
          'under5k': 'Under $5,000', '5_15k': '$5,000 - $15,000',
          '15_30k': '$15,000 - $30,000', 'over30k': 'Over $30,000', 'none': 'No mortgage'
        };
        addMessage('user', mortgageLabels[mortgageLevel] || mortgageLevel);
        extractedData.tax_items.mortgage_interest = mortgageAmounts[mortgageLevel] || 0;

        // Now ask about property tax
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<strong>What's your approximate annual property tax?</strong>`, [
            { label: 'Under $3,000', value: 'proptax_under3k' },
            { label: '$3,000 - $8,000', value: 'proptax_3_8k' },
            { label: '$8,000 - $15,000', value: 'proptax_8_15k' },
            { label: 'Over $15,000', value: 'proptax_over15k' },
            { label: 'Not sure / Skip', value: 'proptax_skip' }
          ]);
        }, 800);

      // Property tax handlers
      } else if (value.startsWith('proptax_')) {
        const propTaxLevel = value.replace('proptax_', '');
        const propTaxAmounts = {
          'under3k': 1500, '3_8k': 5500, '8_15k': 11500, 'over15k': 20000, 'skip': 0
        };
        if (propTaxLevel !== 'skip') {
          const propTaxLabels = {
            'under3k': 'Under $3,000', '3_8k': '$3,000 - $8,000',
            '8_15k': '$8,000 - $15,000', 'over15k': 'Over $15,000'
          };
          addMessage('user', propTaxLabels[propTaxLevel] || propTaxLevel);
        } else {
          addMessage('user', 'Skip');
        }
        extractedData.tax_items.property_tax = propTaxAmounts[propTaxLevel] || 0;
        continueToDeductionsFromFocus();

      // Rental property count handlers
      } else if (value.startsWith('rental_props_')) {
        const rentalCount = value.replace('rental_props_', '');
        const rentalLabels = { '1': '1 property', '2_4': '2-4 properties', '5plus': '5+ properties' };
        addMessage('user', rentalLabels[rentalCount] || rentalCount);
        extractedData.tax_profile.rental_property_count = rentalCount;
        extractedData.tax_profile.has_rental_income = true;

        // Ask about rental income
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<strong>What's your total annual rental income (before expenses)?</strong>`, [
            { label: 'Under $20,000', value: 'rental_income_under20k' },
            { label: '$20,000 - $50,000', value: 'rental_income_20_50k' },
            { label: '$50,000 - $100,000', value: 'rental_income_50_100k' },
            { label: 'Over $100,000', value: 'rental_income_over100k' }
          ]);
        }, 800);

      // Rental income handlers
      } else if (value.startsWith('rental_income_')) {
        const incomeLevel = value.replace('rental_income_', '');
        const incomeAmounts = {
          'under20k': 15000, '20_50k': 35000, '50_100k': 75000, 'over100k': 150000
        };
        const incomeLabels = {
          'under20k': 'Under $20,000', '20_50k': '$20,000 - $50,000',
          '50_100k': '$50,000 - $100,000', 'over100k': 'Over $100,000'
        };
        addMessage('user', incomeLabels[incomeLevel] || incomeLevel);
        extractedData.tax_profile.rental_income = incomeAmounts[incomeLevel] || 0;
        continueToDeductionsFromFocus();

      // Education handlers
      } else if (value.startsWith('edu_')) {
        const eduType = value.replace('edu_', '');
        const eduLabels = {
          'self': 'Yes, for myself',
          'dependents': 'Yes, for dependents',
          'loans': 'I have student loan interest',
          'multiple': 'Multiple of these'
        };
        addMessage('user', eduLabels[eduType] || eduType);
        extractedData.details = extractedData.details || {};
        extractedData.details[value] = true;

        showTyping();
        setTimeout(() => {
          hideTyping();
          if (eduType === 'loans' || eduType === 'multiple') {
            // Ask about student loan interest
            addMessage('ai', `Student loan interest can be deductible up to $2,500.<br><br><strong>How much student loan interest do you pay annually?</strong>`, [
              { label: 'Under $1,000', value: 'student_loan_under1k' },
              { label: '$1,000 - $2,500', value: 'student_loan_1_2.5k' },
              { label: 'Over $2,500', value: 'student_loan_over2.5k' },
              { label: 'Not sure', value: 'student_loan_unsure' }
            ]);
          } else if (eduType === 'dependents') {
            // Ask about education expenses for dependents
            addMessage('ai', `Education credits can save you up to $2,500 per student!<br><br><strong>How many dependents are in college or vocational school?</strong>`, [
              { label: '1 student', value: 'college_students_1' },
              { label: '2 students', value: 'college_students_2' },
              { label: '3+ students', value: 'college_students_3plus' }
            ]);
          } else {
            // Self education - ask about expenses
            addMessage('ai', `<strong>What's your approximate annual education expense?</strong>`, [
              { label: 'Under $5,000', value: 'edu_expense_under5k' },
              { label: '$5,000 - $15,000', value: 'edu_expense_5_15k' },
              { label: 'Over $15,000', value: 'edu_expense_over15k' }
            ]);
          }
        }, 800);

      // Student loan interest handlers
      } else if (value.startsWith('student_loan_')) {
        const loanLevel = value.replace('student_loan_', '');
        const loanAmounts = { 'under1k': 500, '1_2.5k': 1750, 'over2.5k': 2500, 'unsure': 1500 };
        const loanLabels = {
          'under1k': 'Under $1,000', '1_2.5k': '$1,000 - $2,500',
          'over2.5k': 'Over $2,500', 'unsure': 'Not sure'
        };
        addMessage('user', loanLabels[loanLevel] || loanLevel);
        extractedData.tax_items.student_loan_interest = loanAmounts[loanLevel] || 0;
        continueToDeductionsFromFocus();

      // College students count handlers
      } else if (value.startsWith('college_students_')) {
        const count = value.replace('college_students_', '');
        const countLabels = { '1': '1 student', '2': '2 students', '3plus': '3+ students' };
        addMessage('user', countLabels[count] || count);
        extractedData.tax_profile.college_students = count === '3plus' ? 3 : parseInt(count);
        extractedData.tax_profile.has_college_students = true;
        continueToDeductionsFromFocus();

      // Education expense handlers
      } else if (value.startsWith('edu_expense_')) {
        const expLevel = value.replace('edu_expense_', '');
        const expAmounts = { 'under5k': 3000, '5_15k': 10000, 'over15k': 20000 };
        const expLabels = { 'under5k': 'Under $5,000', '5_15k': '$5,000 - $15,000', 'over15k': 'Over $15,000' };
        addMessage('user', expLabels[expLevel] || expLevel);
        extractedData.tax_items.education_expenses = expAmounts[expLevel] || 0;
        continueToDeductionsFromFocus();

      // Healthcare/Medical handlers (from focus flow)
      } else if (value === 'medical_high' || value === 'medical_moderate' ||
                 value === 'medical_hsa' || value === 'medical_ltc') {
        const medLabels = {
          'medical_high': 'Yes, over $5,000 annually',
          'medical_moderate': 'Moderate expenses',
          'medical_hsa': 'I have an HSA',
          'medical_ltc': 'Long-term care expenses'
        };
        addMessage('user', medLabels[value] || value);
        extractedData.details = extractedData.details || {};
        extractedData.details[value] = true;

        showTyping();
        setTimeout(() => {
          hideTyping();
          if (value === 'medical_hsa') {
            // Ask about HSA contributions
            addMessage('ai', `HSA offers triple tax benefits - contributions are deductible, growth is tax-free, and withdrawals for medical expenses are tax-free!<br><br><strong>How much do you contribute to your HSA annually?</strong>`, [
              { label: 'Under $2,000', value: 'hsa_under2k' },
              { label: '$2,000 - $4,000', value: 'hsa_2_4k' },
              { label: 'Maxing out ($4,150 single / $8,300 family)', value: 'hsa_max' },
              { label: 'Not sure', value: 'hsa_unsure' }
            ]);
          } else if (value === 'medical_high' || value === 'medical_ltc') {
            // Ask about specific medical amount for high expenses
            addMessage('ai', `<strong>What's your estimated annual out-of-pocket medical expense?</strong>`, [
              { label: '$5,000 - $10,000', value: 'medical_amt_5_10k' },
              { label: '$10,000 - $25,000', value: 'medical_amt_10_25k' },
              { label: '$25,000 - $50,000', value: 'medical_amt_25_50k' },
              { label: 'Over $50,000', value: 'medical_amt_over50k' }
            ]);
          } else if (value === 'medical_moderate') {
            // Ask about moderate medical expenses too
            addMessage('ai', `<strong>What's your estimated annual out-of-pocket medical expense?</strong>`, [
              { label: 'Under $2,000', value: 'medical_amt_under2k' },
              { label: '$2,000 - $5,000', value: 'medical_amt_2_5k' },
              { label: '$5,000 - $10,000', value: 'medical_amt_5_10k' },
              { label: 'Skip this', value: 'medical_amt_skip' }
            ]);
          } else {
            continueToDeductionsFromFocus();
          }
        }, 800);

      // HSA contribution handlers
      } else if (value.startsWith('hsa_')) {
        const hsaLevel = value.replace('hsa_', '');
        const hsaAmounts = { 'under2k': 1500, '2_4k': 3000, 'max': 4150, 'unsure': 2000 };
        const hsaLabels = {
          'under2k': 'Under $2,000', '2_4k': '$2,000 - $4,000',
          'max': 'Maxing out', 'unsure': 'Not sure'
        };
        addMessage('user', hsaLabels[hsaLevel] || hsaLevel);
        extractedData.tax_items.hsa_contributions = hsaAmounts[hsaLevel] || 0;
        extractedData.tax_profile.has_hsa = true;
        continueToDeductionsFromFocus();

      // Medical amount handlers (from focus flow)
      } else if (value.startsWith('medical_amt_')) {
        const medLevel = value.replace('medical_amt_', '');
        const medAmounts = {
          'under2k': 1000, '2_5k': 3500, '5_10k': 7500,
          '10_25k': 17500, '25_50k': 37500, 'over50k': 60000, 'skip': 0
        };
        const medLabels = {
          'under2k': 'Under $2,000', '2_5k': '$2,000 - $5,000',
          '5_10k': '$5,000 - $10,000', '10_25k': '$10,000 - $25,000',
          '25_50k': '$25,000 - $50,000', 'over50k': 'Over $50,000', 'skip': 'Skip'
        };
        addMessage('user', medLabels[medLevel] || medLevel);
        extractedData.tax_items.medical = medAmounts[medLevel] || 0;
        continueToDeductionsFromFocus();

      // Investment handlers (from focus flow)
      } else if (value.startsWith('inv_')) {
        const invType = value.replace('inv_', '');
        const invLabels = {
          'traditional': '401(k) / Traditional IRA',
          'roth': 'Roth IRA',
          'brokerage': 'Brokerage / Taxable accounts',
          'multiple': 'Multiple account types'
        };
        addMessage('user', invLabels[invType] || invType);
        extractedData.details = extractedData.details || {};
        extractedData.details[value] = true;

        showTyping();
        setTimeout(() => {
          hideTyping();
          if (invType === 'brokerage' || invType === 'multiple') {
            // Ask about capital gains/losses
            addMessage('ai', `Taxable investment accounts have important tax implications.<br><br><strong>Did you have any capital gains or losses this year?</strong>`, [
              { label: 'Net gains (profit)', value: 'capgains_gains' },
              { label: 'Net losses', value: 'capgains_losses' },
              { label: 'About break-even', value: 'capgains_even' },
              { label: 'Haven\'t sold anything', value: 'capgains_none' }
            ]);
          } else if (invType === 'traditional') {
            // Ask about 401k contributions
            addMessage('ai', `<strong>How much are you contributing to your 401(k) or Traditional IRA this year?</strong>`, [
              { label: 'Under $10,000', value: 'trad_contrib_under10k' },
              { label: '$10,000 - $20,000', value: 'trad_contrib_10_20k' },
              { label: 'Maxing out 401(k) ($23,500)', value: 'trad_contrib_max401k' },
              { label: 'Maxing out IRA ($7,000)', value: 'trad_contrib_maxira' }
            ]);
          } else {
            // Roth - ask about contributions
            addMessage('ai', `<strong>How much are you contributing to your Roth IRA this year?</strong>`, [
              { label: 'Under $3,000', value: 'roth_contrib_under3k' },
              { label: '$3,000 - $7,000', value: 'roth_contrib_3_7k' },
              { label: 'Maxing out ($7,000)', value: 'roth_contrib_max' },
              { label: 'Using Backdoor Roth', value: 'roth_contrib_backdoor' }
            ]);
          }
        }, 800);

      // Capital gains handlers
      } else if (value.startsWith('capgains_')) {
        const cgType = value.replace('capgains_', '');
        const cgLabels = {
          'gains': 'Net gains (profit)', 'losses': 'Net losses',
          'even': 'About break-even', 'none': 'Haven\'t sold anything'
        };
        addMessage('user', cgLabels[cgType] || cgType);
        extractedData.tax_profile.has_capital_gains = (cgType === 'gains');
        extractedData.tax_profile.has_capital_losses = (cgType === 'losses');

        if (cgType === 'gains') {
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Approximately how much in capital gains?</strong>`, [
              { label: 'Under $10,000', value: 'capgains_amt_under10k' },
              { label: '$10,000 - $50,000', value: 'capgains_amt_10_50k' },
              { label: '$50,000 - $100,000', value: 'capgains_amt_50_100k' },
              { label: 'Over $100,000', value: 'capgains_amt_over100k' }
            ]);
          }, 800);
        } else if (cgType === 'losses') {
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `Tax-loss harvesting can offset gains and up to $3,000 of ordinary income!<br><br><strong>Approximately how much in capital losses?</strong>`, [
              { label: 'Under $3,000', value: 'caploss_amt_under3k' },
              { label: '$3,000 - $10,000', value: 'caploss_amt_3_10k' },
              { label: 'Over $10,000', value: 'caploss_amt_over10k' }
            ]);
          }, 800);
        } else {
          continueToDeductionsFromFocus();
        }

      // Capital gains amount handlers
      } else if (value.startsWith('capgains_amt_')) {
        const amt = value.replace('capgains_amt_', '');
        const amounts = { 'under10k': 5000, '10_50k': 30000, '50_100k': 75000, 'over100k': 150000 };
        const labels = {
          'under10k': 'Under $10,000', '10_50k': '$10,000 - $50,000',
          '50_100k': '$50,000 - $100,000', 'over100k': 'Over $100,000'
        };
        addMessage('user', labels[amt] || amt);
        extractedData.tax_profile.capital_gains = amounts[amt] || 0;
        continueToDeductionsFromFocus();

      // Capital loss amount handlers
      } else if (value.startsWith('caploss_amt_')) {
        const amt = value.replace('caploss_amt_', '');
        const amounts = { 'under3k': 1500, '3_10k': 6500, 'over10k': 15000 };
        const labels = { 'under3k': 'Under $3,000', '3_10k': '$3,000 - $10,000', 'over10k': 'Over $10,000' };
        addMessage('user', labels[amt] || amt);
        extractedData.tax_profile.capital_losses = amounts[amt] || 0;
        continueToDeductionsFromFocus();

      // Traditional contribution handlers
      } else if (value.startsWith('trad_contrib_')) {
        const level = value.replace('trad_contrib_', '');
        const amounts = { 'under10k': 7500, '10_20k': 15000, 'max401k': 23500, 'maxira': 7000 };
        const labels = {
          'under10k': 'Under $10,000', '10_20k': '$10,000 - $20,000',
          'max401k': 'Maxing out 401(k)', 'maxira': 'Maxing out IRA'
        };
        addMessage('user', labels[level] || level);
        if (level === 'max401k' || level === '10_20k' || level === 'under10k') {
          extractedData.tax_profile.retirement_401k = amounts[level];
          extractedData.tax_profile.has_401k = true;
        } else {
          extractedData.tax_profile.retirement_ira = amounts[level];
        }
        continueToDeductionsFromFocus();

      // Roth contribution handlers
      } else if (value.startsWith('roth_contrib_')) {
        const level = value.replace('roth_contrib_', '');
        const labels = {
          'under3k': 'Under $3,000', '3_7k': '$3,000 - $7,000',
          'max': 'Maxing out ($7,000)', 'backdoor': 'Using Backdoor Roth'
        };
        addMessage('user', labels[level] || level);
        extractedData.tax_profile.has_roth = true;
        if (level === 'backdoor') {
          extractedData.tax_profile.uses_backdoor_roth = true;
        }
        continueToDeductionsFromFocus();

      // Business handlers from focus flow (biz_sole, biz_llc, etc. - different from biz_professional)
      } else if (value === 'biz_sole' || value === 'biz_llc' || value === 'biz_corp' || value === 'biz_side') {
        const bizLabels = {
          'biz_sole': 'Sole Proprietor / Freelancer',
          'biz_llc': 'LLC / Partnership',
          'biz_corp': 'S-Corp / C-Corp',
          'biz_side': 'Side business / Gig work'
        };
        addMessage('user', bizLabels[value] || value);
        extractedData.tax_profile.is_self_employed = true;
        extractedData.details = extractedData.details || {};
        extractedData.details[value] = true;

        // Map to entity types for consistency
        if (value === 'biz_sole') extractedData.tax_profile.entity_type = 'sole';
        if (value === 'biz_llc') extractedData.tax_profile.entity_type = 'llc_single';
        if (value === 'biz_corp') extractedData.tax_profile.entity_type = 'scorp';
        if (value === 'biz_side') extractedData.tax_profile.has_side_business = true;

        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<strong>What's your approximate annual business income (before expenses)?</strong>`, [
            { label: 'Under $25,000', value: 'bizinc_under25k' },
            { label: '$25,000 - $75,000', value: 'bizinc_25_75k' },
            { label: '$75,000 - $150,000', value: 'bizinc_75_150k' },
            { label: 'Over $150,000', value: 'bizinc_over150k' }
          ]);
        }, 800);

      // Business income handlers
      } else if (value.startsWith('bizinc_')) {
        const level = value.replace('bizinc_', '');
        const amounts = { 'under25k': 15000, '25_75k': 50000, '75_150k': 112500, 'over150k': 200000 };
        const labels = {
          'under25k': 'Under $25,000', '25_75k': '$25,000 - $75,000',
          '75_150k': '$75,000 - $150,000', 'over150k': 'Over $150,000'
        };
        addMessage('user', labels[level] || level);
        extractedData.tax_profile.business_income = amounts[level] || 0;
        continueToDeductionsFromFocus();

      } else if (value.startsWith('deduct_')) {
        if (value === 'deduct_skip') {
          addMessage('user', 'Let\'s continue');
        } else {
          const deduction = value.replace('deduct_', '').replace('_', ' ');
          addMessage('user', deduction.charAt(0).toUpperCase() + deduction.slice(1));
          extractedData.deductions = extractedData.deductions || [];
          extractedData.deductions.push(deduction);
        }
        updateProgress(75);

        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `Perfect! Now let's explore tax credits you might qualify for. Credits directly reduce your tax bill dollar-for-dollar.<br><br><strong>Do any of these situations apply to you?</strong>`, [
            { label: '👶 Child Tax Credit', value: 'credit_child' },
            { label: getIcon('academic-cap', 'sm') + ' Education Credits (AOTC/LLC)', value: 'credit_education' },
            { label: getIcon('bolt', 'sm') + ' Energy Efficiency Credits', value: 'credit_energy' },
            { label: getIcon('briefcase', 'sm') + ' Earned Income Credit', value: 'credit_eitc' },
            { label: 'Not sure / Continue', value: 'credit_skip' }
          ]);
        }, 1500);

      } else if (value.startsWith('credit_')) {
        if (value === 'credit_skip') {
          addMessage('user', 'Let\'s continue');
        } else {
          const credit = value.replace('credit_', '').replace('_', ' ');
          addMessage('user', credit.charAt(0).toUpperCase() + credit.slice(1));
          extractedData.credits = extractedData.credits || [];
          extractedData.credits.push(credit);
        }
        updateProgress(90);

        showTyping();
        setTimeout(() => {
          hideTyping();

          // Generate summary
          const summary = generateSummary();
          addMessage('ai', `<strong>Excellent! I now have a comprehensive understanding of your tax situation.</strong><br><br>Here's what we've covered:<br><br>${summary}<br><br>Based on this information, I can provide you with a detailed strategic tax advisory report including:<br><br>✓ <strong>Personalized tax optimization strategies</strong><br>✓ <strong>Estimated tax savings opportunities</strong><br>✓ <strong>Action items for the current tax year</strong><br>✓ <strong>Long-term planning recommendations</strong><br>✓ <strong>Compliance checklist</strong><br><br><strong>Would you like me to generate your comprehensive tax advisory report now?</strong>`, [
            { label: getIcon('chart-bar', 'sm') + ' Yes, generate my report', value: 'generate_report' },
            { label: getIcon('chat-bubble-left-right', 'sm') + ' I have more questions first', value: 'more_questions' },
            { label: getIcon('document-text', 'sm') + ' Let me add documents', value: 'add_documents' }
          ]);
        }, 2000);

      } else if (value === 'generate_report') {
        addMessage('user', 'Yes, please generate my comprehensive tax advisory report');
        updateProgress(95);

        showTyping();
        addMessage('ai', `<strong>Generating your personalized tax advisory report...</strong><br><br>I'm analyzing your information and creating strategic recommendations tailored to your unique situation.<br><br>Your report will include:<br>• Comprehensive tax analysis<br>• Optimization strategies<br>• Estimated savings opportunities<br>• Action plan with timelines<br>• Filing strategy recommendations<br><br><em>Please wait while I prepare your report...</em>`);

        // Actually generate the report via API
        try {
          const reportResponse = await fetch(`/api/advisor/report`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(window.csrfToken ? {'X-CSRF-Token': window.csrfToken} : {})
            },
            body: JSON.stringify({ session_id: sessionId })
          });

          hideTyping();

          if (reportResponse.ok) {
            const reportData = await reportResponse.json();
            updateProgress(100);
            addMessage('ai', `<div class="insight-card"><div class="insight-header" style="display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3);"><span style="font-size: 32px;">🎉</span><strong style="font-size: var(--text-xl);">Your Tax Advisory Report is Ready!</strong></div><div style="color: var(--text-secondary); line-height: 1.6;">I've completed a comprehensive analysis of your tax situation. Your personalized report includes strategic recommendations that could save you thousands of dollars.</div></div><br><strong>What would you like to do next?</strong>`, [
              { label: getIcon('arrow-down-tray', 'sm') + ' Download Full Report (PDF)', value: 'download_report' },
              { label: getIcon('eye', 'sm') + ' View Report Online', value: 'view_report' },
              { label: getIcon('envelope', 'sm') + ' Email Report to Me', value: 'email_report' },
              { label: getIcon('phone', 'sm') + ' Schedule CPA Consultation', value: 'schedule_consult' }
            ]);
          } else {
            updateProgress(90);
            addMessage('ai', `<strong>Report generation encountered an issue.</strong><br><br>Don't worry — your data is saved. Please try again or download a quick summary.`, [
              { label: getIcon('arrow-path', 'sm') + ' Try Again', value: 'generate_report' },
              { label: getIcon('document-text', 'sm') + ' Quick Summary', value: 'show_strategies' }
            ]);
          }
        } catch (error) {
          hideTyping();
          console.error('Report generation failed:', error);
          addMessage('ai', `<strong>Connection issue while generating report.</strong><br><br>Your data is saved. Please check your connection and try again.`, [
            { label: getIcon('arrow-path', 'sm') + ' Retry', value: 'generate_report' },
            { label: getIcon('document-text', 'sm') + ' View Strategies', value: 'show_strategies' }
          ]);
        }

      } else if (value === 'download_report') {
        addMessage('user', 'Download my report as PDF');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<strong>Perfect! Preparing your PDF report...</strong><br><br>Your comprehensive tax advisory report is being generated with:<br>• Executive summary<br>• Detailed analysis of your tax situation<br>• Strategic recommendations<br>• Action items and timelines<br>• Potential savings breakdown<br><br><em>The download will begin automatically...</em>`);

          // Trigger actual report download
          setTimeout(() => {
            generateAndDownloadReport();
          }, 1500);
        }, 1000);

      } else if (value === 'view_report') {
        addMessage('user', 'Let me view the report online');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `Opening your interactive tax advisory report in a new window...<br><br>You'll be able to:<br>• Review all recommendations<br>• See detailed calculations<br>• Print or save as needed<br>• Share with your CPA if desired`);

          setTimeout(() => {
            window.open('/advisory-report-preview?session_id=' + sessionId, '_blank');
          }, 1000);
        }, 1000);

      } else if (value === 'email_report') {
        addMessage('user', 'Email the report to me');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `I'd be happy to email your report to you.<br><br><strong>What email address should I send it to?</strong><br><br><input type="email" id="emailInput" placeholder="your.email@example.com" style="width: 100%; padding: var(--space-3); margin: var(--space-3) 0; background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: var(--radius-lg); color: var(--text); font-size: var(--text-sm);"><button onclick="sendReportEmail()" style="padding: var(--space-3) var(--space-6); background: var(--primary); color: white; border: none; border-radius: var(--radius-lg); cursor: pointer; font-weight: var(--font-semibold);">Send Report</button>`);
        }, 1000);

      } else if (value === 'schedule_consult') {
        addMessage('user', 'I\'d like to schedule a consultation');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<strong>Excellent decision! A personalized consultation can help you maximize your tax savings.</strong><br><br>Our CPA team specializes in individual tax advisory and can provide:<br>• One-on-one strategic planning<br>• Custom optimization strategies<br>• Ongoing tax advisory support<br>• Filing assistance when needed<br><br><strong>What works best for you?</strong>`, [
            { label: getIcon('phone', 'sm') + ' Schedule a call', value: 'consult_call' },
            { label: getIcon('chat-bubble-left-right', 'sm') + ' Chat with a CPA now', value: 'consult_chat' },
            { label: getIcon('envelope', 'sm') + ' Email consultation', value: 'consult_email' }
          ]);
        }, 1500);

      } else if (value === 'focus_input') {
        // Simply focus the input field - escape from retry loop
        const input = document.getElementById('userInput');
        if (input) {
          input.focus();
          input.placeholder = 'Type your message here...';
        }
        retryCount = 0; // Reset retry counter

      } else if (value === 'contact_support') {
        addMessage('user', 'I need help from a person');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `I understand you'd like to speak with someone directly. Here are your options:<br><br>• <strong>Email:</strong> support@taxadvisor.com<br>• <strong>Phone:</strong> 1-800-TAX-HELP (available 9am-6pm ET)<br>• <strong>Live Chat:</strong> Click the chat icon in the corner<br><br>Our team typically responds within 24 hours during business days.`, [
            { label: getIcon('envelope', 'sm') + ' Send email', value: 'consult_email' },
            { label: getIcon('chat-bubble-left-right', 'sm') + ' Continue with AI', value: 'no_manual' },
            { label: getIcon('arrow-path', 'sm') + ' Start fresh', value: 'reset_conversation' }
          ]);
          retryCount = 0; // Reset retry counter
        }, 1000);

      } else if (value === 'more_questions') {
        addMessage('user', 'I have more questions first');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `Of course! I'm here to answer any questions you have. Feel free to ask me about:<br><br>• Specific deductions or credits<br>• Tax planning strategies<br>• Entity structure optimization<br>• Estimated tax payments<br>• Any other tax-related concerns<br><br><strong>What would you like to know?</strong>`);
          document.getElementById('userInput').focus();
        }, 1000);

      } else if (value === 'add_documents') {
        addMessage('user', 'Let me add some documents');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `Great! Adding documents will help me provide even more accurate recommendations.<br><br>You can upload:<br>• W-2 forms<br>• 1099 forms<br>• Previous tax returns<br>• Receipts and statements<br><br>Just drag and drop files below, or click to browse.`);
          document.getElementById('fileInput').click();
        }, 1000);

      } else if (value.startsWith('consult_')) {
        const consultType = value.replace('consult_', '');
        addMessage('user', consultType.charAt(0).toUpperCase() + consultType.slice(1) + ' consultation');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<strong>Perfect! I'm connecting you with our CPA team.</strong><br><br>Your comprehensive tax profile and advisory report will be shared with them so they can provide immediate, informed guidance.<br><br>A member of our team will reach out within 24 hours to schedule your personalized consultation.<br><br><strong>Is there anything else I can help you with today?</strong>`, [
            { label: '✅ No, I\'m all set', value: 'finish_satisfied' },
            { label: getIcon('arrow-down-tray', 'sm') + ' Download my report first', value: 'download_report' },
            { label: getIcon('chat-bubble-left-right', 'sm') + ' Ask another question', value: 'more_questions' }
          ]);
        }, 1500);

      } else if (value === 'finish_satisfied') {
        addMessage('user', 'No, I\'m all set. Thank you!');
        updateProgress(100);
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<div class="insight-card"><strong style="font-size: var(--text-lg);">🎉 Thank you for choosing Premium Tax Advisory!</strong><br><br>Your comprehensive tax profile has been saved securely. You can return anytime to:<br>• Access your advisory report<br>• Update your information<br>• Ask additional questions<br>• Schedule consultations<br><br>Remember, strategic tax planning is an ongoing process. We're here to support you throughout the year, not just during tax season.<br><br><em>Wishing you maximum savings and financial success!</em></div>`);

          // Add confetti or celebration animation here if desired
          updateInsights(['Your tax advisory session is complete!', 'Report saved to your account', 'Next steps emailed to you']);
        }, 1500);

      } else if (value === 'continue_assessment') {
        addMessage('user', 'Let\'s continue with the assessment');
        showTyping();
        setTimeout(() => {
          hideTyping();

          // Determine next logical step based on what's missing
          if (!extractedData.filing_status) {
            addMessage('ai', `What's your filing status?`, [
              { label: 'Single', value: 'filing_single' },
              { label: 'Married Filing Jointly', value: 'filing_married' },
              { label: 'Head of Household', value: 'filing_hoh' },
              { label: 'Married Filing Separately', value: 'filing_mfs' },
              { label: 'Qualifying Surviving Spouse', value: 'filing_qss' }
            ]);
          } else if (!extractedData.income_range) {
            addMessage('ai', `What's your approximate annual income?`, [
              { label: 'Under $50K', value: 'income_0_50k' },
              { label: '$50K - $100K', value: 'income_50_100k' },
              { label: '$100K - $200K', value: 'income_100_200k' },
              { label: '$200K+', value: 'income_200_500k' }
            ]);
          } else if (!extractedData.focus_area) {
            addMessage('ai', `Excellent! <strong>What areas are you most interested in optimizing?</strong>`, [
              { label: getIcon('home', 'sm') + ' Homeownership & Real Estate', value: 'focus_real_estate' },
              { label: getIcon('academic-cap', 'sm') + ' Education & Student Loans', value: 'focus_education' },
              { label: getIcon('briefcase', 'sm') + ' Business & Self-Employment', value: 'focus_business' },
              { label: '🏥 Healthcare & Medical', value: 'focus_healthcare' },
              { label: getIcon('arrow-trending-up', 'sm') + ' Investments & Retirement', value: 'focus_investments' }
            ]);
          } else {
            addMessage('ai', `We've covered the basics! <strong>Ready to generate your comprehensive advisory report?</strong>`, [
              { label: getIcon('chart-bar', 'sm') + ' Yes, generate report', value: 'generate_report' },
              { label: getIcon('chat-bubble-left-right', 'sm') + ' I have questions first', value: 'more_questions' }
            ]);
          }
        }, 1000);

      } else if (value === 'continue_questioning' || value === 'continue_flow') {
        // Resume the intelligent questioning flow after document upload or session restore
        addMessage('user', value === 'continue_questioning' ? 'Yes, let\'s continue' : 'Continue');
        startIntelligentQuestioning();

      } else if (value === 'review_data') {
        // Show user what data we have collected
        addMessage('user', 'Show me what you have');
        showTyping();
        setTimeout(() => {
          hideTyping();
          const profile = extractedData.tax_profile;
          const items = extractedData.tax_items;

          let summary = '<strong>📋 Here\'s what I have so far:</strong><br><br>';

          if (profile.filing_status) summary += `• Filing Status: ${profile.filing_status}<br>`;
          if (profile.state) summary += `• State: ${profile.state_name || profile.state}<br>`;
          if (profile.total_income) summary += `• Total Income: $${profile.total_income.toLocaleString()}<br>`;
          if (profile.dependents !== undefined) summary += `• Dependents: ${profile.dependents}<br>`;
          if (profile.income_source) summary += `• Income Source: ${profile.income_source}<br>`;
          if (profile.is_self_employed) summary += `• Self-Employed: Yes<br>`;
          if (items.mortgage_interest) summary += `• Mortgage Interest: $${items.mortgage_interest.toLocaleString()}<br>`;
          if (items.charitable) summary += `• Charitable Donations: $${items.charitable.toLocaleString()}<br>`;

          if (extractedData.documents && extractedData.documents.length > 0) {
            summary += `<br>📄 Documents uploaded: ${extractedData.documents.length}<br>`;
          }

          summary += '<br><strong>What would you like to do?</strong>';

          addMessage('ai', summary, [
            { label: '✅ Continue with questions', value: 'continue_questioning' },
            { label: getIcon('pencil', 'sm') + ' Make corrections', value: 'make_corrections' },
            { label: getIcon('document-text', 'sm') + ' Upload more documents', value: 'yes_upload' },
            { label: getIcon('chart-bar', 'sm') + ' Generate report', value: 'generate_report' }
          ]);
        }, 800);

      } else if (value === 'make_corrections') {
        addMessage('user', 'I need to make corrections');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `No problem! What would you like to correct?`, [
            { label: getIcon('clipboard-document-list', 'sm') + ' Filing status', value: 'change_filing_status' },
            { label: getIcon('currency-dollar', 'sm') + ' Income amount', value: 'change_income' },
            { label: getIcon('home', 'sm') + ' State', value: 'change_state' },
            { label: '👨‍👩‍👧 Dependents', value: 'change_dependents' },
            { label: getIcon('chat-bubble-left-right', 'sm') + ' Something else', value: 'describe_change' }
          ]);
        }, 500);

      } else if (value === 'change_filing_status') {
        addMessage('user', 'Change my filing status');
        // Clear confirmed status so it can be changed
        confirmedData.fields.delete('tax_profile.filing_status');
        extractedData.tax_profile.filing_status = null;
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `What's your correct filing status?`, [
            { label: 'Single', value: 'filing_single' },
            { label: 'Married Filing Jointly', value: 'filing_married' },
            { label: 'Head of Household', value: 'filing_hoh' },
            { label: 'Married Filing Separately', value: 'filing_mfs' },
            { label: 'Qualifying Surviving Spouse', value: 'filing_qss' }
          ], { inputType: 'radio' });
        }, 500);

      } else if (value === 'change_income') {
        addMessage('user', 'Change my income');
        confirmedData.fields.delete('tax_profile.total_income');
        confirmedData.fields.delete('tax_profile.w2_income');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `What's your correct total annual income?<br><br><input type="number" id="incomeInput" placeholder="Enter amount" style="width: 100%; padding: var(--space-3-5); margin: var(--space-3) 0; background: rgba(255,255,255,0.05); border: 2px solid var(--border); border-radius: var(--radius-lg); color: var(--text); font-size: var(--text-base);" onkeypress="if(event.key==='Enter') captureIncome()"><br><button onclick="captureIncome()" style="padding: var(--space-3) var(--space-8); background: var(--primary); color: white; border: none; border-radius: var(--radius-lg); cursor: pointer; font-weight: var(--font-semibold); margin-top: var(--space-2);">Update Income</button>`);
          setTimeout(() => document.getElementById('incomeInput').focus(), 100);
        }, 500);

      } else if (value === 'change_state') {
        addMessage('user', 'Change my state');
        confirmedData.fields.delete('tax_profile.state');
        extractedData.tax_profile.state = null;
        // Trigger state selection question
        startIntelligentQuestioning();

      } else if (value === 'change_dependents') {
        addMessage('user', 'Change my dependents');
        confirmedData.fields.delete('tax_profile.dependents');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `How many dependents do you have?`, [
            { label: '0', value: 'dependents_0' },
            { label: '1', value: 'dependents_1' },
            { label: '2', value: 'dependents_2' },
            { label: '3+', value: 'dependents_3plus' }
          ]);
        }, 500);

      } else if (value === 'describe_change') {
        addMessage('user', 'I\'ll describe what needs to change');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `Please type what you'd like to change and I'll help you update it.`);
          document.getElementById('userInput').focus();
        }, 500);

      } else if (value === 'continue_to_report') {
        addMessage('user', 'Let\'s move forward with the report');
        updateProgress(85);
        showTyping();
        setTimeout(() => {
          hideTyping();
          const summary = generateSummary();
          addMessage('ai', `<strong>Perfect! Here's what we've covered:</strong><br><br>${summary}<br><br>I can now prepare your comprehensive tax advisory report with personalized recommendations. <strong>Shall we proceed?</strong>`, [
            { label: getIcon('chart-bar', 'sm') + ' Generate my report', value: 'generate_report' },
            { label: getIcon('pencil', 'sm') + ' Make changes first', value: 'review_summary' }
          ]);
        }, 1000);

      } else if (value === 'review_summary') {
        addMessage('user', 'Let me review what we covered');
        showTyping();
        setTimeout(() => {
          hideTyping();
          const summary = generateSummary();
          addMessage('ai', `<strong>Here's a complete summary of your tax profile:</strong><br><br>${summary}<br><br>Would you like to update any of this information or continue to generate your report?`, [
            { label: getIcon('pencil', 'sm') + ' Update filing status', value: 'no_manual' },
            { label: getIcon('pencil', 'sm') + ' Update income/focus', value: 'continue_assessment' },
            { label: '✅ Looks good, continue', value: 'generate_report' }
          ]);
        }, 1000);

      } else if (value === 'ask_question' || value === 'how_it_works') {
        const userMsg = value === 'ask_question' ? 'I have a question' : 'How does this work?';
        addMessage('user', userMsg);

        if (value === 'how_it_works') {
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `<strong>Great question! Here's how our premium tax advisory works:</strong><br><br><strong>1. Understanding Your Situation (5 minutes)</strong><br>I ask targeted questions to understand your financial picture, or you can upload documents for instant analysis.<br><br><strong>2. Comprehensive Analysis</strong><br>I analyze your situation using 2025 IRS rules, identifying every deduction, credit, and strategy available to you.<br><br><strong>3. Personalized Report</strong><br>You receive a detailed advisory report with:<br>• Current tax liability estimate<br>• Potential savings opportunities<br>• Specific action items<br>• Long-term planning strategies<br><br><strong>4. Ongoing Support</strong><br>Access to CPA consultations, filing assistance (if needed), and year-round advisory support.<br><br><strong>Ready to get started with your assessment?</strong>`, [
              { label: '✅ Yes, let\'s begin', value: 'continue_assessment' },
              { label: getIcon('document-text', 'sm') + ' I want to upload docs', value: 'yes_upload' },
              { label: '❓ I have another question', value: 'more_questions' }
            ]);
          }, 1500);
        } else {
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `Of course! I'm here to answer any questions you have about:<br><br>• Tax strategies and optimization<br>• Deductions and credits you may qualify for<br>• Filing requirements and deadlines<br>• How to maximize your refund or minimize taxes owed<br>• Anything else tax-related!<br><br><strong>What would you like to know?</strong> (Feel free to type your question below)`);
            document.getElementById('userInput').focus();
          }, 1000);
        }

      // Error recovery handlers
      } else if (value === 'wait_retry') {
        addMessage('user', 'I\'ll wait and try again');
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `Thanks for your patience! I'm ready to continue now. What would you like to discuss?`, generateSmartQuickActions());
        }, 3000);

      } else if (value === 'retry_analysis') {
        addMessage('user', 'Retry the analysis');
        performTaxCalculation();

      } else if (value === 'reset_conversation') {
        addMessage('user', 'Let\'s start over');
        // Reset session and data
        sessionId = null;
        sessionStorage.removeItem('tax_session_id');
        conversationHistory = [];
        extractedData = {
          filing_status: null,
          income_range: null,
          income_amount: null,
          deductions: [],
          credits: [],
          focus_area: null,
          tax_profile: {},
          documents: [],
          lead_data: { score: 0 }
        };
        // Reset questioning state to allow all questions again
        resetQuestioningState();
        // Reset retry counters
        retryCount = 0;
        updateProgress(0);
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `No problem! Let's start fresh. I'm your AI-powered tax advisor, ready to help you discover strategic opportunities to optimize your tax situation.<br><br><strong>Would you like to upload tax documents for me to analyze, or shall we talk through your situation?</strong>`, [
            { label: getIcon('document-text', 'sm') + ' Upload documents', value: 'yes_upload' },
            { label: getIcon('chat-bubble-left-right', 'sm') + ' Let\'s discuss my situation', value: 'no_manual' },
            { label: '❓ How does this work?', value: 'how_it_works' }
          ]);
        }, 1000);

      } else if (value === 'retry_message') {
        // Track retries to prevent infinite loops
        retryCount++;
        const MAX_RETRIES = 3;

        if (retryCount > MAX_RETRIES) {
          // Too many retries - offer reset as escape route
          addMessage('user', 'I\'ve tried several times...');
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `I'm sorry for the trouble! It seems we're having persistent issues. Let's try a fresh start to get things working properly again.`, [
              { label: getIcon('arrow-path', 'sm') + ' Start fresh', value: 'reset_conversation' },
              { label: getIcon('chat-bubble-left-right', 'sm') + ' Type a new message', value: 'focus_input' },
              { label: getIcon('phone', 'sm') + ' Get human help', value: 'contact_support' }
            ]);
            retryCount = 0; // Reset counter after offering escape
          }, 500);
        } else if (lastUserMessage) {
          // Retry with the last message
          addMessage('user', `Retrying... (attempt ${retryCount} of ${MAX_RETRIES})`);
          await processAIResponse(lastUserMessage);
        } else {
          // No previous message to retry
          addMessage('user', 'Let me try again');
          showTyping();
          setTimeout(() => {
            hideTyping();
            addMessage('ai', `I'm ready when you are! What would you like to discuss?`, generateSmartQuickActions());
            document.getElementById('userInput').focus();
            retryCount = 0; // Reset since we're starting fresh
          }, 500);
        }

      } else {
        // For any other actions not handled, use AI processing
        const displayText = value.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        addMessage('user', displayText);
        await processAIResponse(value);
      }
    }

    // Helper function to continue from focus-specific questions to deductions
    function continueToDeductionsFromFocus() {
      updateProgress(60);
      showTyping();
      setTimeout(() => {
        hideTyping();
        addMessage('ai', `I've gathered some valuable information about your situation. Now let's explore any additional deductions you might have.<br><br><strong>Do you have any of these common deductions?</strong>`, [
          { label: getIcon('home', 'sm') + ' Mortgage Interest', value: 'deduct_mortgage' },
          { label: getIcon('currency-dollar', 'sm') + ' Charitable Donations', value: 'deduct_charity' },
          { label: '🏥 Medical Expenses', value: 'deduct_medical' },
          { label: getIcon('briefcase', 'sm') + ' Business Expenses', value: 'deduct_business' },
          { label: getIcon('arrow-right', 'sm') + ' Continue to Credits', value: 'deduct_skip' }
        ]);
      }, 1200);
    }

    // Helper function to generate summary
    function generateSummary() {
      let summary = '';

      if (extractedData.filing_status) {
        summary += `📋 <strong>Filing Status:</strong> ${extractedData.filing_status}<br>`;
      }
      if (extractedData.income_range) {
        summary += `💰 <strong>Income Range:</strong> ${extractedData.income_range}<br>`;
      }
      if (extractedData.focus_area) {
        summary += `🎯 <strong>Focus Area:</strong> ${extractedData.focus_area}<br>`;
      }
      if (extractedData.deductions && extractedData.deductions.length > 0) {
        summary += `📊 <strong>Deductions:</strong> ${extractedData.deductions.join(', ')}<br>`;
      }
      if (extractedData.credits && extractedData.credits.length > 0) {
        summary += `⭐ <strong>Credits:</strong> ${extractedData.credits.join(', ')}<br>`;
      }

      return summary || 'Your comprehensive tax profile';
    }

    // Helper function to generate and download report
    async function generateAndDownloadReport() {
      try {
        addMessage('ai', '⏳ Generating your PDF report...');

        // Call the advisory report API
        // SECURITY: Use secureFetch for CSRF protection
        const response = await secureFetch('/api/v1/advisory-reports/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            report_type: 'full_analysis',
            include_entity_comparison: true,
            include_multi_year: true,
            years_ahead: 3,
            generate_pdf: true
          })
        });

        if (response.ok) {
          const data = await response.json();

          // Poll for PDF completion
          let pdfReady = false;
          let attempts = 0;
          while (!pdfReady && attempts < 30) {
            await new Promise(resolve => setTimeout(resolve, 1000));
            const statusResponse = await fetch(`/api/v1/advisory-reports/${data.report_id}`);
            const statusData = await statusResponse.json();
            if (statusData.pdf_available) {
              pdfReady = true;
              // Download the PDF
              window.open(`/api/v1/advisory-reports/${data.report_id}/pdf`, '_blank');
              addMessage('ai', `${getIcon('check-circle', 'sm')} <strong>Your report is ready!</strong><br><br>The PDF download should begin automatically. If not, <a href="/api/v1/advisory-reports/${data.report_id}/pdf" target="_blank" style="color: var(--primary);">click here to download</a>.`);
            }
            attempts++;
          }
        } else {
          throw new Error('Failed to generate report');
        }
      } catch (error) {
        DevLogger.error('Report generation error:', error);
        addMessage('ai', `I encountered an issue generating the PDF. However, you can still <a href="/advisory-report-preview?session_id=${sessionId}" target="_blank" style="color: var(--primary);">view your report online here</a>.`);
      }
    }

    // Helper function to send report via email
    async function sendReportEmail() {
      const email = document.getElementById('emailInput').value;
      if (!email || !email.includes('@')) {
        showToast('Please enter a valid email address', 'warning');
        return;
      }

      addMessage('user', `Send to: ${email}`);
      showTyping();

      try {
        const response = await fetch('/api/advisor/report/email', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(window.csrfToken ? {'X-CSRF-Token': window.csrfToken} : {})
          },
          body: JSON.stringify({
            session_id: sessionId,
            email: email
          })
        });

        hideTyping();

        if (response.ok) {
          addMessage('ai', `<strong>Report sent!</strong><br><br>Your tax advisory report has been emailed to <strong>${email}</strong>. Please check your inbox (and spam folder).<br><br><strong>What would you like to do next?</strong>`, [
            { label: getIcon('arrow-down-tray', 'sm') + ' Also download PDF', value: 'download_report' },
            { label: getIcon('phone', 'sm') + ' Schedule consultation', value: 'schedule_consult' },
            { label: '✅ I\'m all set', value: 'finish_satisfied' }
          ]);
        } else {
          // Email service not available — offer PDF download instead
          addMessage('ai', `<strong>Email delivery is not available at this time.</strong><br><br>You can download your report as a PDF instead — it contains all the same information.<br><br><strong>What would you like to do?</strong>`, [
            { label: getIcon('arrow-down-tray', 'sm') + ' Download PDF Report', value: 'download_report' },
            { label: getIcon('phone', 'sm') + ' Schedule consultation', value: 'schedule_consult' }
          ]);
        }
      } catch (error) {
        hideTyping();
        console.error('Email send failed:', error);
        addMessage('ai', `<strong>Unable to send email right now.</strong><br><br>Please download the PDF report instead. You can then email it manually or share it with your CPA.`, [
          { label: getIcon('arrow-down-tray', 'sm') + ' Download PDF Report', value: 'download_report' },
          { label: getIcon('arrow-path', 'sm') + ' Try Again', value: 'email_report' }
        ]);
      }
    }

    // Retry helper with exponential backoff
    async function fetchWithRetry(url, options, maxRetries = 3) {
      let lastError;

      for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout

          const response = await fetch(url, {
            ...options,
            signal: controller.signal
          });

          clearTimeout(timeoutId);

          // Don't retry on client errors (4xx) except 408 (timeout) and 429 (rate limit)
          if (response.status >= 400 && response.status < 500 &&
              response.status !== 408 && response.status !== 429) {
            return response;
          }

          // Retry on server errors (5xx) or specific client errors
          if (!response.ok && attempt < maxRetries) {
            const delay = Math.min(1000 * Math.pow(2, attempt - 1), 8000); // Max 8s delay
            DevLogger.log(`Retry attempt ${attempt} after ${delay}ms`);
            await new Promise(resolve => setTimeout(resolve, delay));
            continue;
          }

          return response;
        } catch (error) {
          lastError = error;

          // Don't retry on abort errors
          if (error.name === 'AbortError') {
            throw new Error('Request timeout - please try again');
          }

          // Retry on network errors
          if (attempt < maxRetries) {
            const delay = Math.min(1000 * Math.pow(2, attempt - 1), 8000);
            DevLogger.log(`Network error, retry attempt ${attempt} after ${delay}ms`);
            await new Promise(resolve => setTimeout(resolve, delay));
            continue;
          }
        }
      }

      throw lastError || new Error('Request failed after retries');
    }

    // Store last message for retry
    let lastUserMessage = null;

    async function processAIResponse(userMessage) {
      isProcessing = true;
      lastUserMessage = userMessage; // Store for retry
      showTyping();

      // Create session if not already created, or upgrade temp session
      const isTemporarySession = sessionId && sessionId.startsWith('temp-');
      if (!sessionId || isTemporarySession) {
        try {
          const sessionResponse = await fetchWithRetry('/api/sessions/create-session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              workflow_type: 'intelligent_conversational',
              tax_year: 2025
            })
          }, 2); // 2 retries for session creation

          if (!sessionResponse.ok) {
            // If session creation fails, generate a temporary client-side ID
            // DON'T store temp IDs in sessionStorage - they shouldn't persist
            sessionId = 'temp-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
            DevLogger.warn('Using temporary session ID (will retry on next message):', sessionId);
          } else {
            const sessionData = await sessionResponse.json();
            const oldSessionId = sessionId;
            sessionId = sessionData.session_id;
            // Only store real session IDs
            sessionStorage.setItem('tax_session_id', sessionId);
            if (oldSessionId && oldSessionId.startsWith('temp-')) {
              DevLogger.log('Upgraded from temporary session to real session:', sessionId);
            }
          }
        } catch (error) {
          DevLogger.error('Failed to create session:', error);
          // Generate temporary client-side session ID as fallback
          // DON'T persist temp sessions - they will be retried on next message
          sessionId = 'temp-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
          DevLogger.warn('Using temporary session ID (will retry on next message):', sessionId);
        }
      }

      // Use the intelligent advisor API for dynamic NLU parsing
      try {
        // Build profile from extracted data for the advisor API
        const statusMap = {
          'Single': 'single',
          'Married Filing Jointly': 'married_joint',
          'Head of Household': 'head_of_household',
          'Married Filing Separately': 'married_separate',
          'Qualifying Surviving Spouse': 'qualifying_widow'
        };

        const profile = {
          filing_status: statusMap[extractedData.tax_profile.filing_status] || extractedData.tax_profile.filing_status || null,
          total_income: extractedData.tax_profile.total_income || null,
          w2_income: extractedData.tax_profile.w2_income || null,
          business_income: extractedData.tax_profile.business_income || null,
          investment_income: extractedData.tax_profile.investment_income || null,
          rental_income: extractedData.tax_profile.rental_income || null,
          dependents: extractedData.tax_profile.dependents || null,
          state: extractedData.tax_profile.state || null,
          mortgage_interest: extractedData.tax_items.mortgage_interest || null,
          charitable_donations: extractedData.tax_items.charitable || null,
          is_self_employed: (extractedData.tax_profile.business_income || 0) > 0
        };

        const response = await fetchWithRetry('/api/advisor/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            message: userMessage,
            profile: profile.filing_status || profile.total_income ? profile : null,
            conversation_history: conversationHistory.slice(-10) // Last 10 messages for context
          })
        }, 3); // 3 retries with exponential backoff

        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();
        hideTyping();
        retryCount = 0; // Reset retry counter on successful response

        // Validate response data
        if (!data || typeof data !== 'object') {
          DevLogger.error('Invalid API response:', data);
          throw new Error('Received invalid response from server');
        }

        // Only add to history if we have actual content
        const responseContent = data.response || '';
        if (responseContent.trim()) {
          conversationHistory.push(
            { role: 'user', content: userMessage },
            { role: 'assistant', content: responseContent }
          );
        } else {
          // Just add user message if response was empty
          conversationHistory.push({ role: 'user', content: userMessage });
          DevLogger.warn('Received empty response from API');
        }

        // Update local extracted data based on API response
        // The API parses the message and updates the profile server-side
        // We sync some key fields back to client
        if (data.profile_completeness > 0) {
          // If API returned tax calculation, update our local data
          if (data.tax_calculation) {
            taxCalculations = data.tax_calculation;
          }
          if (data.strategies && data.strategies.length > 0) {
            taxStrategies = data.strategies;
            extractedData.lead_data.estimated_savings = taxStrategies.reduce((sum, s) => sum + (s.estimated_savings || 0), 0);
          }
          if (data.lead_score) {
            extractedData.lead_data.score = data.lead_score;
          }
          DevLogger.log('API updated profile, completeness:', data.profile_completeness);
          markUnsaved(); // Trigger auto-save
        }

        // Show AI response with quick actions from API
        let aiResponse = data.response || "I'm here to help. Could you please clarify?";
        const quickActions = data.quick_actions || generateSmartQuickActions();

        // Add confidence badge for calculation/strategy/report responses
        if (data.response_type === 'calculation' || data.response_type === 'strategy' || data.response_type === 'report') {
          aiResponse += renderConfidenceBadge(data.response_confidence, data.confidence_reason);
        }

        addMessage('ai', aiResponse, quickActions);

        // Update side panel with API insights
        if (data.profile_completeness !== undefined) {
          updateProgress(Math.round(data.profile_completeness * 100));
        }

        // Also update phase based on local extracted data
        updatePhaseFromData();

        if (data.key_insights && data.key_insights.length > 0) {
          updateInsights(data.key_insights);
        }
        if (data.warnings && data.warnings.length > 0) {
          data.warnings.forEach(w => DevLogger.warn('Tax warning:', w));
        }

        // Save session data for recovery
        saveSessionData();

        // Update savings estimate based on new data
        updateSavingsEstimate();

        // Update live savings display
        if (data.total_potential_savings) {
          LiveSavingsDisplay.update(data.total_potential_savings);
        }

        // Check for celebration triggers
        checkForCelebration(data);

      } catch (error) {
        hideTyping();
        DevLogger.error('AI response error:', error);

        // Handle specific error types
        let errorMessage = '';
        let quickActions = generateSmartQuickActions();

        if (error.message && error.message.includes('429')) {
          // Rate limit exceeded
          errorMessage = "I'm getting a lot of requests right now. Please wait a moment before sending another message.";
          quickActions = [
            { label: 'Wait 30 seconds', value: 'wait_retry' },
            { label: 'Start over', value: 'reset_conversation' }
          ];
        } else if (error.message && error.message.includes('404')) {
          // Session not found - full reset to prevent stale data confusion
          sessionId = null;
          sessionStorage.removeItem('tax_session_id');
          conversationHistory = []; // Clear old history to prevent context confusion
          resetQuestioningState(); // Reset questioning flow
          retryCount = 0;
          // Note: We preserve extractedData since that's the user's actual tax data
          errorMessage = "Your session expired. I've preserved your tax data, but let's start our conversation fresh. How can I help you?";
          quickActions = [
            { label: getIcon('chat-bubble-left-right', 'sm') + ' Continue with my data', value: 'no_manual' },
            { label: getIcon('arrow-path', 'sm') + ' Start completely fresh', value: 'reset_conversation' }
          ];
        } else if (error.message && error.message.includes('504') || error.message && error.message.includes('timeout')) {
          // Timeout - suggest rephrasing
          errorMessage = "That's taking longer than expected. Could you try rephrasing your question or asking something simpler?";
        } else if (!navigator.onLine) {
          // Offline
          errorMessage = "It looks like you're offline. Please check your internet connection and try again.";
          quickActions = [
            { label: 'Try again', value: 'retry_message' }
          ];
        } else {
          // Generic fallback
          errorMessage = generateIntelligentFallback(userMessage);
        }

        addMessage('ai', errorMessage, quickActions);
      } finally {
        // Always reset processing flag
        isProcessing = false;
      }
    }

    // Build system context for AI to understand conversation state
    function buildSystemContext() {
      const progress = getCurrentProgress();
      const confidence = getConfidenceLevel();

      let context = {
        role: 'system',
        content: `You are a premium CPA tax advisor AI assistant specializing in individual tax advisory. You're having a warm, professional conversation with a client.

⚠️ CRITICAL AI DISCLOSURE REQUIREMENTS:
- You are an AI assistant, NOT a licensed CPA or tax professional
- Your responses are ESTIMATES and GENERAL GUIDANCE, not professional tax advice
- Users should ALWAYS verify information with a licensed tax professional before making decisions
- Include relevant IRS publication/form references when giving specific tax guidance

CRITICAL: All tax advice, limits, deductions, and credits must follow 2025 IRS rules and regulations. Use only 2025 tax year information.

Tax Year: 2025
Data Confidence: ${confidence.level} (${confidence.percentage}% complete)
Current conversation state:
- Progress: ${progress}%
- Filing Status: ${extractedData.filing_status || 'Not yet provided'}
- Income Range: ${extractedData.income_range || 'Not yet provided'}
- Focus Area: ${extractedData.focus_area || 'Not yet determined'}
- Deductions: ${extractedData.deductions ? extractedData.deductions.join(', ') : 'None captured yet'}
- Credits: ${extractedData.credits ? extractedData.credits.join(', ') : 'None captured yet'}

2025 IRS Key Information (cite these sources):
- Standard Deduction Single: $15,000 (IRS Rev. Proc. 2024-40)
- Standard Deduction MFJ: $30,000 (IRS Rev. Proc. 2024-40)
- Standard Deduction HOH: $22,500 (IRS Rev. Proc. 2024-40)
- Child Tax Credit: $2,000/child (IRC §24, Form 8812)
- 401(k) Limit: $23,500 / $31,000 catch-up (IRS Notice 2024-80)
- IRA Limit: $7,000 / $8,000 catch-up (IRS Notice 2024-80)
- EITC Max: $7,830 (3+ children) (IRS Rev. Proc. 2024-40)
- SALT Deduction Cap: $10,000 (IRC §164(b)(6))

IRS SOURCE CITATION GUIDELINES:
When discussing specific tax topics, reference relevant IRS resources:
- Deductions: "See IRS Publication 17, Chapter [X]"
- Credits: "See Form [number] instructions"
- Filing Status: "See IRS Publication 501"
- Self-Employment: "See Schedule SE and IRS Publication 334"
- Home Office: "See IRS Publication 587"
- Retirement: "See IRS Publication 590-A/B"

RESPONSE GUIDELINES:
1. Maintain a warm, experienced advisor tone
2. This is INDIVIDUAL tax advisory - emphasize strategic planning
3. ALWAYS use 2025 IRS rules with source citations when specific
4. If data confidence is LOW, emphasize this is general guidance only
5. Extract tax-relevant information and suggest clarifying questions
6. If the user asks off-topic questions, answer briefly then redirect
7. Always recommend consulting a licensed CPA for final decisions
8. Be helpful, patient, and professional

If you need more information to provide good advice, ask specific questions.
If they're ready to move forward, suggest generating their comprehensive advisory report.`
      };

      return context;
    }

    // Generate smart quick actions based on current state
    function generateSmartQuickActions() {
      const progress = getCurrentProgress();

      if (progress < 20) {
        return [
          { label: getIcon('chat-bubble-left-right', 'sm') + ' Tell you my situation', value: 'no_manual' },
          { label: getIcon('document-text', 'sm') + ' Upload documents', value: 'yes_upload' },
          { label: '❓ How does this work?', value: 'how_it_works' }
        ];
      } else if (progress < 50) {
        return [
          { label: getIcon('chart-bar', 'sm') + ' Continue the assessment', value: 'continue_assessment' },
          { label: '❓ I have a question', value: 'ask_question' },
          { label: getIcon('document-text', 'sm') + ' Add documents', value: 'add_documents' }
        ];
      } else if (progress < 90) {
        return [
          { label: '✅ Continue to report', value: 'continue_to_report' },
          { label: getIcon('chat-bubble-left-right', 'sm') + ' Ask something else', value: 'ask_question' },
          { label: getIcon('clipboard-document-list', 'sm') + ' Review what we covered', value: 'review_summary' }
        ];
      } else {
        return [
          { label: getIcon('chart-bar', 'sm') + ' Generate my report', value: 'generate_report' },
          { label: getIcon('phone', 'sm') + ' Schedule consultation', value: 'schedule_consult' },
          { label: getIcon('chat-bubble-left-right', 'sm') + ' I have questions', value: 'more_questions' }
        ];
      }
    }

    // Generate intelligent fallback response
    function generateIntelligentFallback(userMessage) {
      const lowerMessage = userMessage.toLowerCase();

      // Check for common tax questions
      if (lowerMessage.includes('deduction') || lowerMessage.includes('deduct')) {
        return `Great question about deductions! Deductions reduce your taxable income. Common ones include:<br><br>• Mortgage interest<br>• Charitable donations<br>• State and local taxes<br>• Medical expenses (if over 7.5% of income)<br>• Business expenses<br><br>To provide specific guidance for your situation, I need to know a bit more about you. <strong>What's your filing status?</strong>`;
      }

      if (lowerMessage.includes('credit')) {
        return `Tax credits are even better than deductions - they reduce your tax bill dollar-for-dollar! Common credits include:<br><br>• Child Tax Credit<br>• Earned Income Credit<br>• Education credits<br>• Energy efficiency credits<br><br>Let me learn more about your situation so I can identify which credits you qualify for. <strong>Shall we continue with your assessment?</strong>`;
      }

      if (lowerMessage.includes('save') || lowerMessage.includes('savings')) {
        return `I love that you're focused on savings! The amount you can save depends on your specific situation. On average, strategic tax planning saves our clients $2,000-$15,000 annually.<br><br>To calculate your potential savings, I need to understand your:<br>• Income level<br>• Filing status<br>• Current deductions and credits<br>• Financial goals<br><br><strong>Would you like to complete a quick assessment so I can estimate your savings?</strong>`;
      }

      if (lowerMessage.includes('cost') || lowerMessage.includes('price') || lowerMessage.includes('fee')) {
        return `Our individual tax advisory service is complimentary for the initial assessment. We'll provide you with a comprehensive analysis and recommendations at no cost.<br><br>If you'd like ongoing advisory support or assistance with tax filing, we'll discuss those services after your initial report.<br><br><strong>Would you like to continue with your free tax assessment?</strong>`;
      }

      // Handle confused or frustrated users
      if (lowerMessage.includes('confused') || lowerMessage.includes('don\'t understand') || lowerMessage.includes('help')) {
        return `I'm sorry for any confusion! Let me make this simpler.<br><br>I'm here to help you save money on your taxes. All you need to do is answer a few quick questions about your situation, and I'll provide personalized recommendations.<br><br><strong>Would you like to start with something simple? What's your filing status?</strong>`;
      }

      // Handle exit intent
      if (lowerMessage.includes('quit') || lowerMessage.includes('exit') || lowerMessage.includes('stop') || lowerMessage.includes('bye')) {
        return `I understand! Before you go, know that your progress has been saved. You can come back anytime to continue your tax assessment.<br><br>Is there anything specific I can help you with quickly before you go?`;
      }

      // Handle off-topic or personal questions
      if (lowerMessage.includes('who are you') || lowerMessage.includes('what are you') || lowerMessage.includes('your name')) {
        return `I'm your AI-powered tax advisor! I specialize in helping individuals optimize their tax situation.<br><br>I can analyze your income, deductions, and credits to find opportunities to save money on your taxes. <strong>Would you like to get started with a quick assessment?</strong>`;
      }

      // Handle vague income statements
      if (lowerMessage.includes('make good money') || lowerMessage.includes('decent salary') || lowerMessage.includes('earn a lot')) {
        return `That's great! To provide accurate tax advice, I'll need a more specific income range. This helps me identify the right deductions and credits for your situation.<br><br><strong>What's your approximate annual income?</strong>`;
      }

      // Generic helpful response
      return `I appreciate your question! While I'm here primarily to help with your tax advisory needs, I want to make sure I address your concern properly.<br><br>To give you the most accurate guidance, let me learn more about your tax situation. This will help me provide personalized recommendations that could save you thousands of dollars.<br><br><strong>Would you like to continue with your tax assessment, or do you have other specific questions?</strong>`;
    }

    // Get current progress percentage
    function getCurrentProgress() {
      const progressFill = document.getElementById('progressFill');
      if (progressFill) {
        const width = progressFill.style.width;
        return parseInt(width) || 0;
      }
      return 0;
    }

    function updateProgress(percentage) {
      const progressFill = document.getElementById('progressFill');
      const progressText = document.getElementById('progressText');
      if (progressFill) progressFill.style.width = percentage + '%';
      if (progressText) progressText.textContent = `${Math.round(percentage)}% Complete`;

      // Auto-update journey stepper based on percentage
      const stepNumber = percentage < 25 ? 1 : percentage < 50 ? 2 : percentage < 75 ? 3 : 4;
      updateActiveStep(stepNumber);
    }

    // Phase mapping from backend to UI
    const PHASE_MAPPING = {
      'personal_info': { step: 1, label: 'Profile Setup', icon: '📋' },
      'income': { step: 2, label: 'Income Review', icon: '💰' },
      'deductions': { step: 3, label: 'Deductions & Credits', icon: '🎯' },
      'review': { step: 4, label: 'Final Review', icon: '📊' },
      'ready_to_file': { step: 4, label: 'Ready to File!', icon: '✅' }
    };

    // Update progress indicator with full progress data from backend
    function updateProgressIndicator(progressUpdate) {
      if (!progressUpdate) return;

      // Update percentage bar
      const percentage = (progressUpdate.current_step / progressUpdate.total_steps) * 100;
      const progressFill = document.getElementById('progressFill');
      const progressText = document.getElementById('progressText');
      if (progressFill) progressFill.style.width = percentage + '%';
      if (progressText) progressText.textContent = `${Math.round(percentage)}% Complete`;

      // Update phase label
      updatePhaseLabel(progressUpdate.phase_name);

      // Map backend steps (0-4) to UI steps (1-4)
      const uiStep = Math.min(Math.max(progressUpdate.current_step + 1, 1), 4);
      updateActiveStep(uiStep);
    }

    // Update the journey stepper to show active/completed steps
    function updateActiveStep(stepNumber) {
      const steps = document.querySelectorAll('.journey-step');
      steps.forEach((step, index) => {
        const stepNum = index + 1;
        step.classList.remove('active', 'completed');

        if (stepNum === stepNumber) {
          step.classList.add('active');
        } else if (stepNum < stepNumber) {
          step.classList.add('completed');
        }
      });
    }

    // Update the phase label text
    function updatePhaseLabel(phaseName) {
      const label = document.getElementById('currentPhaseLabel');
      if (label && phaseName) {
        label.textContent = phaseName;

        // Add completed class if we're at the end
        if (phaseName.toLowerCase().includes('ready') || phaseName.toLowerCase().includes('complete')) {
          label.classList.add('completed');
        } else {
          label.classList.remove('completed');
        }
      }
    }

    // Update phase based on extracted data (for local tracking)
    function updatePhaseFromData() {
      let phase = 'personal_info';

      if (extractedData.first_name || extractedData.filing_status) {
        phase = 'income';
        if (extractedData.income_explored || extractedData.w2_wages || extractedData.has_w2) {
          phase = 'deductions';
          if (extractedData.deductions_explored || extractedData.itemize_choice) {
            phase = 'review';
            if (extractedData.review_confirmed) {
              phase = 'ready_to_file';
            }
          }
        }
      }

      const phaseInfo = PHASE_MAPPING[phase];
      if (phaseInfo) {
        updatePhaseLabel(phaseInfo.label);
        updateActiveStep(phaseInfo.step);
      }
    }

    // ============================================
    // AUTO-SAVE & SESSION RESTORE
    // ============================================

    let autoSaveTimer = null;
    let lastSaveTime = null;
    let hasUnsavedChanges = false;
    const AUTO_SAVE_INTERVAL = 30000; // 30 seconds

    // Save session progress to server
    async function saveSessionProgress() {
      if (!sessionId || sessionId.startsWith('temp-')) {
        DevLogger.log('Skipping save - no valid session ID');
        return;
      }

      try {
        // SECURITY: Use secureFetch for CSRF protection
        const response = await secureFetch(`/api/sessions/${sessionId}/save`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            extracted_data: extractedData,
            conversation_history: conversationHistory.slice(-30), // Last 30 messages
            current_phase: getCurrentPhase(),
            completion_percentage: getCompletionPercentage()
          })
        });

        if (response.ok) {
          lastSaveTime = new Date();
          hasUnsavedChanges = false;
          updateSaveIndicator('saved');
          DevLogger.log('Session saved at:', lastSaveTime.toISOString());
        } else {
          DevLogger.warn('Save failed:', response.status);
          updateSaveIndicator('error');
        }
      } catch (error) {
        DevLogger.error('Auto-save error:', error);
        updateSaveIndicator('error');
      }
    }

    // Get current phase for saving
    function getCurrentPhase() {
      if (extractedData.review_confirmed) return 'ready_to_file';
      if (extractedData.deductions_explored || extractedData.itemize_choice) return 'review';
      if (extractedData.income_explored || extractedData.w2_wages) return 'deductions';
      if (extractedData.first_name || extractedData.filing_status) return 'income';
      return 'personal_info';
    }

    // Get completion percentage for saving
    function getCompletionPercentage() {
      const progressFill = document.getElementById('progressFill');
      if (progressFill) {
        const width = progressFill.style.width;
        return parseFloat(width) || 0;
      }
      return 0;
    }

    // Update save indicator in UI
    function updateSaveIndicator(status) {
      let indicator = document.getElementById('saveIndicator');
      if (!indicator) {
        // Create indicator if it doesn't exist
        indicator = document.createElement('div');
        indicator.id = 'saveIndicator';
        indicator.className = 'save-indicator';
        const progressText = document.getElementById('progressText');
        if (progressText && progressText.parentNode) {
          progressText.parentNode.insertBefore(indicator, progressText.nextSibling);
        }
      }

      if (status === 'saved') {
        indicator.innerHTML = '<span style="color: #276749;">✓ Saved</span>';
        indicator.style.opacity = '1';
        setTimeout(() => { indicator.style.opacity = '0.5'; }, 2000);
      } else if (status === 'saving') {
        indicator.innerHTML = '<span style="color: #718096;">Saving...</span>';
        indicator.style.opacity = '1';
      } else if (status === 'error') {
        indicator.innerHTML = '<span style="color: #c53030;">Save failed</span>';
        indicator.style.opacity = '1';
      }
    }

    // Start auto-save timer
    function startAutoSave() {
      if (autoSaveTimer) clearInterval(autoSaveTimer);
      autoSaveTimer = setInterval(() => {
        if (hasUnsavedChanges && sessionId) {
          updateSaveIndicator('saving');
          saveSessionProgress();
        }
      }, AUTO_SAVE_INTERVAL);
      DevLogger.log('Auto-save started');
    }

    // Stop auto-save timer
    function stopAutoSave() {
      if (autoSaveTimer) {
        clearInterval(autoSaveTimer);
        autoSaveTimer = null;
      }
    }

    // Mark session as having unsaved changes
    function markUnsaved() {
      hasUnsavedChanges = true;
    }

    // Check for existing session and offer to restore
    async function checkForExistingSession() {
      const savedSessionId = sessionStorage.getItem('tax_session_id');
      if (!savedSessionId || savedSessionId.startsWith('temp-')) {
        return null;
      }

      try {
        const response = await fetch(`/api/sessions/${savedSessionId}/restore`);
        if (response.ok) {
          const data = await response.json();
          if (data.success && (data.extracted_data && Object.keys(data.extracted_data).length > 0)) {
            return data;
          }
        }
      } catch (error) {
        DevLogger.log('No existing session to restore');
      }
      return null;
    }

    // Show resume banner
    function showResumeBanner(sessionData) {
      const banner = document.createElement('div');
      banner.id = 'resumeBanner';
      banner.className = 'resume-banner';
      banner.innerHTML = `
        <div class="resume-content">
          <div class="resume-icon">📋</div>
          <div class="resume-text">
            <strong>Welcome back!</strong>
            <span>You have a saved session (${Math.round(sessionData.completion_percentage || 0)}% complete). Would you like to continue?</span>
          </div>
          <div class="resume-actions">
            <button class="resume-btn primary" onclick="restoreSession()">Continue</button>
            <button class="resume-btn secondary" onclick="dismissResumeBanner(true)">Start Fresh</button>
          </div>
        </div>
      `;

      // Add to page
      const container = document.querySelector('.chat-container');
      if (container) {
        container.insertBefore(banner, container.firstChild);
      }

      // Store session data for restoration
      window._pendingRestore = sessionData;
    }

    // Restore session from saved data
    async function restoreSession() {
      const sessionData = window._pendingRestore;
      if (!sessionData) return;

      // CRITICAL: Reset questioning state before restore
      // This ensures the flow can ask questions appropriate to the restored data state
      resetQuestioningState();
      retryCount = 0;
      confirmedData.clear(); // Clear confirmed data tracking for fresh restore

      // Restore extracted data using safe merge
      if (sessionData.extracted_data) {
        await updateExtractedDataSafe(sessionData.extracted_data, 'session_restore');
      }

      // Restore conversation history
      if (sessionData.conversation_history && sessionData.conversation_history.length > 0) {
        conversationHistory = sessionData.conversation_history;

        // Restore messages to UI
        const messagesContainer = document.getElementById('messages');
        if (messagesContainer) {
          // Clear initial message
          messagesContainer.innerHTML = '';

          // Add restored messages
          conversationHistory.forEach(msg => {
            if (msg.role === 'user') {
              addMessage('user', msg.content, []);
            } else if (msg.role === 'assistant' || msg.role === 'ai') {
              addMessage('ai', msg.content, []);
            }
          });
        }
      }

      // Restore progress
      if (sessionData.completion_percentage) {
        updateProgress(sessionData.completion_percentage);
      }

      // Update phase
      updatePhaseFromData();

      // Dismiss banner
      dismissResumeBanner();

      // Add welcome back message
      addMessage('ai', `Welcome back! I've restored your previous session. You were ${Math.round(sessionData.completion_percentage || 0)}% complete. Let's continue where you left off.`, [
        { label: 'Continue', value: 'continue_flow' },
        { label: 'Review my info', value: 'review_data' }
      ]);

      DevLogger.log('Session restored:', sessionId);
    }

    // Dismiss resume banner and start fresh
    function dismissResumeBanner(startFresh = false) {
      const banner = document.getElementById('resumeBanner');
      if (banner) {
        banner.style.animation = 'slideUp 0.3s ease forwards';
        setTimeout(() => banner.remove(), 300);
      }
      window._pendingRestore = null;

      // If starting fresh, ensure clean state
      if (startFresh) {
        resetQuestioningState();
        retryCount = 0;
        confirmedData.clear();
        // Clear old session from storage so it doesn't keep prompting
        sessionStorage.removeItem('tax_session_id');
        sessionId = null;
      }
    }

    // Save before page unload
    window.addEventListener('beforeunload', (event) => {
      if (hasUnsavedChanges && sessionId && !sessionId.startsWith('temp-')) {
        // Attempt sync save (must use Blob with correct Content-Type for FastAPI)
        const saveData = JSON.stringify({
          extracted_data: extractedData,
          conversation_history: conversationHistory.slice(-30),
          current_phase: getCurrentPhase(),
          completion_percentage: getCompletionPercentage()
        });
        navigator.sendBeacon(
          `/api/sessions/${sessionId}/save`,
          new Blob([saveData], { type: 'application/json' })
        );
      }
    });

    // Expose functions globally
    window.restoreSession = restoreSession;
    window.dismissResumeBanner = dismissResumeBanner;

    function updateInsights(insights) {
      const container = document.getElementById('insights');
      if (insights.length === 0) return;

      container.innerHTML = insights.map(insight => `
        <div class="insight-card">
          <div class="insight-header">
            <span>${insight.icon}</span>
            <span>${insight.title}</span>
          </div>
          <div style="font-size: var(--text-xs-plus); color: var(--text-secondary);">
            ${insight.text}
          </div>
        </div>
      `).join('');
    }

    function updateStats(summary) {
      const grid = document.getElementById('statsGrid');
      const stats = [];

      if (summary.filing_status) stats.push({ label: 'Filing Status', value: summary.filing_status });
      if (summary.total_income) stats.push({ label: 'Income', value: '$' + summary.total_income.toLocaleString() });
      if (summary.deductions_count) stats.push({ label: 'Deductions', value: summary.deductions_count });

      if (stats.length > 0) {
        grid.innerHTML = stats.map(stat => `
          <div class="stat-item">
            <span class="stat-label">${stat.label}</span>
            <span class="stat-value">${stat.value}</span>
          </div>
        `).join('');
      }
    }

    async function handleFileSelect(event) {
      const files = event.target.files;
      if (files.length === 0) return;

      for (const file of files) {
        addMessage('user', `Uploading: ${file.name}`);
        await uploadFileToAI(file);
      }
    }

    async function uploadFileToAI(file) {
      showTyping();

      const formData = new FormData();
      formData.append('file', file);
      formData.append('session_id', sessionId);

      try {
        // SECURITY: Use secureFetch for CSRF protection
        const response = await secureFetch('/api/ai-chat/analyze-document', {
          method: 'POST',
          body: formData
        });

        const data = await response.json();
        hideTyping();

        addMessage('ai', data.ai_response, data.quick_actions || []);

        if (data.extracted_data) {
          // Use safe merge to prevent overwriting confirmed data
          await updateExtractedDataSafe(data.extracted_data, 'document_upload');
        }

        // Update progress
        updateProgress(data.completion_percentage || 0);
        updateStats(data.extracted_summary || {});

        // Update phase based on new extracted data
        updatePhaseFromData();

        // INTEGRATION: Continue questioning flow after document upload
        // Only if we have enough data and didn't already show quick actions
        const hasBasicData = extractedData.tax_profile.filing_status ||
                            extractedData.tax_profile.total_income ||
                            (data.extracted_data && Object.keys(data.extracted_data).length > 2);

        if (hasBasicData && (!data.quick_actions || data.quick_actions.length === 0)) {
          // Offer Express Mode completion after document upload
          setTimeout(() => {
            // Check what's missing and offer targeted follow-up
            const missingFields = [];
            if (!extractedData.tax_profile.filing_status) missingFields.push('filing_status');
            if (!extractedData.tax_profile.state) missingFields.push('state');
            if (!extractedData.tax_profile.dependents && extractedData.tax_profile.dependents !== 0) missingFields.push('dependents');

            const incomeDisplay = extractedData.tax_profile.total_income
              ? `<div style="background: rgba(76, 175, 80, 0.15); padding: var(--space-3); border-radius: var(--radius-lg); margin: var(--space-3) 0;">
                  <span style="color: var(--accent-light);">✓ Income detected:</span>
                  <strong>$${extractedData.tax_profile.total_income.toLocaleString()}</strong>
                </div>`
              : '';

            if (missingFields.length > 0) {
              // Ask the first missing question in Express style
              if (!extractedData.tax_profile.filing_status) {
                addMessage('ai', `<div style="font-size: var(--text-lg); font-weight: var(--font-semibold); margin-bottom: var(--space-3);">📋 Document Analyzed!</div>
                ${incomeDisplay}
                <div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
                  <span style="background: var(--primary); color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-xl); font-size: var(--text-2xs);">Quick Question 1 of ${missingFields.length}</span>
                </div>
                <strong>What's your filing status?</strong>`, [
                  { label: 'Single', value: 'post_upload_filing_single' },
                  { label: 'Married Filing Jointly', value: 'post_upload_filing_married' },
                  { label: 'Head of Household', value: 'post_upload_filing_hoh' },
                  { label: 'Married Filing Separately', value: 'post_upload_filing_mfs' }
                ]);
              } else if (!extractedData.tax_profile.state) {
                addMessage('ai', `<div style="font-size: var(--text-lg); font-weight: var(--font-semibold); margin-bottom: var(--space-3);">📋 Almost Done!</div>
                ${incomeDisplay}
                <strong>Which state do you live in?</strong>`, [
                  { label: 'California', value: 'post_upload_state_CA' },
                  { label: 'Texas', value: 'post_upload_state_TX' },
                  { label: 'New York', value: 'post_upload_state_NY' },
                  { label: 'Florida', value: 'post_upload_state_FL' },
                  { label: 'Other →', value: 'post_upload_state_other' }
                ]);
              } else {
                addMessage('ai', `<div style="font-size: var(--text-lg); font-weight: var(--font-semibold); margin-bottom: var(--space-3);">📋 One More Question!</div>
                ${incomeDisplay}
                <strong>Any dependents?</strong>`, [
                  { label: 'No dependents', value: 'post_upload_deps_0' },
                  { label: '1-2 dependents', value: 'post_upload_deps_2' },
                  { label: '3+ dependents', value: 'post_upload_deps_3plus' }
                ]);
              }
            } else {
              // All data present - offer to generate report
              addMessage('ai', `<div style="text-align: center; padding: var(--space-4);">
                <div style="font-size: 32px; margin-bottom: var(--space-3);">✅</div>
                <div style="font-size: var(--text-lg); font-weight: var(--font-semibold); margin-bottom: var(--space-2);">Document Analysis Complete!</div>
                ${incomeDisplay}
                <div style="color: var(--text-secondary);">I have everything needed for your analysis.</div>
              </div>`, [
                { label: getIcon('chart-bar', 'sm') + ' Generate My Tax Report', value: 'generate_report', primary: true },
                { label: getIcon('document-text', 'sm') + ' Upload more documents', value: 'yes_upload' },
                { label: getIcon('clipboard-document-list', 'sm') + ' Review extracted data', value: 'review_data' }
              ]);
            }
          }, 500);
        }

      } catch (error) {
        hideTyping();
        DevLogger.error('Document upload error:', error);
        addMessage('ai', `I had trouble reading that document. Would you like to try again or enter the information manually?`, [
          { label: getIcon('arrow-path', 'sm') + ' Try again', value: 'yes_upload' },
          { label: getIcon('chat-bubble-left-right', 'sm') + ' Enter manually', value: 'no_manual' },
          { label: '❓ What documents work best?', value: 'what_docs' }
        ]);
      }
    }

    function uploadDocument() {
      // Show upload options modal
      showUploadOptions();
    }

    function showUploadOptions() {
      // Create options modal
      const modal = document.createElement('div');
      modal.className = 'upload-options-modal';
      modal.id = 'uploadOptionsModal';
      modal.innerHTML = `
        <div class="upload-options-content">
          <button class="close-options-btn" onclick="closeUploadOptions()">&times;</button>
          <h3>📎 Upload Document</h3>
          <p>Choose how you'd like to add your document</p>
          <div class="upload-options-grid">
            <button class="upload-option" onclick="selectFileUpload()">
              <div class="option-icon">📁</div>
              <div class="option-title">Browse Files</div>
              <div class="option-desc">Select from your device</div>
            </button>
            <button class="upload-option" onclick="selectCameraCapture()">
              <div class="option-icon">📷</div>
              <div class="option-title">Take Photo</div>
              <div class="option-desc">Capture with camera</div>
            </button>
          </div>
        </div>
      `;
      document.body.appendChild(modal);

      // Animate in
      requestAnimationFrame(() => {
        modal.classList.add('visible');
      });
    }

    function closeUploadOptions() {
      const modal = document.getElementById('uploadOptionsModal');
      if (modal) {
        modal.classList.remove('visible');
        setTimeout(() => modal.remove(), 300);
      }
    }

    function selectFileUpload() {
      closeUploadOptions();
      document.getElementById('fileInput').click();
    }

    function selectCameraCapture() {
      closeUploadOptions();
      PhotoCapture.open();
    }

    function addVoiceInput() {
      VoiceInputSystem.toggleRecording();
    }

    function handleKeyDown(event) {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
      }
    }

    // Auto-resize textarea
    document.getElementById('userInput').addEventListener('input', function() {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });

    // Drag and drop
    const uploadZone = document.querySelector('.upload-zone');
    uploadZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
      uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
      e.preventDefault();
      uploadZone.classList.remove('dragover');
      const files = e.dataTransfer.files;
      document.getElementById('fileInput').files = files;
      handleFileSelect({ target: { files } });
    });

    // ===================================================================
    // LEAD CAPTURE & QUALIFICATION FUNCTIONS
    // ===================================================================

    async function captureName() {
      const nameInput = document.getElementById('nameInput');
      const name = nameInput ? nameInput.value.trim() : '';

      // Validate name - at least 2 characters, no special characters
      if (!name || name.length < 2) {
        showToast('Please enter your name (at least 2 characters)', 'error');
        if (nameInput) nameInput.focus();
        return;
      }

      // Sanitize - remove potentially dangerous characters
      const sanitizedName = name.replace(/[<>"'&]/g, '').substring(0, 100);

      extractedData.contact.name = sanitizedName;
      extractedData.lead_data.score += 15; // Higher score for engaged users
      addMessage('user', name);

      showTyping();
      setTimeout(() => {
        hideTyping();
        addMessage('ai', `Thank you, ${name}! It's a pleasure to work with you.<br><br>Now, to provide you with the most accurate tax analysis and connect you with the right CPA specialist, <strong>may I have your email address?</strong> (We'll send your comprehensive report here)`, [
          { label: getIcon('envelope', 'sm') + ' Enter email', value: 'enter_email' },
          { label: '⏭️ Skip for now', value: 'skip_email' }
        ]);
      }, 1000);
    }

    async function captureEmail() {
      const emailInput = document.getElementById('emailInput');
      const email = emailInput ? emailInput.value.trim().toLowerCase() : '';

      // Validate email with regex
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!email || !emailRegex.test(email)) {
        showToast('Please enter a valid email address (e.g., name@example.com)', 'error');
        if (emailInput) emailInput.focus();
        return;
      }

      // Sanitize and limit length
      const sanitizedEmail = email.substring(0, 254);

      extractedData.contact.email = sanitizedEmail;
      extractedData.lead_data.score += 20; // Qualified lead!
      leadQualified = true;
      addMessage('user', email);

      showTyping();
      setTimeout(() => {
        hideTyping();
        const firstName = extractedData.contact.name ? extractedData.contact.name.split(' ')[0] : 'there';
        addMessage('ai', `Perfect, ${firstName}! I've saved your email.<br><br>🎉 <strong>You're now qualified for our premium tax advisory service!</strong><br><br>Let's analyze your tax situation and calculate your actual potential savings. This will take about 3-5 minutes.<br><br><strong>How would you like to provide your tax information?</strong>`, [
          { label: getIcon('document-text', 'sm') + ' Upload tax documents (fastest)', value: 'upload_docs_qualified' },
          { label: getIcon('chat-bubble-left-right', 'sm') + ' Answer questions conversationally', value: 'conversational_qualified' },
          { label: getIcon('sparkles', 'sm') + ' Hybrid: docs + questions', value: 'hybrid_qualified' }
        ]);
      }, 1500);
    }

    async function proceedToDataGathering() {
      showTyping();
      setTimeout(() => {
        hideTyping();
        addMessage('ai', `No problem! Let's gather your tax information.<br><br><strong>How would you like to share your information with me?</strong>`, [
          { label: getIcon('document-text', 'sm') + ' Upload tax documents', value: 'upload_docs_qualified' },
          { label: getIcon('chat-bubble-left-right', 'sm') + ' Answer questions', value: 'conversational_qualified' }
        ]);
      }, 1000);
    }

    // ===================================================================
    // INTELLIGENT DATA EXTRACTION WITH OPENAI
    // ===================================================================

    async function extractDataWithAI(userMessage) {
      try {
        // SECURITY: Use secureFetch for CSRF protection
        const response = await secureFetch('/api/ai-chat/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            user_message: userMessage,
            conversation_history: conversationHistory,
            extracted_data: extractedData,
            extraction_mode: true,
            system_context: buildSystemContext()
          })
        });

        if (response.ok) {
          const data = await response.json();

          // Merge extracted data
          if (data.extracted_data) {
            mergeExtractedData(data.extracted_data);
          }

          // Update lead score based on data completeness
          calculateLeadScore();

          return data;
        }
      } catch (error) {
        DevLogger.error('AI extraction error:', error);
      }
      return null;
    }

    function mergeExtractedData(newData) {
      // Intelligently merge new data into existing structure
      if (newData.filing_status) extractedData.tax_profile.filing_status = newData.filing_status;
      if (newData.income) extractedData.tax_profile.total_income = newData.income;
      if (newData.w2_income) extractedData.tax_profile.w2_income = newData.w2_income;
      if (newData.business_income) extractedData.tax_profile.business_income = newData.business_income;
      if (newData.dependents) extractedData.tax_profile.dependents = newData.dependents;
      if (newData.state) extractedData.tax_profile.state = newData.state;

      // Deductions
      if (newData.mortgage) extractedData.tax_items.mortgage_interest = newData.mortgage;
      if (newData.charitable) extractedData.tax_items.charitable = newData.charitable;

      DevLogger.log('Merged extracted data:', extractedData);
    }

    function calculateLeadScore() {
      let score = extractedData.lead_data.score;

      // Add points for completeness
      if (extractedData.contact.name) score += 10;
      if (extractedData.contact.email) score += 20;
      if (extractedData.contact.phone) score += 15;
      if (extractedData.tax_profile.filing_status) score += 10;
      if (extractedData.tax_profile.total_income) score += 15;
      if (extractedData.documents.length > 0) score += 20;

      // Complexity scoring (higher = better lead)
      if (extractedData.tax_profile.business_income && extractedData.tax_profile.business_income > 0) {
        score += 25;
        extractedData.lead_data.complexity = 'complex';
      }
      if (extractedData.tax_profile.rental_income && extractedData.tax_profile.rental_income > 0) {
        score += 20;
      }
      if (extractedData.tax_profile.total_income && extractedData.tax_profile.total_income > 100000) {
        score += 15;
      }

      extractedData.lead_data.score = Math.min(score, 100);
      extractedData.lead_data.ready_for_cpa = score >= 60;

      updateProgress(Math.min(score, 95)); // Cap at 95% until report generated

      // Update journey stepper based on current data
      advanceJourneyBasedOnData();
    }

    // ===================================================================
    // INTELLIGENT ADVISOR API INTEGRATION
    // ===================================================================

    // Store strategies from API
    let taxStrategies = [];
    let currentStrategyIndex = 0;

    // Step-by-step strategy exploration
    function showNextStrategy() {
      if (!taxStrategies || taxStrategies.length === 0) {
        addMessage('ai', 'No strategies available. Let me run the analysis first.');
        performTaxCalculation();
        return;
      }

      const strategy = taxStrategies[currentStrategyIndex];
      const isLast = currentStrategyIndex === taxStrategies.length - 1;
      const isFirst = currentStrategyIndex === 0;

      const priorityColors = {
        'high': '#10b981',
        'medium': '#f59e0b',
        'low': '#6b7280'
      };
      const priorityColor = priorityColors[strategy.priority] || '#4a5568';

      addMessage('ai', `
        <div style="margin-bottom: var(--space-4); display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: var(--text-xs-plus); color: #718096;">Strategy ${currentStrategyIndex + 1} of ${taxStrategies.length}</span>
          <span style="background: ${priorityColor}; color: white; padding: var(--space-1) var(--space-2-5); border-radius: var(--radius-base); font-size: var(--text-2xs); font-weight: var(--font-semibold); text-transform: uppercase;">${strategy.priority} priority</span>
        </div>

        <div style="font-size: var(--text-lg); font-weight: var(--font-bold); color: var(--color-primary-500); margin-bottom: var(--space-2);">
          ${strategy.title}
        </div>

        <div class="insight-card" style="margin: var(--space-4) 0;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-3);">
            <span style="color: #718096; font-size: var(--text-xs-plus);">Estimated Annual Savings</span>
            <span style="font-size: var(--text-2xl); font-weight: var(--font-extrabold); color: #276749;">$${Math.round(strategy.estimated_savings).toLocaleString()}</span>
          </div>
        </div>

        <div style="font-size: var(--text-sm); color: #4a5568; line-height: 1.7; margin-bottom: var(--space-4);">
          ${strategy.detailed_explanation || strategy.summary}
        </div>

        ${strategy.action_steps && strategy.action_steps.length > 0 ? `
          <div style="background: #ebf8ff; border-radius: var(--radius-lg); padding: var(--space-4); margin-bottom: var(--space-4);">
            <div style="font-weight: var(--font-semibold); color: var(--color-primary-500); margin-bottom: var(--space-2-5);">Action Steps:</div>
            <ol style="margin: 0; padding-left: var(--space-5); color: #4a5568; font-size: var(--text-sm); line-height: 1.8;">
              ${strategy.action_steps.map(step => `<li>${step}</li>`).join('')}
            </ol>
          </div>
        ` : ''}

        ${strategy.irs_reference ? `
          <div style="font-size: var(--text-xs); color: #718096; font-style: italic;">
            Reference: ${strategy.irs_reference}
          </div>
        ` : ''}
      `, getStrategyNavigationButtons(isFirst, isLast));
    }

    function getStrategyNavigationButtons(isFirst, isLast) {
      const buttons = [];

      if (!isFirst) {
        buttons.push({ label: '← Previous', value: 'previous_strategy' });
      }

      if (!isLast) {
        buttons.push({ label: 'Next Strategy →', value: 'next_strategy', primary: true });
      } else {
        buttons.push({ label: 'View Summary', value: 'finish_strategies', primary: true });
      }

      return buttons;
    }

    function showStrategySummary() {
      const totalSavings = taxStrategies.reduce((sum, s) => sum + (s.estimated_savings || 0), 0);
      const highPriority = taxStrategies.filter(s => s.priority === 'high');

      let strategyList = taxStrategies.map((s, i) => `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: var(--space-3); background: ${i % 2 === 0 ? '#f7fafc' : 'white'}; border-bottom: 1px solid #e2e8f0;">
          <div style="display: flex; align-items: center; gap: var(--space-3);">
            <span style="width: 24px; height: 24px; background: var(--color-primary-500); color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: var(--text-xs); font-weight: var(--font-semibold);">${i + 1}</span>
            <span style="font-size: var(--text-sm); color: var(--color-primary-900);">${s.title}</span>
          </div>
          <span style="font-weight: var(--font-bold); color: #276749;">$${Math.round(s.estimated_savings).toLocaleString()}</span>
        </div>
      `).join('');

      addMessage('ai', `
        <div style="margin-bottom: var(--space-5);">
          <span style="font-size: var(--text-lg); font-weight: var(--font-bold); color: var(--color-primary-500);">Your Tax Optimization Summary</span>
        </div>

        <div class="insight-card" style="margin-bottom: var(--space-5);">
          <div style="text-align: center;">
            <div style="font-size: var(--text-xs-plus); color: #718096; margin-bottom: var(--space-2);">Total Potential Savings</div>
            <div style="font-size: 32px; font-weight: var(--font-extrabold); color: #276749;">$${Math.round(totalSavings).toLocaleString()}</div>
            <div style="font-size: var(--text-xs-plus); color: #4a5568; margin-top: var(--space-2);">${taxStrategies.length} strategies • ${highPriority.length} high priority</div>
          </div>
        </div>

        <div style="background: white; border: 1px solid #e2e8f0; border-radius: var(--radius-lg); overflow: hidden; margin-bottom: var(--space-5);">
          <div style="background: var(--color-primary-500); color: white; padding: var(--space-3) var(--space-4); font-weight: var(--font-semibold); font-size: var(--text-sm);">
            Strategy Breakdown
          </div>
          ${strategyList}
        </div>

        <div style="font-size: var(--text-sm); color: #4a5568; line-height: 1.6; margin-bottom: var(--space-4);">
          I recommend starting with the high-priority strategies first. Would you like a comprehensive report you can share with a tax professional?
        </div>
      `, [
        { label: 'Generate Full Report', value: 'generate_report', primary: true },
        { label: 'Review strategies again', value: 'explore_strategies' },
        { label: 'Connect with CPA', value: 'request_cpa_early' }
      ]);

      // Update lead score and progress
      extractedData.lead_data.estimated_savings = totalSavings;
      calculateLeadScore();
      updateProgress(85);
    }

    async function getIntelligentAnalysis() {
      // Debug: Log current state
      DevLogger.log('getIntelligentAnalysis called with:', {
        filing_status: extractedData.tax_profile.filing_status,
        total_income: extractedData.tax_profile.total_income,
        dependents: extractedData.tax_profile.dependents
      });

      if (!extractedData.tax_profile.total_income || !extractedData.tax_profile.filing_status) {
        DevLogger.warn('Missing required data:', {
          has_income: !!extractedData.tax_profile.total_income,
          has_filing_status: !!extractedData.tax_profile.filing_status
        });
        return null;
      }

      // Map filing status to API format
      const statusMap = {
        'Single': 'single',
        'Married Filing Jointly': 'married_joint',
        'Head of Household': 'head_of_household',
        'Married Filing Separately': 'married_separate',
        'Qualifying Surviving Spouse': 'qualifying_widow'
      };

      // Validate the filing status mapping
      const apiFilingStatus = statusMap[extractedData.tax_profile.filing_status];
      if (!apiFilingStatus) {
        DevLogger.error('Invalid filing status:', extractedData.tax_profile.filing_status);
        // Try to recover by using the value directly if it looks like an API value
        const directValues = ['single', 'married_joint', 'married_separate', 'head_of_household', 'qualifying_widow'];
        if (!directValues.includes(extractedData.tax_profile.filing_status.toLowerCase())) {
          return null;
        }
      }

      // Clear any existing error banners
      clearErrorBanner();

      // Ensure we have a session ID
      if (!sessionId) {
        sessionId = 'advisor-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        sessionStorage.setItem('tax_session_id', sessionId);
        DevLogger.log('Created new session ID:', sessionId);
      }

      try {
        // Build profile for API
        const profile = {
          filing_status: apiFilingStatus || statusMap[extractedData.tax_profile.filing_status] || 'single',
          total_income: extractedData.tax_profile.total_income,
          w2_income: extractedData.tax_profile.w2_income || extractedData.tax_profile.total_income,
          business_income: extractedData.tax_profile.business_income || 0,
          investment_income: extractedData.tax_profile.investment_income || 0,
          rental_income: extractedData.tax_profile.rental_income || 0,
          dependents: extractedData.tax_profile.dependents || 0,
          state: extractedData.tax_profile.state || '',
          mortgage_interest: extractedData.tax_items.mortgage_interest || 0,
          charitable_donations: extractedData.tax_items.charitable || 0,
          is_self_employed: extractedData.tax_profile.business_income > 0
        };

        DevLogger.log('Sending to API:', profile);

        const response = await fetchWithRetry('/api/advisor/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            message: 'Analyze my tax situation',
            profile: profile
          })
        }, 3); // 3 retries with exponential backoff

        if (response.ok) {
          const data = await response.json();
          taxCalculations = data.tax_calculation;
          taxStrategies = data.strategies || [];
          extractedData.lead_data.estimated_savings = taxStrategies.reduce((sum, s) => sum + s.estimated_savings, 0);
          extractedData.lead_data.score = data.lead_score || extractedData.lead_data.score;

          // Update journey step
          advanceJourneyBasedOnData();

          return {
            calculation: data.tax_calculation,
            strategies: data.strategies,
            insights: data.key_insights,
            totalSavings: taxStrategies.reduce((sum, s) => sum + s.estimated_savings, 0),
            complexity: data.complexity
          };
        } else {
          // Handle non-OK response
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || `Server error: ${response.status}`);
        }
      } catch (error) {
        DevLogger.error('Intelligent analysis error:', error);

        // Show error banner with retry option
        if (!navigator.onLine) {
          showErrorBanner(
            'Connection Lost',
            'Please check your internet connection and try again.',
            'performTaxCalculation()'
          );
        } else if (error.message.includes('429')) {
          showErrorBanner(
            'Service Busy',
            'Our servers are handling high traffic. Please wait a moment and try again.',
            'performTaxCalculation()'
          );
        } else {
          showErrorBanner(
            'Analysis Error',
            'We encountered an issue analyzing your data. Please try again.',
            'performTaxCalculation()'
          );
        }
      }
      return null;
    }

    async function calculateTaxLiability() {
      const analysis = await getIntelligentAnalysis();
      if (analysis) {
        return analysis.calculation;
      }
      return null;
    }

    // ===================================================================
    // INTELLIGENT QUESTIONING ENGINE - Comprehensive Tax Discovery
    // ===================================================================

    // Track conversation state to prevent loops
    let questioningState = {
      askedQuestions: new Set(),
      currentPhase: 'basics', // basics, income_details, deductions, goals, summary
      callCount: 0,
      maxCalls: 50 // Safety limit to prevent infinite loops
    };

    function markQuestionAsked(questionId) {
      questioningState.askedQuestions.add(questionId);
    }

    function wasQuestionAsked(questionId) {
      return questioningState.askedQuestions.has(questionId);
    }

    function resetQuestioningState() {
      questioningState.askedQuestions.clear();
      questioningState.callCount = 0;
      questioningState.currentPhase = 'basics';
    }

    async function startIntelligentQuestioning() {
      // Loop prevention - increment call counter
      questioningState.callCount++;

      // Safety check - if we've called this too many times, skip to summary
      if (questioningState.callCount > questioningState.maxCalls) {
        DevLogger.warn('startIntelligentQuestioning exceeded max calls, skipping to summary');
        await showPreliminarySummary();
        return;
      }

      showTyping();

      setTimeout(async () => {
        hideTyping();

        const profile = extractedData.tax_profile;
        const isHighEarner = (profile.total_income || 0) >= 200000;
        const isVeryHighEarner = (profile.total_income || 0) >= 500000;
        const isSelfEmployed = profile.is_self_employed || profile.income_source === 'Self-Employed / 1099';
        const isBusinessOwner = profile.income_source === 'Business Owner';
        const isInvestor = profile.income_source === 'Investments / Retirement';
        const hasMultipleSources = profile.income_source === 'Multiple sources';

        // =====================================================================
        // PHASE 1: BASIC INFORMATION
        // =====================================================================

        // Step 1: Filing Status
        if (!profile.filing_status) {
          markQuestionAsked('filing_status');
          // Use radio buttons for filing status (mutually exclusive with descriptions)
          addMessage('ai', `Let's start with the basics. What's your filing status for 2025?`, [
            { label: 'Single', value: 'filing_single', description: 'Unmarried or legally separated' },
            { label: 'Married Filing Jointly', value: 'filing_married', description: 'Married and filing together with spouse' },
            { label: 'Married Filing Separately', value: 'filing_mfs', description: 'Married but filing individual returns' },
            { label: 'Head of Household', value: 'filing_hoh', description: 'Unmarried and paying 50%+ of household costs' }
          ], { inputType: 'radio' });
          return;
        }

        // Step 2: State of Residence
        if (!profile.state) {
          markQuestionAsked('state');
          // Use dropdown for state selection (50 states is too many for buttons)
          addMessage('ai', `Which state do you live in? This affects your state tax calculation.`, [], {
            inputType: 'dropdown',
            placeholder: 'Select your state...',
            groups: [
              {
                label: '⭐ No Income Tax States',
                options: [
                  { label: 'Alaska', value: 'state_AK' },
                  { label: 'Florida', value: 'state_FL' },
                  { label: 'Nevada', value: 'state_NV' },
                  { label: 'South Dakota', value: 'state_SD' },
                  { label: 'Tennessee', value: 'state_TN' },
                  { label: 'Texas', value: 'state_TX' },
                  { label: 'Washington', value: 'state_WA' },
                  { label: 'Wyoming', value: 'state_WY' }
                ]
              },
              {
                label: '🌴 West',
                options: [
                  { label: 'Arizona', value: 'state_AZ' },
                  { label: 'California', value: 'state_CA' },
                  { label: 'Colorado', value: 'state_CO' },
                  { label: 'Hawaii', value: 'state_HI' },
                  { label: 'Idaho', value: 'state_ID' },
                  { label: 'Montana', value: 'state_MT' },
                  { label: 'New Mexico', value: 'state_NM' },
                  { label: 'Oregon', value: 'state_OR' },
                  { label: 'Utah', value: 'state_UT' }
                ]
              },
              {
                label: '🌾 Midwest',
                options: [
                  { label: 'Illinois', value: 'state_IL' },
                  { label: 'Indiana', value: 'state_IN' },
                  { label: 'Iowa', value: 'state_IA' },
                  { label: 'Kansas', value: 'state_KS' },
                  { label: 'Michigan', value: 'state_MI' },
                  { label: 'Minnesota', value: 'state_MN' },
                  { label: 'Missouri', value: 'state_MO' },
                  { label: 'Nebraska', value: 'state_NE' },
                  { label: 'North Dakota', value: 'state_ND' },
                  { label: 'Ohio', value: 'state_OH' },
                  { label: 'Wisconsin', value: 'state_WI' }
                ]
              },
              {
                label: '🏛️ Northeast',
                options: [
                  { label: 'Connecticut', value: 'state_CT' },
                  { label: 'Delaware', value: 'state_DE' },
                  { label: 'Maine', value: 'state_ME' },
                  { label: 'Maryland', value: 'state_MD' },
                  { label: 'Massachusetts', value: 'state_MA' },
                  { label: 'New Hampshire', value: 'state_NH' },
                  { label: 'New Jersey', value: 'state_NJ' },
                  { label: 'New York', value: 'state_NY' },
                  { label: 'Pennsylvania', value: 'state_PA' },
                  { label: 'Rhode Island', value: 'state_RI' },
                  { label: 'Vermont', value: 'state_VT' }
                ]
              },
              {
                label: '🌸 South',
                options: [
                  { label: 'Alabama', value: 'state_AL' },
                  { label: 'Arkansas', value: 'state_AR' },
                  { label: 'Georgia', value: 'state_GA' },
                  { label: 'Kentucky', value: 'state_KY' },
                  { label: 'Louisiana', value: 'state_LA' },
                  { label: 'Mississippi', value: 'state_MS' },
                  { label: 'North Carolina', value: 'state_NC' },
                  { label: 'Oklahoma', value: 'state_OK' },
                  { label: 'South Carolina', value: 'state_SC' },
                  { label: 'Virginia', value: 'state_VA' },
                  { label: 'West Virginia', value: 'state_WV' },
                  { label: 'Washington D.C.', value: 'state_DC' }
                ]
              }
            ]
          });
          return;
        }

        // Step 2b: Other State - ask which one
        if (profile.state === 'OTHER' && !profile.state_name && !wasQuestionAsked('state_name')) {
          markQuestionAsked('state_name');
          addMessage('ai', `Which state do you reside in?<br><br>
            <select id="stateSelect" style="width: 100%; padding: var(--space-3); margin: var(--space-2) 0; border: 2px solid var(--border); border-radius: var(--radius-lg); font-size: 15px; background: white;">
              <option value="">Select your state...</option>
              <option value="AL">Alabama</option><option value="AK">Alaska</option><option value="AZ">Arizona</option>
              <option value="AR">Arkansas</option><option value="CO">Colorado</option><option value="CT">Connecticut</option>
              <option value="DE">Delaware</option><option value="DC">District of Columbia</option><option value="GA">Georgia</option>
              <option value="HI">Hawaii</option><option value="ID">Idaho</option><option value="IL">Illinois</option>
              <option value="IN">Indiana</option><option value="IA">Iowa</option><option value="KS">Kansas</option>
              <option value="KY">Kentucky</option><option value="LA">Louisiana</option><option value="ME">Maine</option>
              <option value="MD">Maryland</option><option value="MA">Massachusetts</option><option value="MI">Michigan</option>
              <option value="MN">Minnesota</option><option value="MS">Mississippi</option><option value="MO">Missouri</option>
              <option value="MT">Montana</option><option value="NE">Nebraska</option><option value="NV">Nevada</option>
              <option value="NH">New Hampshire</option><option value="NJ">New Jersey</option><option value="NM">New Mexico</option>
              <option value="NC">North Carolina</option><option value="ND">North Dakota</option><option value="OH">Ohio</option>
              <option value="OK">Oklahoma</option><option value="OR">Oregon</option><option value="PA">Pennsylvania</option>
              <option value="RI">Rhode Island</option><option value="SC">South Carolina</option><option value="SD">South Dakota</option>
              <option value="TN">Tennessee</option><option value="UT">Utah</option><option value="VT">Vermont</option>
              <option value="VA">Virginia</option><option value="WA">Washington</option><option value="WV">West Virginia</option>
              <option value="WI">Wisconsin</option><option value="WY">Wyoming</option>
            </select>
            <button onclick="selectOtherState()" style="padding: var(--space-3) var(--space-6); background: var(--primary); color: white; border: none; border-radius: var(--radius-lg); cursor: pointer; font-weight: var(--font-semibold); margin-top: var(--space-2);">Continue →</button>`);
          return;
        }

        // Step 3: Income Range
        if (!profile.total_income) {
          markQuestionAsked('income');
          // Use radio buttons for income ranges (mutually exclusive)
          addMessage('ai', `What's your approximate total household income for 2025?`, [
            { label: '$0 - $50,000', value: 'income_0_50k', description: 'Entry-level, part-time, or starting out' },
            { label: '$50,000 - $100,000', value: 'income_50_100k', description: 'Middle income range' },
            { label: '$100,000 - $200,000', value: 'income_100_200k', description: 'Upper-middle income' },
            { label: '$200,000 - $500,000', value: 'income_200_500k', description: 'High earner, more tax strategies available' },
            { label: 'Over $500,000', value: 'income_500k_plus', description: 'Top bracket, complex planning needed' }
          ], { inputType: 'radio' });
          return;
        }

        // Step 4: Primary Income Source
        if (!profile.income_source) {
          markQuestionAsked('income_source');
          addMessage('ai', `What's your primary source of income?`, [
            { label: 'W-2 Employee', value: 'source_w2' },
            { label: 'Self-Employed / 1099', value: 'source_self_employed' },
            { label: 'Business Owner', value: 'source_business' },
            { label: 'Investments / Retirement', value: 'source_investments' },
            { label: 'Multiple sources', value: 'source_multiple' }
          ]);
          return;
        }

        // W-4 Withholding Status (for W-2 employees)
        const isW2Employee = profile.income_source === 'W-2 Employee';
        if (isW2Employee && !profile.withholding_explored && !wasQuestionAsked('withholding')) {
          markQuestionAsked('withholding');
          addMessage('ai', `Do you adjust your W-4 withholding to manage your tax refund/payment?`, [
            { label: 'Yes, I adjust it strategically', value: 'withhold_strategic' },
            { label: 'No, I use the default settings', value: 'withhold_default' },
            { label: 'I usually get a large refund', value: 'withhold_large_refund' },
            { label: 'I usually owe taxes', value: 'withhold_owe' },
            { label: 'Not sure / Skip', value: 'withhold_skip' }
          ]);
          return;
        }

        // Prior Year Tax Situation
        if (!profile.prior_year_explored && !wasQuestionAsked('prior_year')) {
          markQuestionAsked('prior_year');
          addMessage('ai', `How did your tax situation last year compare to your expectations?`, [
            { label: 'Got a large refund (over $2,000)', value: 'prior_large_refund' },
            { label: 'Got a small refund (under $2,000)', value: 'prior_small_refund' },
            { label: 'Owed money to the IRS', value: 'prior_owed' },
            { label: 'About break-even', value: 'prior_breakeven' },
            { label: 'First time filing / Skip', value: 'prior_skip' }
          ]);
          return;
        }

        // Spouse Income (for Married Filing Jointly)
        const isMFJ = profile.filing_status === 'Married Filing Jointly';
        if (isMFJ && !profile.spouse_income_explored && !wasQuestionAsked('spouse_income')) {
          markQuestionAsked('spouse_income');
          addMessage('ai', `For joint filers, I need to understand your spouse's income situation. <strong>Does your spouse have income?</strong>`, [
            { label: 'Yes, W-2 employment', value: 'spouse_w2' },
            { label: 'Yes, self-employed', value: 'spouse_self_employed' },
            { label: 'Yes, both W-2 and self-employed', value: 'spouse_both' },
            { label: 'No, spouse doesn\'t work', value: 'spouse_none' },
            { label: 'Skip this question', value: 'spouse_skip' }
          ]);
          return;
        }

        // =====================================================================
        // PHASE 2: INCOME-SPECIFIC DEEP DIVE
        // =====================================================================

        // Business Owner / Self-Employed Follow-up
        if ((isSelfEmployed || isBusinessOwner) && !profile.business_explored && !wasQuestionAsked('business_type')) {
          markQuestionAsked('business_type');
          addMessage('ai', `Great! Understanding your business helps me find more deductions. What type of business do you operate?`, [
            { label: 'Professional Services (consulting, legal, medical)', value: 'biz_professional' },
            { label: 'Retail / E-commerce', value: 'biz_retail' },
            { label: 'Real Estate', value: 'biz_realestate' },
            { label: 'Tech / Software', value: 'biz_tech' },
            { label: 'Farming / Agriculture', value: 'biz_farm' },
            { label: 'Other Service Business', value: 'biz_service' }
          ]);
          return;
        }

        // Business Entity Type
        if ((isSelfEmployed || isBusinessOwner) && profile.business_type && !profile.entity_type && !wasQuestionAsked('entity_type')) {
          markQuestionAsked('entity_type');
          // Use radio buttons for business structure (mutually exclusive with descriptions)
          addMessage('ai', `What's your business structure? This significantly impacts your tax strategy.`, [
            { label: 'Sole Proprietorship', value: 'entity_sole', description: 'Self-employed, no formal business entity' },
            { label: 'Single-Member LLC', value: 'entity_llc_single', description: 'One owner, limited liability protection' },
            { label: 'Multi-Member LLC / Partnership', value: 'entity_llc_multi', description: 'Multiple owners sharing profits/losses' },
            { label: 'S-Corporation', value: 'entity_scorp', description: 'Pass-through taxation, salary + distributions' },
            { label: 'C-Corporation', value: 'entity_ccorp', description: 'Separate entity, double taxation possible' }
          ], { inputType: 'radio' });
          return;
        }

        // Business Revenue (for business owners)
        if ((isSelfEmployed || isBusinessOwner) && profile.entity_type && !profile.business_revenue && !wasQuestionAsked('business_revenue')) {
          markQuestionAsked('business_revenue');
          addMessage('ai', `What's your approximate annual business revenue?`, [
            { label: 'Under $50,000', value: 'revenue_under50k' },
            { label: '$50,000 - $100,000', value: 'revenue_50_100k' },
            { label: '$100,000 - $250,000', value: 'revenue_100_250k' },
            { label: '$250,000 - $500,000', value: 'revenue_250_500k' },
            { label: 'Over $500,000', value: 'revenue_over500k' }
          ]);
          return;
        }

        // Business Expense Categories (for self-employed) - MULTI-SELECT
        if ((isSelfEmployed || isBusinessOwner) && profile.business_revenue && !profile.business_expenses_explored && !wasQuestionAsked('business_expenses')) {
          markQuestionAsked('business_expenses');
          addMessage('ai', `What are your major business expense categories? (Select all that apply)`, [
            { label: getIcon('home', 'sm') + ' Home Office', value: 'bizexp_home_office' },
            { label: getIcon('truck', 'sm') + ' Vehicle / Mileage', value: 'bizexp_vehicle' },
            { label: getIcon('cpu-chip', 'sm') + ' Equipment & Software', value: 'bizexp_equipment' },
            { label: '📢 Marketing & Advertising', value: 'bizexp_marketing' },
            { label: getIcon('cube', 'sm') + ' Supplies & Materials', value: 'bizexp_supplies' },
            { label: getIcon('academic-cap', 'sm') + ' Training & Education', value: 'bizexp_training' }
          ], { multiSelect: true });
          return;
        }

        // Net Business Income (profit after expenses) - critical for self-employment tax
        if ((isSelfEmployed || isBusinessOwner) && profile.business_revenue && !profile.net_income_explored && !wasQuestionAsked('net_business_income')) {
          markQuestionAsked('net_business_income');
          addMessage('ai', `<strong>What's your approximate NET business income (profit after expenses)?</strong><br><small>This determines your self-employment tax (15.3%).</small>`, [
            { label: 'Under $25,000 net', value: 'netincome_under25k' },
            { label: '$25,000 - $75,000 net', value: 'netincome_25_75k' },
            { label: '$75,000 - $150,000 net', value: 'netincome_75_150k' },
            { label: '$150,000 - $250,000 net', value: 'netincome_150_250k' },
            { label: 'Over $250,000 net', value: 'netincome_over250k' }
          ]);
          return;
        }

        // QBI Deduction Eligibility (20% pass-through deduction)
        const qbiThreshold = profile.filing_status === 'Married Filing Jointly' ? 364200 : 182100;
        if ((isSelfEmployed || isBusinessOwner) && profile.net_business_income && !profile.qbi_explored && !wasQuestionAsked('qbi_eligibility')) {
          markQuestionAsked('qbi_eligibility');
          const mayQualify = (profile.total_income || 0) < qbiThreshold;
          addMessage('ai', `<strong>Are you aware of the QBI (Qualified Business Income) deduction?</strong><br><small>${mayQualify ? 'You may qualify for a 20% deduction on your business income!' : 'Phase-out may apply at your income level, but partial deduction possible.'}</small>`, [
            { label: 'Yes, I claim QBI deduction', value: 'qbi_yes' },
            { label: 'No, what is it?', value: 'qbi_learn' },
            { label: 'My CPA handles this', value: 'qbi_cpa' },
            { label: 'Not sure if I qualify', value: 'qbi_unsure' }
          ]);
          return;
        }

        // Mark business as explored after all business questions
        if ((isSelfEmployed || isBusinessOwner) && !profile.business_explored) {
          profile.business_explored = true;
        }

        // Multiple Income Sources Breakdown
        if (hasMultipleSources && !profile.income_sources_detailed && !wasQuestionAsked('multiple_sources')) {
          markQuestionAsked('multiple_sources');
          addMessage('ai', `You mentioned multiple income sources. Which of these apply? (Select your primary sources)`, [
            { label: 'W-2 Employment + Side Business', value: 'multi_w2_biz' },
            { label: 'W-2 Employment + Investments', value: 'multi_w2_invest' },
            { label: 'Self-Employment + Rental Income', value: 'multi_self_rental' },
            { label: 'Retirement Income + Part-time Work', value: 'multi_retire_work' },
            { label: 'Other combination', value: 'multi_other' }
          ]);
          return;
        }

        // Investment Income Follow-up for Investors or High Earners - MULTI-SELECT
        if ((isInvestor || isVeryHighEarner) && !profile.investment_explored && !wasQuestionAsked('investment_type')) {
          markQuestionAsked('investment_type');
          addMessage('ai', `${isVeryHighEarner ? 'At your income level, investment strategy is crucial. ' : ''}What types of investment income do you have? (Select all that apply)`, [
            { label: getIcon('arrow-trending-up', 'sm') + ' Stock dividends & capital gains', value: 'invest_stocks' },
            { label: getIcon('home', 'sm') + ' Rental property income', value: 'invest_rental' },
            { label: '💵 Interest income (bonds, savings)', value: 'invest_interest' },
            { label: getIcon('clipboard-document-list', 'sm') + ' Partnership/K-1 income', value: 'invest_k1' },
            { label: '🪙 Cryptocurrency', value: 'invest_crypto' }
          ], { multiSelect: true });
          return;
        }

        // Rental Property Follow-up
        if (profile.has_rental_income && !profile.rental_explored && !wasQuestionAsked('rental_count')) {
          markQuestionAsked('rental_count');
          addMessage('ai', `How many rental properties do you own?`, [
            { label: '1 property', value: 'rental_1' },
            { label: '2-4 properties', value: 'rental_2_4' },
            { label: '5+ properties', value: 'rental_5plus' }
          ]);
          return;
        }

        // Capital Gains/Losses (for stock investors)
        if (profile.investment_type === 'stocks' || profile.investment_type === 'multiple') {
          if (!profile.capital_gains_explored && !wasQuestionAsked('capital_gains')) {
            markQuestionAsked('capital_gains');
            addMessage('ai', `<strong>Did you have any capital gains or losses from selling stocks this year?</strong>`, [
              { label: 'Yes, net gains (profit)', value: 'capgain_gains' },
              { label: 'Yes, net losses', value: 'capgain_losses' },
              { label: 'About break-even', value: 'capgain_even' },
              { label: 'Haven\'t sold anything', value: 'capgain_none' }
            ]);
            return;
          }
        }

        // Capital Gains Amount Follow-up
        if (profile.has_capital_gains && !profile.capital_gains_amount_explored && !wasQuestionAsked('capital_gains_amount')) {
          markQuestionAsked('capital_gains_amount');
          addMessage('ai', `<strong>Approximately how much in capital gains?</strong>`, [
            { label: 'Under $10,000', value: 'capgainamt_under10k' },
            { label: '$10,000 - $50,000', value: 'capgainamt_10_50k' },
            { label: '$50,000 - $100,000', value: 'capgainamt_50_100k' },
            { label: 'Over $100,000', value: 'capgainamt_over100k' }
          ]);
          return;
        }

        // Capital Losses Amount Follow-up
        if (profile.has_capital_losses && !profile.capital_losses_amount_explored && !wasQuestionAsked('capital_losses_amount')) {
          markQuestionAsked('capital_losses_amount');
          addMessage('ai', `Capital losses can offset gains and up to $3,000 of ordinary income! <strong>Approximately how much in losses?</strong>`, [
            { label: 'Under $3,000', value: 'caplossamt_under3k' },
            { label: '$3,000 - $10,000', value: 'caplossamt_3_10k' },
            { label: 'Over $10,000', value: 'caplossamt_over10k' }
          ]);
          return;
        }

        // =====================================================================
        // PHASE 3: DEPENDENTS & FAMILY
        // =====================================================================

        // Dependents
        if (profile.dependents == null) {
          markQuestionAsked('dependents');
          addMessage('ai', `Do you have any dependents (children under 17, elderly parents, etc.)?`, [
            { label: 'No dependents', value: 'dependents_0' },
            { label: '1 dependent', value: 'dependents_1' },
            { label: '2 dependents', value: 'dependents_2' },
            { label: '3 or more', value: 'dependents_3plus' }
          ]);
          return;
        }

        // Dependent Ages (if has children)
        if (profile.dependents > 0 && !profile.dependent_ages_explored && !wasQuestionAsked('dependent_ages')) {
          markQuestionAsked('dependent_ages');
          addMessage('ai', `What are the ages of your dependents? (Select the category that best fits)`, [
            { label: 'All under 6 years old', value: 'dep_age_under6' },
            { label: 'Children 6-17 years old', value: 'dep_age_6_17' },
            { label: 'College students (18-24)', value: 'dep_age_college' },
            { label: 'Adult dependents / elderly parents', value: 'dep_age_adult' },
            { label: 'Mix of ages', value: 'dep_age_mixed' }
          ]);
          return;
        }

        // Childcare Expenses (if young children)
        if (profile.dependents > 0 && profile.has_young_children && !profile.childcare_explored && !wasQuestionAsked('childcare')) {
          markQuestionAsked('childcare');
          addMessage('ai', `Do you pay for childcare or daycare expenses?`, [
            { label: 'Yes, over $5,000/year', value: 'childcare_high' },
            { label: 'Yes, under $5,000/year', value: 'childcare_low' },
            { label: 'No childcare expenses', value: 'childcare_none' }
          ]);
          return;
        }

        // =====================================================================
        // PHASE 4: DEDUCTIONS & TAX ITEMS
        // =====================================================================

        // Major Deductions
        if (!profile.deductions_explored) {
          markQuestionAsked('deductions');
          const deductionOptions = [
            { label: 'Own a home (mortgage interest)', value: 'deduction_mortgage' },
            { label: 'Make charitable donations', value: 'deduction_charity' },
            { label: 'Have high medical expenses', value: 'deduction_medical' },
            { label: 'Contribute to retirement (401k/IRA)', value: 'deduction_retirement' }
          ];

          // Add high-income specific option
          if (isHighEarner) {
            deductionOptions.push({ label: 'Have investment losses to harvest', value: 'deduction_investment_loss' });
          }

          deductionOptions.push({ label: 'None of these / Continue', value: 'deduction_none' });

          addMessage('ai', `Which of these tax situations apply to you?`, deductionOptions);
          return;
        }

        // Retirement Contribution Details (if they selected retirement)
        if (profile.has_retirement_contributions && !profile.retirement_detailed && !wasQuestionAsked('retirement_type')) {
          markQuestionAsked('retirement_type');
          addMessage('ai', `What retirement accounts do you contribute to?`, [
            { label: '401(k) through employer', value: 'retire_401k' },
            { label: 'Traditional IRA', value: 'retire_trad_ira' },
            { label: 'Roth IRA', value: 'retire_roth_ira' },
            { label: '401(k) and IRA', value: 'retire_both' },
            { label: 'SEP-IRA or Solo 401(k) (self-employed)', value: 'retire_sep' }
          ]);
          return;
        }

        // 401k Contribution Amount
        if (profile.has_401k && !profile.retirement_401k && !wasQuestionAsked('401k_amount')) {
          markQuestionAsked('401k_amount');
          addMessage('ai', `How much are you contributing to your 401(k) this year?`, [
            { label: 'Less than $10,000', value: '401k_under10k' },
            { label: '$10,000 - $15,000', value: '401k_10_15k' },
            { label: '$15,000 - $23,000', value: '401k_15_23k' },
            { label: 'Maxing out ($23,500)', value: '401k_max' },
            { label: 'Not sure', value: '401k_unsure' }
          ]);
          return;
        }

        // HSA Contributions (for those with high-deductible health plans)
        if (!profile.hsa_explored && !wasQuestionAsked('hsa_contributions')) {
          markQuestionAsked('hsa_contributions');
          addMessage('ai', `Do you have a Health Savings Account (HSA)?`, [
            { label: 'Yes, I contribute to an HSA', value: 'hsa_yes' },
            { label: 'No HSA', value: 'hsa_no' },
            { label: 'Not sure', value: 'hsa_unsure' }
          ]);
          return;
        }

        // HSA Amount Follow-up
        if (profile.has_hsa && !profile.hsa_amount_explored && !wasQuestionAsked('hsa_amount')) {
          markQuestionAsked('hsa_amount');
          addMessage('ai', `HSA contributions are tax-deductible! <strong>How much do you contribute annually?</strong>`, [
            { label: 'Under $2,000', value: 'hsaamt_under2k' },
            { label: '$2,000 - $4,000', value: 'hsaamt_2_4k' },
            { label: 'Maxing out ($4,150 single / $8,300 family)', value: 'hsaamt_max' },
            { label: 'Not sure', value: 'hsaamt_unsure' }
          ]);
          return;
        }

        // Student Loan Interest
        if (!profile.student_loan_explored && !wasQuestionAsked('student_loan')) {
          markQuestionAsked('student_loan');
          addMessage('ai', `Do you pay student loan interest?`, [
            { label: 'Yes, I pay student loan interest', value: 'studentloan_yes' },
            { label: 'No student loans', value: 'studentloan_no' }
          ]);
          return;
        }

        // Student Loan Amount Follow-up
        if (profile.has_student_loans && !profile.student_loan_amount_explored && !wasQuestionAsked('student_loan_amount')) {
          markQuestionAsked('student_loan_amount');
          addMessage('ai', `Student loan interest is deductible up to $2,500. <strong>How much interest do you pay annually?</strong>`, [
            { label: 'Under $1,000', value: 'studentloanamt_under1k' },
            { label: '$1,000 - $2,500', value: 'studentloanamt_1_2500' },
            { label: 'Over $2,500', value: 'studentloanamt_over2500' }
          ]);
          return;
        }

        // Energy Efficiency Credits (for homeowners or those planning major purchases)
        if ((profile.owns_home || profile.primary_goal === 'home') && !profile.energy_explored && !wasQuestionAsked('energy_credits')) {
          markQuestionAsked('energy_credits');
          addMessage('ai', `Have you made any energy-efficient improvements or purchases this year?`, [
            { label: '☀️ Solar panels installed', value: 'energy_solar' },
            { label: getIcon('truck', 'sm') + ' Electric vehicle purchased', value: 'energy_ev' },
            { label: getIcon('home', 'sm') + ' Heat pump / HVAC upgrade', value: 'energy_hvac' },
            { label: '🪟 Windows / insulation / doors', value: 'energy_home_improve' },
            { label: 'None of these', value: 'energy_none' }
          ]);
          return;
        }

        // Education Credits (AOTC, Lifetime Learning, 529)
        const hasCollegeAgeKids = profile.dependent_ages === 'college' || profile.dependent_ages === 'mixed';
        if ((hasCollegeAgeKids || profile.dependents > 0) && !profile.education_credits_explored && !wasQuestionAsked('education_credits')) {
          markQuestionAsked('education_credits');
          addMessage('ai', `<strong>Are you paying for higher education expenses?</strong><br><small>Education credits can save up to $2,500 per student!</small>`, [
            { label: 'Yes, college tuition for dependents', value: 'educredit_dependents' },
            { label: 'Yes, for myself (taking classes)', value: 'educredit_self' },
            { label: 'I contribute to a 529 plan', value: 'educredit_529' },
            { label: 'No education expenses', value: 'educredit_none' }
          ]);
          return;
        }

        // Standard Deduction vs Itemized Decision
        const hasItemizableDeductions = profile.has_mortgage || profile.has_charitable || profile.has_medical || (items.property_tax > 0);
        const standardDeduction = profile.filing_status === 'Married Filing Jointly' ? 29200 :
                                  profile.filing_status === 'Head of Household' ? 21900 : 14600;
        if (hasItemizableDeductions && !profile.itemize_decision_explored && !wasQuestionAsked('itemize_decision')) {
          markQuestionAsked('itemize_decision');
          const estimatedItemized = (items.mortgage_interest || 0) + Math.min((items.property_tax || 0), 10000) + (items.charitable || 0) + (items.medical || 0);
          const shouldItemize = estimatedItemized > standardDeduction;
          addMessage('ai', `<strong>Based on your deductions, do you typically itemize or take the standard deduction?</strong><br><small>2025 standard deduction: $${standardDeduction.toLocaleString()} for ${profile.filing_status || 'your filing status'}${shouldItemize ? '<br>Your itemized deductions may exceed this!' : ''}</small>`, [
            { label: 'I itemize deductions', value: 'itemize_yes' },
            { label: 'I take the standard deduction', value: 'itemize_standard' },
            { label: 'My CPA decides', value: 'itemize_cpa' },
            { label: 'Not sure', value: 'itemize_unsure' }
          ]);
          return;
        }

        // =====================================================================
        // PHASE 5: TAX GOALS & LIFE EVENTS
        // =====================================================================

        // Tax Goals
        if (!profile.goals_explored) {
          markQuestionAsked('goals');
          addMessage('ai', `What's your primary tax goal this year?`, [
            { label: 'Reduce my current tax bill', value: 'goal_reduce_taxes' },
            { label: 'Maximize retirement savings', value: 'goal_retirement' },
            { label: 'Plan for a major life event', value: 'goal_life_event' },
            { label: 'Build long-term wealth tax-efficiently', value: 'goal_wealth' },
            { label: 'General tax optimization', value: 'goal_optimize' }
          ]);
          return;
        }

        // Life Event Details
        if (profile.primary_goal === 'life_event' && !profile.life_event_type && !wasQuestionAsked('life_event_type')) {
          markQuestionAsked('life_event_type');
          addMessage('ai', `What type of life event are you planning for?`, [
            { label: 'Getting married', value: 'event_marriage' },
            { label: 'Having a baby', value: 'event_baby' },
            { label: 'Buying a home', value: 'event_home' },
            { label: 'Starting a business', value: 'event_business' },
            { label: 'Retiring soon', value: 'event_retirement' },
            { label: 'Selling a home or major asset', value: 'event_sale' }
          ]);
          return;
        }

        // =====================================================================
        // PHASE 6: HIGH-INCOME SPECIFIC QUESTIONS
        // =====================================================================

        // High Earner Advanced Strategies
        if (isVeryHighEarner && !profile.advanced_explored && !wasQuestionAsked('advanced_strategies')) {
          markQuestionAsked('advanced_strategies');
          addMessage('ai', `At your income level, there are advanced strategies worth exploring. Do any of these interest you?`, [
            { label: 'Backdoor Roth IRA strategies', value: 'adv_backdoor' },
            { label: 'Charitable giving optimization (DAF)', value: 'adv_charitable' },
            { label: 'Deferred compensation plans', value: 'adv_deferred' },
            { label: 'Estate planning considerations', value: 'adv_estate' },
            { label: 'Just show me all tax-saving opportunities', value: 'adv_all' }
          ]);
          return;
        }

        // Cryptocurrency Holdings (for investors or tech workers)
        if ((isInvestor || profile.business_type === 'tech' || isHighEarner) &&
            !profile.crypto_explored && !wasQuestionAsked('crypto_holdings')) {
          markQuestionAsked('crypto_holdings');
          addMessage('ai', `Do you have any cryptocurrency holdings or transactions this year?`, [
            { label: 'Yes, I hold crypto but haven\'t sold', value: 'crypto_hold' },
            { label: 'Yes, I sold/traded crypto', value: 'crypto_sold' },
            { label: 'Yes, I earned crypto (mining/staking/rewards)', value: 'crypto_earned' },
            { label: 'No cryptocurrency', value: 'crypto_none' }
          ]);
          return;
        }

        // Stock Options (for employees at startups/tech)
        if (!profile.stock_options_explored && !wasQuestionAsked('stock_options')) {
          // Ask if they have W-2 income and haven't specified
          if (profile.income_source === 'W-2 Employee' || !profile.is_self_employed) {
            markQuestionAsked('stock_options');
            addMessage('ai', `Do you receive stock options or equity compensation from your employer?`, [
              { label: 'Yes, I have ISOs (Incentive Stock Options)', value: 'options_iso' },
              { label: 'Yes, I have NSOs (Non-Qualified Stock Options)', value: 'options_nso' },
              { label: 'Yes, I have RSUs (Restricted Stock Units)', value: 'options_rsu' },
              { label: 'Yes, I have ESPP (Employee Stock Purchase Plan)', value: 'options_espp' },
              { label: 'No equity compensation', value: 'options_none' }
            ]);
            return;
          }
        }

        // Foreign Income / FBAR Requirements (for high earners and investors)
        if ((isHighEarner || isInvestor) && !profile.foreign_explored && !wasQuestionAsked('foreign_income')) {
          markQuestionAsked('foreign_income');
          addMessage('ai', `<strong>Do you have any foreign income or foreign bank accounts?</strong><br><small>Foreign accounts over $10,000 require FBAR reporting.</small>`, [
            { label: 'Yes, I have foreign income', value: 'foreign_income' },
            { label: 'Yes, foreign bank accounts only', value: 'foreign_accounts' },
            { label: 'Both foreign income and accounts', value: 'foreign_both' },
            { label: 'No foreign income or accounts', value: 'foreign_none' }
          ]);
          return;
        }

        // Estimated Tax Payments (for self-employed or investors)
        if ((profile.is_self_employed || isInvestor || profile.has_rental_income) &&
            !profile.estimated_explored && !wasQuestionAsked('estimated_payments')) {
          markQuestionAsked('estimated_payments');
          addMessage('ai', `Do you make quarterly estimated tax payments?`, [
            { label: 'Yes, I make regular estimated payments', value: 'estimated_yes' },
            { label: 'Sometimes, but not consistently', value: 'estimated_sometimes' },
            { label: 'No, I don\'t make estimated payments', value: 'estimated_no' },
            { label: 'Not sure if I should be', value: 'estimated_unsure' }
          ]);
          return;
        }

        // =====================================================================
        // COMPLETE - Show Summary
        // =====================================================================

        await showPreliminarySummary();

      }, 1000);
    }

    // Handler for selecting state from dropdown
    function selectOtherState() {
      const select = document.getElementById('stateSelect');
      const stateCode = select ? select.value : '';

      if (!stateCode) {
        showToast('Please select your state', 'warning');
        return;
      }

      const stateName = select.options[select.selectedIndex].text;
      addMessage('user', stateName);
      extractedData.tax_profile.state = stateCode;
      extractedData.tax_profile.state_name = stateName;
      calculateLeadScore();

      // Ask about multi-state filing
      askMultiStateQuestion();
    }

    // Multi-state filing question
    function askMultiStateQuestion() {
      if (!extractedData.tax_profile.multistate_explored) {
        extractedData.tax_profile.multistate_explored = true;
        showTyping();
        setTimeout(() => {
          hideTyping();
          addMessage('ai', `<strong>Did you work or live in any other states this year?</strong><br><small>You may need to file returns in multiple states.</small>`, [
            { label: 'No, just one state', value: 'multistate_no' },
            { label: 'Yes, worked in another state', value: 'multistate_work' },
            { label: 'Yes, moved to a new state', value: 'multistate_moved' },
            { label: 'Yes, multiple states (remote work)', value: 'multistate_remote' }
          ]);
        }, 800);
      } else {
        startIntelligentQuestioning();
      }
    }

    // Show summary of collected information before running analysis
    async function showPreliminarySummary() {
      // Reset questioning call count - flow completed successfully
      questioningState.callCount = 0;

      const profile = extractedData.tax_profile;
      const items = extractedData.tax_items;

      const filingLabel = {
        'Single': 'Single',
        'Married Filing Jointly': 'Married Filing Jointly',
        'Head of Household': 'Head of Household',
        'Married Filing Separately': 'Married Filing Separately',
        'Qualifying Surviving Spouse': 'Qualifying Surviving Spouse'
      }[profile.filing_status] || profile.filing_status;

      // Build state display
      const stateDisplay = profile.state_name || profile.state || 'Not specified';

      // Build income complexity indicator
      const isHighEarner = (profile.total_income || 0) >= 200000;
      const isVeryHighEarner = (profile.total_income || 0) >= 500000;
      const complexityIndicator = extractedData.lead_data.complexity === 'complex' ? '🔷 Complex' :
                                   extractedData.lead_data.complexity === 'moderate' ? '🔶 Moderate' : '🟢 Standard';

      // Build additional details section
      let additionalDetails = '';

      // Business details
      if (profile.is_self_employed || profile.income_source === 'Business Owner') {
        const entityLabels = {
          'sole': 'Sole Proprietorship', 'llc_single': 'Single-Member LLC',
          'llc_multi': 'Partnership/Multi-Member LLC', 'scorp': 'S-Corporation', 'ccorp': 'C-Corporation'
        };
        const bizTypeLabels = {
          'professional': 'Professional Services', 'retail': 'Retail/E-commerce',
          'realestate': 'Real Estate', 'tech': 'Tech/Software', 'service': 'Service Business'
        };

        additionalDetails += `
          <div style="margin-top: var(--space-4); padding-top: var(--space-4); border-top: 1px solid #e2e8f0;">
            <div style="font-weight: var(--font-semibold); color: var(--color-primary-500); margin-bottom: var(--space-2-5);">Business Details</div>
            ${profile.business_type ? `<div style="display: flex; justify-content: space-between; margin-bottom: var(--space-1-5);">
              <span style="color: #4a5568;">Business Type:</span>
              <strong>${bizTypeLabels[profile.business_type] || profile.business_type}</strong>
            </div>` : ''}
            ${profile.entity_type ? `<div style="display: flex; justify-content: space-between; margin-bottom: var(--space-1-5);">
              <span style="color: #4a5568;">Entity Structure:</span>
              <strong>${entityLabels[profile.entity_type] || profile.entity_type}</strong>
            </div>` : ''}
            ${profile.business_revenue ? `<div style="display: flex; justify-content: space-between; margin-bottom: var(--space-1-5);">
              <span style="color: #4a5568;">Business Revenue:</span>
              <strong>$${profile.business_revenue.toLocaleString()}</strong>
            </div>` : ''}
          </div>
        `;
      }

      // Investment details
      if (profile.has_investment_income || profile.has_rental_income) {
        const investLabels = {
          'stocks': 'Stocks & Dividends', 'rental': 'Rental Property',
          'interest': 'Interest Income', 'k1': 'Partnership/K-1', 'multiple': 'Multiple Types'
        };

        additionalDetails += `
          <div style="margin-top: var(--space-4); padding-top: var(--space-4); border-top: 1px solid #e2e8f0;">
            <div style="font-weight: var(--font-semibold); color: var(--color-primary-500); margin-bottom: var(--space-2-5);">Investment Profile</div>
            ${profile.investment_type ? `<div style="display: flex; justify-content: space-between; margin-bottom: var(--space-1-5);">
              <span style="color: #4a5568;">Investment Type:</span>
              <strong>${investLabels[profile.investment_type] || profile.investment_type}</strong>
            </div>` : ''}
            ${profile.rental_property_count ? `<div style="display: flex; justify-content: space-between; margin-bottom: var(--space-1-5);">
              <span style="color: #4a5568;">Rental Properties:</span>
              <strong>${profile.rental_property_count === '5plus' ? '5+' : profile.rental_property_count === '2_4' ? '2-4' : '1'}</strong>
            </div>` : ''}
          </div>
        `;
      }

      // Tax items collected
      const taxItemsList = [];
      if (items.mortgage_interest) taxItemsList.push(`Mortgage Interest: $${items.mortgage_interest.toLocaleString()}`);
      if (items.charitable) taxItemsList.push(`Charitable Donations: $${items.charitable.toLocaleString()}`);
      if (items.medical) taxItemsList.push(`Medical Expenses: $${items.medical.toLocaleString()}`);
      if (profile.retirement_401k) taxItemsList.push(`401(k) Contributions: $${profile.retirement_401k.toLocaleString()}`);
      if (items.childcare) taxItemsList.push(`Childcare Expenses: $${items.childcare.toLocaleString()}`);

      if (taxItemsList.length > 0) {
        additionalDetails += `
          <div style="margin-top: var(--space-4); padding-top: var(--space-4); border-top: 1px solid #e2e8f0;">
            <div style="font-weight: var(--font-semibold); color: var(--color-primary-500); margin-bottom: var(--space-2-5);">Deductions & Credits</div>
            ${taxItemsList.map(item => `<div style="color: #4a5568; font-size: var(--text-xs-plus); margin-bottom: var(--space-1);">• ${item}</div>`).join('')}
          </div>
        `;
      }

      // Life event
      if (profile.life_event_type) {
        const eventLabels = {
          'marriage': 'Getting married', 'baby': 'Having a baby', 'home': 'Buying a home',
          'business': 'Starting a business', 'retirement': 'Retiring soon', 'sale': 'Selling major asset'
        };
        additionalDetails += `
          <div style="margin-top: var(--space-4); padding-top: var(--space-4); border-top: 1px solid #e2e8f0;">
            <div style="display: flex; justify-content: space-between;">
              <span style="color: #4a5568;">Life Event:</span>
              <strong>${eventLabels[profile.life_event_type] || profile.life_event_type}</strong>
            </div>
          </div>
        `;
      }

      addMessage('ai', `
        <div style="margin-bottom: var(--space-4);">
          <strong style="font-size: var(--text-lg); color: var(--color-primary-500);">Your Tax Profile Summary</strong>
          <div style="margin-top: var(--space-2); display: inline-block; background: var(--color-accent-50); color: var(--color-accent-500); padding: var(--space-1) var(--space-3); border-radius: var(--radius-xl); font-size: var(--text-xs); font-weight: var(--font-semibold);">
            ${complexityIndicator} Tax Situation
          </div>
        </div>

        <div style="background: #f7fafc; border-radius: var(--radius-lg); padding: var(--space-4); margin-bottom: var(--space-4);">
          <div style="display: grid; gap: var(--space-2-5);">
            <div style="display: flex; justify-content: space-between;">
              <span style="color: #4a5568;">Filing Status:</span>
              <strong>${filingLabel}</strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: #4a5568;">State:</span>
              <strong>${stateDisplay}</strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: #4a5568;">Total Income:</span>
              <strong style="${isVeryHighEarner ? 'color: #276749;' : ''}">$${(profile.total_income || 0).toLocaleString()}</strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: #4a5568;">Income Source:</span>
              <strong>${profile.income_source || 'Not specified'}</strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: #4a5568;">Dependents:</span>
              <strong>${profile.dependents || 0}${profile.has_young_children ? ' (includes young children)' : profile.has_college_students ? ' (includes college students)' : ''}</strong>
            </div>
            ${profile.primary_goal ? `<div style="display: flex; justify-content: space-between;">
              <span style="color: #4a5568;">Primary Goal:</span>
              <strong>${profile.primary_goal === 'reduce_taxes' ? 'Reduce Tax Bill' :
                        profile.primary_goal === 'retirement' ? 'Maximize Retirement' :
                        profile.primary_goal === 'wealth' ? 'Build Wealth' :
                        profile.primary_goal === 'life_event' ? 'Life Event Planning' : 'Tax Optimization'}</strong>
            </div>` : ''}
          </div>

          ${additionalDetails}
        </div>

        <div style="font-size: var(--text-sm); color: #4a5568; line-height: 1.6;">
          ${isVeryHighEarner ? '<strong>High-income analysis:</strong> I\'ll identify advanced strategies including Backdoor Roth, tax-loss harvesting, and deferred compensation options.<br><br>' : ''}
          ${profile.is_self_employed ? '<strong>Business owner analysis:</strong> I\'ll evaluate entity structure optimization, QBI deduction, and self-employment tax strategies.<br><br>' : ''}
          Ready to run your personalized tax analysis and identify savings opportunities.
        </div>
      `, [
        { label: 'Run Full Analysis →', value: 'run_full_analysis', primary: true },
        { label: 'Edit my information', value: 'edit_profile' }
      ]);
    }

    async function performTaxCalculation() {
      // Show loading overlay for better UX
      showLoadingOverlay('Analyzing Your Tax Situation', 'Running 30+ optimization strategies...');

      const analysis = await getIntelligentAnalysis();

      // Hide loading overlay
      hideLoadingOverlay();

      // Clear any previous error banners
      clearErrorBanner();

      if (analysis && analysis.calculation) {
        const calc = analysis.calculation;
        const strategies = analysis.strategies || [];
        const totalSavings = analysis.totalSavings || 0;

        // Store for later use
        taxCalculations = calc;
        taxStrategies = strategies;

        // Phase 1: Show initial tax breakdown
        addMessage('ai', `
          <div style="margin-bottom: var(--space-5);">
            <span style="font-size: var(--text-lg); font-weight: var(--font-bold); color: var(--color-primary-500);">Tax Analysis Complete</span>
          </div>

          <div style="background: #f7fafc; border: 1px solid #e2e8f0; border-radius: var(--radius-lg); padding: var(--space-5); margin-bottom: var(--space-5);">
            <div style="font-size: var(--text-xs-plus); color: #4a5568; margin-bottom: var(--space-4); text-transform: uppercase; letter-spacing: 0.5px;">Your 2025 Tax Summary</div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); margin-bottom: var(--space-4);">
              <div>
                <div style="font-size: var(--text-xs); color: #718096;">Federal Tax</div>
                <div style="font-size: 22px; font-weight: var(--font-bold); color: var(--color-primary-500);">$${Math.round(calc.federal_tax).toLocaleString()}</div>
              </div>
              <div>
                <div style="font-size: var(--text-xs); color: #718096;">State Tax</div>
                <div style="font-size: 22px; font-weight: var(--font-bold); color: var(--color-primary-500);">$${Math.round(calc.state_tax).toLocaleString()}</div>
              </div>
            </div>

            <div style="border-top: 1px solid #e2e8f0; padding-top: var(--space-4); display: flex; justify-content: space-between; align-items: center;">
              <div>
                <div style="font-size: var(--text-xs); color: #718096;">Total Tax Liability</div>
                <div style="font-size: 26px; font-weight: var(--font-extrabold); color: var(--color-primary-500);">$${Math.round(calc.total_tax).toLocaleString()}</div>
              </div>
              <div style="text-align: right;">
                <div style="font-size: var(--text-xs); color: #718096;">Effective Rate</div>
                <div style="font-size: var(--text-xl); font-weight: var(--font-bold); color: var(--color-primary-400);">${calc.effective_rate}%</div>
              </div>
            </div>
          </div>

          <div style="font-size: var(--text-sm); color: #4a5568; line-height: 1.6;">
            Based on your profile, I've identified <strong>${strategies.length} tax optimization strategies</strong> that could potentially save you <strong style="color: #276749;">$${Math.round(totalSavings).toLocaleString()}</strong>.
          </div>

          <div style="margin-top: var(--space-4); font-size: var(--text-sm); color: #4a5568;">
            Would you like me to walk you through each strategy in detail?
          </div>
        `, [
          { label: 'Yes, show me the strategies', value: 'explore_strategies', primary: true },
          { label: 'Skip to summary', value: 'quick_summary' }
        ]);

        // Update lead score and progress
        extractedData.lead_data.estimated_savings = totalSavings;
        calculateLeadScore();
        updateProgress(75);

        if (extractedData.lead_data.score >= 60) {
          sendLeadToCPA();
        }
      } else {
        // Debug: Show what data we have
        DevLogger.error('Analysis failed. Current data:', {
          filing_status: extractedData.tax_profile.filing_status,
          total_income: extractedData.tax_profile.total_income,
          dependents: extractedData.tax_profile.dependents
        });

        // Provide helpful error message based on what's missing
        let missingFields = [];
        if (!extractedData.tax_profile.filing_status) missingFields.push('filing status');
        if (!extractedData.tax_profile.total_income) missingFields.push('income');

        if (missingFields.length > 0) {
          addMessage('ai', `I need your ${missingFields.join(' and ')} to complete the analysis. Could you provide that information?`, [
            { label: 'Single', value: 'filing_single' },
            { label: 'Married Filing Jointly', value: 'filing_married' },
            { label: '$50K - $100K', value: 'income_50_100k' },
            { label: '$100K - $200K', value: 'income_100_200k' }
          ]);
        } else {
          // We have the data but API failed - show error and retry option
          addMessage('ai', `I encountered an issue analyzing your data. Let me try again.`, [
            { label: 'Retry Analysis', value: 'retry_analysis', primary: true },
            { label: 'Start Over', value: 'reset_conversation' }
          ]);
        }
        document.getElementById('userInput').focus();
      }
    }

    // Show all strategies in detail
    function showAllStrategies() {
      if (!taxStrategies || taxStrategies.length === 0) {
        addMessage('ai', `I haven't analyzed your strategies yet. Let me calculate your tax situation first.`);
        performTaxCalculation();
        return;
      }

      let strategyHTML = `
        <div style="margin-bottom: var(--space-5);">
          <span style="font-size: var(--text-xl); font-weight: var(--font-bold); color: var(--accent-light);">Your Personalized Tax Strategies</span>
          <div style="font-size: var(--text-sm); color: var(--text-secondary); margin-top: var(--space-2);">
            ${taxStrategies.length} strategies • Total potential savings: $${taxStrategies.reduce((sum, s) => sum + s.estimated_savings, 0).toLocaleString()}
          </div>
        </div>
      `;

      taxStrategies.forEach((strategy, index) => {
        const priorityColors = {
          'high': '#10b981',
          'medium': '#f59e0b',
          'low': '#64748b'
        };
        const priorityColor = priorityColors[strategy.priority] || '#64748b';

        strategyHTML += `
          <div class="insight-card" style="margin: var(--space-4) 0; padding: var(--space-5);">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: var(--space-3);">
              <div>
                <span style="background: ${priorityColor}; color: white; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-base); font-size: var(--text-2xs); font-weight: var(--font-semibold); text-transform: uppercase; margin-right: var(--space-2);">${strategy.priority}</span>
                <span style="background: var(--surface-light); color: var(--text-secondary); padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-base); font-size: var(--text-2xs);">${strategy.category}</span>
              </div>
              <div class="savings-amount" style="font-size: var(--text-xl);">$${Math.round(strategy.estimated_savings).toLocaleString()}</div>
            </div>
            <div style="font-size: var(--text-base); font-weight: var(--font-semibold); color: var(--accent-light); margin-bottom: var(--space-2);">${strategy.title}</div>
            <div style="font-size: var(--text-sm); color: var(--text-secondary); margin-bottom: var(--space-3);">${strategy.summary}</div>
            <details style="cursor: pointer;">
              <summary style="color: var(--accent-light); font-weight: var(--font-medium);">View Details & Action Steps</summary>
              <div style="padding: var(--space-3) 0; font-size: var(--text-xs-plus); color: var(--text-secondary); white-space: pre-line;">${strategy.detailed_explanation}</div>
              <div style="margin-top: var(--space-3);">
                <strong style="font-size: var(--text-xs-plus);">Action Steps:</strong>
                <ul style="margin: var(--space-2) 0 0 var(--space-5); font-size: var(--text-xs-plus); color: var(--text-secondary);">
                  ${strategy.action_steps.map(step => `<li style="margin: var(--space-1) 0;">${step}</li>`).join('')}
                </ul>
              </div>
              ${strategy.irs_reference ? `<div style="margin-top: var(--space-3); font-size: var(--text-xs); color: var(--text-muted);">📚 Reference: ${strategy.irs_reference}</div>` : ''}
            </details>
          </div>
        `;
      });

      strategyHTML += `<div style="margin-top: var(--space-5);"><strong>Ready to implement these strategies?</strong></div>`;

      addMessage('ai', strategyHTML, [
        { label: 'Generate My Report →', value: 'generate_report', primary: true },
        { label: 'Connect with CPA', value: 'request_cpa_early' },
        { label: 'Ask a Question', value: 'ask_question' }
      ]);

      updateProgress(85);
    }

    // ===================================================================
    // CPA LEAD HANDOFF
    // ===================================================================

    async function sendLeadToCPA() {
      if (!extractedData.lead_data.ready_for_cpa) {
        return false;
      }

      try {
        // SECURITY: Use secureFetch for CSRF protection
        const response = await secureFetch('/api/leads/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contact: extractedData.contact,
            tax_profile: extractedData.tax_profile,
            tax_items: extractedData.tax_items,
            lead_score: extractedData.lead_data.score,
            complexity: extractedData.lead_data.complexity,
            estimated_savings: extractedData.lead_data.estimated_savings,
            session_id: sessionId,
            source: 'intelligent_advisor',
            status: 'qualified'
          })
        });

        return response.ok;
      } catch (error) {
        DevLogger.error('Lead handoff error:', error);
        return false;
      }
    }

    async function captureIncome() {
      const incomeInput = document.getElementById('incomeInput');
      const rawValue = incomeInput ? incomeInput.value.replace(/[^0-9]/g, '') : '0';
      const income = parseInt(rawValue, 10);

      // Validate income - must be positive and reasonable (max $50M for individuals)
      if (!income || income <= 0) {
        showToast('Please enter a valid income amount', 'error');
        if (incomeInput) incomeInput.focus();
        return;
      }

      if (income > 50000000) {
        showToast('Please verify this amount - it seems unusually high', 'warning');
      }

      // Mark as user-confirmed to prevent AI from overwriting
      setConfirmedValues({
        'tax_profile.total_income': income,
        'tax_profile.w2_income': income
      });
      extractedData.lead_data.score += 15;
      addMessage('user', `$${income.toLocaleString()}`);
      updateStats({ total_income: income });
      calculateLeadScore();

      startIntelligentQuestioning();
    }

    // Helper to continue deduction flow or move to credits
    function askNextDeductionOrCredits() {
      const deductions = extractedData.deductions || [];

      // If user has selected deductions, offer to continue or move to credits
      if (deductions.length > 0) {
        addMessage('ai', `Any other deductions?`, [
          { label: 'Mortgage', value: 'has_mortgage' },
          { label: 'Charity', value: 'has_charity' },
          { label: 'Medical', value: 'has_medical' },
          { label: 'Done, continue →', value: 'deductions_done' }
        ]);
      } else {
        // Move to credits
        addMessage('ai', `Any tax credits you might qualify for?`, [
          { label: 'Child Tax Credit', value: 'credit_child' },
          { label: 'Education Credit', value: 'credit_education' },
          { label: 'Skip to report →', value: 'generate_report' }
        ]);
      }
    }

    async function analyzeDeductions() {
      showTyping();
      setTimeout(() => {
        hideTyping();
        addMessage('ai', `Which deductions apply to you?`, [
          { label: 'Mortgage', value: 'has_mortgage' },
          { label: 'Charity', value: 'has_charity' },
          { label: 'Medical', value: 'has_medical' },
          { label: 'Business', value: 'has_business' },
          { label: 'Retirement', value: 'has_retirement' },
          { label: 'None / Skip →', value: 'deductions_done' }
        ]);
      }, 800);
    }

    async function requestCPAConnection() {
      showTyping();
      await sendLeadToCPA();

      setTimeout(() => {
        hideTyping();
        const savings = Math.round(extractedData.lead_data.estimated_savings || 0).toLocaleString();

        addMessage('ai', `I've notified our CPA team about your <strong>$${savings}</strong> savings opportunity. They'll reach out within 24 hours.<br><br>What would you like to do next?`, [
          { label: 'Schedule a call', value: 'schedule_time' },
          { label: 'Just email me', value: 'email_only' },
          { label: 'Get my report first', value: 'generate_report' }
        ]);
      }, 1500);
    }

    // Make functions globally accessible
    window.handleQuickAction = handleQuickAction;
    window.sendReportEmail = sendReportEmail;
    window.sendMessage = sendMessage;
    window.captureName = captureName;
    window.captureEmail = captureEmail;
    window.captureIncome = captureIncome;

    // Initialize on load
    window.addEventListener('DOMContentLoaded', () => {
      DevLogger.log('Page loaded, initializing...');
      const messagesContainer = document.getElementById('messages');
      DevLogger.log('Messages container found:', messagesContainer);

      // Reset questioning state on page load for clean start
      resetQuestioningState();
      retryCount = 0;

      // Check initial connection status
      updateConnectionStatus(navigator.onLine);

      // Start health check monitoring
      startHealthCheck();

      // Attach event listeners to initial quick action buttons
      const initialButtons = document.querySelectorAll('#initialQuickActions button[data-action]');
      DevLogger.log('Found initial buttons:', initialButtons.length);

      initialButtons.forEach(button => {
        button.addEventListener('click', function(e) {
          e.preventDefault();
          e.stopPropagation();
          const action = this.getAttribute('data-action');
          DevLogger.log('Initial button clicked:', action);
          DevLogger.log('Button element:', this);

          // Disable button temporarily to prevent double clicks
          this.disabled = true;
          setTimeout(() => {
            this.disabled = false;
          }, 2000);

          handleQuickAction(action);
        });
      });

      // Also add click handlers to any buttons added later via event delegation
      document.addEventListener('click', function(e) {
        if (e.target.classList.contains('quick-action') && e.target.dataset.action) {
          e.preventDefault();
          const action = e.target.dataset.action;
          DevLogger.log('Delegated button clicked:', action);
          handleQuickAction(action);
        }
      });

      // Check unified consent before initializing session
      if (checkAdvisorConsent()) {
        // Check for existing session first
        checkForExistingSession().then(sessionData => {
          if (sessionData) {
            // Found existing session - show resume banner
            sessionId = sessionData.session_id;
            showResumeBanner(sessionData);
          }
          // Initialize session (will use existing or create new)
          initializeSession();
          // Start auto-save
          startAutoSave();
        });
      }

      setTimeout(() => {
        const input = document.getElementById('userInput');
        if (input) input.focus();
      }, 100);
    });

    // =================================================================
    // REAL-TIME FORM VALIDATION UTILITIES
    // =================================================================

    const ValidationUtils = {
      // SSN validation (XXX-XX-XXXX)
      validateSSN: function(ssn) {
        const clean = ssn.replace(/[^0-9]/g, '');
        if (clean.length !== 9) {
          return { valid: false, message: 'SSN must be 9 digits' };
        }
        if (clean === '000000000' || clean.startsWith('000') || clean.startsWith('666') || clean.startsWith('9')) {
          return { valid: false, message: 'Invalid SSN format' };
        }
        return { valid: true, formatted: `${clean.slice(0,3)}-${clean.slice(3,5)}-${clean.slice(5)}` };
      },

      // EIN validation (XX-XXXXXXX)
      validateEIN: function(ein) {
        const clean = ein.replace(/[^0-9]/g, '');
        if (clean.length !== 9) {
          return { valid: false, message: 'EIN must be 9 digits' };
        }
        return { valid: true, formatted: `${clean.slice(0,2)}-${clean.slice(2)}` };
      },

      // Currency validation
      validateCurrency: function(value, fieldName = 'Amount', options = {}) {
        const clean = value.replace(/[$,\s]/g, '');
        const num = parseFloat(clean);

        if (isNaN(num)) {
          return { valid: false, message: `${fieldName} must be a valid number` };
        }
        if (!options.allowNegative && num < 0) {
          return { valid: false, message: `${fieldName} cannot be negative` };
        }
        if (options.max && num > options.max) {
          return { valid: false, message: `${fieldName} cannot exceed $${options.max.toLocaleString()}` };
        }
        if (options.min && num < options.min) {
          return { valid: false, message: `${fieldName} must be at least $${options.min.toLocaleString()}` };
        }
        return { valid: true, value: num, formatted: `$${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` };
      },

      // Date validation
      validateDate: function(dateStr, fieldName = 'Date') {
        const formats = [
          /^\d{4}-\d{2}-\d{2}$/,  // YYYY-MM-DD
          /^\d{2}\/\d{2}\/\d{4}$/, // MM/DD/YYYY
        ];

        if (!formats.some(f => f.test(dateStr))) {
          return { valid: false, message: `${fieldName} format should be MM/DD/YYYY or YYYY-MM-DD` };
        }

        const date = new Date(dateStr);
        if (isNaN(date.getTime())) {
          return { valid: false, message: `${fieldName} is not a valid date` };
        }
        return { valid: true, date: date };
      },

      // Apply validation state to input element
      applyValidationState: function(input, result) {
        // Remove existing states
        input.classList.remove('field-valid', 'field-error', 'field-warning');

        // Find or create validation message element
        let msgEl = input.parentElement.querySelector('.validation-message');
        if (!msgEl) {
          msgEl = document.createElement('div');
          msgEl.className = 'validation-message';
          input.parentElement.appendChild(msgEl);
        }

        if (result.valid) {
          input.classList.add('field-valid');
          msgEl.className = 'validation-message success';
          msgEl.textContent = result.message || '✓ Valid';
        } else {
          input.classList.add('field-error');
          msgEl.className = 'validation-message error';
          msgEl.textContent = result.message;
        }

        // Auto-hide success message after 2 seconds
        if (result.valid) {
          setTimeout(() => {
            msgEl.style.display = 'none';
          }, 2000);
        }
      },

      // Debounce function for real-time validation
      debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
          const later = () => {
            clearTimeout(timeout);
            func(...args);
          };
          clearTimeout(timeout);
          timeout = setTimeout(later, wait);
        };
      }
    };

    // Progress indicator utility
    const ProgressIndicator = {
      container: null,
      bar: null,
      text: null,

      create: function(parentEl) {
        this.container = document.createElement('div');
        this.container.className = 'progress-container';
        this.container.innerHTML = `
          <div class="progress-bar" style="width: 0%"></div>
        `;
        this.text = document.createElement('div');
        this.text.className = 'progress-text';

        parentEl.appendChild(this.container);
        parentEl.appendChild(this.text);

        this.bar = this.container.querySelector('.progress-bar');
        return this;
      },

      update: function(percent, message) {
        if (this.bar) {
          this.bar.style.width = `${Math.min(100, Math.max(0, percent))}%`;
        }
        if (this.text && message) {
          this.text.textContent = message;
        }
      },

      remove: function() {
        if (this.container) this.container.remove();
        if (this.text) this.text.remove();
      }
    };

    // Loading skeleton utility
    const SkeletonLoader = {
      show: function(container, count = 3) {
        const skeletons = [];
        for (let i = 0; i < count; i++) {
          const skeleton = document.createElement('div');
          skeleton.className = 'skeleton skeleton-message';
          skeleton.style.width = `${50 + Math.random() * 30}%`;
          skeleton.style.marginLeft = i % 2 === 0 ? '0' : 'auto';
          container.appendChild(skeleton);
          skeletons.push(skeleton);
        }
        return skeletons;
      },

      hide: function(skeletons) {
        skeletons.forEach(s => s.remove());
      }
    };

    // Mobile keyboard handling
    if (/iPhone|iPad|iPod|Android/i.test(navigator.userAgent)) {
      const input = document.getElementById('userInput');
      if (input) {
        input.addEventListener('focus', function() {
          // Scroll to input when focused on mobile
          setTimeout(() => {
            this.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }, 300);
        });
      }
    }

    // ===================================================================
    // PHASE 3: UX/VISUAL FLOW IMPROVEMENTS
    // ===================================================================

    // Phase 3.1: Upload Progress Percentage with XMLHttpRequest
    async function uploadFileWithProgress(file) {
      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        const formData = new FormData();
        formData.append('file', file);
        formData.append('session_id', sessionId);

        // Create progress UI
        const progressContainer = document.createElement('div');
        progressContainer.className = 'upload-progress-container';
        progressContainer.innerHTML = `
          <div class="upload-progress-info">
            <span class="upload-filename">${file.name}</span>
            <span class="upload-percent">0%</span>
          </div>
          <div class="upload-progress-bar">
            <div class="upload-progress-fill" style="width: 0%"></div>
          </div>
        `;
        const messagesContainer = document.getElementById('messages');
        if (messagesContainer) {
          messagesContainer.appendChild(progressContainer);
          messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        const progressFill = progressContainer.querySelector('.upload-progress-fill');
        const progressPercent = progressContainer.querySelector('.upload-percent');

        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const percent = Math.round((e.loaded / e.total) * 100);
            progressFill.style.width = percent + '%';
            progressPercent.textContent = percent + '%';
          }
        });

        xhr.onload = () => {
          progressContainer.remove();
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              resolve(JSON.parse(xhr.responseText));
            } catch (e) {
              reject(new Error('Invalid response'));
            }
          } else {
            reject(new Error(`Upload failed: ${xhr.status}`));
          }
        };

        xhr.onerror = () => {
          progressContainer.remove();
          reject(new Error('Network error'));
        };

        xhr.open('POST', '/api/ai-chat/analyze-document');
        xhr.send(formData);
      });
    }

    // Phase 3.3: Enhanced Keyboard Navigation
    function initEnhancedKeyboardNav() {
      document.addEventListener('keydown', (e) => {
        // Escape: Close modals
        if (e.key === 'Escape') {
          closeUploadOptions();
          closeFilePreview();
          const modals = document.querySelectorAll('.modal-overlay, .upload-options-modal.visible');
          modals.forEach(m => m.remove());
        }

        // Tab: Navigate quick actions -> input
        if (e.key === 'Tab') {
          const quickActions = document.querySelectorAll('.quick-action:not(:disabled)');
          const input = document.getElementById('userInput');
          if (quickActions.length > 0 && document.activeElement === input && !e.shiftKey) {
            e.preventDefault();
            quickActions[0].focus();
          }
        }

        // Arrow keys for quick actions
        if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
          const quickActions = Array.from(document.querySelectorAll('.quick-action:not(:disabled)'));
          const currentIdx = quickActions.indexOf(document.activeElement);
          if (currentIdx >= 0) {
            e.preventDefault();
            const newIdx = e.key === 'ArrowRight'
              ? (currentIdx + 1) % quickActions.length
              : (currentIdx - 1 + quickActions.length) % quickActions.length;
            quickActions[newIdx].focus();
          }
        }

        // Enter: Select focused action
        if (e.key === 'Enter' && document.activeElement.classList.contains('quick-action')) {
          e.preventDefault();
          document.activeElement.click();
        }
      });
    }
    initEnhancedKeyboardNav();

    // Phase 3.4: Actionable Error Messages
    const ERROR_ACTIONS = {
      network: {
        message: "Connection lost. Please check your internet.",
        actions: [
          { label: "Retry", action: () => retryLastAction() },
          { label: "Work Offline", action: () => enableOfflineMode() }
        ]
      },
      rate_limit: {
        message: "Too many requests. Please wait a moment.",
        actions: [
          { label: "Wait 30s", action: () => showCountdown(30) }
        ]
      },
      upload_failed: {
        message: "Upload failed.",
        actions: [
          { label: "Retry", action: () => retryLastUpload() },
          { label: "Try smaller file", action: () => showFileSizeHint() }
        ]
      },
      timeout: {
        message: "Request timed out.",
        actions: [
          { label: "Retry", action: () => retryLastAction() }
        ]
      }
    };

    let lastAction = null;
    let lastUploadFile = null;

    function showActionableError(errorType, customMessage) {
      const errorConfig = ERROR_ACTIONS[errorType] || {
        message: customMessage || "Something went wrong.",
        actions: [{ label: "Retry", action: () => retryLastAction() }]
      };

      const errorDiv = document.createElement('div');
      errorDiv.className = 'actionable-error';
      errorDiv.innerHTML = `
        <div class="error-message">${errorConfig.message}</div>
        <div class="error-actions">
          ${errorConfig.actions.map((a, i) =>
            `<button class="error-action-btn" data-idx="${i}">${a.label}</button>`
          ).join('')}
        </div>
      `;

      errorConfig.actions.forEach((a, i) => {
        const btn = errorDiv.querySelector(`[data-idx="${i}"]`);
        if (btn) btn.onclick = a.action;
      });

      const messages = document.getElementById('messages');
      if (messages) {
        messages.appendChild(errorDiv);
        messages.scrollTop = messages.scrollHeight;
      }
    }

    function retryLastAction() {
      if (lastAction) lastAction();
    }

    function retryLastUpload() {
      if (lastUploadFile) {
        handleValidatedUpload(lastUploadFile);
      }
    }

    function showCountdown(seconds) {
      showToast(`Please wait ${seconds} seconds...`, 'info');
      setTimeout(() => {
        showToast('You can try again now', 'success');
      }, seconds * 1000);
    }

    function showFileSizeHint() {
      showToast('Try a file under 10MB, or compress images before uploading', 'info');
    }

    function enableOfflineMode() {
      showToast('Offline mode enabled. Your data will be saved locally.', 'info');
    }

    // Phase 3.5: Offline Detection
    // Note: isOnline and offlineQueue already declared earlier in the file

    function showOfflineBanner() {
      if (document.getElementById('offlineBanner')) return;
      const banner = document.createElement('div');
      banner.id = 'offlineBanner';
      banner.className = 'offline-banner';
      banner.innerHTML = `
        <span>📡 You're offline. Messages will be sent when connection is restored.</span>
      `;
      document.body.prepend(banner);
    }

    function hideOfflineBanner() {
      const banner = document.getElementById('offlineBanner');
      if (banner) {
        banner.classList.add('fade-out');
        setTimeout(() => banner.remove(), 300);
      }
    }

    // Note: processOfflineQueue is defined earlier in the file (async version at ~line 4070)
    // Do NOT redefine it here to avoid race conditions with parallel message processing

    window.addEventListener('offline', () => {
      isOnline = false;
      showOfflineBanner();
    });

    window.addEventListener('online', async () => {
      isOnline = true;
      hideOfflineBanner();
      // Use the async version defined earlier to process messages sequentially
      await processOfflineQueue();
    });

    // ===================================================================
    // PHASE 4: DOCUMENT HANDLING IMPROVEMENTS
    // ===================================================================

    // Phase 4.1: Client-Side File Validation
    function validateFile(file) {
      const errors = [];
      const maxSize = 50 * 1024 * 1024; // 50MB
      const minSize = 1024; // 1KB

      if (file.size > maxSize) {
        errors.push(`File exceeds 50MB limit (${(file.size / 1024 / 1024).toFixed(1)}MB)`);
      }

      if (file.size < minSize) {
        errors.push("File too small - may be corrupted");
      }

      const ext = file.name.split('.').pop().toLowerCase();
      const allowedExts = ['pdf', 'png', 'jpg', 'jpeg', 'heic', 'gif', 'webp'];
      if (!allowedExts.includes(ext)) {
        errors.push(`Unsupported file type: .${ext}. Allowed: PDF, PNG, JPG, HEIC`);
      }

      // Check MIME type
      const allowedMimes = [
        'application/pdf',
        'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/heic'
      ];
      if (file.type && !allowedMimes.includes(file.type)) {
        errors.push(`Invalid file format: ${file.type}`);
      }

      return {
        isValid: errors.length === 0,
        errors: errors
      };
    }

    // Phase 4.2: File Preview Before Upload
    let pendingUploadFile = null;

    function showFilePreview(file) {
      const validation = validateFile(file);
      if (!validation.isValid) {
        showToast(validation.errors[0], 'error');
        return;
      }

      pendingUploadFile = file;
      lastUploadFile = file;

      const modal = document.createElement('div');
      modal.className = 'file-preview-modal';
      modal.id = 'filePreviewModal';

      const isPDF = file.type === 'application/pdf';

      modal.innerHTML = `
        <div class="file-preview-content">
          <button class="close-preview-btn" onclick="closeFilePreview()">&times;</button>
          <h3>📄 Confirm Upload</h3>
          <div class="preview-container">
            ${isPDF
              ? `<div class="pdf-preview"><span class="pdf-icon">📑</span><span>${file.name}</span></div>`
              : `<img id="imagePreview" class="image-preview" alt="Preview" />`
            }
          </div>
          <div class="file-info">
            <span>${file.name}</span>
            <span>${(file.size / 1024).toFixed(1)} KB</span>
          </div>
          <div class="preview-actions">
            <button class="preview-cancel" onclick="closeFilePreview()">Cancel</button>
            <button class="preview-confirm" onclick="confirmUpload()">Upload</button>
          </div>
        </div>
      `;

      document.body.appendChild(modal);

      // Load image preview
      if (!isPDF) {
        const reader = new FileReader();
        reader.onload = (e) => {
          const img = document.getElementById('imagePreview');
          if (img) img.src = e.target.result;
        };
        reader.readAsDataURL(file);
      }

      requestAnimationFrame(() => modal.classList.add('visible'));
    }

    function closeFilePreview() {
      const modal = document.getElementById('filePreviewModal');
      if (modal) {
        modal.classList.remove('visible');
        setTimeout(() => modal.remove(), 300);
      }
      pendingUploadFile = null;
    }

    function confirmUpload() {
      if (pendingUploadFile) {
        handleValidatedUpload(pendingUploadFile);
        closeFilePreview();
      }
    }

    // Phase 4.3: Parallel Uploads with Progress
    async function uploadFilesParallel(files) {
      const fileArray = Array.from(files);
      const validated = fileArray.filter(f => validateFile(f).isValid);
      const invalid = fileArray.filter(f => !validateFile(f).isValid);

      if (invalid.length > 0) {
        showToast(`${invalid.length} file(s) skipped due to validation errors`, 'warning');
      }

      if (validated.length === 0) {
        showToast('No valid files to upload', 'error');
        return;
      }

      // Process uploads SEQUENTIALLY to prevent race conditions on extractedData
      // Each upload may modify extractedData, so we must wait for each to complete
      const results = [];
      for (const file of validated) {
        try {
          const result = await uploadWithRetry(file);
          results.push({ status: 'fulfilled', value: result });
        } catch (error) {
          results.push({ status: 'rejected', reason: error });
        }
      }

      const succeeded = results.filter(r => r.status === 'fulfilled').length;
      const failed = results.filter(r => r.status === 'rejected').length;

      if (succeeded > 0) {
        showToast(`Uploaded ${succeeded} of ${validated.length} file(s)`, 'success');
      }
      if (failed > 0) {
        showToast(`${failed} file(s) failed to upload`, 'error');
      }

      return results;
    }

    // Phase 4.4: Retry Mechanism with Exponential Backoff
    async function uploadWithRetry(file, maxRetries = 3) {
      for (let i = 0; i < maxRetries; i++) {
        try {
          return await uploadFileWithProgress(file);
        } catch (e) {
          DevLogger.warn(`Upload attempt ${i + 1} failed:`, e.message);
          if (i === maxRetries - 1) {
            showActionableError('upload_failed');
            throw e;
          }
          // Exponential backoff: 1s, 2s, 4s
          await new Promise(r => setTimeout(r, 1000 * Math.pow(2, i)));
        }
      }
    }

    async function handleValidatedUpload(file) {
      addMessage('user', `Uploading: ${file.name}`);
      showTyping();

      try {
        const data = await uploadWithRetry(file);
        hideTyping();

        addMessage('ai', data.ai_response, data.quick_actions || []);

        if (data.extracted_data) {
          // Use safe merge to prevent overwriting confirmed data and handle nested objects
          await updateExtractedDataSafe(data.extracted_data, 'document_upload');
        }

        updateProgress(data.completion_percentage || 0);
        updateStats(data.extracted_summary || {});
        updatePhaseFromData();
      } catch (error) {
        hideTyping();
        // Error already shown by uploadWithRetry
      }
    }

    // Phase 4.5: Camera Preview Before Capture
    const PhotoCaptureEnhanced = {
      stream: null,
      videoElement: null,
      previewCanvas: null,
      capturedImage: null,

      open: function() {
        const modal = document.createElement('div');
        modal.className = 'camera-modal';
        modal.id = 'cameraModal';
        modal.innerHTML = `
          <div class="camera-content">
            <button class="close-camera-btn" onclick="PhotoCaptureEnhanced.close()">&times;</button>
            <h3>📷 Capture Document</h3>
            <div class="camera-container">
              <video id="cameraVideo" autoplay playsinline></video>
              <canvas id="cameraCanvas" style="display: none;"></canvas>
              <div id="capturePreview" class="capture-preview" style="display: none;">
                <img id="capturedImg" alt="Captured" />
              </div>
            </div>
            <div class="camera-controls">
              <button id="captureBtn" class="camera-btn capture" onclick="PhotoCaptureEnhanced.capture()">
                📸 Capture
              </button>
              <button id="retakeBtn" class="camera-btn retake" style="display: none;" onclick="PhotoCaptureEnhanced.retake()">
                🔄 Retake
              </button>
              <button id="usePhotoBtn" class="camera-btn use" style="display: none;" onclick="PhotoCaptureEnhanced.usePhoto()">
                ✓ Use Photo
              </button>
            </div>
          </div>
        `;
        document.body.appendChild(modal);
        requestAnimationFrame(() => modal.classList.add('visible'));
        this.startCamera();
      },

      startCamera: async function() {
        try {
          this.stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment' }
          });
          this.videoElement = document.getElementById('cameraVideo');
          if (this.videoElement) {
            this.videoElement.srcObject = this.stream;
          }
        } catch (e) {
          showToast('Camera access denied. Please allow camera permissions.', 'error');
          this.close();
        }
      },

      capture: function() {
        const video = document.getElementById('cameraVideo');
        const canvas = document.getElementById('cameraCanvas');
        const preview = document.getElementById('capturePreview');
        const capturedImg = document.getElementById('capturedImg');

        if (video && canvas) {
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          const ctx = canvas.getContext('2d');
          ctx.drawImage(video, 0, 0);

          this.capturedImage = canvas.toDataURL('image/jpeg', 0.9);
          capturedImg.src = this.capturedImage;

          video.style.display = 'none';
          preview.style.display = 'block';
          const captureBtn = document.getElementById('captureBtn');
          const retakeBtn = document.getElementById('retakeBtn');
          const usePhotoBtn = document.getElementById('usePhotoBtn');
          if (captureBtn) captureBtn.style.display = 'none';
          if (retakeBtn) retakeBtn.style.display = 'inline-block';
          if (usePhotoBtn) usePhotoBtn.style.display = 'inline-block';
        }
      },

      retake: function() {
        const video = document.getElementById('cameraVideo');
        const preview = document.getElementById('capturePreview');
        const captureBtn = document.getElementById('captureBtn');
        const retakeBtn = document.getElementById('retakeBtn');
        const usePhotoBtn = document.getElementById('usePhotoBtn');

        if (video) video.style.display = 'block';
        if (preview) preview.style.display = 'none';
        if (captureBtn) captureBtn.style.display = 'inline-block';
        if (retakeBtn) retakeBtn.style.display = 'none';
        if (usePhotoBtn) usePhotoBtn.style.display = 'none';

        this.capturedImage = null;
      },

      usePhoto: async function() {
        if (!this.capturedImage) return;

        // Convert data URL to File
        const res = await fetch(this.capturedImage);
        const blob = await res.blob();
        const file = new File([blob], `capture_${Date.now()}.jpg`, { type: 'image/jpeg' });

        this.close();
        handleValidatedUpload(file);
      },

      close: function() {
        if (this.stream) {
          this.stream.getTracks().forEach(track => track.stop());
          this.stream = null;
        }
        const modal = document.getElementById('cameraModal');
        if (modal) {
          modal.classList.remove('visible');
          setTimeout(() => modal.remove(), 300);
        }
      }
    };

    // Override the original file select to use preview
    const originalHandleFileSelect = handleFileSelect;
    handleFileSelect = function(event) {
      const files = event.target.files;
      if (files.length === 0) return;

      if (files.length === 1) {
        // Single file: show preview
        showFilePreview(files[0]);
      } else {
        // Multiple files: upload in parallel
        uploadFilesParallel(files);
      }
    };

    // Override PhotoCapture to use enhanced version
    if (typeof PhotoCapture !== 'undefined') {
      PhotoCapture.open = PhotoCaptureEnhanced.open.bind(PhotoCaptureEnhanced);
    }


    // Professional Standards Acknowledgment is now handled by the unified advisor consent modal (see top of file)
