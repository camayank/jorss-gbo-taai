// ==========================================================================
// advisor-data.js — API calls, fetch retry, session persistence, network
// Extracted from intelligent-advisor.js (Sprint 1: Module Extraction)
// ==========================================================================

import {
  extractedData, sessionId, conversationHistory, isOnline, offlineQueue,
  lastActivityTime, sessionRecoveryAttempted, isProcessingQueue,
  localStorageWarningShown, hasUnsavedChanges, autoSaveTimer, lastSaveTime,
  AUTO_SAVE_INTERVAL,
  setSessionId, setIsOnline, setLastActivityTime, setSessionRecoveryAttempted,
  setIsProcessingQueue, setLocalStorageWarningShown, setHasUnsavedChanges,
  setAutoSaveTimer, setLastSaveTime, setConversationHistory,
  secureFetch, getCSRFToken, DevLogger, RobustnessConfig, showToast,
  safeDeepMerge, updateExtractedDataSafe, setExtractedData,
  confirmedData, markUnsaved, retryCount, setRetryCount,
  taxCalculations, taxStrategies, setTaxCalculations, setTaxStrategies,
  premiumUnlocked
} from './advisor-core.js';

// Forward-declare imports used in offline queue processing
// processAIResponse is in advisor-chat but we need it for the offline queue
let _processAIResponse = null;
export function _setProcessAIResponse(fn) { _processAIResponse = fn; }

// ======================== FETCH WITH RETRY ========================

export async function fetchWithRetry(url, options = {}, maxRetries = 3) {
  let lastError;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000);

      const sessionToken = sessionStorage.getItem('advisor_session_token');
      const mergedHeaders = { ...options.headers };
      if (sessionToken && url.includes('/api/advisor/')) {
        mergedHeaders['X-Session-Token'] = sessionToken;
      }

      const method = (options.method || 'GET').toUpperCase();
      if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
        const csrfToken = getCSRFToken();
        if (csrfToken) {
          mergedHeaders['X-CSRF-Token'] = csrfToken;
        }
      }

      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: mergedHeaders,
        credentials: 'same-origin'
      });

      clearTimeout(timeoutId);

      // Don't retry on client errors (4xx) except 408 (timeout) and 429 (rate limit)
      if (response.status >= 400 && response.status < 500 &&
          response.status !== 408 && response.status !== 429) {
        return response;
      }

      // Retry on server errors (5xx) or specific client errors
      if (!response.ok && attempt < maxRetries) {
        const delay = Math.min(1000 * Math.pow(2, attempt - 1), 8000);
        DevLogger.log(`Retry attempt ${attempt} after ${delay}ms`);
        await new Promise(resolve => setTimeout(resolve, delay));
        continue;
      }

      return response;
    } catch (error) {
      lastError = error;

      if (error.name === 'AbortError') {
        throw new Error('Request timeout - please try again');
      }

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

// ======================== NETWORK MONITORING ========================

export function initNetworkMonitoring() {
  window.addEventListener('online', handleOnline);
  window.addEventListener('offline', handleOffline);
}

function handleOnline() {
  setIsOnline(true);
  updateConnectionStatus(true);
  hideOfflineBanner();
  showToast('Connection restored!', 'success');
  processOfflineQueue();
}

function handleOffline() {
  setIsOnline(false);
  updateConnectionStatus(false);
  showOfflineBanner();
}

export async function processOfflineQueue() {
  if (isProcessingQueue) {
    DevLogger.log('Queue processing already in progress, skipping');
    return;
  }
  if (offlineQueue.length === 0) return;

  setIsProcessingQueue(true);
  try {
    showToast(`Sending ${offlineQueue.length} queued message(s)...`, 'info');

    while (offlineQueue.length > 0 && isOnline) {
      const message = offlineQueue.shift();
      try {
        if (_processAIResponse) {
          await _processAIResponse(message);
        }
      } catch (error) {
        DevLogger.error('Failed to process queued message:', error);
        if (!isOnline) {
          offlineQueue.unshift(message);
          break;
        }
      }
    }
  } finally {
    setIsProcessingQueue(false);
  }
}

// ======================== CONNECTION STATUS ========================

export function updateConnectionStatus(online) {
  const statusEl = document.getElementById('connectionStatus');
  const textEl = document.getElementById('connectionText');
  const dotEl = document.getElementById('connectionDot');
  if (!statusEl || !textEl || !dotEl) return;

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

export function showOfflineBanner() {
  const banner = document.getElementById('offlineBanner');
  if (banner) {
    banner.classList.add('active');
  }
}

export function hideOfflineBanner() {
  const banner = document.getElementById('offlineBanner');
  if (banner) {
    banner.classList.remove('active');
  }
}

// ======================== HEALTH CHECK ========================

let healthCheckInterval = null;

export function startHealthCheck() {
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
      if (!navigator.onLine) {
        updateConnectionStatus(false);
      }
    }
  }, 30000);
}

