/**
 * index.js — Barrel file for advisor modules.
 *
 * Responsibilities:
 *  1. Import all five modules.
 *  2. Expose every function that HTML onclick / inline handlers depend on as window globals.
 *  3. Consolidate the 4 scattered DOMContentLoaded listeners into one.
 *  4. Wire up delegated event listeners (quick-action buttons, data-action buttons).
 */

// ── Module imports ──────────────────────────────────────────────────────────

import {
  sessionId,
  setSessionId,
  setRetryCount,
  DevLogger,
  checkAdvisorConsent,
  setupAdvisorConsent,
  setupNoticeBanner,
  initializeSession,
  clearConversation,
  showToast,
  toggleDarkMode,
  escapeHtml
} from './advisor-core.js';

import {
  sendMessage,
  handleKeyDown,
  processAIResponse,
  addMessage
} from './advisor-chat.js';

import {
  initNetworkMonitoring,
  updateConnectionStatus,
  startHealthCheck,
  checkForExistingSession,
  showResumeBanner,
  restoreSession,
  dismissResumeBanner,
  startAutoSave,
  initRobustnessFeatures,
  performTaxCalculation,
  _setProcessAIResponse
} from './advisor-data.js';

import {
  handleQuickAction,
  resetQuestioningState,
  captureName,
  captureEmail,
  captureIncome
} from './advisor-flow.js';

import {
  CelebrationSystem,
  VoiceInputSystem,
  SmartNudgeSystem,
  LiveSavingsDisplay,
  PhotoCapture,
  PhotoCaptureEnhanced,
  initUXEnhancements,
  uploadDocument,
  showUploadOptions,
  closeUploadOptions,
  selectFileUpload,
  selectCameraCapture,
  addVoiceInput,
  showFilePreview,
  closeFilePreview,
  confirmUpload,
  handleFileSelect,
  openCpaModal,
  closeCpaModal,
  showActionableError,
  generateAndDownloadReport,
  sendReportEmail,
  unlockPremiumStrategies,
  submitLeadCapture,
  dismissLeadCapture,
  unlockAllCards,
  toggleQuickEdit,
  editField,
  showShimmerLoading,
  hideShimmerLoading,
  triggerConfetti,
  updateJourneyStepperForHybrid,
  addManyOptionsClass
} from './advisor-display.js';


// ── Wire cross-module bridges ────────────────────────────────────────────────
_setProcessAIResponse(processAIResponse);

// ── Window globals (required by HTML onclick attributes) ─────────────────────

// Core
window.clearConversation   = clearConversation;
window.toggleDarkMode      = toggleDarkMode;

// Chat
window.sendMessage         = sendMessage;
window.handleKeyDown       = handleKeyDown;

// Flow
window.handleQuickAction   = handleQuickAction;
window.__handleQuickAction = handleQuickAction;  // For hybrid flow components
window.captureName         = captureName;
window.captureEmail        = captureEmail;
window.captureIncome       = captureIncome;

// Hybrid flow: free-form submit handler
window.__submitFreeForm = function() {
    const textarea = document.getElementById('freeform-textarea');
    if (!textarea || !textarea.value.trim()) return;
    const text = textarea.value.trim();
    const wrapper = textarea.closest('.freeform-wrapper');
    if (wrapper) wrapper.remove();
    showShimmerLoading();
    updateJourneyStepperForHybrid('details');
    const input = document.getElementById('user-input') || document.getElementById('userInput');
    if (input) {
        input.value = text;
        sendMessage();
    }
};
window.__showShimmerLoading = showShimmerLoading;
window.__hideShimmerLoading = hideShimmerLoading;

// Data / Session
window.restoreSession      = restoreSession;
window.dismissResumeBanner = dismissResumeBanner;
window.performTaxCalculation = performTaxCalculation;

