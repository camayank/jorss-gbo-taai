/**
 * Unit tests for schema-validated tax profile.
 * Run with: node tests/js/tax-profile.test.cjs
 */

var assert = require('assert');
var loadModule = require('./load-module.cjs');

var schemaMod = loadModule('src/web/static/js/advisor/schema/tax-profile.js');
var schema = schemaMod.AdvisorFSMSchema || schemaMod;

var TAX_PROFILE_SCHEMA = schema.TAX_PROFILE_SCHEMA;
var NESTED_KEYS = schema.NESTED_KEYS;
var createValidatedProfile = schema.createValidatedProfile;
var validateProfile = schema.validateProfile;

var passed = 0;
var failed = 0;

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log('  \x1b[32m✓\x1b[0m ' + name);
  } catch (e) {
    failed++;
    console.log('  \x1b[31m✗\x1b[0m ' + name);
    console.log('    ' + e.message);
  }
}

// ---- Schema Structure ----
console.log('\nSchema structure:');

test('TAX_PROFILE_SCHEMA has expected sections', function() {
  assert.ok(TAX_PROFILE_SCHEMA.contact, 'Missing contact section');
  assert.ok(TAX_PROFILE_SCHEMA.tax_profile, 'Missing tax_profile section');
  assert.ok(TAX_PROFILE_SCHEMA.tax_items, 'Missing tax_items section');
  assert.ok(TAX_PROFILE_SCHEMA.business, 'Missing business section');
  assert.ok(TAX_PROFILE_SCHEMA.lead_data, 'Missing lead_data section');
  assert.ok(TAX_PROFILE_SCHEMA.documents, 'Missing documents section');
});

test('NESTED_KEYS maps nested fields to sections', function() {
  assert.strictEqual(NESTED_KEYS['filing_status'], 'tax_profile');
  assert.strictEqual(NESTED_KEYS['name'], 'contact');
  assert.strictEqual(NESTED_KEYS['mortgage_interest'], 'tax_items');
  assert.strictEqual(NESTED_KEYS['revenue'], 'business');
  assert.strictEqual(NESTED_KEYS['score'], 'lead_data');
});

// ---- createValidatedProfile ----
console.log('\ncreateValidatedProfile:');

test('Creates default structure with null values', function() {
  var profile = createValidatedProfile();
  var raw = profile.__raw || profile;
  assert.strictEqual(raw.contact.name, null);
  assert.strictEqual(raw.tax_profile.filing_status, null);
  assert.strictEqual(raw.tax_profile.total_income, null);
  assert.strictEqual(raw.lead_data.score, 0);
  assert.strictEqual(raw.lead_data.complexity, 'simple');
  assert.ok(Array.isArray(raw.documents));
  assert.strictEqual(raw.documents.length, 0);
});

test('Accepts initial data', function() {
  var profile = createValidatedProfile({
    contact: { name: 'John', email: 'john@test.com' },
    tax_profile: { filing_status: 'Single', total_income: 75000 }
  });
  var raw = profile.__raw || profile;
  assert.strictEqual(raw.contact.name, 'John');
  assert.strictEqual(raw.contact.email, 'john@test.com');
  assert.strictEqual(raw.tax_profile.filing_status, 'Single');
  assert.strictEqual(raw.tax_profile.total_income, 75000);
  // Unset fields should be default
  assert.strictEqual(raw.contact.phone, null);
});

test('Preserves dynamic root-level properties from initial data', function() {
  var profile = createValidatedProfile({
    focus_area: 'retirement',
    custom_prop: 'test'
  });
  var raw = profile.__raw || profile;
  assert.strictEqual(raw.focus_area, 'retirement');
  assert.strictEqual(raw.custom_prop, 'test');
});

test('Proxy allows normal reads and writes', function() {
  var profile = createValidatedProfile();
  profile.tax_profile.filing_status = 'Single';
  assert.strictEqual(profile.tax_profile.filing_status, 'Single');
  profile.lead_data.score = 50;
  assert.strictEqual(profile.lead_data.score, 50);
});

test('__raw returns underlying data', function() {
  var profile = createValidatedProfile();
  var raw = profile.__raw;
  assert.ok(raw, '__raw should return the underlying object');
  assert.ok(raw.contact, 'Raw should have contact section');
  assert.ok(raw.tax_profile, 'Raw should have tax_profile section');
});

test('__isValidatedProfile identity check works', function() {
  var profile = createValidatedProfile();
  assert.strictEqual(profile.__isValidatedProfile, true);
});

test('Copies initial documents array', function() {
  var docs = [{ name: 'w2.pdf' }];
  var profile = createValidatedProfile({ documents: docs });
  var raw = profile.__raw || profile;
  assert.strictEqual(raw.documents.length, 1);
  assert.strictEqual(raw.documents[0].name, 'w2.pdf');
  // Should be a copy, not a reference
  docs.push({ name: 'other.pdf' });
  assert.strictEqual(raw.documents.length, 1);
});

// ---- validateProfile ----
console.log('\nvalidateProfile:');

test('Valid profile passes validation', function() {
  var profile = createValidatedProfile({
    contact: { name: 'Jane' },
    tax_profile: { filing_status: 'Single', total_income: 100000 },
    lead_data: { score: 10, complexity: 'simple' }
  });
  var result = validateProfile(profile);
  assert.strictEqual(result.valid, true);
  assert.strictEqual(result.errors.length, 0);
});

test('Catches type mismatch (number field gets string)', function() {
  var profile = createValidatedProfile();
  profile.tax_profile.total_income = 'not a number';
  var result = validateProfile(profile);
  assert.strictEqual(result.valid, false);
  assert.ok(result.errors.some(function(e) { return e.indexOf('total_income') !== -1; }));
});

test('Catches invalid enum value', function() {
  var profile = createValidatedProfile();
  profile.tax_profile.filing_status = 'invalid_status';
  var result = validateProfile(profile);
  assert.strictEqual(result.valid, false);
  assert.ok(result.errors.some(function(e) { return e.indexOf('filing_status') !== -1; }));
});

test('Catches boolean type mismatch', function() {
  var profile = createValidatedProfile();
  profile.tax_items.has_hsa = 'yes';
  var result = validateProfile(profile);
  assert.strictEqual(result.valid, false);
  assert.ok(result.errors.some(function(e) { return e.indexOf('has_hsa') !== -1; }));
});

test('Null values pass validation (optional fields)', function() {
  var profile = createValidatedProfile();
  // All fields null by default should pass
  var result = validateProfile(profile);
  assert.strictEqual(result.valid, true);
});

test('Returns errors for null/undefined data', function() {
  var result = validateProfile(null);
  assert.strictEqual(result.valid, false);
  assert.ok(result.errors.length > 0);
});

test('Returns errors for missing sections', function() {
  var result = validateProfile({ contact: { name: null } });
  assert.strictEqual(result.valid, false);
  assert.ok(result.errors.some(function(e) { return e.indexOf('Missing section') !== -1; }));
});

// ---- Summary ----
console.log('\n' + (passed + failed) + ' tests, ' + passed + ' passed, ' + failed + ' failed');
if (failed > 0) {
  process.exit(1);
} else {
  console.log('\x1b[32mAll tests passed!\x1b[0m\n');
}
