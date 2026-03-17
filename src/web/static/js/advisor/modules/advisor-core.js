// ==========================================================================
// advisor-core.js — State, utilities, security, consent, session management
// Extracted from intelligent-advisor.js (Sprint 1: Module Extraction)
// ==========================================================================

// ======================== CONSENT MANAGEMENT ========================

export function disableChat() {
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

export function enableChat() {
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

// Current consent version. Bump this string (e.g. to 'v2') to force all users
// to re-consent after a material change to the privacy/standards notice.
export const CONSENT_VERSION = 'v1';

/**
 * Try to read a value from localStorage. Returns null if localStorage is
 * unavailable (e.g. private-browsing mode with storage blocked).
 */
function localStorageGet(key) {
  try {
    return localStorage.getItem(key);
  } catch (e) {
    return null;
  }
}

/**
 * Try to write a value to localStorage. Returns false if unavailable.
 */
function localStorageSet(key, value) {
  try {
    localStorage.setItem(key, value);
    return true;
  } catch (e) {
    return false;
  }
}

/** Returns true if a stored consent token is present and matches the current version. */
function hasValidPersistedConsent() {
  const token = localStorageGet('advisor_consent_token');
  const version = localStorageGet('advisor_consent_version');
  return token !== null && version === CONSENT_VERSION;
}

/** Returns true if user already consented (persisted across sessions or this session) */
export function checkAdvisorConsent() {
  // Primary check: valid token in localStorage (survives tab close)
  if (hasValidPersistedConsent()) {
    var modal = document.getElementById('advisorConsentModal');
    if (modal) modal.classList.add('hidden');
    enableChat();
    return true;
  }

  // Fallback check: sessionStorage consent set in the current tab
  if (sessionStorage.getItem('advisor_consent') === 'true') {
    var modal = document.getElementById('advisorConsentModal');
    if (modal) modal.classList.add('hidden');
    enableChat();
    return true;
  }

  // No valid consent found — show modal and disable chat
  var modal = document.getElementById('advisorConsentModal');
  if (modal) modal.classList.remove('hidden');
  disableChat();
  return false;
}

/** Wire up consent modal checkbox + button */
export function setupAdvisorConsent() {
  var checkbox = document.getElementById('advisorConsentCheck');
  var btn = document.getElementById('advisorConsentBtn');
  if (!checkbox || !btn) return;

  checkbox.addEventListener('change', function () {
    btn.disabled = !this.checked;
  });

  btn.addEventListener('click', async function () {
    const acknowledgedAt = new Date().toISOString();

    // Always set sessionStorage immediately so the current tab is unblocked
    // even if the server call or localStorage write fails.
    sessionStorage.setItem('advisor_consent', 'true');
    sessionStorage.setItem('advisor_consent_at', acknowledgedAt);

    var modal = document.getElementById('advisorConsentModal');
    if (modal) modal.classList.add('hidden');
    enableChat();
    const chatInput = document.getElementById('userInput');
    if (chatInput) chatInput.focus();

    // Log acknowledgment to server and persist the returned token
    try {
      const response = await fetch('/api/advisor/acknowledge-standards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: typeof sessionId !== 'undefined' ? sessionId : 'unknown',
          acknowledged_at: acknowledgedAt
        })
      });

      if (response.ok) {
        let responseData = {};
        try { responseData = await response.json(); } catch (_) {}

        // Persist the consent token in localStorage so it survives tab close.
        // Fall back to a locally-generated token if the server omits one.
        const token = responseData.token || ('v1_' + Date.now());
        const stored = localStorageSet('advisor_consent_token', token);
        localStorageSet('advisor_consent_version', CONSENT_VERSION);

        if (!stored) {
          // localStorage unavailable — sessionStorage fallback already set above.
          console.warn('localStorage unavailable; consent will not persist across sessions.');
        }
      }
    } catch (e) {
      console.warn('Could not log acknowledgment:', e);
    }

    // Initialize session after consent
    initializeSession();
    showToast('Welcome! Your data will be handled securely.', 'success');
  });
}

