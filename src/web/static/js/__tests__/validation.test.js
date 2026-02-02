/**
 * Validation Module Tests
 *
 * Tests for the form validation module including:
 * - Individual validators (required, email, SSN, etc.)
 * - Field validation
 * - Form validation
 * - Tax-specific validators
 */

import { describe, it, expect } from 'vitest';
import {
  validators,
  validateField,
  validateForm,
  createFormValidation,
  schemas,
} from '../core/validation.js';

describe('Validators', () => {
  describe('required', () => {
    it('should fail for null', () => {
      expect(validators.required(null)).toBe('This field is required');
    });

    it('should fail for undefined', () => {
      expect(validators.required(undefined)).toBe('This field is required');
    });

    it('should fail for empty string', () => {
      expect(validators.required('')).toBe('This field is required');
    });

    it('should fail for whitespace-only string', () => {
      expect(validators.required('   ')).toBe('This field is required');
    });

    it('should fail for empty array', () => {
      expect(validators.required([])).toBe('This field is required');
    });

    it('should pass for non-empty string', () => {
      expect(validators.required('hello')).toBeNull();
    });

    it('should pass for number', () => {
      expect(validators.required(0)).toBeNull();
      expect(validators.required(123)).toBeNull();
    });

    it('should pass for non-empty array', () => {
      expect(validators.required([1, 2, 3])).toBeNull();
    });

    it('should use custom message', () => {
      expect(validators.required('', 'Custom error')).toBe('Custom error');
    });
  });

  describe('email', () => {
    it('should pass for valid email', () => {
      expect(validators.email('test@example.com')).toBeNull();
      expect(validators.email('user.name@domain.co.uk')).toBeNull();
      expect(validators.email('user+tag@gmail.com')).toBeNull();
    });

    it('should fail for invalid email', () => {
      expect(validators.email('invalid')).toBe('Please enter a valid email address');
      expect(validators.email('missing@domain')).toBe('Please enter a valid email address');
      expect(validators.email('@nodomain.com')).toBe('Please enter a valid email address');
      expect(validators.email('spaces in@email.com')).toBe('Please enter a valid email address');
    });

    it('should pass for empty value (use required for empty check)', () => {
      expect(validators.email('')).toBeNull();
      expect(validators.email(null)).toBeNull();
    });
  });

  describe('phone', () => {
    it('should pass for valid US phone numbers', () => {
      expect(validators.phone('1234567890')).toBeNull();
      expect(validators.phone('123-456-7890')).toBeNull();
      expect(validators.phone('(123) 456-7890')).toBeNull();
      expect(validators.phone('11234567890')).toBeNull(); // With country code
    });

    it('should fail for invalid phone numbers', () => {
      expect(validators.phone('123456')).toBe('Please enter a valid phone number');
      expect(validators.phone('12345678901234')).toBe('Please enter a valid phone number');
    });

    it('should pass for empty value', () => {
      expect(validators.phone('')).toBeNull();
    });
  });

  describe('ssn', () => {
    it('should pass for valid SSN', () => {
      expect(validators.ssn('123-45-6789')).toBeNull();
      expect(validators.ssn('123456789')).toBeNull();
    });

    it('should fail for invalid SSN starting with 000', () => {
      expect(validators.ssn('000-12-3456')).toBe('Please enter a valid SSN (XXX-XX-XXXX)');
    });

    it('should fail for invalid SSN starting with 666', () => {
      expect(validators.ssn('666-12-3456')).toBe('Please enter a valid SSN (XXX-XX-XXXX)');
    });

    it('should fail for invalid SSN starting with 9XX', () => {
      expect(validators.ssn('900-12-3456')).toBe('Please enter a valid SSN (XXX-XX-XXXX)');
    });

    it('should fail for SSN with 00 middle digits', () => {
      expect(validators.ssn('123-00-6789')).toBe('Please enter a valid SSN (XXX-XX-XXXX)');
    });

    it('should fail for SSN with 0000 last digits', () => {
      expect(validators.ssn('123-45-0000')).toBe('Please enter a valid SSN (XXX-XX-XXXX)');
    });

    it('should fail for wrong length', () => {
      expect(validators.ssn('12345678')).toBe('Please enter a valid SSN (XXX-XX-XXXX)');
      expect(validators.ssn('1234567890')).toBe('Please enter a valid SSN (XXX-XX-XXXX)');
    });

    it('should pass for empty value', () => {
      expect(validators.ssn('')).toBeNull();
    });
  });

  describe('ein', () => {
    it('should pass for valid EIN', () => {
      expect(validators.ein('12-3456789')).toBeNull();
      expect(validators.ein('123456789')).toBeNull();
    });

    it('should fail for invalid EIN', () => {
      expect(validators.ein('12345678')).toBe('Please enter a valid EIN (XX-XXXXXXX)');
      expect(validators.ein('1234567890')).toBe('Please enter a valid EIN (XX-XXXXXXX)');
    });

    it('should pass for empty value', () => {
      expect(validators.ein('')).toBeNull();
    });
  });

  describe('zipCode', () => {
    it('should pass for valid ZIP codes', () => {
      expect(validators.zipCode('12345')).toBeNull();
      expect(validators.zipCode('12345-6789')).toBeNull();
    });

    it('should fail for invalid ZIP codes', () => {
      expect(validators.zipCode('1234')).toBe('Please enter a valid ZIP code');
      expect(validators.zipCode('123456')).toBe('Please enter a valid ZIP code');
      expect(validators.zipCode('12345-67')).toBe('Please enter a valid ZIP code');
      expect(validators.zipCode('abcde')).toBe('Please enter a valid ZIP code');
    });

    it('should pass for empty value', () => {
      expect(validators.zipCode('')).toBeNull();
    });
  });

  describe('minLength', () => {
    it('should pass when value meets minimum', () => {
      expect(validators.minLength(3)('abc')).toBeNull();
      expect(validators.minLength(3)('abcdef')).toBeNull();
    });

    it('should fail when value is too short', () => {
      expect(validators.minLength(3)('ab')).toBe('Must be at least 3 characters');
    });

    it('should pass for empty value', () => {
      expect(validators.minLength(3)('')).toBeNull();
    });
  });

  describe('maxLength', () => {
    it('should pass when value is within limit', () => {
      expect(validators.maxLength(5)('abc')).toBeNull();
      expect(validators.maxLength(5)('abcde')).toBeNull();
    });

    it('should fail when value exceeds limit', () => {
      expect(validators.maxLength(5)('abcdef')).toBe('Must be no more than 5 characters');
    });

    it('should pass for empty value', () => {
      expect(validators.maxLength(5)('')).toBeNull();
    });
  });

  describe('min', () => {
    it('should pass when value meets minimum', () => {
      expect(validators.min(10)(10)).toBeNull();
      expect(validators.min(10)(15)).toBeNull();
    });

    it('should fail when value is below minimum', () => {
      expect(validators.min(10)(5)).toBe('Must be at least 10');
    });

    it('should pass for empty value', () => {
      expect(validators.min(10)('')).toBeNull();
      expect(validators.min(10)(null)).toBeNull();
    });
  });

  describe('max', () => {
    it('should pass when value is within maximum', () => {
      expect(validators.max(100)(50)).toBeNull();
      expect(validators.max(100)(100)).toBeNull();
    });

    it('should fail when value exceeds maximum', () => {
      expect(validators.max(100)(150)).toBe('Must be no more than 100');
    });

    it('should pass for empty value', () => {
      expect(validators.max(100)('')).toBeNull();
    });
  });

  describe('numeric', () => {
    it('should pass for numeric values', () => {
      expect(validators.numeric(123)).toBeNull();
      expect(validators.numeric('123.45')).toBeNull();
      expect(validators.numeric(-50)).toBeNull();
      expect(validators.numeric(0)).toBeNull();
    });

    it('should fail for non-numeric values', () => {
      expect(validators.numeric('abc')).toBe('Please enter a valid number');
      expect(validators.numeric('12.34.56')).toBe('Please enter a valid number');
    });

    it('should pass for empty value', () => {
      expect(validators.numeric('')).toBeNull();
    });
  });

  describe('integer', () => {
    it('should pass for integers', () => {
      expect(validators.integer(123)).toBeNull();
      expect(validators.integer(-50)).toBeNull();
      expect(validators.integer(0)).toBeNull();
      expect(validators.integer('42')).toBeNull();
    });

    it('should fail for non-integers', () => {
      expect(validators.integer(12.5)).toBe('Please enter a whole number');
      expect(validators.integer('12.5')).toBe('Please enter a whole number');
    });

    it('should pass for empty value', () => {
      expect(validators.integer('')).toBeNull();
    });
  });

  describe('positive', () => {
    it('should pass for positive numbers', () => {
      expect(validators.positive(1)).toBeNull();
      expect(validators.positive(100)).toBeNull();
    });

    it('should fail for zero and negative numbers', () => {
      expect(validators.positive(0)).toBe('Must be a positive number');
      expect(validators.positive(-1)).toBe('Must be a positive number');
    });

    it('should pass for empty value', () => {
      expect(validators.positive('')).toBeNull();
    });
  });

  describe('nonNegative', () => {
    it('should pass for zero and positive numbers', () => {
      expect(validators.nonNegative(0)).toBeNull();
      expect(validators.nonNegative(100)).toBeNull();
    });

    it('should fail for negative numbers', () => {
      expect(validators.nonNegative(-1)).toBe('Cannot be negative');
    });

    it('should pass for empty value', () => {
      expect(validators.nonNegative('')).toBeNull();
    });
  });

  describe('currency', () => {
    it('should pass for valid currency amounts', () => {
      expect(validators.currency('100')).toBeNull();
      expect(validators.currency('$1,234.56')).toBeNull();
      expect(validators.currency('1000.00')).toBeNull();
    });

    it('should fail for invalid currency amounts', () => {
      expect(validators.currency('abc')).toBe('Please enter a valid amount');
    });

    it('should pass for empty value', () => {
      expect(validators.currency('')).toBeNull();
    });
  });

  describe('date', () => {
    it('should pass for valid dates', () => {
      expect(validators.date('2024-01-15')).toBeNull();
      expect(validators.date('2024/01/15')).toBeNull();
    });

    it('should fail for invalid dates', () => {
      expect(validators.date('invalid-date')).toBe('Please enter a valid date');
    });

    it('should pass for empty value', () => {
      expect(validators.date('')).toBeNull();
    });
  });

  describe('taxYear', () => {
    it('should pass for valid tax years', () => {
      expect(validators.taxYear(2024)).toBeNull();
      expect(validators.taxYear('2023')).toBeNull();
      expect(validators.taxYear(1990)).toBeNull();
    });

    it('should fail for invalid tax years', () => {
      expect(validators.taxYear(1989)).toBe('Please enter a valid tax year');
      expect(validators.taxYear(2099)).toBe('Please enter a valid tax year');
    });

    it('should pass for empty value', () => {
      expect(validators.taxYear('')).toBeNull();
    });
  });

  describe('stateCode', () => {
    it('should pass for valid state codes', () => {
      expect(validators.stateCode('CA')).toBeNull();
      expect(validators.stateCode('ny')).toBeNull(); // Case insensitive
      expect(validators.stateCode('TX')).toBeNull();
      expect(validators.stateCode('DC')).toBeNull();
    });

    it('should fail for invalid state codes', () => {
      expect(validators.stateCode('XX')).toBe('Please select a valid state');
      expect(validators.stateCode('ZZ')).toBe('Please select a valid state');
    });

    it('should pass for empty value', () => {
      expect(validators.stateCode('')).toBeNull();
    });
  });

  describe('filingStatus', () => {
    it('should pass for valid filing statuses', () => {
      expect(validators.filingStatus('single')).toBeNull();
      expect(validators.filingStatus('married_filing_jointly')).toBeNull();
      expect(validators.filingStatus('married_filing_separately')).toBeNull();
      expect(validators.filingStatus('head_of_household')).toBeNull();
      expect(validators.filingStatus('qualifying_widow')).toBeNull();
    });

    it('should fail for invalid filing statuses', () => {
      expect(validators.filingStatus('invalid')).toBe('Please select a filing status');
      expect(validators.filingStatus('SINGLE')).toBe('Please select a filing status');
    });

    it('should pass for empty value', () => {
      expect(validators.filingStatus('')).toBeNull();
    });
  });

  describe('pattern', () => {
    it('should pass when pattern matches', () => {
      const alphanumeric = validators.pattern(/^[a-z0-9]+$/i);
      expect(alphanumeric('abc123')).toBeNull();
    });

    it('should fail when pattern does not match', () => {
      const alphanumeric = validators.pattern(/^[a-z0-9]+$/i, 'Letters and numbers only');
      expect(alphanumeric('abc 123')).toBe('Letters and numbers only');
    });

    it('should pass for empty value', () => {
      const alphanumeric = validators.pattern(/^[a-z0-9]+$/i);
      expect(alphanumeric('')).toBeNull();
    });
  });

  describe('matches', () => {
    it('should pass when fields match', () => {
      const matchPassword = validators.matches('password', 'Password');
      const formData = { password: 'secret123', confirmPassword: 'secret123' };
      expect(matchPassword('secret123', null, formData)).toBeNull();
    });

    it('should fail when fields do not match', () => {
      const matchPassword = validators.matches('password', 'Password');
      const formData = { password: 'secret123', confirmPassword: 'different' };
      expect(matchPassword('different', null, formData)).toBe('Must match Password');
    });

    it('should pass for empty value', () => {
      const matchPassword = validators.matches('password');
      expect(matchPassword('', null, { password: 'secret' })).toBeNull();
    });
  });
});

