/**
 * Form Validation Module
 * Reusable validators for tax form inputs.
 *
 * Usage:
 *   import { validators, validateField, validateForm } from '/static/js/core/validation.js';
 */

// ============================================
// VALIDATOR FUNCTIONS
// ============================================

export const validators = {
  /**
   * Required field
   */
  required: (value, message = 'This field is required') => {
    if (value === null || value === undefined) return message;
    if (typeof value === 'string' && value.trim() === '') return message;
    if (Array.isArray(value) && value.length === 0) return message;
    return null;
  },

  /**
   * Email format
   */
  email: (value, message = 'Please enter a valid email address') => {
    if (!value) return null; // Use required validator for empty check
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(value) ? null : message;
  },

  /**
   * Phone number (US)
   */
  phone: (value, message = 'Please enter a valid phone number') => {
    if (!value) return null;
    const cleaned = value.replace(/\D/g, '');
    const valid = cleaned.length === 10 || (cleaned.length === 11 && cleaned[0] === '1');
    return valid ? null : message;
  },

  /**
   * Social Security Number
   */
  ssn: (value, message = 'Please enter a valid SSN (XXX-XX-XXXX)') => {
    if (!value) return null;
    const cleaned = value.replace(/\D/g, '');
    if (cleaned.length !== 9) return message;
    // Cannot start with 000, 666, or 9XX
    if (/^(000|666|9)/.test(cleaned)) return message;
    // Middle and last parts cannot be all zeros
    if (cleaned.slice(3, 5) === '00') return message;
    if (cleaned.slice(5) === '0000') return message;
    return null;
  },

  /**
   * Employer Identification Number
   */
  ein: (value, message = 'Please enter a valid EIN (XX-XXXXXXX)') => {
    if (!value) return null;
    const cleaned = value.replace(/\D/g, '');
    return cleaned.length === 9 ? null : message;
  },

  /**
   * ZIP code (US)
   */
  zipCode: (value, message = 'Please enter a valid ZIP code') => {
    if (!value) return null;
    const re = /^\d{5}(-\d{4})?$/;
    return re.test(value) ? null : message;
  },

  /**
   * Minimum length
   */
  minLength: (min) => (value, message = `Must be at least ${min} characters`) => {
    if (!value) return null;
    return value.length >= min ? null : message;
  },

  /**
   * Maximum length
   */
  maxLength: (max) => (value, message = `Must be no more than ${max} characters`) => {
    if (!value) return null;
    return value.length <= max ? null : message;
  },

  /**
   * Minimum value (for numbers)
   */
  min: (minVal) => (value, message = `Must be at least ${minVal}`) => {
    if (value === null || value === undefined || value === '') return null;
    const num = parseFloat(value);
    return isNaN(num) || num >= minVal ? null : message;
  },

  /**
   * Maximum value (for numbers)
   */
  max: (maxVal) => (value, message = `Must be no more than ${maxVal}`) => {
    if (value === null || value === undefined || value === '') return null;
    const num = parseFloat(value);
    return isNaN(num) || num <= maxVal ? null : message;
  },

  /**
   * Numeric only
   */
  numeric: (value, message = 'Please enter a valid number') => {
    if (!value && value !== 0) return null;
    return !isNaN(parseFloat(value)) && isFinite(value) ? null : message;
  },

  /**
   * Integer only
   */
  integer: (value, message = 'Please enter a whole number') => {
    if (!value && value !== 0) return null;
    return Number.isInteger(Number(value)) ? null : message;
  },

  /**
   * Positive number
   */
  positive: (value, message = 'Must be a positive number') => {
    if (!value && value !== 0) return null;
    const num = parseFloat(value);
    return isNaN(num) || num > 0 ? null : message;
  },

  /**
   * Non-negative number
   */
  nonNegative: (value, message = 'Cannot be negative') => {
    if (!value && value !== 0) return null;
    const num = parseFloat(value);
    return isNaN(num) || num >= 0 ? null : message;
  },

  /**
   * Currency format
   */
  currency: (value, message = 'Please enter a valid amount') => {
    if (!value) return null;
    const cleaned = value.toString().replace(/[$,\s]/g, '');
    const num = parseFloat(cleaned);
    return !isNaN(num) && isFinite(num) ? null : message;
  },

  /**
   * Date in YYYY-MM-DD format
   */
  date: (value, message = 'Please enter a valid date') => {
    if (!value) return null;
    const date = new Date(value);
    return !isNaN(date.getTime()) ? null : message;
  },

  /**
   * Date not in future
   */
  notFutureDate: (value, message = 'Date cannot be in the future') => {
    if (!value) return null;
    const date = new Date(value);
    const today = new Date();
    today.setHours(23, 59, 59, 999);
    return date <= today ? null : message;
  },

  /**
   * Date in range
   */
  dateRange: (minDate, maxDate) => (value, message) => {
    if (!value) return null;
    const date = new Date(value);
    const min = minDate ? new Date(minDate) : null;
    const max = maxDate ? new Date(maxDate) : null;

    if (min && date < min) return message || `Date must be after ${min.toLocaleDateString()}`;
    if (max && date > max) return message || `Date must be before ${max.toLocaleDateString()}`;
    return null;
  },

  /**
   * Pattern matching
   */
  pattern: (regex, errorMessage = 'Invalid format') => (value, message = errorMessage) => {
    if (!value) return null;
    const re = typeof regex === 'string' ? new RegExp(regex) : regex;
    return re.test(value) ? null : message;
  },

  /**
   * Match another field
   */
  matches: (fieldName, label = fieldName) => (value, message, formData) => {
    if (!value) return null;
    return value === formData[fieldName] ? null : message || `Must match ${label}`;
  },

  /**
   * Tax year validation
   */
  taxYear: (value, message = 'Please enter a valid tax year') => {
    if (!value) return null;
    const year = parseInt(value, 10);
    const currentYear = new Date().getFullYear();
    return year >= 1990 && year <= currentYear + 1 ? null : message;
  },

  /**
   * US state code
   */
  stateCode: (value, message = 'Please select a valid state') => {
    if (!value) return null;
    const states = [
      'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
      'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
      'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
      'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
      'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
      'DC', 'PR', 'VI', 'GU', 'AS', 'MP',
    ];
    return states.includes(value.toUpperCase()) ? null : message;
  },

  /**
   * Filing status validation
   */
  filingStatus: (value, message = 'Please select a filing status') => {
    if (!value) return null;
    const validStatuses = [
      'single',
      'married_filing_jointly',
      'married_filing_separately',
      'head_of_household',
      'qualifying_widow',
      'qualifying_surviving_spouse',
    ];
    return validStatuses.includes(value) ? null : message;
  },
};

