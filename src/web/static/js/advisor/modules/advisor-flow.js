// ==========================================================================
// advisor-flow.js — Questioning engine, journey steps, lead flow, summary
// Extracted from intelligent-advisor.js (Sprint 1: Module Extraction)
// ==========================================================================

import {
  extractedData, sessionId, taxCalculations, taxStrategies, premiumUnlocked,
  retryCount, leadQualified, currentStrategyIndex,
  setSessionId, setRetryCount, setLeadQualified, setTaxCalculations,
  setTaxStrategies, setCurrentStrategyIndex, setPremiumUnlocked,
  secureFetch, escapeHtml, DevLogger, showToast, getCSRFToken,
  setConfirmedValue, setConfirmedValues, confirmedData, markUnsaved,
  RobustnessConfig
} from './advisor-core.js';

import {
  addMessage, showTyping, hideTyping, showQuestion, processAIResponse
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
      if (typeof getIcon === 'function') stepIconEl.innerHTML = getIcon('check', 'md');
    } else if (i === stepNumber) {
      stepEl.classList.add('active');
      if (typeof getIcon === 'function') stepIconEl.innerHTML = getIcon(journeySteps[i].icon, 'md');
    } else {
      if (typeof getIcon === 'function') stepIconEl.innerHTML = getIcon(journeySteps[i].icon, 'md');
    }
  }
}