describe('validateField', () => {
  it('should run single validator', () => {
    expect(validateField('', validators.required)).toBe('This field is required');
    expect(validateField('hello', validators.required)).toBeNull();
  });

  it('should run multiple validators', () => {
    const rules = [validators.required, validators.email];
    expect(validateField('', rules)).toBe('This field is required');
    expect(validateField('invalid', rules)).toBe('Please enter a valid email address');
    expect(validateField('test@example.com', rules)).toBeNull();
  });

  it('should support custom messages', () => {
    const rules = [[validators.required, 'Email is required'], validators.email];
    expect(validateField('', rules)).toBe('Email is required');
  });

  it('should stop at first error', () => {
    const rules = [validators.required, validators.email, validators.minLength(10)];
    expect(validateField('', rules)).toBe('This field is required');
  });
});

describe('validateForm', () => {
  const schema = {
    email: [validators.required, validators.email],
    phone: [validators.phone],
    ssn: [validators.required, validators.ssn],
  };

  it('should return valid result for valid form', () => {
    const formData = {
      email: 'test@example.com',
      phone: '123-456-7890',
      ssn: '123-45-6789',
    };

    const result = validateForm(formData, schema);
    expect(result.isValid).toBe(true);
    expect(result.errors).toEqual({});
  });

  it('should return errors for invalid form', () => {
    const formData = {
      email: '',
      phone: '123',
      ssn: '000-00-0000',
    };

    const result = validateForm(formData, schema);
    expect(result.isValid).toBe(false);
    expect(result.errors.email).toBe('This field is required');
    expect(result.errors.phone).toBe('Please enter a valid phone number');
    expect(result.errors.ssn).toBe('Please enter a valid SSN (XXX-XX-XXXX)');
  });

  it('should skip optional fields when empty', () => {
    const formData = {
      email: 'test@example.com',
      phone: '', // Optional field
      ssn: '123-45-6789',
    };

    const result = validateForm(formData, schema);
    expect(result.isValid).toBe(true);
  });
});

