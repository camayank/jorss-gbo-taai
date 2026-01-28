/**
 * Tax Return Alpine.js Store
 * Core state management for tax form wizard.
 *
 * Usage:
 *   import { registerTaxReturnStore } from '/static/js/alpine/stores/tax-return.js';
 *   document.addEventListener('alpine:init', () => registerTaxReturnStore(Alpine));
 *
 *   // In templates:
 *   <div x-data x-text="$store.taxReturn.currentStep"></div>
 */

/**
 * Register the tax return store with Alpine.js
 * @param {Object} Alpine - Alpine.js instance
 */
export function registerTaxReturnStore(Alpine) {
  Alpine.store('taxReturn', {
    // ========================================
    // STATE
    // ========================================

    // Navigation
    currentStep: 1,
    totalSteps: 7,
    stepNames: [
      'Personal Info',
      'Filing Status',
      'Income',
      'Adjustments',
      'Deductions',
      'Credits',
      'Review',
    ],

    // Personal Information
    firstName: '',
    lastName: '',
    ssn: '',
    dateOfBirth: '',
    email: '',
    phone: '',

    // Filing info
    filingStatus: '',
    taxYear: new Date().getFullYear(),

    // Address
    address: {
      street: '',
      apt: '',
      city: '',
      state: '',
      zipCode: '',
    },

    // Spouse (if married filing jointly)
    spouse: {
      firstName: '',
      lastName: '',
      ssn: '',
      dateOfBirth: '',
    },

    // Income
    wages: 0,
    businessIncome: 0,
    investmentIncome: 0,
    rentalIncome: 0,
    retirementIncome: 0,
    socialSecurityIncome: 0,
    otherIncome: 0,

    // W-2s
    w2Forms: [],

    // 1099s
    form1099s: [],

    // Adjustments
    adjustments: {
      studentLoanInterest: 0,
      educatorExpenses: 0,
      hsaContributions: 0,
      iraContributions: 0,
      selfEmploymentTax: 0,
      alimonyPaid: 0,
      movingExpenses: 0,
    },

    // Deductions
    standardDeduction: true,
    itemizedDeductions: {
      medicalExpenses: 0,
      stateTaxes: 0,
      propertyTaxes: 0,
      mortgageInterest: 0,
      charitableCash: 0,
      charitableNonCash: 0,
      casualtyLosses: 0,
      miscExpenses: 0,
    },

    // Dependents
    dependents: [],

    // State
    state: '',
    hasStateReturn: true,

    // Computed values (updated via calculations)
    computed: {
      totalIncome: 0,
      agi: 0,
      deductionAmount: 0,
      taxableIncome: 0,
      federalTax: 0,
      stateTax: 0,
      totalTax: 0,
      effectiveRate: 0,
      totalWithheld: 0,
      estimatedRefund: 0,
    },

    // Validation
    fieldStates: {},
    validationMessages: [],

    // UI State
    isLoading: false,
    isDirty: false,
    isSaving: false,
    lastSaved: null,
    sessionId: null,

    // ========================================
    // GETTERS
    // ========================================

    get fullName() {
      return `${this.firstName} ${this.lastName}`.trim();
    },

    get currentStepName() {
      return this.stepNames[this.currentStep - 1] || '';
    },

    get isFirstStep() {
      return this.currentStep === 1;
    },

    get isLastStep() {
      return this.currentStep === this.totalSteps;
    },

    get progress() {
      return Math.round((this.currentStep / this.totalSteps) * 100);
    },

    get isMarried() {
      return this.filingStatus === 'married_filing_jointly' ||
        this.filingStatus === 'married_filing_separately';
    },

    get totalW2Wages() {
      return this.w2Forms.reduce((sum, w2) => sum + (parseFloat(w2.wages) || 0), 0);
    },

    get total1099Income() {
      return this.form1099s.reduce((sum, f) => sum + (parseFloat(f.amount) || 0), 0);
    },

    // ========================================
    // NAVIGATION ACTIONS
    // ========================================

    /**
     * Navigate to step
     */
    goToStep(step) {
      if (step >= 1 && step <= this.totalSteps) {
        this.currentStep = step;
        this.isDirty = true;
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    },

    /**
     * Next step
     */
    nextStep() {
      if (this.currentStep < this.totalSteps) {
        if (this.validateCurrentStep()) {
          this.currentStep++;
          this.isDirty = true;
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }
      }
    },

    /**
     * Previous step
     */
    prevStep() {
      if (this.currentStep > 1) {
        this.currentStep--;
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    },

    // ========================================
    // FIELD ACTIONS
    // ========================================

    /**
     * Update field value
     */
    updateField(field, value) {
      // Handle nested fields (e.g., 'address.city')
      if (field.includes('.')) {
        const [parent, child] = field.split('.');
        if (this[parent] && typeof this[parent] === 'object') {
          this[parent][child] = value;
        }
      } else if (field in this) {
        this[field] = value;
      }
      this.isDirty = true;
      this.recalculate();
    },

    /**
     * Update multiple fields
     */
    updateFields(fields) {
      Object.entries(fields).forEach(([field, value]) => {
        this.updateField(field, value);
      });
    },

    // ========================================
    // W-2 ACTIONS
    // ========================================

    /**
     * Add W-2 form
     */
    addW2(w2 = {}) {
      this.w2Forms.push({
        id: Date.now(),
        employerName: w2.employerName || '',
        employerEin: w2.employerEin || '',
        employerAddress: w2.employerAddress || '',
        wages: w2.wages || 0,
        federalWithheld: w2.federalWithheld || 0,
        socialSecurityWages: w2.socialSecurityWages || 0,
        socialSecurityWithheld: w2.socialSecurityWithheld || 0,
        medicareWages: w2.medicareWages || 0,
        medicareWithheld: w2.medicareWithheld || 0,
        stateWages: w2.stateWages || 0,
        stateWithheld: w2.stateWithheld || 0,
        localWages: w2.localWages || 0,
        localWithheld: w2.localWithheld || 0,
      });
      this.isDirty = true;
      this.recalculate();
    },

    /**
     * Update W-2 form
     */
    updateW2(id, data) {
      const index = this.w2Forms.findIndex((w) => w.id === id);
      if (index !== -1) {
        this.w2Forms[index] = { ...this.w2Forms[index], ...data };
        this.isDirty = true;
        this.recalculate();
      }
    },

    /**
     * Remove W-2 form
     */
    removeW2(id) {
      this.w2Forms = this.w2Forms.filter((w) => w.id !== id);
      this.isDirty = true;
      this.recalculate();
    },

    // ========================================
    // 1099 ACTIONS
    // ========================================

    /**
     * Add 1099 form
     */
    add1099(form1099 = {}) {
      this.form1099s.push({
        id: Date.now(),
        type: form1099.type || '1099-MISC', // 1099-MISC, 1099-NEC, 1099-INT, 1099-DIV, 1099-B, etc.
        payerName: form1099.payerName || '',
        payerTin: form1099.payerTin || '',
        amount: form1099.amount || 0,
        federalWithheld: form1099.federalWithheld || 0,
        stateWithheld: form1099.stateWithheld || 0,
        description: form1099.description || '',
      });
      this.isDirty = true;
      this.recalculate();
    },

    /**
     * Update 1099 form
     */
    update1099(id, data) {
      const index = this.form1099s.findIndex((f) => f.id === id);
      if (index !== -1) {
        this.form1099s[index] = { ...this.form1099s[index], ...data };
        this.isDirty = true;
        this.recalculate();
      }
    },

    /**
     * Remove 1099 form
     */
    remove1099(id) {
      this.form1099s = this.form1099s.filter((f) => f.id !== id);
      this.isDirty = true;
      this.recalculate();
    },

    // ========================================
    // DEPENDENT ACTIONS
    // ========================================

    /**
     * Add dependent
     */
    addDependent(dependent = {}) {
      this.dependents.push({
        id: Date.now(),
        firstName: dependent.firstName || '',
        lastName: dependent.lastName || '',
        relationship: dependent.relationship || '',
        ssn: dependent.ssn || '',
        dateOfBirth: dependent.dateOfBirth || '',
        monthsLived: dependent.monthsLived || 12,
        isStudent: dependent.isStudent || false,
        isDisabled: dependent.isDisabled || false,
        providedSupport: dependent.providedSupport || true,
      });
      this.isDirty = true;
      this.recalculate();
    },

    /**
     * Update dependent
     */
    updateDependent(id, data) {
      const index = this.dependents.findIndex((d) => d.id === id);
      if (index !== -1) {
        this.dependents[index] = { ...this.dependents[index], ...data };
        this.isDirty = true;
        this.recalculate();
      }
    },

    /**
     * Remove dependent
     */
    removeDependent(id) {
      this.dependents = this.dependents.filter((d) => d.id !== id);
      this.isDirty = true;
      this.recalculate();
    },

    // ========================================
    // CALCULATIONS
    // ========================================

    /**
     * Recalculate all computed values
     */
    recalculate() {
      // Total income from all sources
      this.computed.totalIncome =
        (parseFloat(this.wages) || 0) +
        this.totalW2Wages +
        this.total1099Income +
        (parseFloat(this.businessIncome) || 0) +
        (parseFloat(this.investmentIncome) || 0) +
        (parseFloat(this.rentalIncome) || 0) +
        (parseFloat(this.retirementIncome) || 0) +
        (parseFloat(this.socialSecurityIncome) || 0) +
        (parseFloat(this.otherIncome) || 0);

      // Calculate total adjustments
      const totalAdjustments = Object.values(this.adjustments).reduce(
        (sum, val) => sum + (parseFloat(val) || 0),
        0
      );

      // AGI = Total Income - Adjustments
      this.computed.agi = Math.max(0, this.computed.totalIncome - totalAdjustments);

      // Determine deduction amount
      if (this.standardDeduction) {
        this.computed.deductionAmount = this.getStandardDeduction();
      } else {
        this.computed.deductionAmount = Object.values(this.itemizedDeductions).reduce(
          (sum, val) => sum + (parseFloat(val) || 0),
          0
        );
      }

      // Taxable income
      this.computed.taxableIncome = Math.max(0, this.computed.agi - this.computed.deductionAmount);

      // Federal tax
      this.computed.federalTax = this.calculateFederalTax(
        this.computed.taxableIncome,
        this.filingStatus
      );

      // Total withholding
      this.computed.totalWithheld = this.calculateTotalWithheld();

      // Effective rate
      this.computed.effectiveRate =
        this.computed.totalIncome > 0
          ? ((this.computed.federalTax / this.computed.totalIncome) * 100).toFixed(1)
          : 0;

      // Estimated refund/owed
      this.computed.estimatedRefund = this.computed.totalWithheld - this.computed.federalTax;
    },

    /**
     * Get standard deduction based on filing status
     */
    getStandardDeduction() {
      // 2025 standard deduction amounts
      const deductions = {
        single: 14600,
        married_filing_jointly: 29200,
        married_filing_separately: 14600,
        head_of_household: 21900,
        qualifying_widow: 29200,
        qualifying_surviving_spouse: 29200,
      };
      return deductions[this.filingStatus] || 14600;
    },

    /**
     * Calculate federal tax using tax brackets
     */
    calculateFederalTax(taxableIncome, filingStatus) {
      // 2025 tax brackets (simplified)
      const brackets = {
        single: [
          [11600, 0.1],
          [47150, 0.12],
          [100525, 0.22],
          [191950, 0.24],
          [243725, 0.32],
          [609350, 0.35],
          [Infinity, 0.37],
        ],
        married_filing_jointly: [
          [23200, 0.1],
          [94300, 0.12],
          [201050, 0.22],
          [383900, 0.24],
          [487450, 0.32],
          [731200, 0.35],
          [Infinity, 0.37],
        ],
        married_filing_separately: [
          [11600, 0.1],
          [47150, 0.12],
          [100525, 0.22],
          [191950, 0.24],
          [243725, 0.32],
          [365600, 0.35],
          [Infinity, 0.37],
        ],
        head_of_household: [
          [16550, 0.1],
          [63100, 0.12],
          [100500, 0.22],
          [191950, 0.24],
          [243700, 0.32],
          [609350, 0.35],
          [Infinity, 0.37],
        ],
      };

      const bracketSet = brackets[filingStatus] || brackets.single;
      let tax = 0;
      let prevCutoff = 0;

      for (const [cutoff, rate] of bracketSet) {
        if (taxableIncome <= prevCutoff) break;
        const taxableInBracket = Math.min(taxableIncome, cutoff) - prevCutoff;
        tax += taxableInBracket * rate;
        prevCutoff = cutoff;
      }

      return Math.round(tax);
    },

    /**
     * Calculate total withholdings
     */
    calculateTotalWithheld() {
      let total = 0;

      // From W-2s
      for (const w2 of this.w2Forms) {
        total += parseFloat(w2.federalWithheld) || 0;
      }

      // From 1099s
      for (const f1099 of this.form1099s) {
        total += parseFloat(f1099.federalWithheld) || 0;
      }

      return total;
    },

    // ========================================
    // VALIDATION
    // ========================================

    /**
     * Validate current step
     */
    validateCurrentStep() {
      this.validationMessages = [];

      switch (this.currentStep) {
        case 1: // Personal Info
          if (!this.firstName) this.validationMessages.push('First name is required');
          if (!this.lastName) this.validationMessages.push('Last name is required');
          if (!this.ssn) this.validationMessages.push('SSN is required');
          break;

        case 2: // Filing Status
          if (!this.filingStatus) this.validationMessages.push('Filing status is required');
          if (this.isMarried && !this.spouse.firstName) {
            this.validationMessages.push('Spouse information is required');
          }
          break;

        case 3: // Income
          // Income can be zero, just validate if entered
          break;

        // Other steps...
      }

      return this.validationMessages.length === 0;
    },

    /**
     * Validate field
     */
    setFieldState(field, isValid, message = '') {
      this.fieldStates[field] = { isValid, message };
    },

    /**
     * Get field state
     */
    getFieldState(field) {
      return this.fieldStates[field] || { isValid: true, message: '' };
    },

    // ========================================
    // PERSISTENCE
    // ========================================

    /**
     * Export form data as JSON
     */
    toJSON() {
      return {
        // Personal
        firstName: this.firstName,
        lastName: this.lastName,
        ssn: this.ssn,
        dateOfBirth: this.dateOfBirth,
        email: this.email,
        phone: this.phone,

        // Filing
        filingStatus: this.filingStatus,
        taxYear: this.taxYear,

        // Address
        address: { ...this.address },

        // Spouse
        spouse: { ...this.spouse },

        // Income
        wages: this.wages,
        businessIncome: this.businessIncome,
        investmentIncome: this.investmentIncome,
        rentalIncome: this.rentalIncome,
        retirementIncome: this.retirementIncome,
        socialSecurityIncome: this.socialSecurityIncome,
        otherIncome: this.otherIncome,

        // Forms
        w2Forms: [...this.w2Forms],
        form1099s: [...this.form1099s],

        // Adjustments & Deductions
        adjustments: { ...this.adjustments },
        standardDeduction: this.standardDeduction,
        itemizedDeductions: { ...this.itemizedDeductions },

        // Dependents
        dependents: [...this.dependents],

        // State
        state: this.state,
        hasStateReturn: this.hasStateReturn,

        // Meta
        currentStep: this.currentStep,
        sessionId: this.sessionId,
      };
    },

    /**
     * Import form data from JSON
     */
    fromJSON(data) {
      if (!data) return;

      // Merge data into store
      Object.keys(data).forEach((key) => {
        if (key in this && key !== 'computed' && key !== 'fieldStates') {
          if (typeof data[key] === 'object' && !Array.isArray(data[key])) {
            this[key] = { ...this[key], ...data[key] };
          } else {
            this[key] = data[key];
          }
        }
      });

      this.recalculate();
      this.isDirty = false;
    },

    /**
     * Reset form to initial state
     */
    reset() {
      this.currentStep = 1;
      this.firstName = '';
      this.lastName = '';
      this.ssn = '';
      this.dateOfBirth = '';
      this.email = '';
      this.phone = '';
      this.filingStatus = '';
      this.address = { street: '', apt: '', city: '', state: '', zipCode: '' };
      this.spouse = { firstName: '', lastName: '', ssn: '', dateOfBirth: '' };
      this.wages = 0;
      this.businessIncome = 0;
      this.investmentIncome = 0;
      this.rentalIncome = 0;
      this.retirementIncome = 0;
      this.socialSecurityIncome = 0;
      this.otherIncome = 0;
      this.w2Forms = [];
      this.form1099s = [];
      this.adjustments = {
        studentLoanInterest: 0,
        educatorExpenses: 0,
        hsaContributions: 0,
        iraContributions: 0,
        selfEmploymentTax: 0,
        alimonyPaid: 0,
        movingExpenses: 0,
      };
      this.standardDeduction = true;
      this.itemizedDeductions = {
        medicalExpenses: 0,
        stateTaxes: 0,
        propertyTaxes: 0,
        mortgageInterest: 0,
        charitableCash: 0,
        charitableNonCash: 0,
        casualtyLosses: 0,
        miscExpenses: 0,
      };
      this.dependents = [];
      this.state = '';
      this.hasStateReturn = true;
      this.fieldStates = {};
      this.validationMessages = [];
      this.isDirty = false;
      this.sessionId = null;
      this.recalculate();
    },
  });
}

// Export for non-module usage
if (typeof window !== 'undefined') {
  window.registerTaxReturnStore = registerTaxReturnStore;
}
