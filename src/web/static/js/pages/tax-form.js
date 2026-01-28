/**
 * Tax Form Wizard Page JavaScript
 *
 * Handles multi-step tax form wizard functionality.
 * Imports core utilities from modular system.
 */

// Import core utilities
import {
  escapeHtml,
  formatCurrency,
  formatNumber,
  debounce,
  showToast,
} from '/static/js/core/utils.js';

import { api, getCSRFToken } from '/static/js/core/api.js';

// =============================================================================
// STATE MANAGEMENT
// =============================================================================
const state = {
  currentStep: 1,
  totalSteps: 6,
  sessionId: null,
  filingStatus: null,
  formData: {},
  validationErrors: {},
  computed: {
    totalIncome: 0,
    agi: 0,
    taxableIncome: 0,
    totalTax: 0,
    effectiveRate: 0,
    refundOrOwed: 0,
  },
  recommendations: [],
  isDirty: false,
  lastSaved: null,
};

// =============================================================================
// INITIALIZATION
// =============================================================================
export function init() {
  // Load session if exists
  const savedSession = localStorage.getItem('tax_form_session');
  if (savedSession) {
    try {
      const parsed = JSON.parse(savedSession);
      Object.assign(state, parsed);
      restoreFormState();
    } catch (e) {
      console.error('Failed to restore session:', e);
    }
  }

  // Initialize step display
  updateStepDisplay();
  updateProgressBar();

  // Setup form handlers
  setupFormHandlers();

  // Setup auto-save
  setupAutoSave();

  // Check for deadline
  checkDeadline();
}

// =============================================================================
// STEP NAVIGATION
// =============================================================================
export function nextStep() {
  if (!validateCurrentStep()) {
    showToast('Please fix the errors before continuing', 'error');
    return;
  }

  if (state.currentStep < state.totalSteps) {
    state.currentStep++;
    updateStepDisplay();
    updateProgressBar();
    saveSession();
    scrollToTop();
  }
}

export function prevStep() {
  if (state.currentStep > 1) {
    state.currentStep--;
    updateStepDisplay();
    updateProgressBar();
    scrollToTop();
  }
}

export function goToStep(step) {
  if (step >= 1 && step <= state.totalSteps) {
    // Allow going back, but validate when going forward
    if (step > state.currentStep && !validateCurrentStep()) {
      showToast('Please complete the current step first', 'warning');
      return;
    }
    state.currentStep = step;
    updateStepDisplay();
    updateProgressBar();
    scrollToTop();
  }
}

function updateStepDisplay() {
  // Hide all step sections
  document.querySelectorAll('.step-section').forEach(section => {
    section.classList.remove('active');
  });

  // Show current step
  const currentSection = document.querySelector(`[data-step="${state.currentStep}"]`);
  if (currentSection) {
    currentSection.classList.add('active');
  }

  // Update step indicators
  document.querySelectorAll('.step').forEach((step, index) => {
    const stepNum = index + 1;
    step.classList.remove('active', 'completed');

    if (stepNum === state.currentStep) {
      step.classList.add('active');
    } else if (stepNum < state.currentStep) {
      step.classList.add('completed');
    }
  });

  // Update navigation buttons
  const prevBtn = document.getElementById('btnPrev');
  const nextBtn = document.getElementById('btnNext');

  if (prevBtn) {
    prevBtn.style.visibility = state.currentStep === 1 ? 'hidden' : 'visible';
  }

  if (nextBtn) {
    nextBtn.textContent = state.currentStep === state.totalSteps ? 'Generate Report' : 'Continue';
  }
}