export function advanceJourneyBasedOnData() {
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

// ======================== CONFIDENCE ========================

export function getConfidenceLevel() {
  let score = 0;
  let maxScore = 100;

  if (extractedData.tax_profile?.filing_status) score += 15;
  if (extractedData.tax_profile?.total_income) score += 20;
  if (extractedData.tax_items?.mortgage_interest || extractedData.tax_items?.charitable || extractedData.tax_items?.medical) score += 15;
  if (extractedData.tax_items?.retirement_contributions || extractedData.tax_items?.has_hsa) score += 15;
  if (extractedData.contact?.name) score += 5;
  if (extractedData.documents && extractedData.documents.length > 0) score += 20;
  if (extractedData.tax_profile?.state) score += 10;

  const percentage = Math.round((score / maxScore) * 100);

  if (percentage >= 70) return { level: 'high', percentage, label: 'High confidence' };
  if (percentage >= 40) return { level: 'medium', percentage, label: 'Moderate confidence' };
  return { level: 'low', percentage, label: 'Limited data' };
}

export function getConfidenceDisclaimer(includeIRS = false) {
  const confidence = getConfidenceLevel();
  let disclaimer = '';

  if (confidence.level === 'high') {
    disclaimer = `<div class="confidence-indicator confidence-high">
      <span>${typeof getIcon === 'function' ? getIcon('check-circle', 'sm') : ''} ${confidence.label} (${confidence.percentage}% data)</span>
      <span style="margin-left: auto; font-size: var(--text-2xs);">Verify with a tax professional before filing</span>
    </div>`;
  } else if (confidence.level === 'medium') {
    disclaimer = `<div class="confidence-indicator confidence-medium">
      <span>${typeof getIcon === 'function' ? getIcon('exclamation-triangle', 'sm') : ''} ${confidence.label} (${confidence.percentage}% data)</span>
      <span style="margin-left: auto; font-size: var(--text-2xs);">Provide more details for better accuracy</span>
    </div>`;
  } else {
    disclaimer = `<div class="confidence-indicator confidence-low">
      <span>${typeof getIcon === 'function' ? getIcon('information-circle', 'sm') : ''} ${confidence.label} (${confidence.percentage}% data)</span>
      <span style="margin-left: auto; font-size: var(--text-2xs);">General guidance only - more info needed</span>
    </div>`;
  }

  if (includeIRS) {
    disclaimer += `<div style="font-size: var(--text-2xs); color: var(--text-secondary); margin-top: var(--space-2);">
      ${typeof getIcon === 'function' ? getIcon('clipboard-document-list', 'sm') : ''} Based on 2025 IRS guidelines. See <a href="https://www.irs.gov/forms-instructions" target="_blank" rel="noopener" style="color: var(--primary);">IRS.gov</a> for official forms.
    </div>`;
  }

  return disclaimer;
}

// ======================== QUESTIONING STATE ========================

export let questioningState = {
  askedQuestions: new Set(),
  currentPhase: 'basics',
  callCount: 0,
  maxCalls: 50
};

export function markQuestionAsked(questionId) {
  questioningState.askedQuestions.add(questionId);
}

export function wasQuestionAsked(questionId) {
  return questioningState.askedQuestions.has(questionId);
}

export function resetQuestioningState() {
  questioningState.askedQuestions.clear();
  questioningState.callCount = 0;
  questioningState.currentPhase = 'basics';
}

// ======================== LEAD SCORING ========================

export function calculateLeadScore() {
  let score = 0;

  if (extractedData.contact.name) score += 10;
  if (extractedData.contact.email) score += 20;
  if (extractedData.contact.phone) score += 15;
  if (extractedData.tax_profile.filing_status) score += 10;
  if (extractedData.tax_profile.total_income) score += 15;
  if (extractedData.documents.length > 0) score += 20;

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

  updateProgress(Math.min(score, 95));
  advanceJourneyBasedOnData();
}

// ======================== HANDLE QUICK ACTION ========================
// Note: FSM dispatch block REMOVED per Sprint 1 requirements

export async function handleQuickAction(value, displayLabel = null) {
  DevLogger.log('====== handleQuickAction CALLED ======');
  DevLogger.log('Quick action clicked:', value);
  DevLogger.log('Display label:', displayLabel);

  // All action handling falls through to AI processing
  var displayText = value.replace(/_/g, ' ').replace(/\b\w/g, function(l) { return l.toUpperCase(); });
  addMessage('user', displayLabel || displayText);
  await processAIResponse(value);
}

// ======================== INTELLIGENT QUESTIONING ENGINE ========================

export async function startIntelligentQuestioning() {
  questioningState.callCount++;

  if (questioningState.callCount > questioningState.maxCalls) {
    DevLogger.warn('startIntelligentQuestioning exceeded max calls, skipping to summary');
    await showPreliminarySummary();
    return;
  }

  showTyping();

  setTimeout(async () => {
    hideTyping();

    const profile = extractedData.tax_profile;
    const items = extractedData.tax_items;
    const isHighEarner = (profile.total_income || 0) >= 200000;
    const isSelfEmployed = profile.is_self_employed || profile.income_source === 'Self-Employed / 1099';
    const isBusinessOwner = profile.income_source === 'Business Owner';

    // PHASE 1: BASIC INFORMATION

    // Filing Status
    if (!profile.filing_status) {
      markQuestionAsked('filing_status');
      addMessage('ai', `Let's start with the basics. What's your filing status for 2025?`, [
        { label: 'Single', value: 'filing_single', description: 'Unmarried or legally separated' },
        { label: 'Married Filing Jointly', value: 'filing_married', description: 'Married and filing together with spouse' },
        { label: 'Married Filing Separately', value: 'filing_mfs', description: 'Married but filing individual returns' },
        { label: 'Head of Household', value: 'filing_hoh', description: 'Unmarried and paying 50%+ of household costs' }
      ], { inputType: 'radio' });
      return;
    }

    // State
    if (!profile.state) {
      markQuestionAsked('state');
      addMessage('ai', `Which state do you live in? This affects your state tax calculation.`, [], {
        inputType: 'dropdown',
        placeholder: 'Select your state...',
        groups: [
          {
            label: 'No Income Tax States',
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
            label: 'West',
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
            label: 'Midwest',
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
            label: 'Northeast',
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
            label: 'South',
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

    // Income
    if (!profile.total_income && !wasQuestionAsked('income')) {
      markQuestionAsked('income');
      addMessage('ai', `What's your approximate total annual income for 2025?`, [
        { label: 'Under $30K', value: 'income_under30k' },
        { label: '$30K - $50K', value: 'income_30_50k' },
        { label: '$50K - $100K', value: 'income_50_100k' },
        { label: '$100K - $200K', value: 'income_100_200k' },
        { label: '$200K - $500K', value: 'income_200_500k' },
        { label: '$500K+', value: 'income_500k_plus' },
        { label: 'Enter exact amount', value: 'income_custom' }
      ]);
      return;
    }

    // Income source
    if (!profile.income_source && !wasQuestionAsked('income_source')) {
      markQuestionAsked('income_source');
      addMessage('ai', `<strong>Where does most of your income come from?</strong><br><small>This helps identify relevant deductions and strategies.</small>`, [
        { label: 'W-2 Employee', value: 'source_w2' },
        { label: 'Self-Employed / 1099', value: 'source_self_employed' },
        { label: 'Business Owner', value: 'source_business' },
        { label: 'Investments / Retirement', value: 'source_investments' },
        { label: 'Multiple sources', value: 'source_multiple' }
      ]);
      return;
    }

    // Dependents
    if (profile.dependents == null && !wasQuestionAsked('dependents')) {
      markQuestionAsked('dependents');
      addMessage('ai', `<strong>Do you have any dependents?</strong><br><small>This affects credits like Child Tax Credit ($2,000/child).</small>`, [
        { label: 'No dependents', value: 'deps_0' },
        { label: '1 dependent', value: 'deps_1' },
        { label: '2 dependents', value: 'deps_2' },
        { label: '3+ dependents', value: 'deps_3plus' }
      ]);
      return;
    }

    // If we have the basics, try running the analysis
    if (profile.filing_status && profile.total_income) {
      // Skip to preliminary summary if we've asked enough
      await showPreliminarySummary();
      return;
    }

    // Fallback: ask for the most important missing piece
    addMessage('ai', `I have most of your information. What else can you tell me about your tax situation?`, [
      { label: 'Run my analysis \u2192', value: 'run_full_analysis', primary: true },
      { label: 'Add deductions', value: 'explore_deductions' },
      { label: 'Upload documents', value: 'yes_upload' }
    ]);
  }, 800);
}

// ======================== PRELIMINARY SUMMARY ========================

export async function showPreliminarySummary() {
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

  const stateDisplay = profile.state_name || profile.state || 'Not specified';
  const isVeryHighEarner = (profile.total_income || 0) >= 500000;
  const complexityIndicator = extractedData.lead_data.complexity === 'complex' ? 'Complex' :
                               extractedData.lead_data.complexity === 'moderate' ? 'Moderate' : 'Standard';

  let additionalDetails = '';

  if (profile.is_self_employed || profile.income_source === 'Business Owner') {
    additionalDetails += `
      <div style="margin-top: var(--space-4); padding-top: var(--space-4); border-top: 1px solid #e2e8f0;">
        <div style="font-weight: var(--font-semibold); color: var(--color-primary-500); margin-bottom: var(--space-2-5);">Business Details</div>
        ${profile.business_type ? `<div style="display: flex; justify-content: space-between; margin-bottom: var(--space-1-5);">
          <span style="color: #4a5568;">Business Type:</span>
          <strong>${profile.business_type}</strong>
        </div>` : ''}
      </div>
    `;
  }

  const taxItemsList = [];
  if (items.mortgage_interest) taxItemsList.push(`Mortgage Interest: $${items.mortgage_interest.toLocaleString()}`);
  if (items.charitable) taxItemsList.push(`Charitable Donations: $${items.charitable.toLocaleString()}`);
  if (items.medical) taxItemsList.push(`Medical Expenses: $${items.medical.toLocaleString()}`);

  if (taxItemsList.length > 0) {
    additionalDetails += `
      <div style="margin-top: var(--space-4); padding-top: var(--space-4); border-top: 1px solid #e2e8f0;">
        <div style="font-weight: var(--font-semibold); color: var(--color-primary-500); margin-bottom: var(--space-2-5);">Deductions & Credits</div>
        ${taxItemsList.map(item => `<div style="color: #4a5568; font-size: var(--text-xs-plus); margin-bottom: var(--space-1);">\u2022 ${item}</div>`).join('')}
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
          <strong>${profile.dependents || 0}</strong>
        </div>
      </div>

      ${additionalDetails}
    </div>

    <div style="font-size: var(--text-sm); color: #4a5568; line-height: 1.6;">
      Ready to run your personalized tax analysis and identify savings opportunities.
    </div>
  `, [
    { label: 'Run Full Analysis \u2192', value: 'run_full_analysis', primary: true },
    { label: 'Edit my information', value: 'edit_profile' }
  ]);
}

// ======================== DEDUCTION HELPERS ========================

export async function analyzeDeductions() {
  showTyping();
  setTimeout(() => {
    hideTyping();
    addMessage('ai', `Which deductions apply to you?`, [
      { label: 'Mortgage', value: 'has_mortgage' },
      { label: 'Charity', value: 'has_charity' },
      { label: 'Medical', value: 'has_medical' },
      { label: 'Business', value: 'has_business' },
      { label: 'Retirement', value: 'has_retirement' },
      { label: 'None / Skip \u2192', value: 'deductions_done' }
    ]);
  }, 800);
}

export function askNextDeductionOrCredits() {
  const deductions = extractedData.deductions || [];

  if (deductions.length > 0) {
    addMessage('ai', `Any other deductions?`, [
      { label: 'Mortgage', value: 'has_mortgage' },
      { label: 'Charity', value: 'has_charity' },
      { label: 'Medical', value: 'has_medical' },
      { label: 'Done, continue \u2192', value: 'deductions_done' }
    ]);
  } else {
    addMessage('ai', `Any tax credits you might qualify for?`, [
      { label: 'Child Tax Credit', value: 'credit_child' },
      { label: 'Education Credit', value: 'credit_education' },
      { label: 'Skip to report \u2192', value: 'generate_report' }
    ]);
  }
}

// ======================== CPA CONNECTION ========================

export async function requestCPAConnection() {
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

// ======================== SUMMARY ========================

export function generateSummary() {
  let summary = '';

  if (extractedData.filing_status) {
    summary += `<strong>Filing Status:</strong> ${extractedData.filing_status}<br>`;
  }
  if (extractedData.income_range) {
    summary += `<strong>Income Range:</strong> ${extractedData.income_range}<br>`;
  }
  if (extractedData.focus_area) {
    summary += `<strong>Focus Area:</strong> ${extractedData.focus_area}<br>`;
  }
  if (extractedData.deductions && extractedData.deductions.length > 0) {
    summary += `<strong>Deductions:</strong> ${extractedData.deductions.join(', ')}<br>`;
  }
  if (extractedData.credits && extractedData.credits.length > 0) {
    summary += `<strong>Credits:</strong> ${extractedData.credits.join(', ')}<br>`;
  }

  return summary || 'Your comprehensive tax profile';
}

// ======================== LEAD CAPTURE HELPERS ========================

export async function captureName() {
  const nameInput = document.getElementById('nameInput');
  const name = nameInput ? nameInput.value.trim() : '';

  if (!name || name.length < 2) {
    showToast('Please enter your name (at least 2 characters)', 'error');
    if (nameInput) nameInput.focus();
    return;
  }

  const sanitizedName = name.replace(/[<>"'&]/g, '').substring(0, 100);

  extractedData.contact.name = sanitizedName;
  extractedData.lead_data.score += 15;
  addMessage('user', name);

  showTyping();
  setTimeout(() => {
    hideTyping();
    addMessage('ai', `Thank you, ${name}! It's a pleasure to work with you.<br><br>Now, to provide you with the most accurate tax analysis and connect you with the right CPA specialist, <strong>may I have your email address?</strong>`, [
      { label: (typeof getIcon === 'function' ? getIcon('envelope', 'sm') : '') + ' Enter email', value: 'enter_email' },
      { label: 'Skip for now', value: 'skip_email' }
    ]);
  }, 1000);
}

export async function captureEmail() {
  const emailInput = document.getElementById('emailInput');
  const email = emailInput ? emailInput.value.trim().toLowerCase() : '';

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!email || !emailRegex.test(email)) {
    showToast('Please enter a valid email address (e.g., name@example.com)', 'error');
    if (emailInput) emailInput.focus();
    return;
  }

  const sanitizedEmail = email.substring(0, 254);

  extractedData.contact.email = sanitizedEmail;
  extractedData.lead_data.score += 20;
  setLeadQualified(true);
  addMessage('user', email);

  showTyping();
  setTimeout(() => {
    hideTyping();
    const firstName = extractedData.contact.name ? extractedData.contact.name.split(' ')[0] : 'there';
    addMessage('ai', `Perfect, ${firstName}! I've saved your email.<br><br><strong>You're now qualified for our premium tax advisory service!</strong><br><br><strong>How would you like to provide your tax information?</strong>`, [
      { label: (typeof getIcon === 'function' ? getIcon('document-text', 'sm') : '') + ' Upload tax documents (fastest)', value: 'upload_docs_qualified' },
      { label: (typeof getIcon === 'function' ? getIcon('chat-bubble-left-right', 'sm') : '') + ' Answer questions conversationally', value: 'conversational_qualified' },
      { label: (typeof getIcon === 'function' ? getIcon('sparkles', 'sm') : '') + ' Hybrid: docs + questions', value: 'hybrid_qualified' }
    ]);
  }, 1500);
}

export async function captureIncome() {
  const incomeInput = document.getElementById('incomeInput');
  const rawValue = incomeInput ? incomeInput.value.replace(/[^0-9]/g, '') : '0';
  const income = parseInt(rawValue, 10);

  if (!income || income <= 0) {
    showToast('Please enter a valid income amount', 'error');
    if (incomeInput) incomeInput.focus();
    return;
  }

  if (income > 50000000) {
    showToast('Please verify this amount - it seems unusually high', 'warning');
  }

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

// Expose lead capture helpers globally for inline HTML onclick
window.captureName = captureName;
window.captureEmail = captureEmail;
window.captureIncome = captureIncome;