// Display / UI
window.handleFileSelect    = handleFileSelect;
window.uploadDocument      = uploadDocument;
window.showUploadOptions   = showUploadOptions;
window.closeUploadOptions  = closeUploadOptions;
window.selectFileUpload    = selectFileUpload;
window.selectCameraCapture = selectCameraCapture;
window.addVoiceInput       = addVoiceInput;
window.showFilePreview     = showFilePreview;
window.closeFilePreview    = closeFilePreview;
window.confirmUpload       = confirmUpload;
window.openCpaModal        = openCpaModal;
window.closeCpaModal       = closeCpaModal;
window.generateAndDownloadReport = generateAndDownloadReport;
window.sendReportEmail     = sendReportEmail;
window.toggleQuickEdit     = toggleQuickEdit;
window.editField           = editField;

// Premium / Lead capture
window.unlockPremiumStrategies = unlockPremiumStrategies;
window.submitLeadCapture   = submitLeadCapture;
window.dismissLeadCapture  = dismissLeadCapture;

// Systems accessible by onclick in dynamic HTML
window.SmartNudgeSystem    = SmartNudgeSystem;
window.PhotoCapture        = PhotoCapture;
window.PhotoCaptureEnhanced = PhotoCaptureEnhanced;
window.CelebrationSystem   = CelebrationSystem;
window.VoiceInputSystem    = VoiceInputSystem;

// Workflow selector (referenced in template)
window.openWorkflowSelector = window.openWorkflowSelector || function() {
  DevLogger.log('Workflow selector not loaded');
};


// ── Single consolidated DOMContentLoaded ─────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  DevLogger.log('Page loaded, initializing...');

  // 1. Consent system
  setupAdvisorConsent();
  setupNoticeBanner();

  // 2. Robustness features (network monitoring, error handling)
  initRobustnessFeatures();

  // 3. UX enhancements (nudge, voice, live savings, keyboard nav, drag-drop)
  initUXEnhancements();

  // 4. Theme is initialized inside advisor-core.js on import (initTheme runs at module eval)

  // 5. Reset questioning state for clean start
  resetQuestioningState();
  setRetryCount(0);

  // 6. Check connection status
  updateConnectionStatus(navigator.onLine);

  // 7. Start health check monitoring
  startHealthCheck();

  // 8. Attach event listeners to initial quick action buttons in the HTML
  const initialButtons = document.querySelectorAll('#initialQuickActions button[data-action]');
  DevLogger.log('Found initial buttons:', initialButtons.length);

  initialButtons.forEach(button => {
    button.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      const action = this.getAttribute('data-action');
      DevLogger.log('Initial button clicked:', action);

      this.disabled = true;
      setTimeout(() => { this.disabled = false; }, 2000);

      handleQuickAction(action);
    });
  });

  // 9. Delegated click handler for dynamically-added quick-action buttons
  document.addEventListener('click', function(e) {
    if (e.target.classList.contains('quick-action') && e.target.dataset.action) {
      e.preventDefault();
      const action = e.target.dataset.action;
      DevLogger.log('Delegated button clicked:', action);
      handleQuickAction(action);
    }
  });

  // 10. Delegated event listener for DOMPurify-safe data-action buttons inside messages
  const messagesContainer = document.getElementById('messages');
  if (messagesContainer) {
    DevLogger.log('Messages container found:', messagesContainer);

    messagesContainer.addEventListener('click', function(e) {
      const btn = e.target.closest('[data-action]');
      if (!btn || !this.contains(btn)) return;
      const action = btn.dataset.action;
      e.stopPropagation();
      if (action === 'unlock-premium') unlockPremiumStrategies();
      else if (action === 'submit-lead') submitLeadCapture();
      else if (action === 'dismiss-lead') dismissLeadCapture();
      else if (action === 'generate_report') handleQuickAction('generate_report');
    });
  }

  // 11. Initialize session (backend is source of truth — no client-side restore banner)
  if (checkAdvisorConsent()) {
    initializeSession();
    startAutoSave();
  }

  // 12. Focus input
  setTimeout(() => {
    const input = document.getElementById('userInput');
    if (input) input.focus();
  }, 100);

  DevLogger.log('All initialization complete');
});