function updateProgressBar() {
  const progress = ((state.currentStep - 1) / (state.totalSteps - 1)) * 100;

  const progressFill = document.getElementById('progressFill');
  if (progressFill) {
    progressFill.style.width = `${progress}%`;
  }

  const mobileProgressBar = document.getElementById('mobileProgressBar');
  if (mobileProgressBar) {
    mobileProgressBar.style.width = `${progress}%`;
  }
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// =============================================================================
// FORM HANDLING
// =============================================================================
function setupFormHandlers() {
  // Filing status selection
  document.querySelectorAll('.filing-status-option').forEach(option => {
    option.addEventListener('click', () => {
      selectFilingStatus(option.dataset.status);
    });
  });

  // Form inputs
  document.querySelectorAll('.form-input, .form-select').forEach(input => {
    input.addEventListener('change', handleInputChange);
    input.addEventListener('blur', validateField);
  });

  // Currency inputs - format on blur
  document.querySelectorAll('.currency-input').forEach(input => {
    input.addEventListener('blur', formatCurrencyInput);
    input.addEventListener('focus', unformatCurrencyInput);
  });
}

function handleInputChange(event) {
  const { name, value, type, checked } = event.target;

  // Update form data
  state.formData[name] = type === 'checkbox' ? checked : value;
  state.isDirty = true;

  // Recalculate if income-related field
  if (isIncomeField(name)) {
    recalculateTaxes();
  }
}

function validateField(event) {
  const input = event.target;
  const { name, value, required } = input;

  // Clear previous error
  clearFieldError(name);

  // Required check
  if (required && !value.trim()) {
    setFieldError(name, 'This field is required');
    return false;
  }

  // Specific validations
  if (name.includes('ssn') && value) {
    if (!/^\d{3}-?\d{2}-?\d{4}$/.test(value)) {
      setFieldError(name, 'Invalid SSN format');
      return false;
    }
  }

  if (name.includes('email') && value) {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      setFieldError(name, 'Invalid email format');
      return false;
    }
  }

  if (name.includes('phone') && value) {
    if (!/^[\d\s\-\(\)]{10,}$/.test(value)) {
      setFieldError(name, 'Invalid phone format');
      return false;
    }
  }

  // Mark as valid
  input.classList.remove('error');
  input.classList.add('success');
  return true;
}

function validateCurrentStep() {
  let isValid = true;

  const currentSection = document.querySelector(`[data-step="${state.currentStep}"]`);
  if (!currentSection) return true;

  // Validate all required fields in current step
  currentSection.querySelectorAll('[required]').forEach(input => {
    if (!input.value.trim()) {
      setFieldError(input.name, 'This field is required');
      isValid = false;
    }
  });

  // Step-specific validation
  switch (state.currentStep) {
    case 1:
      if (!state.filingStatus) {
        showToast('Please select your filing status', 'warning');
        isValid = false;
      }
      break;
  }

  return isValid;
}

function setFieldError(name, message) {
  state.validationErrors[name] = message;

  const input = document.querySelector(`[name="${name}"]`);
  if (input) {
    input.classList.add('error');
    input.classList.remove('success');

    // Show error message
    let errorEl = input.parentElement.querySelector('.form-error');
    if (!errorEl) {
      errorEl = document.createElement('span');
      errorEl.className = 'form-error';
      input.parentElement.appendChild(errorEl);
    }
    errorEl.textContent = message;
  }
}

function clearFieldError(name) {
  delete state.validationErrors[name];

  const input = document.querySelector(`[name="${name}"]`);
  if (input) {
    input.classList.remove('error');
    const errorEl = input.parentElement.querySelector('.form-error');
    if (errorEl) errorEl.remove();
  }
}

// =============================================================================
// FILING STATUS
// =============================================================================
export function selectFilingStatus(status) {
  state.filingStatus = status;
  state.formData.filingStatus = status;
  state.isDirty = true;

  // Update UI
  document.querySelectorAll('.filing-status-option').forEach(option => {
    option.classList.toggle('selected', option.dataset.status === status);
  });

  // Recalculate taxes with new status
  recalculateTaxes();

  // Show spouse fields if applicable
  const spouseFields = document.querySelectorAll('.spouse-field');
  const showSpouse = status === 'married_filing_jointly';
  spouseFields.forEach(field => {
    field.style.display = showSpouse ? 'block' : 'none';
  });
}

// =============================================================================
// TAX CALCULATIONS
// =============================================================================
function isIncomeField(name) {
  const incomeFields = ['wages', 'businessIncome', 'investmentIncome', 'otherIncome', 'w2Income'];
  return incomeFields.some(f => name.toLowerCase().includes(f.toLowerCase()));
}