// ======================== SESSION RECOVERY ========================

export function updateLastActivity() {
  setLastActivityTime(Date.now());
  sessionStorage.setItem('tax_advisor_last_activity', lastActivityTime.toString());
}

export function checkSessionValidity() {
  const now = Date.now();
  const storedTime = parseInt(sessionStorage.getItem('tax_advisor_last_activity') || '0');

  if (storedTime && (now - storedTime) > RobustnessConfig.sessionTimeout) {
    return false;
  }
  return true;
}

export async function attemptSessionRecovery() {
  if (sessionRecoveryAttempted) return false;
  setSessionRecoveryAttempted(true);

  const storedSessionId = sessionStorage.getItem('tax_session_id');
  const storedData = sessionStorage.getItem('tax_advisor_data');

  if (storedSessionId && storedData) {
    try {
      const savedData = JSON.parse(storedData);

      const response = await secureFetch(`/api/sessions/${storedSessionId}/restore`);
      if (response.ok) {
        setSessionId(storedSessionId);

        if (savedData.extractedData) {
          setExtractedData(safeDeepMerge(extractedData, savedData.extractedData));
        }

        showToast('Previous session restored', 'success');
        return true;
      }
    } catch (error) {
      console.log('Session recovery failed:', error);
    }
  }

  setSessionRecoveryAttempted(false);
  return false;
}

export function saveSessionData() {
  try {
    const dataToSave = JSON.stringify({
      extractedData: extractedData,
      timestamp: Date.now()
    });

    const sizeInBytes = new Blob([dataToSave]).size;
    const maxSize = 4 * 1024 * 1024;

    if (sizeInBytes > maxSize) {
      DevLogger.warn('Session data too large, trimming conversation history');
      const trimmedData = {
        extractedData: {
          ...extractedData,
          documents: extractedData.documents?.slice(-5) || []
        },
        timestamp: Date.now()
      };
      sessionStorage.setItem('tax_advisor_data', JSON.stringify(trimmedData));
    } else {
      sessionStorage.setItem('tax_advisor_data', dataToSave);
    }
    updateLastActivity();
    setLocalStorageWarningShown(false);
  } catch (error) {
    if (error.name === 'QuotaExceededError' || error.code === 22) {
      if (!localStorageWarningShown) {
        showToast('Storage full - your data is saved on our server but local backup failed. Consider clearing browser storage.', 'warning');
        setLocalStorageWarningShown(true);
      }
      try {
        var keysToTry = ['tax_advisor_cache', 'tax_advisor_preferences'];
        for (var ki = 0; ki < keysToTry.length; ki++) {
          sessionStorage.removeItem(keysToTry[ki]);
        }
        DevLogger.warn('Cleared non-essential storage due to quota exceeded');
      } catch (e) {
        DevLogger.error('Failed to clear storage:', e);
      }
    } else {
      DevLogger.warn('Failed to save session data:', error);
    }
  }
}

// ======================== AUTO-SAVE & SESSION RESTORE ========================

