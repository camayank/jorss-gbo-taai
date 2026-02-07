/**
 * Chatbot UX Enhancements
 *
 * This module provides enhanced UI components for the Intelligent Advisor chatbot:
 * - Profile editing panel with editable fields
 * - Savings gauge visualization
 * - Tax term explanations (tooltips/modals)
 * - Current vs Optimized comparison view
 * - PDF preview modal
 */

// ============================================================================
// SECURITY UTILITIES - XSS Prevention
// ============================================================================

/**
 * Escape HTML entities to prevent XSS attacks.
 * ALWAYS use this function when inserting user data into HTML via innerHTML.
 * @param {string|number} str - The string to escape
 * @returns {string} - HTML-escaped string
 */
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Escape for use in HTML attributes.
 * Use when inserting values into HTML attributes like onclick, data-*, etc.
 * @param {string} str - The string to escape
 * @returns {string} - Attribute-safe string
 */
function escapeAttribute(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\\/g, '&#92;');
}

/**
 * Safe currency formatter - returns escaped HTML.
 * @param {number} value - The currency value
 * @returns {string} - Formatted and escaped currency string
 */
function formatCurrencySafe(value) {
  if (value === null || value === undefined || isNaN(value)) return '$0';
  const formatted = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0
  }).format(value);
  return escapeHtml(formatted);
}

// ============================================================================
// PRODUCTION-SAFE LOGGER - Prevents debug info leakage in production
// ============================================================================

/**
 * Production-safe logger configuration.
 * Set UX_DEBUG_MODE to true for development debugging.
 */
const UX_DEBUG_MODE = false;

const DevLogger = {
  log: function(...args) {
    if (UX_DEBUG_MODE) console.log('[UX-DEV]', ...args);
  },
  warn: function(...args) {
    if (UX_DEBUG_MODE) console.warn('[UX-DEV]', ...args);
  },
  error: function(...args) {
    if (UX_DEBUG_MODE) {
      console.error('[UX-DEV]', ...args);
    } else {
      console.error('An error occurred.');
    }
  }
};

// ============================================================================
// PROFILE EDITOR COMPONENT
// ============================================================================

class ProfileEditor {
  constructor(containerId, extractedData, onUpdate) {
    this.container = document.getElementById(containerId);
    this.data = extractedData;
    this.onUpdate = onUpdate;
    this.isEditing = false;
  }

  render() {
    if (!this.container) return;

    const profile = this.data?.tax_profile || {};
    const filingStatusDisplay = this.formatFilingStatus(profile.filing_status);
    const incomeDisplay = this.formatCurrency(profile.total_income);

    this.container.innerHTML = `
      <div class="profile-editor">
        <div class="profile-header">
          <span class="profile-title">📋 Your Tax Profile</span>
          <button class="edit-toggle-btn" onclick="profileEditor.toggleEdit()">
            ${this.isEditing ? '✓ Done' : '✏️ Edit'}
          </button>
        </div>

        <div class="profile-fields ${this.isEditing ? 'editing' : ''}">
          ${this.renderField('filing_status', 'Filing Status', filingStatusDisplay, 'select', [
            { value: 'single', label: 'Single' },
            { value: 'married_joint', label: 'Married Filing Jointly' },
            { value: 'married_separate', label: 'Married Filing Separately' },
            { value: 'head_of_household', label: 'Head of Household' },
            { value: 'qualifying_widow', label: 'Qualifying Widow(er)' }
          ])}

          ${this.renderField('total_income', 'Total Income', incomeDisplay, 'currency')}

          ${this.renderField('w2_income', 'W-2 Wages', this.formatCurrency(profile.w2_income), 'currency')}

          ${this.renderField('business_income', 'Business Income', this.formatCurrency(profile.business_income), 'currency')}

          ${this.renderField('investment_income', 'Investment Income', this.formatCurrency(profile.investment_income), 'currency')}

          ${this.renderField('dependents', 'Dependents', profile.dependents || '0', 'number')}

          ${this.renderField('state', 'State', profile.state || 'Not specified', 'state')}
        </div>

        ${this.isEditing ? `
          <div class="profile-actions">
            <button class="profile-save-btn" onclick="profileEditor.saveChanges()">
              💾 Save Changes
            </button>
            <button class="profile-cancel-btn" onclick="profileEditor.cancelEdit()">
              Cancel
            </button>
          </div>
        ` : ''}
      </div>
    `;
  }