function recalculateTaxes() {
  // Gather income values
  const wages = parseFloat(state.formData.wages) || 0;
  const businessIncome = parseFloat(state.formData.businessIncome) || 0;
  const investmentIncome = parseFloat(state.formData.investmentIncome) || 0;
  const otherIncome = parseFloat(state.formData.otherIncome) || 0;

  // Total income
  state.computed.totalIncome = wages + businessIncome + investmentIncome + otherIncome;

  // AGI (simplified - just total income for now)
  state.computed.agi = state.computed.totalIncome;

  // Standard deduction based on filing status
  const standardDeductions = {
    'single': 14600,
    'married_filing_jointly': 29200,
    'married_filing_separately': 14600,
    'head_of_household': 21900,
    'qualifying_widow': 29200,
  };

  const deduction = standardDeductions[state.filingStatus] || 14600;

  // Taxable income
  state.computed.taxableIncome = Math.max(0, state.computed.agi - deduction);

  // Calculate federal tax (simplified 2025 brackets)
  state.computed.totalTax = calculateFederalTax(state.computed.taxableIncome, state.filingStatus);

  // Effective rate
  state.computed.effectiveRate = state.computed.totalIncome > 0
    ? (state.computed.totalTax / state.computed.totalIncome * 100).toFixed(1)
    : 0;

  // Withholding
  const withheld = parseFloat(state.formData.federalWithheld) || 0;
  state.computed.refundOrOwed = withheld - state.computed.totalTax;

  // Update UI
  updateTaxSummary();

  // Generate recommendations
  generateRecommendations();
}

function calculateFederalTax(taxableIncome, filingStatus) {
  // 2025 Tax brackets (simplified)
  const brackets = {
    'single': [
      [11600, 0.10],
      [47150, 0.12],
      [100525, 0.22],
      [191950, 0.24],
      [243725, 0.32],
      [609350, 0.35],
      [Infinity, 0.37],
    ],
    'married_filing_jointly': [
      [23200, 0.10],
      [94300, 0.12],
      [201050, 0.22],
      [383900, 0.24],
      [487450, 0.32],
      [731200, 0.35],
      [Infinity, 0.37],
    ],
  };

  const bracketSet = brackets[filingStatus] || brackets['single'];
  let tax = 0;
  let prevCutoff = 0;

  for (const [cutoff, rate] of bracketSet) {
    if (taxableIncome <= prevCutoff) break;
    const taxableInBracket = Math.min(taxableIncome, cutoff) - prevCutoff;
    tax += taxableInBracket * rate;
    prevCutoff = cutoff;
  }

  return Math.round(tax);
}

function updateTaxSummary() {
  // Update summary elements
  const elements = {
    'totalIncome': state.computed.totalIncome,
    'agi': state.computed.agi,
    'taxableIncome': state.computed.taxableIncome,
    'totalTax': state.computed.totalTax,
    'effectiveRate': state.computed.effectiveRate,
    'refundOrOwed': Math.abs(state.computed.refundOrOwed),
  };

  Object.entries(elements).forEach(([id, value]) => {
    const el = document.getElementById(id);
    if (el) {
      if (id === 'effectiveRate') {
        el.textContent = `${value}%`;
      } else {
        el.textContent = formatCurrency(value);
      }
    }
  });

  // Update refund/owed display
  const refundDisplay = document.getElementById('refundDisplay');
  if (refundDisplay) {
    const isRefund = state.computed.refundOrOwed >= 0;
    refundDisplay.classList.toggle('owed', !isRefund);

    const label = refundDisplay.querySelector('.refund-label');
    if (label) {
      label.textContent = isRefund ? 'Estimated Refund' : 'Estimated Amount Owed';
    }
  }
}

// =============================================================================
// RECOMMENDATIONS
// =============================================================================
function generateRecommendations() {
  state.recommendations = [];

  const income = state.computed.totalIncome;
  const filingStatus = state.filingStatus;

  // 401(k) recommendation
  if (income > 50000) {
    const maxContribution = 23000;
    const potentialSavings = Math.min(maxContribution * 0.22, income * 0.06);
    state.recommendations.push({
      title: 'Maximize 401(k) Contributions',
      savings: potentialSavings,
      description: 'Contribute the maximum to reduce taxable income.',
      category: 'retirement',
    });
  }

  // IRA recommendation
  if (income < 160000) {
    state.recommendations.push({
      title: 'Traditional IRA Contribution',
      savings: 7000 * 0.22,
      description: 'Deductible IRA contribution for additional tax savings.',
      category: 'retirement',
    });
  }

  // HSA recommendation
  if (state.formData.hasHDHP) {
    const hsaLimit = filingStatus === 'married_filing_jointly' ? 8300 : 4150;
    state.recommendations.push({
      title: 'Maximize HSA Contribution',
      savings: hsaLimit * 0.22,
      description: 'Triple tax advantage with HSA contributions.',
      category: 'deductions',
    });
  }

  // Business deductions
  if (state.formData.businessIncome > 0) {
    state.recommendations.push({
      title: 'QBI Deduction (Section 199A)',
      savings: state.formData.businessIncome * 0.20 * 0.22,
      description: 'Qualified Business Income deduction available.',
      category: 'business',
    });
  }

  // Update recommendations UI
  updateRecommendationsUI();
}