/** Wire up the dismissible notice banner */
export function setupNoticeBanner() {
  var dismissBtn = document.getElementById('dismissNoticeBtn');
  var banner = document.getElementById('advisorNoticeBanner');
  if (dismissBtn && banner) {
    dismissBtn.addEventListener('click', function () {
      banner.style.display = 'none';
    });
  }
}

// ======================== STATE VARIABLES ========================

export let sessionId = null;
export let conversationHistory = [];
export let extractedData = {
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

export let isProcessing = false;
export let taxCalculations = null;
export let leadQualified = false;
export let retryCount = 0;
export let questionNumber = 0;
export let premiumUnlocked = false;
export let taxStrategies = [];
export let currentStrategyIndex = 0;

// Setter helpers for mutable state that other modules need to update
export function setSessionId(val) { sessionId = val; }
export function setIsProcessing(val) { isProcessing = val; }
export function setTaxCalculations(val) { taxCalculations = val; }
export function setLeadQualified(val) { leadQualified = val; }
export function setRetryCount(val) { retryCount = val; }
export function setQuestionNumber(val) { questionNumber = val; }
export function setPremiumUnlocked(val) { premiumUnlocked = val; }
export function setTaxStrategies(val) { taxStrategies = val; }
export function setCurrentStrategyIndex(val) { currentStrategyIndex = val; }
export function setConversationHistory(val) { conversationHistory = val; }
export function setExtractedData(val) { extractedData = val; }

// ======================== ROBUSTNESS CONFIG ========================

export const RobustnessConfig = {
  maxRetries: 3,
  retryDelay: 1000,
  maxMessageLength: 5000,
  minMessageLength: 1,
  rateLimitMessages: 30,
  rateLimitWindow: 60000,
  sessionTimeout: 30 * 60 * 1000,
  offlineQueueMax: 10,
  debugMode: false
};

// ======================== LOGGER ========================

export const DevLogger = {
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
    if (RobustnessConfig.debugMode) {
      console.error('[DEV]', ...args);
    } else {
      console.error('An error occurred. Enable debugMode for details.');
    }
  },
  debug: function(...args) {
    if (RobustnessConfig.debugMode) {
      console.debug('[DEV]', ...args);
    }
  }
};

// ======================== HTML ESCAPING ========================

export function escapeHtml(str) {
  if (typeof str !== 'string') return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ======================== CSRF PROTECTION ========================

export function getCSRFToken() {
  const cookies = document.cookie.split(';');
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split('=');
    if (name === 'csrf_token') {
      return decodeURIComponent(value);
    }
  }
  const metaTag = document.querySelector('meta[name="csrf-token"]');
  return metaTag ? metaTag.getAttribute('content') : null;
}

export async function secureFetch(url, options = {}) {
  const method = (options.method || 'GET').toUpperCase();

  if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
    const csrfToken = getCSRFToken();
    if (csrfToken) {
      options.headers = {
        ...options.headers,
        'X-CSRF-Token': csrfToken
      };
    }
  }

  const sessionToken = sessionStorage.getItem('advisor_session_token');
  if (sessionToken && url.includes('/api/advisor/')) {
    options.headers = { ...options.headers, 'X-Session-Token': sessionToken };
  }

  options.credentials = options.credentials || 'same-origin';

  return fetch(url, options);
}

// ======================== RATE LIMITING ========================

export const rateLimitState = {
  messages: [],
  blocked: false,
  blockUntil: null
};

export function checkRateLimit() {
  const now = Date.now();

  if (rateLimitState.blocked) {
    if (now < rateLimitState.blockUntil) {
      const waitSeconds = Math.ceil((rateLimitState.blockUntil - now) / 1000);
      return {
        allowed: false,
        reason: `Too many messages. Please wait ${waitSeconds} seconds.`
      };
    }
    rateLimitState.blocked = false;
    rateLimitState.blockUntil = null;
  }

  rateLimitState.messages = rateLimitState.messages.filter(
    time => now - time < RobustnessConfig.rateLimitWindow
  );

  if (rateLimitState.messages.length >= RobustnessConfig.rateLimitMessages) {
    rateLimitState.blocked = true;
    rateLimitState.blockUntil = now + 30000;
    return {
      allowed: false,
      reason: 'You\'re sending messages too quickly. Please slow down.'
    };
  }

  rateLimitState.messages.push(now);
  return { allowed: true };
}