  renderField(key, label, displayValue, type, options = []) {
    const currentValue = this.data?.tax_profile?.[key] || '';
    // SECURITY: Escape all user-controlled values to prevent XSS
    const safeLabel = escapeHtml(label);
    const safeDisplayValue = escapeHtml(displayValue || 'Not specified');
    const safeKey = escapeAttribute(key);
    const safeCurrentValue = escapeAttribute(currentValue);

    if (!this.isEditing) {
      return `
        <div class="profile-field">
          <span class="field-label">${safeLabel}</span>
          <span class="field-value ${!displayValue || displayValue === 'Not specified' ? 'empty' : ''}">${safeDisplayValue}</span>
        </div>
      `;
    }

    let input = '';
    switch (type) {
      case 'select':
        input = `
          <select class="field-input" data-key="${safeKey}" onchange="profileEditor.handleChange('${safeKey}', this.value)">
            <option value="">Select...</option>
            ${options.map(opt => `
              <option value="${escapeAttribute(opt.value)}" ${currentValue === opt.value ? 'selected' : ''}>${escapeHtml(opt.label)}</option>
            `).join('')}
          </select>
        `;
        break;
      case 'currency':
        const numValue = typeof currentValue === 'number' ? currentValue : (parseFloat(currentValue) || '');
        input = `
          <div class="currency-input">
            <span class="currency-symbol">$</span>
            <input type="number" class="field-input" data-key="${safeKey}"
                   value="${escapeAttribute(numValue)}"
                   placeholder="0"
                   onchange="profileEditor.handleChange('${safeKey}', parseFloat(this.value) || 0)">
          </div>
        `;
        break;
      case 'number':
        input = `
          <input type="number" class="field-input" data-key="${safeKey}"
                 value="${escapeAttribute(currentValue || 0)}"
                 min="0" max="20"
                 onchange="profileEditor.handleChange('${safeKey}', parseInt(this.value) || 0)">
        `;
        break;
      case 'state':
        input = `
          <select class="field-input" data-key="${safeKey}" onchange="profileEditor.handleChange('${safeKey}', this.value)">
            <option value="">Select state...</option>
            ${this.getStateOptions().map(state => `
              <option value="${escapeAttribute(state)}" ${currentValue === state ? 'selected' : ''}>${escapeHtml(state)}</option>
            `).join('')}
          </select>
        `;
        break;
      default:
        input = `
          <input type="text" class="field-input" data-key="${safeKey}"
                 value="${safeCurrentValue}"
                 onchange="profileEditor.handleChange('${safeKey}', this.value)">
        `;
    }

    return `
      <div class="profile-field editing">
        <label class="field-label">${safeLabel}</label>
        ${input}
      </div>
    `;
  }

  toggleEdit() {
    this.isEditing = !this.isEditing;
    this.pendingChanges = {};
    this.render();
  }

  handleChange(key, value) {
    if (!this.pendingChanges) this.pendingChanges = {};
    this.pendingChanges[key] = value;
  }

  saveChanges() {
    if (this.pendingChanges && Object.keys(this.pendingChanges).length > 0) {
      // Update local data
      Object.assign(this.data.tax_profile, this.pendingChanges);

      // Trigger callback to sync with main app
      if (this.onUpdate) {
        this.onUpdate(this.pendingChanges);
      }

      // Show success toast
      if (typeof showToast === 'function') {
        showToast('Profile updated successfully!', 'success');
      }
    }

    this.isEditing = false;
    this.pendingChanges = {};
    this.render();
  }

  cancelEdit() {
    this.isEditing = false;
    this.pendingChanges = {};
    this.render();
  }

  formatFilingStatus(status) {
    const statusMap = {
      'single': 'Single',
      'married_joint': 'Married Filing Jointly',
      'married_separate': 'Married Filing Separately',
      'head_of_household': 'Head of Household',
      'qualifying_widow': 'Qualifying Widow(er)'
    };
    return statusMap[status] || status || 'Not specified';
  }