function updateRecommendationsUI() {
  const container = document.getElementById('recommendationsList');
  if (!container) return;

  if (state.recommendations.length === 0) {
    container.innerHTML = '<p class="text-muted">Complete your tax information to see personalized recommendations.</p>';
    return;
  }

  const totalSavings = state.recommendations.reduce((sum, r) => sum + r.savings, 0);

  container.innerHTML = `
    <div style="margin-bottom: var(--space-4); padding: var(--space-3); background: var(--color-success-100); border-radius: var(--radius-lg); text-align: center;">
      <div style="font-size: var(--text-sm); color: var(--color-success-700);">Potential Tax Savings</div>
      <div style="font-size: var(--text-2xl); font-weight: bold; color: var(--color-success-600);">${formatCurrency(totalSavings)}</div>
    </div>
    ${state.recommendations.map(r => `
      <div class="recommendation-item">
        <div class="recommendation-title">${escapeHtml(r.title)}</div>
        <div class="recommendation-savings">Save up to ${formatCurrency(r.savings)}</div>
        <div class="recommendation-desc">${escapeHtml(r.description)}</div>
      </div>
    `).join('')}
  `;
}

// =============================================================================
// CURRENCY INPUT FORMATTING
// =============================================================================
function formatCurrencyInput(event) {
  const input = event.target;
  const value = parseFloat(input.value.replace(/[^0-9.-]/g, '')) || 0;
  input.value = formatCurrency(value).replace('$', '');
}

function unformatCurrencyInput(event) {
  const input = event.target;
  const value = parseFloat(input.value.replace(/[^0-9.-]/g, '')) || 0;
  input.value = value || '';
}

// =============================================================================
// AUTO-SAVE
// =============================================================================
function setupAutoSave() {
  // Auto-save every 30 seconds if dirty
  setInterval(() => {
    if (state.isDirty) {
      saveSession();
    }
  }, 30000);

  // Save on page unload
  window.addEventListener('beforeunload', () => {
    if (state.isDirty) {
      saveSession();
    }
  });
}

function saveSession() {
  try {
    state.lastSaved = new Date().toISOString();
    state.isDirty = false;

    localStorage.setItem('tax_form_session', JSON.stringify({
      currentStep: state.currentStep,
      filingStatus: state.filingStatus,
      formData: state.formData,
      computed: state.computed,
      lastSaved: state.lastSaved,
    }));

    updateSaveStatus('saved');
  } catch (e) {
    console.error('Failed to save session:', e);
    updateSaveStatus('error');
  }
}

function restoreFormState() {
  // Restore filing status
  if (state.filingStatus) {
    selectFilingStatus(state.filingStatus);
  }

  // Restore form values
  Object.entries(state.formData).forEach(([name, value]) => {
    const input = document.querySelector(`[name="${name}"]`);
    if (input) {
      if (input.type === 'checkbox') {
        input.checked = value;
      } else {
        input.value = value;
      }
    }
  });

  // Recalculate
  recalculateTaxes();
}

function updateSaveStatus(status) {
  const saveStatus = document.getElementById('saveStatus');
  const saveText = document.getElementById('saveText');
  const saveTimestamp = document.getElementById('saveTimestamp');

  if (saveStatus) saveStatus.dataset.state = status;

  if (saveText) {
    const messages = {
      'saved': 'All changes saved',
      'saving': 'Saving...',
      'error': 'Save failed',
    };
    saveText.textContent = messages[status] || '';
  }

  if (saveTimestamp && state.lastSaved) {
    const time = new Date(state.lastSaved);
    saveTimestamp.textContent = time.toLocaleTimeString();
  }
}