describe('createFormValidation', () => {
  const schema = {
    email: [validators.required, validators.email],
    name: [validators.required],
  };

  it('should create validation data object', () => {
    const validation = createFormValidation(schema);
    expect(validation.errors).toEqual({});
    expect(validation.touched).toEqual({});
    expect(validation.isSubmitting).toBe(false);
  });

  it('should have validateField method', () => {
    const validation = createFormValidation(schema);
    expect(typeof validation.validateField).toBe('function');
  });

  it('should have validateAll method', () => {
    const validation = createFormValidation(schema);
    expect(typeof validation.validateAll).toBe('function');
  });

  it('should have helper methods', () => {
    const validation = createFormValidation(schema);
    expect(typeof validation.getError).toBe('function');
    expect(typeof validation.hasError).toBe('function');
    expect(typeof validation.isValid).toBe('function');
    expect(typeof validation.clearErrors).toBe('function');
    expect(typeof validation.reset).toBe('function');
  });
});

describe('Pre-built Schemas', () => {
  it('should have contact schema', () => {
    expect(schemas.contact).toBeDefined();
    expect(schemas.contact.email).toBeDefined();
    expect(schemas.contact.phone).toBeDefined();
    expect(schemas.contact.firstName).toBeDefined();
    expect(schemas.contact.lastName).toBeDefined();
  });

  it('should have address schema', () => {
    expect(schemas.address).toBeDefined();
    expect(schemas.address.street).toBeDefined();
    expect(schemas.address.city).toBeDefined();
    expect(schemas.address.state).toBeDefined();
    expect(schemas.address.zipCode).toBeDefined();
  });

  it('should have taxpayer schema', () => {
    expect(schemas.taxpayer).toBeDefined();
    expect(schemas.taxpayer.firstName).toBeDefined();
    expect(schemas.taxpayer.lastName).toBeDefined();
    expect(schemas.taxpayer.ssn).toBeDefined();
    expect(schemas.taxpayer.filingStatus).toBeDefined();
  });

  it('should have W-2 schema', () => {
    expect(schemas.w2).toBeDefined();
    expect(schemas.w2.employerName).toBeDefined();
    expect(schemas.w2.employerEin).toBeDefined();
    expect(schemas.w2.wages).toBeDefined();
  });

  it('should validate contact schema correctly', () => {
    const validContact = {
      email: 'test@example.com',
      phone: '123-456-7890',
      firstName: 'John',
      lastName: 'Doe',
    };

    const result = validateForm(validContact, schemas.contact);
    expect(result.isValid).toBe(true);
  });

  it('should validate taxpayer schema correctly', () => {
    const validTaxpayer = {
      firstName: 'John',
      lastName: 'Doe',
      ssn: '123-45-6789',
      dateOfBirth: '1990-01-15',
      filingStatus: 'single',
    };

    const result = validateForm(validTaxpayer, schemas.taxpayer);
    expect(result.isValid).toBe(true);
  });
});