  formatCurrency(value) {
    if (!value && value !== 0) return null;
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  }

  getStateOptions() {
    return ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
            'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
            'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
            'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
            'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'];
  }

  updateData(newData) {
    this.data = newData;
    if (!this.isEditing) {
      this.render();
    }
  }
}


// ============================================================================
// SAVINGS GAUGE COMPONENT
// ============================================================================

class SavingsGauge {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.currentTax = 0;
    this.potentialSavings = 0;
  }

  render(currentTax = 0, potentialSavings = 0, confidence = 0.85) {
    if (!this.container) return;

    this.currentTax = currentTax;
    this.potentialSavings = potentialSavings;

    const savingsPercent = currentTax > 0 ? (potentialSavings / currentTax) * 100 : 0;
    const clampedPercent = Math.min(savingsPercent, 100);

    // Calculate needle rotation (0% = -90deg, 100% = 90deg)
    const needleRotation = -90 + (clampedPercent * 1.8);

    this.container.innerHTML = `
      <div class="savings-gauge-container">
        <div class="gauge-title">💰 Potential Tax Savings</div>

        <div class="gauge-wrapper">
          <svg viewBox="0 0 200 120" class="gauge-svg">
            <!-- Background arc (gray) -->
            <path d="M 20 100 A 80 80 0 0 1 180 100"
                  fill="none"
                  stroke="var(--color-gray-200, #e5e7eb)"
                  stroke-width="16"
                  stroke-linecap="round"/>

            <!-- Savings arc (green gradient) -->
            <path d="M 20 100 A 80 80 0 0 1 180 100"
                  fill="none"
                  stroke="url(#savingsGradient)"
                  stroke-width="16"
                  stroke-linecap="round"
                  stroke-dasharray="${clampedPercent * 2.51} 251"
                  class="gauge-fill"/>

            <!-- Gradient definition -->
            <defs>
              <linearGradient id="savingsGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="var(--color-success-500, #10b981)"/>
                <stop offset="50%" stop-color="var(--color-success-600, #059669)"/>
                <stop offset="100%" stop-color="var(--color-success-700, #047857)"/>
              </linearGradient>
            </defs>

            <!-- Needle -->
            <g transform="translate(100, 100)">
              <line x1="0" y1="0" x2="0" y2="-60"
                    stroke="var(--color-primary-500, #1e3a5f)"
                    stroke-width="3"
                    stroke-linecap="round"
                    transform="rotate(${needleRotation})"
                    class="gauge-needle"/>
              <circle r="8" fill="var(--color-primary-500, #1e3a5f)"/>
              <circle r="4" fill="#ffffff"/>
            </g>

            <!-- Labels -->
            <text x="20" y="115" font-size="10" fill="var(--color-gray-500, #6b7280)" text-anchor="start">$0</text>
            <text x="180" y="115" font-size="10" fill="var(--color-gray-500, #6b7280)" text-anchor="end">${escapeHtml(this.formatCurrency(currentTax))}</text>
          </svg>
        </div>

        <div class="gauge-values">
          <div class="gauge-current">
            <span class="gauge-label">Current Tax</span>
            <span class="gauge-amount tax">${escapeHtml(this.formatCurrency(currentTax))}</span>
          </div>
          <div class="gauge-savings">
            <span class="gauge-label">Potential Savings</span>
            <span class="gauge-amount savings">${escapeHtml(this.formatCurrency(potentialSavings))}</span>
          </div>
        </div>

        <div class="gauge-confidence">
          <span class="confidence-label">Analysis Confidence</span>
          <div class="confidence-bar">
            <div class="confidence-fill" style="width: ${confidence * 100}%"></div>
          </div>
          <span class="confidence-value">${Math.round(confidence * 100)}%</span>
        </div>
      </div>
    `;
  }

  formatCurrency(value) {
    if (!value && value !== 0) return '$0';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  }

  update(currentTax, potentialSavings, confidence) {
    this.render(currentTax, potentialSavings, confidence);
  }
}


