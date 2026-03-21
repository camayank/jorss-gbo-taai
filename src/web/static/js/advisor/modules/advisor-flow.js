// ==========================================================================
// advisor-flow.js — Thin pass-through to backend
//
// REWRITTEN: All questions, transitions, and flow logic live on the backend.
// This module's only job is to send user actions to the backend via
// processAIResponse and let the response_type drive rendering.
// ==========================================================================

import {
  extractedData, sessionId, DevLogger, showToast, secureFetch, getCSRFToken,
  setConfirmedValue, confirmedData, markUnsaved
} from './advisor-core.js';

import {
  addMessage, showTyping, hideTyping, processAIResponse
} from './advisor-chat.js';

import {
  fetchWithRetry, sendLeadToCPA, performTaxCalculation
} from './advisor-data.js';

import {
  updateSavingsEstimate, updateProgress, showLoadingOverlay, hideLoadingOverlay,
  showErrorBanner, clearErrorBanner, updatePhaseFromData, updateStats,
  LiveSavingsDisplay
} from './advisor-display.js';

// ======================== JOURNEY STEPPER ========================

export let currentJourneyStep = 1;
export const journeySteps = {
  1: { name: 'Profile', icon: 'clipboard-document-list' },
  2: { name: 'Income', icon: 'currency-dollar' },
  3: { name: 'Analysis', icon: 'sparkles' },
  4: { name: 'Report', icon: 'chart-bar' }
};

export function updateJourneyStep(stepNumber) {
  if (stepNumber < 1 || stepNumber > 4) return;
  currentJourneyStep = stepNumber;
  for (let i = 1; i <= 4; i++) {
    const stepEl = document.getElementById(`step-${i}`);
    if (!stepEl) continue;
    const stepIconEl = stepEl.querySelector('.step-icon');
    stepEl.classList.remove('active', 'completed');
    if (i < stepNumber) {
      stepEl.classList.add('completed');
      if (stepIconEl) stepIconEl.textContent = '\u2713';
    } else if (i === stepNumber) {
      stepEl.classList.add('active');
    }
  }
}

export function advanceJourneyBasedOnData() {
  // Journey advancement is now driven by backend response metadata
  // This is kept for backward compatibility with advisor-chat.js
}

// ======================== CONFIDENCE HELPERS ========================

export function getConfidenceLevel() {
  return 'standard';
}

export function getConfidenceDisclaimer(includeIRS = false) {
  let disclaimer = '\n\n<div class="confidence-disclaimer">';
  disclaimer += '<small>Estimates are for planning purposes only. Consult a tax professional for advice specific to your situation.</small>';
  if (includeIRS) {
    disclaimer += '<br><small>IRS Circular 230: This communication was not intended to be used for avoiding penalties.</small>';
  }
  disclaimer += '</div>';
  return disclaimer;
}

// ======================== QUESTIONING STATE ========================
// Kept for backward compatibility — no longer drives anything

export let questioningState = {
  callCount: 0,
  maxCalls: 50,
  askedQuestions: new Set(),
};

export function markQuestionAsked(questionId) {
  questioningState.askedQuestions.add(questionId);
}

export function wasQuestionAsked(questionId) {
  return questioningState.askedQuestions.has(questionId);
}

export function resetQuestioningState() {
  questioningState.callCount = 0;
  questioningState.askedQuestions = new Set();
}

export function calculateLeadScore() {
  return 0; // Backend calculates this now
}

// ======================== HANDLE QUICK ACTION ========================
// THE CORE FUNCTION — every user click comes through here.
// Every action goes straight to the backend. No local state. No client-side questions.