// ============================================
// VALIDATION RUNNER
// ============================================

/**
 * Validate a single field
 * @param {any} value - Field value
 * @param {Array} rules - Array of validator functions or [validator, customMessage] tuples
 * @param {Object} formData - Full form data (for cross-field validation)
 * @returns {string|null} - Error message or null if valid
 */
export function validateField(value, rules, formData = {}) {
  if (!Array.isArray(rules)) {
    rules = [rules];
  }

  for (const rule of rules) {
    let validator, customMessage;

    if (Array.isArray(rule)) {
      [validator, customMessage] = rule;
    } else {
      validator = rule;
    }

    const error = validator(value, customMessage, formData);
    if (error) {
      return error;
    }
  }

  return null;
}

/**
 * Validate entire form
 * @param {Object} formData - Form data object
 * @param {Object} schema - Validation schema { fieldName: [validators] }
 * @returns {Object} - { isValid, errors: { fieldName: errorMessage } }
 */
export function validateForm(formData, schema) {
  const errors = {};
  let isValid = true;

  for (const [fieldName, rules] of Object.entries(schema)) {
    const error = validateField(formData[fieldName], rules, formData);
    if (error) {
      errors[fieldName] = error;
      isValid = false;
    }
  }

  return { isValid, errors };
}

// ============================================
// ALPINE.JS INTEGRATION
// ============================================

/**
 * Create Alpine.js form validation data
 * @param {Object} schema - Validation schema
 * @returns {Object} - Alpine.js data object
 */
export function createFormValidation(schema) {
  return {
    errors: {},
    touched: {},
    isSubmitting: false,

    validateField(fieldName) {
      if (!schema[fieldName]) return;
      const error = validateField(this[fieldName], schema[fieldName], this);
      this.errors[fieldName] = error;
      this.touched[fieldName] = true;
      return !error;
    },

    validateAll() {
      const result = validateForm(this, schema);
      this.errors = result.errors;
      // Mark all fields as touched
      Object.keys(schema).forEach((field) => {
        this.touched[field] = true;
      });
      return result.isValid;
    },

    getError(fieldName) {
      return this.touched[fieldName] ? this.errors[fieldName] : null;
    },

    hasError(fieldName) {
      return this.touched[fieldName] && !!this.errors[fieldName];
    },

    isValid(fieldName) {
      return this.touched[fieldName] && !this.errors[fieldName];
    },

    clearErrors() {
      this.errors = {};
      this.touched = {};
    },

    reset() {
      this.errors = {};
      this.touched = {};
      this.isSubmitting = false;
    },
  };
}

// ============================================
// COMMON VALIDATION SCHEMAS
// ============================================

export const schemas = {
  // Contact information
  contact: {
    email: [validators.required, validators.email],
    phone: [validators.phone],
    firstName: [validators.required, validators.minLength(2)],
    lastName: [validators.required, validators.minLength(2)],
  },

  // Address
  address: {
    street: [validators.required],
    city: [validators.required],
    state: [validators.required, validators.stateCode],
    zipCode: [validators.required, validators.zipCode],
  },

  // Basic taxpayer info
  taxpayer: {
    firstName: [validators.required],
    lastName: [validators.required],
    ssn: [validators.required, validators.ssn],
    dateOfBirth: [validators.required, validators.date, validators.notFutureDate],
    filingStatus: [validators.required, validators.filingStatus],
  },

  // Dependent
  dependent: {
    firstName: [validators.required],
    lastName: [validators.required],
    relationship: [validators.required],
    ssn: [validators.required, validators.ssn],
    dateOfBirth: [validators.required, validators.date, validators.notFutureDate],
  },

  // W-2 income
  w2: {
    employerName: [validators.required],
    employerEin: [validators.required, validators.ein],
    wages: [validators.required, validators.currency, validators.nonNegative],
    federalWithheld: [validators.currency, validators.nonNegative],
    stateWithheld: [validators.currency, validators.nonNegative],
  },

  // 1099 income
  income1099: {
    payerName: [validators.required],
    payerTin: [validators.required, validators.ein],
    amount: [validators.required, validators.currency, validators.nonNegative],
    type: [validators.required],
  },
};

// ============================================
// EXPORT AS GLOBAL (for non-module usage)
// ============================================

if (typeof window !== 'undefined') {
  window.TaxValidation = {
    validators,
    validateField,
    validateForm,
    createFormValidation,
    schemas,
  };
}