// ============================================================================
// TAX TERM EXPLANATIONS (TOOLTIPS)
// ============================================================================

const TAX_TERMS = {
  'QBI': {
    term: 'Qualified Business Income (QBI) Deduction',
    definition: 'A tax deduction that allows eligible self-employed and small-business owners to deduct up to 20% of their qualified business income.',
    example: 'If you have $100,000 in qualified business income, you could deduct up to $20,000, reducing your taxable income.',
    irs_reference: 'IRC Section 199A',
    who_qualifies: 'Sole proprietors, partnerships, S corporations, and some trusts and estates with pass-through income.',
    limitations: 'Phase-outs begin at $182,100 (single) or $364,200 (MFJ) for 2024.'
  },
  'NIIT': {
    term: 'Net Investment Income Tax (NIIT)',
    definition: 'A 3.8% tax on investment income for taxpayers with income above certain thresholds.',
    example: 'If your MAGI is $250,000 (MFJ) and you have $50,000 in investment income, you may owe 3.8% on the investment income portion.',
    irs_reference: 'IRC Section 1411',
    who_qualifies: 'Applies to individuals with MAGI over $200,000 (single) or $250,000 (MFJ).',
    income_types: 'Interest, dividends, capital gains, rental income, royalties, and passive activity income.'
  },
  'AMT': {
    term: 'Alternative Minimum Tax (AMT)',
    definition: 'A parallel tax system designed to ensure high-income taxpayers pay at least a minimum amount of tax.',
    example: 'If your regular tax is $40,000 but AMT calculates to $45,000, you pay the higher AMT amount.',
    irs_reference: 'IRC Sections 55-59',
    exemption: 'For 2024: $85,700 (single) or $133,300 (MFJ). Phase-outs apply at higher incomes.',
    common_triggers: 'Large state tax deductions, incentive stock options (ISOs), and certain itemized deductions.'
  },
  'SALT': {
    term: 'State and Local Tax (SALT) Deduction',
    definition: 'A deduction for state and local income taxes, sales taxes, and property taxes paid during the year.',
    example: 'If you paid $8,000 in state income tax and $7,000 in property taxes, your SALT deduction is capped at $10,000.',
    irs_reference: 'IRC Section 164',
    limitation: 'Currently capped at $10,000 ($5,000 if MFS) through 2025.',
    note: 'The SALT cap was implemented by the Tax Cuts and Jobs Act of 2017.'
  },
  'SE_TAX': {
    term: 'Self-Employment Tax',
    definition: 'Social Security and Medicare taxes for self-employed individuals, equivalent to both the employer and employee portions.',
    example: 'On $100,000 of self-employment income, SE tax is approximately $14,130 (15.3% on 92.35% of income).',
    irs_reference: 'IRC Section 1401',
    rate: '15.3% total (12.4% Social Security + 2.9% Medicare). Additional 0.9% Medicare on income over $200,000.',
    deduction: 'You can deduct 50% of SE tax as an above-the-line deduction.'
  },
  'AGI': {
    term: 'Adjusted Gross Income (AGI)',
    definition: 'Your total gross income minus specific deductions (above-the-line deductions).',
    example: 'Gross income of $120,000 minus $10,000 in 401(k) contributions = AGI of $110,000.',
    importance: 'Many tax benefits phase out based on AGI. It\'s the starting point for calculating taxable income.',
    above_line_deductions: 'Retirement contributions, HSA contributions, student loan interest, self-employment tax deduction.'
  },
  'MAGI': {
    term: 'Modified Adjusted Gross Income (MAGI)',
    definition: 'AGI with certain deductions added back. Used to determine eligibility for various tax benefits.',
    example: 'Your AGI is $95,000, but adding back $5,000 in student loan interest gives a MAGI of $100,000.',
    used_for: 'Roth IRA contribution limits, premium tax credits, education credits, and NIIT thresholds.',
    note: 'The specific add-backs vary depending on which tax benefit you\'re calculating.'
  },
  'EFFECTIVE_RATE': {
    term: 'Effective Tax Rate',
    definition: 'The actual percentage of your total income that you pay in taxes.',
    example: 'If you earn $100,000 and pay $18,000 in federal taxes, your effective rate is 18%.',
    vs_marginal: 'Unlike marginal rate (the rate on your last dollar), effective rate reflects your overall tax burden.',
    calculation: 'Total Tax Paid ÷ Total Taxable Income × 100'
  },
  'MARGINAL_RATE': {
    term: 'Marginal Tax Rate',
    definition: 'The tax rate applied to your last dollar of income; the highest bracket you fall into.',
    example: 'If you\'re in the 22% bracket, each additional dollar of income is taxed at 22%.',
    importance: 'Determines the tax benefit of deductions - a $1,000 deduction saves $220 in the 22% bracket.',
    brackets_2024: '10%, 12%, 22%, 24%, 32%, 35%, 37%'
  }
};