export async function saveSessionProgress() {
  if (!sessionId || sessionId.startsWith('temp-')) {
    DevLogger.log('Skipping save - no valid session ID');
    return;
  }

  try {
    const response = await secureFetch(`/api/sessions/${sessionId}/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        extracted_data: extractedData.__raw || extractedData,
        conversation_history: conversationHistory.slice(-30),
        current_phase: getCurrentPhase(),
        completion_percentage: getCompletionPercentage()
      })
    });

    if (response.ok) {
      setLastSaveTime(new Date());
      setHasUnsavedChanges(false);
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

function getCurrentPhase() {
  if (extractedData.review_confirmed) return 'ready_to_file';
  if (extractedData.deductions_explored || extractedData.itemize_choice) return 'review';
  if (extractedData.income_explored || extractedData.w2_wages) return 'deductions';
  if (extractedData.first_name || extractedData.filing_status) return 'income';
  return 'personal_info';
}

function getCompletionPercentage() {
  const progressFill = document.getElementById('progressFill');
  if (progressFill) {
    const width = progressFill.style.width;
    return parseFloat(width) || 0;
  }
  return 0;
}

function updateSaveIndicator(status) {
  let indicator = document.getElementById('saveIndicator');
  if (!indicator) {
    indicator = document.createElement('div');
    indicator.id = 'saveIndicator';
    indicator.className = 'save-indicator';
    const progressText = document.getElementById('progressText');
    if (progressText && progressText.parentNode) {
      progressText.parentNode.insertBefore(indicator, progressText.nextSibling);
    }
  }

  if (status === 'saved') {
    indicator.innerHTML = '<span style="color: #276749;">\u2713 Saved</span>';
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

export function startAutoSave() {
  if (autoSaveTimer) clearInterval(autoSaveTimer);
  setAutoSaveTimer(setInterval(() => {
    if (hasUnsavedChanges && sessionId) {
      updateSaveIndicator('saving');
      saveSessionProgress();
    }
  }, AUTO_SAVE_INTERVAL));
  DevLogger.log('Auto-save started');
}

export function stopAutoSave() {
  if (autoSaveTimer) {
    clearInterval(autoSaveTimer);
    setAutoSaveTimer(null);
  }
}

export async function checkForExistingSession() {
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

export function showResumeBanner(sessionData) {
  const banner = document.createElement('div');
  banner.id = 'resumeBanner';
  banner.className = 'resume-banner';
  banner.innerHTML = `
    <div class="resume-content">
      <div class="resume-icon">\uD83D\uDCCB</div>
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

  const container = document.querySelector('.chat-container');
  if (container) {
    container.insertBefore(banner, container.firstChild);
  }

  window._pendingRestore = sessionData;
}

export async function restoreSession() {
  const sessionData = window._pendingRestore;
  if (!sessionData) return;

  // Import dynamically to avoid circular dependency
  const { resetQuestioningState, advanceJourneyBasedOnData } = await import('./advisor-flow.js');
  const { addMessage } = await import('./advisor-chat.js');
  const { updateProgress, updatePhaseFromData } = await import('./advisor-display.js');

  resetQuestioningState();
  setRetryCount(0);
  confirmedData.clear();

  if (sessionData.extracted_data) {
    await updateExtractedDataSafe(sessionData.extracted_data, 'session_restore');
  }

  if (sessionData.conversation_history && sessionData.conversation_history.length > 0) {
    setConversationHistory(sessionData.conversation_history);

    const messagesContainer = document.getElementById('messages');
    if (messagesContainer) {
      messagesContainer.innerHTML = '';

      conversationHistory.forEach(msg => {
        if (msg.role === 'user') {
          addMessage('user', msg.content, []);
        } else if (msg.role === 'assistant' || msg.role === 'ai') {
          addMessage('ai', msg.content, []);
        }
      });
    }
  }

  if (sessionData.completion_percentage) {
    updateProgress(sessionData.completion_percentage);
  }

  updatePhaseFromData();
  dismissResumeBanner();

  addMessage('ai', `Welcome back! I've restored your previous session. You were ${Math.round(sessionData.completion_percentage || 0)}% complete. Let's continue where you left off.`, [
    { label: 'Continue', value: 'continue_flow' },
    { label: 'Review my info', value: 'review_data' }
  ]);

  DevLogger.log('Session restored:', sessionId);
}

export function dismissResumeBanner(startFresh = false) {
  const banner = document.getElementById('resumeBanner');
  if (banner) {
    banner.style.animation = 'slideUp 0.3s ease forwards';
    setTimeout(() => banner.remove(), 300);
  }
  window._pendingRestore = null;

  if (startFresh) {
    // Import dynamically
    import('./advisor-flow.js').then(({ resetQuestioningState }) => {
      resetQuestioningState();
    });
    setRetryCount(0);
    confirmedData.clear();
    sessionStorage.removeItem('tax_session_id');
    setSessionId(null);
  }
}

// Save before page unload
window.addEventListener('beforeunload', (event) => {
  if (hasUnsavedChanges && sessionId && !sessionId.startsWith('temp-')) {
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

// Expose for HTML onclick
window.restoreSession = restoreSession;
window.dismissResumeBanner = dismissResumeBanner;

// ======================== ROBUSTNESS INIT ========================

export function initRobustnessFeatures() {
  initNetworkMonitoring();

  setInterval(saveSessionData, 30000);

  attemptSessionRecovery();

  if (RobustnessConfig.debugMode) {
    DevLogger.log('Robustness features initialized:', {
      online: isOnline,
      sessionValid: checkSessionValidity(),
      queueSize: offlineQueue.length
    });
  }
}

// ======================== TAX CALCULATION API ========================

export async function performTaxCalculation() {
  // Import dynamically to avoid circular dependency
  const { addMessage } = await import('./advisor-chat.js');
  const { showLoadingOverlay, hideLoadingOverlay, clearErrorBanner, updateProgress } = await import('./advisor-display.js');
  const { calculateLeadScore, advanceJourneyBasedOnData } = await import('./advisor-flow.js');

  showLoadingOverlay('Analyzing Your Tax Situation', 'Running 30+ optimization strategies...');

  const analysis = await getIntelligentAnalysis();

  hideLoadingOverlay();
  clearErrorBanner();

  if (analysis && analysis.calculation) {
    const calc = analysis.calculation;
    const strategies = analysis.strategies || [];
    const totalSavings = analysis.totalSavings || 0;

    setTaxCalculations(calc);
    setTaxStrategies(strategies);

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

    extractedData.lead_data.estimated_savings = totalSavings;
    calculateLeadScore();
    updateProgress(75);

    if (extractedData.lead_data.score >= 60) {
      const { showLeadConsentDialog } = await import('./advisor-display.js');
      showLeadConsentDialog(extractedData.contact).then(consent => {
        if (consent) {
          sendLeadToCPA();
        }
      }).catch(err => DevLogger.error('Lead consent dialog error:', err));
    }
  } else {
    DevLogger.error('Analysis failed. Current data:', {
      filing_status: extractedData.tax_profile.filing_status,
      total_income: extractedData.tax_profile.total_income,
      dependents: extractedData.tax_profile.dependents
    });

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
      addMessage('ai', `I encountered an issue analyzing your data. Let me try again.`, [
        { label: 'Retry Analysis', value: 'retry_analysis', primary: true },
        { label: 'Start Over', value: 'reset_conversation' }
      ]);
    }
    document.getElementById('userInput').focus();
  }
}

export async function calculateTaxLiability() {
  const analysis = await getIntelligentAnalysis();
  if (analysis) {
    return analysis.calculation;
  }
  return null;
}

export async function getIntelligentAnalysis() {
  const { showErrorBanner, clearErrorBanner } = await import('./advisor-display.js');
  const { advanceJourneyBasedOnData } = await import('./advisor-flow.js');

  DevLogger.log('getIntelligentAnalysis called with:', {
    filing_status: extractedData.tax_profile.filing_status,
    total_income: extractedData.tax_profile.total_income,
    dependents: extractedData.tax_profile.dependents
  });

  if (!extractedData.tax_profile.total_income || !extractedData.tax_profile.filing_status) {
    DevLogger.warn('Missing required data');
    return null;
  }

  const statusMap = {
    'Single': 'single',
    'Married Filing Jointly': 'married_joint',
    'Head of Household': 'head_of_household',
    'Married Filing Separately': 'married_separate',
    'Qualifying Surviving Spouse': 'qualifying_widow'
  };

  const apiFilingStatus = statusMap[extractedData.tax_profile.filing_status];
  if (!apiFilingStatus) {
    const directValues = ['single', 'married_joint', 'married_separate', 'head_of_household', 'qualifying_widow'];
    if (!directValues.includes(extractedData.tax_profile.filing_status.toLowerCase())) {
      return null;
    }
  }

  clearErrorBanner();

  if (!sessionId) {
    setSessionId('session-' + crypto.randomUUID());
    sessionStorage.setItem('tax_session_id', sessionId);
  }

  try {
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

    const response = await fetchWithRetry('/api/advisor/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        message: 'Analyze my tax situation',
        profile: profile
      })
    }, 3);

    if (response.ok) {
      const data = await response.json();
      setTaxCalculations(data.tax_calculation);
      setTaxStrategies(data.strategies || []);
      extractedData.lead_data.estimated_savings = taxStrategies.reduce((sum, s) => sum + s.estimated_savings, 0);
      extractedData.lead_data.score = data.lead_score || extractedData.lead_data.score;

      advanceJourneyBasedOnData();

      return {
        calculation: data.tax_calculation,
        strategies: data.strategies,
        insights: data.key_insights,
        totalSavings: taxStrategies.reduce((sum, s) => sum + s.estimated_savings, 0),
        complexity: data.complexity
      };
    } else {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Server error: ${response.status}`);
    }
  } catch (error) {
    DevLogger.error('Intelligent analysis error:', error);

    if (!navigator.onLine) {
      showErrorBanner('Connection Lost', 'Please check your internet connection and try again.', 'performTaxCalculation()');
    } else if (error.message.includes('429')) {
      showErrorBanner('Service Busy', 'Our servers are handling high traffic. Please wait a moment and try again.', 'performTaxCalculation()');
    } else {
      showErrorBanner('Analysis Error', 'We encountered an issue analyzing your data. Please try again.', 'performTaxCalculation()');
    }
  }
  return null;
}

export async function sendLeadToCPA() {
  if (!extractedData.lead_data.ready_for_cpa) {
    return false;
  }

  try {
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

// ======================== INTELLIGENT DATA EXTRACTION ========================

export async function extractDataWithAI(userMessage) {
  try {
    const response = await secureFetch('/api/ai-chat/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        user_message: userMessage,
        conversation_history: conversationHistory,
        extracted_data: extractedData,
        extraction_mode: true
      })
    });

    if (response.ok) {
      const data = await response.json();

      if (data.extracted_data) {
        mergeExtractedData(data.extracted_data);
      }

      return data;
    }
  } catch (error) {
    DevLogger.error('AI extraction error:', error);
  }
  return null;
}

function mergeExtractedData(newData) {
  if (newData.filing_status) extractedData.tax_profile.filing_status = newData.filing_status;
  if (newData.income) extractedData.tax_profile.total_income = newData.income;
  if (newData.w2_income) extractedData.tax_profile.w2_income = newData.w2_income;
  if (newData.business_income) extractedData.tax_profile.business_income = newData.business_income;
  if (newData.dependents) extractedData.tax_profile.dependents = newData.dependents;
  if (newData.state) extractedData.tax_profile.state = newData.state;

  if (newData.mortgage) extractedData.tax_items.mortgage_interest = newData.mortgage;
  if (newData.charitable) extractedData.tax_items.charitable = newData.charitable;

  DevLogger.log('Merged extracted data:', extractedData);
}

// ======================== FILE HANDLING ========================

export async function handleFileSelect(event) {
  const MAX_FILE_SIZE = 10 * 1024 * 1024;
  const ALLOWED_TYPES = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg'];
  const files = event.target.files;
  if (files.length === 0) return;

  const { addMessage } = await import('./advisor-chat.js');
  const { startIntelligentQuestioning } = await import('./advisor-flow.js');
  const { updateProgress, updatePhaseFromData } = await import('./advisor-display.js');

  for (const file of files) {
    if (file.size > MAX_FILE_SIZE) {
      showToast(`File "${file.name}" exceeds 10MB limit`, 'error');
      continue;
    }
    if (ALLOWED_TYPES.length > 0 && !ALLOWED_TYPES.includes(file.type)) {
      showToast(`File type not supported: ${file.type || 'unknown'}. Please upload PDF, JPG, or PNG.`, 'error');
      continue;
    }
    addMessage('user', `Uploading: ${file.name}`);
    await uploadFileToAI(file);
  }
}

async function uploadFileToAI(file) {
  const { showTyping, hideTyping, addMessage } = await import('./advisor-chat.js');
  const { startIntelligentQuestioning } = await import('./advisor-flow.js');
  const { updateProgress, updateStats, updatePhaseFromData } = await import('./advisor-display.js');

  showTyping();

  const formData = new FormData();
  formData.append('file', file);
  formData.append('session_id', sessionId);

  try {
    const response = await secureFetch('/api/ai-chat/analyze-document', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();
    hideTyping();

    addMessage('ai', data.ai_response, data.quick_actions || []);

    if (data.extracted_data) {
      await updateExtractedDataSafe(data.extracted_data, 'document_upload');
    }

    updateProgress(data.completion_percentage || 0);
    updateStats(data.extracted_summary || {});
    updatePhaseFromData();

    if (!data.quick_actions || data.quick_actions.length === 0) {
      setTimeout(() => {
        startIntelligentQuestioning();
      }, 500);
    }

  } catch (error) {
    hideTyping();
    DevLogger.error('Document upload error:', error);
    addMessage('ai', `I had trouble reading that document. Would you like to try again or enter the information manually?`, [
      { label: (typeof getIcon === 'function' ? getIcon('arrow-path', 'sm') : '') + ' Try again', value: 'yes_upload' },
      { label: (typeof getIcon === 'function' ? getIcon('chat-bubble-left-right', 'sm') : '') + ' Enter manually', value: 'no_manual' },
      { label: '\u2753 What documents work best?', value: 'what_docs' }
    ]);
  }
}