// ======================== OFFLINE / NETWORK STATE ========================

export const offlineQueue = [];
export let isOnline = navigator.onLine;
export let lastActivityTime = Date.now();
export let sessionRecoveryAttempted = false;

export function setIsOnline(val) { isOnline = val; }
export function setLastActivityTime(val) { lastActivityTime = val; }
export function setSessionRecoveryAttempted(val) { sessionRecoveryAttempted = val; }

// ======================== DATA PROTECTION LAYER ========================

export const dataMutex = {
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

export const confirmedData = {
  fields: new Set(),
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

export function safeDeepMerge(target, source, parentPath = '') {
  if (!source || typeof source !== 'object') return target;

  const result = { ...target };

  for (const key of Object.keys(source)) {
    const fieldPath = parentPath ? `${parentPath}.${key}` : key;
    const sourceValue = source[key];
    const targetValue = result[key];

    if (confirmedData.isConfirmed(fieldPath) && targetValue != null) {
      DevLogger.log(`Skipping confirmed field: ${fieldPath}`);
      continue;
    }

    if (sourceValue == null) continue;

    if (typeof sourceValue === 'object' && !Array.isArray(sourceValue) &&
        typeof targetValue === 'object' && !Array.isArray(targetValue)) {
      result[key] = safeDeepMerge(targetValue || {}, sourceValue, fieldPath);
    } else if (Array.isArray(sourceValue) && Array.isArray(targetValue)) {
      const combined = [...targetValue];
      for (const item of sourceValue) {
        const exists = combined.some(existing =>
          JSON.stringify(existing) === JSON.stringify(item)
        );
        if (!exists) combined.push(item);
      }
      result[key] = combined;
    } else {
      result[key] = sourceValue;
    }
  }

  return result;
}

export async function updateExtractedDataSafe(newData, source = 'unknown') {
  await dataMutex.acquire();
  try {
    DevLogger.log(`Updating extractedData from ${source}:`, newData);
    extractedData = safeDeepMerge(extractedData, newData);
    markUnsaved();
  } finally {
    dataMutex.release();
  }
}

export function setConfirmedValue(path, value) {
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

export function setConfirmedValues(values) {
  for (const [path, value] of Object.entries(values)) {
    setConfirmedValue(path, value);
  }
}

// ======================== INPUT VALIDATION ========================

export function sanitizeInput(input) {
  if (typeof input !== 'string') return '';

  let sanitized = input
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/<[^>]*>/g, '')
    .replace(/javascript:/gi, '')
    .replace(/on\w+\s*=/gi, '')
    .trim();

  if (sanitized.length > RobustnessConfig.maxMessageLength) {
    sanitized = sanitized.substring(0, RobustnessConfig.maxMessageLength);
  }

  return sanitized;
}

export function validateMessage(message) {
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

export function validateNumericInput(value, min = 0, max = Infinity) {
  const num = parseFloat(value);
  if (isNaN(num)) return { valid: false, error: 'Must be a valid number' };
  if (num < min) return { valid: false, error: `Must be at least ${min}` };
  if (num > max) return { valid: false, error: `Must be no more than ${max}` };
  return { valid: true, value: num };
}

// ======================== TOAST NOTIFICATION ========================

export function showToast(message, type = 'info') {
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

  if (type === 'error') {
    toast.style.background = '#ef4444';
    toast.setAttribute('role', 'alert');
  } else if (type === 'warning') {
    toast.style.background = '#f59e0b';
    toast.setAttribute('role', 'status');
  } else if (type === 'success') {
    toast.style.background = '#10b981';
    toast.setAttribute('role', 'status');
  } else {
    toast.style.background = '#2098d4';
    toast.setAttribute('role', 'status');
  }

  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'slideDown 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ======================== SESSION MANAGEMENT ========================

export async function initializeSession() {
  DevLogger.log('initializeSession called');

  try {
    DevLogger.log('Creating session...');
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
    if (data.session_token) {
      sessionStorage.setItem('advisor_session_token', data.session_token);
    }
    DevLogger.log('Session initialized:', sessionId);
  } catch (error) {
    DevLogger.error('Session initialization error:', error);
  }
}

export function clearConversation() {
  if (!confirm('Start a new conversation? This will clear your current session.')) {
    return;
  }

  questionNumber = 0;
  updateQuestionCounter();

  sessionStorage.removeItem('tax_session_id');
  sessionStorage.removeItem('tax_data_consent');
  sessionStorage.removeItem('tax_consent_timestamp');

  window.location.reload();
}

// ======================== QUESTION COUNTER ========================

export function getEstimatedTotal() {
  var label = document.getElementById('currentPhaseLabel');
  var phase = label ? label.textContent.trim().toLowerCase() : '';
  if (phase.indexOf('income') !== -1) return 8;
  if (phase.indexOf('analysis') !== -1 || phase.indexOf('deduction') !== -1) return 12;
  if (phase.indexOf('report') !== -1) return 15;
  return 5;
}

export function updateQuestionCounter() {
  var el = document.getElementById('questionCounterText');
  if (!el) return;
  if (questionNumber < 1) { el.textContent = ''; return; }
  el.textContent = 'Question ' + questionNumber + ' of ~' + getEstimatedTotal();
}

// ======================== DARK MODE ========================

function applyDarkMode(isDark) {
  if (isDark) {
    document.documentElement.setAttribute('data-theme', 'advisor-dark');
  } else {
    document.documentElement.removeAttribute('data-theme');
  }
  var btn = document.getElementById('themeToggle');
  if (btn) {
    btn.innerHTML = isDark ? getIcon('sun', 'sm') : getIcon('moon', 'sm');
  }
}

function initTheme() {
  var saved = localStorage.getItem('advisor-theme');
  if (saved === 'dark') {
    applyDarkMode(true);
  } else if (saved === 'light') {
    applyDarkMode(false);
  } else {
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    applyDarkMode(prefersDark);
  }
}

export function toggleDarkMode() {
  var isDark = document.documentElement.getAttribute('data-theme') === 'advisor-dark';
  var newState = !isDark;
  applyDarkMode(newState);
  localStorage.setItem('advisor-theme', newState ? 'dark' : 'light');
}

// Listen for system preference changes
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
  if (!localStorage.getItem('advisor-theme')) {
    applyDarkMode(e.matches);
  }
});

// Initialize theme immediately
initTheme();

// ======================== AUTO-SAVE STATE ========================

export let autoSaveTimer = null;
export let lastSaveTime = null;
export let hasUnsavedChanges = false;
export const AUTO_SAVE_INTERVAL = 30000;

export function markUnsaved() {
  hasUnsavedChanges = true;
}

export function setHasUnsavedChanges(val) { hasUnsavedChanges = val; }
export function setAutoSaveTimer(val) { autoSaveTimer = val; }
export function setLastSaveTime(val) { lastSaveTime = val; }

// ======================== QUEUE PROCESSING MUTEX ========================

export let isProcessingQueue = false;
export function setIsProcessingQueue(val) { isProcessingQueue = val; }

// ======================== ERROR HANDLER ========================

export function handleError(error, context = 'Unknown') {
  DevLogger.error(`Error in ${context}:`, error);

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

  showToast(userMessage, 'error');

  return {
    message: userMessage,
    action: recoveryAction,
    originalError: error
  };
}

// Track localStorage quota usage
export let localStorageWarningShown = false;
export function setLocalStorageWarningShown(val) { localStorageWarningShown = val; }

// Last user message for retry
export let lastUserMessage = null;
export function setLastUserMessage(val) { lastUserMessage = val; }