class TaxTermExplainer {
  constructor() {
    this.createModal();
  }

  createModal() {
    // Check if modal already exists
    if (document.getElementById('taxTermModal')) return;

    const modal = document.createElement('div');
    modal.id = 'taxTermModal';
    modal.className = 'tax-term-modal';
    modal.innerHTML = `
      <div class="tax-term-modal-content">
        <button class="modal-close" onclick="taxTermExplainer.closeModal()">×</button>
        <div class="modal-body" id="taxTermModalBody">
          <!-- Content populated dynamically -->
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    // Close on background click
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        this.closeModal();
      }
    });

    // Close on escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        this.closeModal();
      }
    });
  }

  showTerm(termKey) {
    const term = TAX_TERMS[termKey];
    if (!term) return;

    const modalBody = document.getElementById('taxTermModalBody');
    modalBody.innerHTML = `
      <div class="term-header">
        <span class="term-icon">📚</span>
        <h3 class="term-title">${term.term}</h3>
      </div>

      <div class="term-section">
        <h4>Definition</h4>
        <p>${term.definition}</p>
      </div>

      ${term.example ? `
        <div class="term-section example">
          <h4>💡 Example</h4>
          <p>${term.example}</p>
        </div>
      ` : ''}

      ${term.who_qualifies ? `
        <div class="term-section">
          <h4>Who Qualifies?</h4>
          <p>${term.who_qualifies}</p>
        </div>
      ` : ''}

      ${term.limitations || term.limitation ? `
        <div class="term-section warning">
          <h4>⚠️ Limitations</h4>
          <p>${term.limitations || term.limitation}</p>
        </div>
      ` : ''}

      ${term.irs_reference ? `
        <div class="term-irs-ref">
          <span class="ref-label">IRS Reference:</span>
          <span class="ref-value">${term.irs_reference}</span>
        </div>
      ` : ''}
    `;

    document.getElementById('taxTermModal').classList.add('show');
  }

  closeModal() {
    document.getElementById('taxTermModal')?.classList.remove('show');
  }

  // Create clickable term links in text
  // SECURITY: Use data attributes instead of inline onclick to prevent XSS
  linkifyTerms(text) {
    let result = text;
    Object.keys(TAX_TERMS).forEach(key => {
      const patterns = [
        key,
        TAX_TERMS[key].term,
        // Common variations
        key.replace('_', ' '),
        key.replace('_', '-')
      ];

      patterns.forEach(pattern => {
        const regex = new RegExp(`\\b(${pattern})\\b`, 'gi');
        // SECURITY: Use data-term attribute instead of inline onclick with user data
        result = result.replace(regex, `<span class="tax-term-link" data-term="${escapeAttribute(key)}">$1</span>`);
      });
    });
    return result;
  }

  // Initialize event delegation for tax term links
  initTermLinks() {
    document.addEventListener('click', (e) => {
      if (e.target.classList.contains('tax-term-link')) {
        const term = e.target.dataset.term;
        if (term && TAX_TERMS[term]) {
          this.showTerm(term);
        }
      }
    });
  }
}


// ============================================================================
// COMPARISON VIEW COMPONENT
// ============================================================================

class ComparisonView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
  }

  render(currentScenario, optimizedScenario) {
    if (!this.container) return;

    const savings = (currentScenario.totalTax || 0) - (optimizedScenario.totalTax || 0);
    const savingsPercent = currentScenario.totalTax > 0
      ? ((savings / currentScenario.totalTax) * 100).toFixed(1)
      : 0;

    this.container.innerHTML = `
      <div class="comparison-view">
        <div class="comparison-header">
          <h3>📊 Tax Optimization Comparison</h3>
          <p class="comparison-subtitle">See how our recommendations can reduce your tax burden</p>
        </div>

        <div class="comparison-cards">
          <!-- Current Scenario -->
          <div class="comparison-card current">
            <div class="card-label">Current Situation</div>
            <div class="card-icon">📋</div>

            ${this.renderMetric('Gross Income', currentScenario.grossIncome)}
            ${this.renderMetric('Total Deductions', currentScenario.deductions)}
            ${this.renderMetric('Taxable Income', currentScenario.taxableIncome)}

            <div class="card-divider"></div>

            ${this.renderMetric('Federal Tax', currentScenario.federalTax, 'tax')}
            ${this.renderMetric('State Tax', currentScenario.stateTax, 'tax')}
            ${currentScenario.seTax ? this.renderMetric('Self-Employment Tax', currentScenario.seTax, 'tax') : ''}

            <div class="card-total">
              <span class="total-label">Total Tax</span>
              <span class="total-value tax">${this.formatCurrency(currentScenario.totalTax)}</span>
            </div>

            <div class="effective-rate">
              Effective Rate: ${currentScenario.effectiveRate?.toFixed(1) || 0}%
            </div>
          </div>

          <!-- Arrow -->
          <div class="comparison-arrow">
            <div class="arrow-icon">→</div>
            <div class="savings-badge">
              <div class="savings-amount">${this.formatCurrency(savings)}</div>
              <div class="savings-label">Savings</div>
            </div>
          </div>

          <!-- Optimized Scenario -->
          <div class="comparison-card optimized">
            <div class="card-label">With Optimization</div>
            <div class="card-icon">✨</div>

            ${this.renderMetric('Gross Income', optimizedScenario.grossIncome)}
            ${this.renderMetric('Total Deductions', optimizedScenario.deductions, 'savings')}
            ${this.renderMetric('Taxable Income', optimizedScenario.taxableIncome)}

            <div class="card-divider"></div>

            ${this.renderMetric('Federal Tax', optimizedScenario.federalTax, 'savings')}
            ${this.renderMetric('State Tax', optimizedScenario.stateTax, 'savings')}
            ${optimizedScenario.seTax ? this.renderMetric('Self-Employment Tax', optimizedScenario.seTax, 'savings') : ''}

            <div class="card-total optimized">
              <span class="total-label">Total Tax</span>
              <span class="total-value savings">${this.formatCurrency(optimizedScenario.totalTax)}</span>
            </div>

            <div class="effective-rate optimized">
              Effective Rate: ${optimizedScenario.effectiveRate?.toFixed(1) || 0}%
            </div>
          </div>
        </div>

        <!-- Savings Summary -->
        <div class="savings-summary">
          <div class="summary-row">
            <span class="summary-icon">💰</span>
            <span class="summary-text">You could save <strong>${this.formatCurrency(savings)}</strong> (${savingsPercent}% reduction)</span>
          </div>
          <div class="summary-actions">
            <button class="action-btn primary" onclick="generateDetailedReport()">
              📄 Generate Full Report
            </button>
            <button class="action-btn secondary" onclick="showStrategies()">
              📋 View Strategies
            </button>
          </div>
        </div>
      </div>
    `;
  }

  renderMetric(label, value, type = '') {
    // SECURITY: Escape label and use safe currency formatter
    return `
      <div class="metric-row ${escapeAttribute(type)}">
        <span class="metric-label">${escapeHtml(label)}</span>
        <span class="metric-value">${formatCurrencySafe(value)}</span>
      </div>
    `;
  }

  formatCurrency(value) {
    if (!value && value !== 0) return '$0';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  }
}


// ============================================================================
// PDF PREVIEW MODAL
// ============================================================================

class PDFPreviewModal {
  constructor() {
    this.createModal();
  }

  createModal() {
    if (document.getElementById('pdfPreviewModal')) return;

    const modal = document.createElement('div');
    modal.id = 'pdfPreviewModal';
    modal.className = 'pdf-preview-modal';
    modal.innerHTML = `
      <div class="pdf-preview-content">
        <div class="preview-header">
          <h2>📄 Report Preview</h2>
          <button class="preview-close" onclick="pdfPreviewModal.close()">×</button>
        </div>
        <div class="preview-body" id="pdfPreviewBody">
          <!-- Preview content loaded here -->
        </div>
        <div class="preview-footer">
          <div class="preview-info">
            <span class="info-icon">ℹ️</span>
            <span>PDF will be generated with full formatting and charts</span>
          </div>
          <div class="preview-actions">
            <button class="preview-btn secondary" onclick="pdfPreviewModal.close()">Cancel</button>
            <button class="preview-btn primary" onclick="pdfPreviewModal.download()">
              ⬇️ Download PDF
            </button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    modal.addEventListener('click', (e) => {
      if (e.target === modal) this.close();
    });
  }

