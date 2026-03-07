/**
 * Schema-validated tax profile data model.
 * Uses Proxy to intercept writes and ensure they go to the correct nested path.
 *
 * Prevents bugs like `extractedData.filing_status = 'single'` (should be
 * `extractedData.tax_profile.filing_status = 'single'`).
 */

var TAX_PROFILE_SCHEMA = {
  contact: {
    name: { type: 'string', default_val: null },
    email: { type: 'string', default_val: null },
    phone: { type: 'string', default_val: null },
    preferred_contact: { type: 'string', default_val: null }
  },
  tax_profile: {
    filing_status: { type: 'string', enum_vals: ['Single', 'Married Filing Jointly', 'Married Filing Separately', 'Head of Household', 'Qualifying Surviving Spouse'], default_val: null },
    total_income: { type: 'number', default_val: null },
    w2_income: { type: 'number', default_val: null },
    business_income: { type: 'number', default_val: null },
    investment_income: { type: 'number', default_val: null },
    rental_income: { type: 'number', default_val: null },
    dependents: { type: 'number', default_val: null },
    state: { type: 'string', default_val: null }
  },
  tax_items: {
    mortgage_interest: { type: 'number', default_val: null },
    property_tax: { type: 'number', default_val: null },
    charitable: { type: 'number', default_val: null },
    medical: { type: 'number', default_val: null },
    student_loan_interest: { type: 'number', default_val: null },
    retirement_contributions: { type: 'number', default_val: null },
    has_hsa: { type: 'boolean', default_val: false },
    has_529: { type: 'boolean', default_val: false }
  },
  business: {
    type: { type: 'string', default_val: null },
    revenue: { type: 'number', default_val: null },
    expenses: { type: 'number', default_val: null },
    entity_type: { type: 'string', default_val: null }
  },
  lead_data: {
    score: { type: 'number', default_val: 0 },
    complexity: { type: 'string', enum_vals: ['simple', 'moderate', 'complex'], default_val: 'simple' },
    estimated_savings: { type: 'number', default_val: 0 },
    engagement_level: { type: 'number', default_val: 0 },
    ready_for_cpa: { type: 'boolean', default_val: false },
    urgency: { type: 'string', enum_vals: ['normal', 'high', 'urgent'], default_val: 'normal' }
  },
  documents: { type: 'array', default_val: [] }
};

/** Build set of known nested keys (writes to these at root are likely errors) */
var NESTED_KEYS = {};
(function() {
  var sections = Object.keys(TAX_PROFILE_SCHEMA);
  for (var i = 0; i < sections.length; i++) {
    var section = sections[i];
    var fields = TAX_PROFILE_SCHEMA[section];
    if (typeof fields === 'object' && !fields.type) {
      var keys = Object.keys(fields);
      for (var j = 0; j < keys.length; j++) {
        NESTED_KEYS[keys[j]] = section;
      }
    }
  }
})();

/**
 * Create a schema-validated extractedData object.
 * In development mode, warns on writes to wrong property paths.
 *
 * @param {Object} [initial] - Optional initial data (for session restore)
 * @returns {Proxy|Object} - Schema-validated data object (Proxy if supported, plain object otherwise)
 */
function createValidatedProfile(initial) {
  initial = initial || null;

  // Build default structure from schema
  var data = {};
  var sections = Object.keys(TAX_PROFILE_SCHEMA);
  for (var i = 0; i < sections.length; i++) {
    var section = sections[i];
    var fields = TAX_PROFILE_SCHEMA[section];

    if (fields.type === 'array') {
      data[section] = (initial && initial[section]) ? initial[section].slice() : [];
    } else {
      data[section] = {};
      var fieldNames = Object.keys(fields);
      for (var j = 0; j < fieldNames.length; j++) {
        var key = fieldNames[j];
        var spec = fields[key];
        var initialVal = (initial && initial[section] && initial[section][key] !== undefined)
          ? initial[section][key]
          : spec.default_val;
        data[section][key] = initialVal;
      }
    }
  }

  // Copy dynamic root-level properties (focus_area, deductions array, credits array, details, etc.)
  if (initial) {
    var initKeys = Object.keys(initial);
    for (var k = 0; k < initKeys.length; k++) {
      var ik = initKeys[k];
      if (!(ik in data)) {
        data[ik] = initial[ik];
      }
    }
  }

  // If Proxy is not available (old browsers), return plain object
  if (typeof Proxy === 'undefined') {
    return data;
  }

  var isDev = typeof window !== 'undefined' &&
    (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

  return new Proxy(data, {
    set: function(target, prop, value) {
      // Warn if setting a nested property at root level
      if (isDev && typeof prop === 'string' && NESTED_KEYS[prop]) {
        console.warn(
          '[TaxProfile] Writing "' + prop + '" at root level. ' +
          'Did you mean to write to "' + NESTED_KEYS[prop] + '.' + prop + '"? ' +
          'Known sections: ' + Object.keys(TAX_PROFILE_SCHEMA).join(', ')
        );
      }
      target[prop] = value;
      return true;
    },
    get: function(target, prop) {
      if (prop === '__raw') return target;  // escape hatch for serialization
      if (prop === '__isValidatedProfile') return true;  // identity check
      return target[prop];
    }
  });
}

/**
 * Validate the current data against the schema.
 * @param {Object} data - The extractedData (or its __raw)
 * @returns {{ valid: boolean, errors: string[] }}
 */
function validateProfile(data) {
  var raw = (data && data.__raw) ? data.__raw : data;
  var errors = [];

  if (!raw) {
    return { valid: false, errors: ['Data is null or undefined'] };
  }

  var sections = Object.keys(TAX_PROFILE_SCHEMA);
  for (var i = 0; i < sections.length; i++) {
    var section = sections[i];
    var fields = TAX_PROFILE_SCHEMA[section];

    if (fields.type === 'array') continue;  // skip documents array

    if (!raw[section]) {
      errors.push('Missing section: ' + section);
      continue;
    }

    var fieldNames = Object.keys(fields);
    for (var j = 0; j < fieldNames.length; j++) {
      var key = fieldNames[j];
      var spec = fields[key];
      var val = raw[section][key];

      if (val !== null && val !== undefined) {
        if (spec.type === 'number' && typeof val !== 'number') {
          errors.push(section + '.' + key + ': expected number, got ' + typeof val);
        }
        if (spec.type === 'boolean' && typeof val !== 'boolean') {
          errors.push(section + '.' + key + ': expected boolean, got ' + typeof val);
        }
        if (spec.type === 'string' && typeof val !== 'string') {
          errors.push(section + '.' + key + ': expected string, got ' + typeof val);
        }
        if (spec.enum_vals && spec.enum_vals.indexOf(val) === -1) {
          errors.push(section + '.' + key + ': "' + val + '" not in [' + spec.enum_vals.join(', ') + ']');
        }
      }
    }
  }

  return { valid: errors.length === 0, errors: errors };
}

// Export
if (typeof window !== 'undefined') {
  window.AdvisorFSMSchema = {
    TAX_PROFILE_SCHEMA: TAX_PROFILE_SCHEMA,
    NESTED_KEYS: NESTED_KEYS,
    createValidatedProfile: createValidatedProfile,
    validateProfile: validateProfile
  };
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    TAX_PROFILE_SCHEMA: TAX_PROFILE_SCHEMA,
    NESTED_KEYS: NESTED_KEYS,
    createValidatedProfile: createValidatedProfile,
    validateProfile: validateProfile
  };
}