// =============================================================================
// DEADLINE CHECK
// =============================================================================
function checkDeadline() {
  const deadlineBanner = document.getElementById('deadlineBanner');
  if (!deadlineBanner) return;

  const taxDeadline = new Date('2026-04-15');
  const today = new Date();
  const daysUntil = Math.ceil((taxDeadline - today) / (1000 * 60 * 60 * 24));

  if (daysUntil > 0 && daysUntil <= 90) {
    const deadlineMessage = document.getElementById('deadlineMessage');
    if (deadlineMessage) {
      deadlineMessage.textContent = `${daysUntil} days until April 15, 2026`;
    }
    deadlineBanner.style.display = 'block';
  }
}

// =============================================================================
// WELCOME MODAL
// =============================================================================
export function showWelcomeModal() {
  const modal = document.getElementById('welcomeModal');
  if (modal) modal.classList.remove('hidden');
}

export function hideWelcomeModal() {
  const modal = document.getElementById('welcomeModal');
  if (modal) modal.classList.add('hidden');
}

export function startIntegratedFlow() {
  hideWelcomeModal();
  // Start with step 1
  goToStep(1);
}

// =============================================================================
// DOCUMENT UPLOAD
// =============================================================================
export function handleDocumentUpload(event) {
  const files = event.target.files;
  if (!files.length) return;

  for (const file of files) {
    uploadDocument(file);
  }

  event.target.value = '';
}

async function uploadDocument(file) {
  showToast(`Uploading ${file.name}...`, 'info');

  const formData = new FormData();
  formData.append('file', file);
  formData.append('session_id', state.sessionId);

  try {
    const response = await fetch('/api/documents/upload', {
      method: 'POST',
      headers: {
        'X-CSRF-Token': getCSRFToken(),
      },
      body: formData,
    });

    const data = await response.json();

    if (data.success) {
      showToast(`${file.name} uploaded successfully`, 'success');

      // If OCR extracted data, auto-fill form
      if (data.extracted_data) {
        autoFillFromExtraction(data.extracted_data);
      }

      // Add to uploaded files list
      addUploadedFile(file, data.file_id);
    } else {
      showToast(`Failed to upload ${file.name}`, 'error');
    }
  } catch (e) {
    console.error('Upload error:', e);
    showToast(`Error uploading ${file.name}`, 'error');
  }
}

function autoFillFromExtraction(data) {
  // Auto-fill form fields from extracted document data
  const mappings = {
    'wages': 'wages',
    'federal_withheld': 'federalWithheld',
    'state_withheld': 'stateWithheld',
    'employer_name': 'employerName',
    'employer_ein': 'employerEin',
  };

  Object.entries(mappings).forEach(([extractedKey, formKey]) => {
    if (data[extractedKey]) {
      state.formData[formKey] = data[extractedKey];

      const input = document.querySelector(`[name="${formKey}"]`);
      if (input) {
        input.value = data[extractedKey];
        input.classList.add('auto-filled');
      }
    }
  });

  recalculateTaxes();
  showToast('Document data extracted and applied', 'success');
}

function addUploadedFile(file, fileId) {
  const list = document.getElementById('uploadedFilesList');
  if (!list) return;

  const item = document.createElement('div');
  item.className = 'uploaded-file';
  item.innerHTML = `
    <span class="uploaded-file-icon">📄</span>
    <div class="uploaded-file-info">
      <div class="uploaded-file-name">${escapeHtml(file.name)}</div>
      <div class="uploaded-file-size">${formatFileSize(file.size)}</div>
    </div>
    <button class="uploaded-file-remove" onclick="removeUploadedFile('${fileId}', this)" title="Remove file">×</button>
  `;
  list.appendChild(item);
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

export function removeUploadedFile(fileId, button) {
  // Remove from UI
  const item = button.closest('.uploaded-file');
  if (item) item.remove();

  // TODO: Call API to delete file
}

// =============================================================================
// EXPORTS FOR GLOBAL ACCESS
// =============================================================================
window.nextStep = nextStep;
window.prevStep = prevStep;
window.goToStep = goToStep;
window.selectFilingStatus = selectFilingStatus;
window.showWelcomeModal = showWelcomeModal;
window.hideWelcomeModal = hideWelcomeModal;
window.startIntegratedFlow = startIntegratedFlow;
window.handleDocumentUpload = handleDocumentUpload;
window.removeUploadedFile = removeUploadedFile;

// Initialize on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

export { state };