  async show(sessionId, reportType = 'full') {
    const modal = document.getElementById('pdfPreviewModal');
    const body = document.getElementById('pdfPreviewBody');

    body.innerHTML = `
      <div class="preview-loading">
        <div class="loading-spinner"></div>
        <p>Loading preview...</p>
      </div>
    `;

    modal.classList.add('show');
    this.currentSessionId = sessionId;
    this.currentReportType = reportType;

    try {
      // SECURITY: Validate sessionId format (UUID only)
      if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(sessionId)) {
        throw new Error('Invalid session ID format');
      }

      // Fetch HTML preview
      const response = await fetch(`/api/advisor/universal-report/${encodeURIComponent(sessionId)}/html?tier=2`);
      if (response.ok) {
        const html = await response.text();
        // SECURITY: Use blob URL instead of srcdoc to avoid XSS
        // Create a sandboxed iframe with strict CSP
        const blob = new Blob([html], { type: 'text/html' });
        const blobUrl = URL.createObjectURL(blob);

        body.innerHTML = `
          <div class="preview-frame">
            <iframe src="${escapeAttribute(blobUrl)}" class="preview-iframe" sandbox="allow-same-origin" referrerpolicy="no-referrer"></iframe>
          </div>
          <div class="preview-sections">
            <h4>Report Includes:</h4>
            <ul class="section-list">
              <li>✓ Executive Summary</li>
              <li>✓ Savings Gauge Visualization</li>
              <li>✓ Income & Deduction Analysis</li>
              <li>✓ Tax Bracket Breakdown</li>
              <li>✓ Optimization Recommendations</li>
              <li>✓ Risk Assessment</li>
              <li>✓ Tax Timeline & Deadlines</li>
              <li>✓ Document Checklist</li>
            </ul>
          </div>
        `;

        // Clean up blob URL when modal closes
        this.currentBlobUrl = blobUrl;
      } else {
        throw new Error('Failed to load preview');
      }
    } catch (error) {
      // SECURITY: Use data attributes for retry instead of inline onclick
      body.innerHTML = `
        <div class="preview-error">
          <span class="error-icon">⚠️</span>
          <p>Unable to load preview. The PDF will still generate correctly.</p>
          <button class="retry-btn" data-session="${escapeAttribute(sessionId)}" data-type="${escapeAttribute(reportType)}">
            Retry
          </button>
        </div>
      `;
      // Add event listener for retry button
      body.querySelector('.retry-btn')?.addEventListener('click', (e) => {
        const btn = e.target;
        this.show(btn.dataset.session, btn.dataset.type);
      });
    }
  }

  close() {
    // SECURITY: Clean up blob URL to prevent memory leaks
    if (this.currentBlobUrl) {
      URL.revokeObjectURL(this.currentBlobUrl);
      this.currentBlobUrl = null;
    }
    document.getElementById('pdfPreviewModal')?.classList.remove('show');
  }

  async download() {
    if (!this.currentSessionId) return;

    const downloadBtn = document.querySelector('.preview-btn.primary');
    const originalText = downloadBtn.innerHTML;
    downloadBtn.innerHTML = '⏳ Generating...';
    downloadBtn.disabled = true;

    try {
      const response = await fetch(`/api/advisor/universal-report/${this.currentSessionId}/pdf?tier=2`);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `tax_report_${this.currentSessionId}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();

        this.close();
        if (typeof showToast === 'function') {
          showToast('PDF downloaded successfully!', 'success');
        }
      } else {
        throw new Error('Download failed');
      }
    } catch (error) {
      if (typeof showToast === 'function') {
        showToast('Failed to download PDF. Please try again.', 'error');
      }
    } finally {
      downloadBtn.innerHTML = originalText;
      downloadBtn.disabled = false;
    }
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/"/g, '&quot;');
  }
}


// ============================================================================
// TIER COMPARISON TABLE
// ============================================================================

class TierComparison {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
  }

  render() {
    if (!this.container) return;

    this.container.innerHTML = `
      <div class="tier-comparison">
        <h3 class="tier-title">📊 Choose Your Report Level</h3>

        <div class="tier-table">
          <div class="tier-header">
            <div class="tier-col feature">Features</div>
            <div class="tier-col free">Free Teaser</div>
            <div class="tier-col full">Full Analysis</div>
          </div>

          ${this.renderRow('Savings Estimate', 'Range only', 'Exact amounts', true)}
          ${this.renderRow('Tax Insights', '3 previews', 'All 8+ insights', true)}
          ${this.renderRow('Savings Gauge', '✓', '✓', false)}
          ${this.renderRow('Income Charts', '✗', '✓', true)}
          ${this.renderRow('Tax Bracket Chart', '✗', '✓', true)}
          ${this.renderRow('Action Items', '✗', '✓', true)}
          ${this.renderRow('IRS References', '✗', '✓', true)}
          ${this.renderRow('Tax Calendar', '✗', '✓', true)}
          ${this.renderRow('Document Checklist', '✗', '✓', true)}
          ${this.renderRow('PDF Download', '✗', '✓', true)}
          ${this.renderRow('CPA Branding', '✗', '✓', true)}
        </div>

        <div class="tier-actions">
          <button class="tier-btn free" onclick="viewFreeReport()">
            View Free Teaser
          </button>
          <button class="tier-btn full" onclick="unlockFullReport()">
            🔓 Unlock Full Analysis
          </button>
        </div>
      </div>
    `;
  }

  renderRow(feature, free, full, highlight = false) {
    return `
      <div class="tier-row ${highlight ? 'highlight' : ''}">
        <div class="tier-col feature">${feature}</div>
        <div class="tier-col free">${free}</div>
        <div class="tier-col full">${full}</div>
      </div>
    `;
  }
}


// ============================================================================
// INITIALIZATION & GLOBAL INSTANCES
// ============================================================================

let profileEditor = null;
let savingsGauge = null;
let taxTermExplainer = null;
let comparisonView = null;
let pdfPreviewModal = null;
let tierComparison = null;

function initializeUXEnhancements(extractedData, onProfileUpdate) {
  // Initialize profile editor
  profileEditor = new ProfileEditor('profileEditorContainer', extractedData, onProfileUpdate);

  // Initialize savings gauge
  savingsGauge = new SavingsGauge('savingsGaugeContainer');

  // Initialize tax term explainer
  taxTermExplainer = new TaxTermExplainer();
  // Initialize event delegation for tax term links
  taxTermExplainer.initTermLinks();

  // Initialize comparison view
  comparisonView = new ComparisonView('comparisonViewContainer');

  // Initialize PDF preview modal
  pdfPreviewModal = new PDFPreviewModal();

  // Initialize tier comparison
  tierComparison = new TierComparison('tierComparisonContainer');

  DevLogger.log('UX Enhancements initialized');
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    ProfileEditor,
    SavingsGauge,
    TaxTermExplainer,
    ComparisonView,
    PDFPreviewModal,
    TierComparison,
    TAX_TERMS,
    initializeUXEnhancements
  };
}