export async function handleQuickAction(value, displayLabel = null) {
  DevLogger.log('handleQuickAction:', value);

  // Silent actions that don't show user message
  const silentActions = new Set([
    'start', 'continue', 'no_manual', 'start_estimate', 'continue_assessment',
    'continue_normal',
  ]);

  // Upload actions — trigger file picker, don't send to backend
  if (value === 'yes_upload' || value === 'upload_w2' || value === 'upload_1099') {
    const fileInput = document.getElementById('fileInput');
    if (fileInput) fileInput.click();
    return;
  }

  // Report generation — special endpoint
  if (value === 'generate_report' || value === 'download_report') {
    addMessage('user', 'Generate Report');
    addMessage('ai', 'Generating your comprehensive tax advisory report...');
    try {
      const resp = await secureFetch('/api/advisor/report?session_id=' + sessionId, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, report_type: 'full_analysis' })
      });
      if (resp.ok) {
        addMessage('ai', 'Your tax advisory report is ready.', [
          { label: 'View Strategies', value: 'show_strategies' },
          { label: 'Ask a question', value: 'ask_question' }
        ]);
      }
    } catch (e) {
      addMessage('ai', 'Report generation temporarily unavailable.');
    }
    return;
  }

  // "How does this work" — informational
  if (value === 'what_docs') {
    addMessage('user', 'How does this work?');
    addMessage('ai',
      'I\'ll ask you questions about your tax situation — filing status, income, deductions, and more. ' +
      'From that, I compute your actual federal and state tax using IRS formulas. ' +
      'You can also upload W-2s or 1099s and I\'ll extract the data automatically.\n\n' +
      'The whole process takes about 2-5 minutes.', [
      { label: 'Start my estimate', value: 'start' },
      { label: 'Upload a document', value: 'yes_upload' }
    ]);
    return;
  }

  // Show user's selection as a chat message (unless silent)
  if (!silentActions.has(value)) {
    const displayText = displayLabel
      || value.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    addMessage('user', displayText);
  }

  // Send to backend — this is it. Backend returns the next question,
  // transition, summary, confirmation, calculation, or anything else.
  await processAIResponse(value);
}

// ======================== DEPRECATED FUNCTIONS ========================
// These existed for the old client-side Phase 1 flow.
// Now they just route to the backend.

export async function startIntelligentQuestioning() {
  await processAIResponse('continue');
}

export async function showPreliminarySummary() {
  await processAIResponse('continue');
}

export async function analyzeDeductions() {
  await processAIResponse('continue');
}

export function askNextDeductionOrCredits() {
  // No-op — backend handles deduction flow
}

export async function requestCPAConnection() {
  addMessage('ai', 'To connect with a CPA, please complete your tax profile first. They\'ll receive your full analysis.', [
    { label: 'Continue Profile', value: 'continue' }
  ]);
}

export function generateSummary() {
  // No-op — backend generates summary
}

// ======================== LEAD CAPTURE ========================
// These are still needed for the CPA connection flow

export async function captureName() {
  const input = document.getElementById('userInput');
  if (!input) return;
  const name = input.value.trim();
  if (!name) {
    showToast('Please enter your name', 'warning');
    return;
  }
  extractedData.lead_data = extractedData.lead_data || {};
  extractedData.lead_data.name = name;
  addMessage('user', name);
  input.value = '';
  markUnsaved();

  addMessage('ai', `Thanks, ${name}! What's your email address so we can send your report?`, []);
}

export async function captureEmail() {
  const input = document.getElementById('userInput');
  if (!input) return;
  const email = input.value.trim();
  if (!email || !email.includes('@')) {
    showToast('Please enter a valid email', 'warning');
    return;
  }
  extractedData.lead_data = extractedData.lead_data || {};
  extractedData.lead_data.email = email;
  addMessage('user', email);
  input.value = '';
  markUnsaved();

  try {
    await sendLeadToCPA(extractedData.lead_data);
    addMessage('ai', 'Your information has been sent to a CPA who will review your situation and reach out within 24 hours.', [
      { label: 'Continue exploring', value: 'continue' }
    ]);
  } catch (e) {
    addMessage('ai', 'There was an issue sending your info. Please try again.', [
      { label: 'Try again', value: 'request_cpa' }
    ]);
  }
}

export async function captureIncome() {
  const input = document.getElementById('userInput');
  if (!input) return;
  const text = input.value.trim();
  if (!text) return;

  addMessage('user', text);
  input.value = '';

  // Send to backend for parsing
  await processAIResponse(text);
}
