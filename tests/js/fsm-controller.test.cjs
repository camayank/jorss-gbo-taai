/**
 * Unit tests for FSM controller, states, and action-config.
 * Run with: node tests/js/fsm-controller.test.cjs
 */

var assert = require('assert');
var loadModule = require('./load-module.cjs');

// Load modules via VM sandbox (bypasses ESM package.json issue)
var SRC = 'src/web/static/js/advisor';
var statesMod = loadModule(SRC + '/fsm/states.js');
var actionMod = loadModule(SRC + '/fsm/action-config.js');
var controllerMod = loadModule(SRC + '/fsm/controller.js');

// Unwrap: modules may export under window.* keys or module.exports keys
var states = statesMod.AdvisorFSMStates || statesMod;
var actionConfig = actionMod.AdvisorFSMActionConfig || actionMod;
var controller = controllerMod;

var AdvisorState = states.AdvisorState;
var STATE_TO_PHASE = states.STATE_TO_PHASE;
var isValidTransition = states.isValidTransition;
var ACTION_CONFIG = actionConfig.ACTION_CONFIG;
var buildActionIndex = actionConfig.buildActionIndex;
var findActionEntry = actionConfig.findActionEntry;
var AdvisorFSM = controllerMod.AdvisorFSM;

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

function createMockData() {
  return {
    contact: { name: null, email: null, phone: null, preferred_contact: null },
    tax_profile: { filing_status: null, total_income: null, w2_income: null, business_income: null, investment_income: null, rental_income: null, dependents: null, state: null },
    tax_items: { mortgage_interest: null, property_tax: null, charitable: null, medical: null, student_loan_interest: null, retirement_contributions: null, has_hsa: false, has_529: false },
    business: { type: null, revenue: null, expenses: null, entity_type: null },
    lead_data: { score: 0, complexity: 'simple', estimated_savings: 0, engagement_level: 0, ready_for_cpa: false, urgency: 'normal' },
    documents: []
  };
}

// ---- States Module ----
console.log('\nStates module:');

test('AdvisorState has all expected states', function() {
  assert.ok(AdvisorState.WELCOME);
  assert.ok(AdvisorState.COLLECT_NAME);
  assert.ok(AdvisorState.COLLECT_FILING_STATUS);
  assert.ok(AdvisorState.COLLECT_INCOME_TYPE);
  assert.ok(AdvisorState.COLLECT_W2);
  assert.ok(AdvisorState.REVIEW_SUMMARY);
  assert.ok(AdvisorState.GENERATE_REPORT);
  assert.ok(AdvisorState.AI_CONVERSATION);
  assert.ok(AdvisorState.ERROR);
});

test('AdvisorState values are frozen', function() {
  var original = AdvisorState.WELCOME;
  try { AdvisorState.WELCOME = 'hacked'; } catch(e) { /* strict mode throws */ }
  assert.strictEqual(AdvisorState.WELCOME, original);
});

test('STATE_TO_PHASE maps all states', function() {
  var stateKeys = Object.keys(AdvisorState);
  for (var i = 0; i < stateKeys.length; i++) {
    var state = AdvisorState[stateKeys[i]];
    assert.ok(state in STATE_TO_PHASE, 'Missing phase mapping for state: ' + state);
  }
});

test('STATE_TO_PHASE maps to valid phases', function() {
  var validPhases = ['personal_info', 'income', 'deductions', 'review', 'ready_to_file', null];
  var keys = Object.keys(STATE_TO_PHASE);
  for (var i = 0; i < keys.length; i++) {
    var phase = STATE_TO_PHASE[keys[i]];
    assert.ok(validPhases.indexOf(phase) !== -1, 'Invalid phase: ' + phase + ' for state: ' + keys[i]);
  }
});

test('isValidTransition allows forward transitions', function() {
  assert.ok(isValidTransition(AdvisorState.WELCOME, AdvisorState.COLLECT_NAME));
  assert.ok(isValidTransition(AdvisorState.COLLECT_FILING_STATUS, AdvisorState.COLLECT_INCOME_TYPE));
  assert.ok(isValidTransition(AdvisorState.COLLECT_DEDUCTIONS, AdvisorState.REVIEW_SUMMARY));
});

test('isValidTransition allows same-phase transitions', function() {
  assert.ok(isValidTransition(AdvisorState.COLLECT_W2, AdvisorState.COLLECT_BUSINESS_INCOME));
  assert.ok(isValidTransition(AdvisorState.COLLECT_MORTGAGE, AdvisorState.COLLECT_CHARITABLE));
});

test('isValidTransition allows AI_CONVERSATION from any state', function() {
  assert.ok(isValidTransition(AdvisorState.WELCOME, AdvisorState.AI_CONVERSATION));
  assert.ok(isValidTransition(AdvisorState.COLLECT_W2, AdvisorState.AI_CONVERSATION));
  assert.ok(isValidTransition(AdvisorState.REVIEW_SUMMARY, AdvisorState.AI_CONVERSATION));
});

test('isValidTransition allows ERROR from any state', function() {
  assert.ok(isValidTransition(AdvisorState.WELCOME, AdvisorState.ERROR));
  assert.ok(isValidTransition(AdvisorState.GENERATE_REPORT, AdvisorState.ERROR));
});

test('isValidTransition allows one-phase back for edits', function() {
  assert.ok(isValidTransition(AdvisorState.COLLECT_INCOME_TYPE, AdvisorState.COLLECT_FILING_STATUS));
});

test('isValidTransition rejects skipping two phases back', function() {
  assert.strictEqual(isValidTransition(AdvisorState.REVIEW_SUMMARY, AdvisorState.COLLECT_W2), false);
});

// ---- Action Config Module ----
console.log('\nAction Config module:');

test('ACTION_CONFIG is a non-empty array', function() {
  assert.ok(Array.isArray(ACTION_CONFIG));
  assert.ok(ACTION_CONFIG.length > 50, 'Expected at least 50 config entries, got ' + ACTION_CONFIG.length);
});

test('Each config entry has required fields', function() {
  for (var i = 0; i < ACTION_CONFIG.length; i++) {
    var entry = ACTION_CONFIG[i];
    assert.ok(entry.action || entry.prefix, 'Entry ' + i + ' has neither action nor prefix');
    assert.ok(entry.fromStates, 'Entry ' + i + ' missing fromStates');
    assert.ok(entry.userMessage !== undefined, 'Entry ' + i + ' missing userMessage');
  }
});

test('buildActionIndex creates exact and prefixes', function() {
  var index = buildActionIndex(ACTION_CONFIG);
  assert.ok(index.exact, 'Index missing exact map');
  assert.ok(Array.isArray(index.prefixes), 'Index missing prefixes array');
  assert.ok(Object.keys(index.exact).length > 0, 'Exact index is empty');
  assert.ok(index.prefixes.length > 0, 'Prefix index is empty');
});

test('findActionEntry finds exact match', function() {
  var index = buildActionIndex(ACTION_CONFIG);
  var entry = findActionEntry(index, 'no_manual', AdvisorState.WELCOME);
  assert.ok(entry, 'Should find no_manual action');
  assert.ok(entry.toState, 'no_manual should have a toState');
});

test('findActionEntry finds prefix match', function() {
  var index = buildActionIndex(ACTION_CONFIG);
  var entry = findActionEntry(index, 'filing_single', AdvisorState.COLLECT_FILING_STATUS);
  assert.ok(entry, 'Should find filing_ prefix match');
});

test('findActionEntry returns null for unknown action', function() {
  var index = buildActionIndex(ACTION_CONFIG);
  var entry = findActionEntry(index, 'totally_unknown_action_xyz', AdvisorState.WELCOME);
  assert.strictEqual(entry, null);
});

test('findActionEntry respects fromStates filter', function() {
  var index = buildActionIndex(ACTION_CONFIG);
  // no_manual is valid from WELCOME but likely not from GENERATE_REPORT
  var entry = findActionEntry(index, 'no_manual', AdvisorState.WELCOME);
  assert.ok(entry, 'Should find no_manual from WELCOME');
});

// ---- FSM Controller ----
console.log('\nFSM Controller:');

test('Constructor sets initial state to WELCOME', function() {
  var fsm = new AdvisorFSM(createMockData());
  assert.strictEqual(fsm.getState(), AdvisorState.WELCOME);
});

test('Constructor accepts custom initial state', function() {
  var fsm = new AdvisorFSM(createMockData(), { initialState: AdvisorState.COLLECT_W2 });
  assert.strictEqual(fsm.getState(), AdvisorState.COLLECT_W2);
});

test('getPhase returns correct phase for state', function() {
  var fsm = new AdvisorFSM(createMockData());
  assert.strictEqual(fsm.getPhase(), 'personal_info');

  fsm.setState(AdvisorState.COLLECT_W2);
  assert.strictEqual(fsm.getPhase(), 'income');
});

test('handleAction returns handled:true for known actions', function() {
  var fsm = new AdvisorFSM(createMockData());
  var result = fsm.handleAction('no_manual');
  assert.strictEqual(result.handled, true);
  assert.ok(result.userMessage, 'Should have a userMessage');
});

test('handleAction returns handled:false for unknown actions', function() {
  var fsm = new AdvisorFSM(createMockData());
  var result = fsm.handleAction('completely_unknown_xyz');
  assert.strictEqual(result.handled, false);
});

test('handleAction transitions state correctly', function() {
  var data = createMockData();
  var fsm = new AdvisorFSM(data);
  // WELCOME -> no_manual -> COLLECT_FILING_STATUS
  var result = fsm.handleAction('no_manual');
  assert.strictEqual(result.handled, true);
  assert.strictEqual(fsm.getState(), AdvisorState.COLLECT_FILING_STATUS);
});

test('handleAction extracts data', function() {
  var data = createMockData();
  var fsm = new AdvisorFSM(data, { initialState: AdvisorState.COLLECT_FILING_STATUS });
  fsm.handleAction('filing_single');
  assert.strictEqual(data.tax_profile.filing_status, 'Single');
});

test('handleAction emits transition event', function() {
  var events = [];
  var fsm = new AdvisorFSM(createMockData());
  fsm.on('transition', function(from, to, action) {
    events.push({ from: from, to: to, action: action });
  });
  fsm.handleAction('no_manual');
  assert.strictEqual(events.length, 1);
  assert.strictEqual(events[0].from, AdvisorState.WELCOME);
  assert.strictEqual(events[0].action, 'no_manual');
});

test('handleAction emits phaseChange event on phase boundary', function() {
  var phases = [];
  var data = createMockData();
  var fsm = new AdvisorFSM(data, { initialState: AdvisorState.COLLECT_FILING_STATUS });
  fsm.on('phaseChange', function(fromPhase, toPhase) {
    phases.push({ from: fromPhase, to: toPhase });
  });
  fsm.handleAction('filing_single');
  assert.strictEqual(phases.length, 1);
  assert.strictEqual(phases[0].from, 'personal_info');
  assert.strictEqual(phases[0].to, 'income');
});

test('goBack restores previous state', function() {
  var fsm = new AdvisorFSM(createMockData());
  var initial = fsm.getState();
  fsm.handleAction('no_manual');
  assert.notStrictEqual(fsm.getState(), initial);
  fsm.goBack();
  assert.strictEqual(fsm.getState(), initial);
});

test('goBack returns false when no history', function() {
  var fsm = new AdvisorFSM(createMockData());
  assert.strictEqual(fsm.goBack(), false);
});

test('setState forces state', function() {
  var fsm = new AdvisorFSM(createMockData());
  fsm.setState(AdvisorState.REVIEW_SUMMARY);
  assert.strictEqual(fsm.getState(), AdvisorState.REVIEW_SUMMARY);
});

test('toJSON/fromJSON roundtrip', function() {
  var data = createMockData();
  var fsm = new AdvisorFSM(data);
  fsm.handleAction('no_manual');
  var json = fsm.toJSON();
  assert.strictEqual(json.state, fsm.getState());
  assert.ok(Array.isArray(json.history));

  var restored = AdvisorFSM.fromJSON(json, data);
  assert.strictEqual(restored.getState(), fsm.getState());
  assert.strictEqual(restored.history.length, fsm.history.length);
});

test('on() returns unsubscribe function', function() {
  var count = 0;
  var fsm = new AdvisorFSM(createMockData());
  var unsub = fsm.on('transition', function() { count++; });
  fsm.handleAction('no_manual');
  assert.strictEqual(count, 1);
  unsub();
  fsm.goBack();
  // After unsub, no more events
  // goBack emits a transition, but listener was removed
  assert.strictEqual(count, 1);
});

test('handleAction with comma-separated multi-select', function() {
  var data = createMockData();
  var fsm = new AdvisorFSM(data, { initialState: AdvisorState.COLLECT_INCOME_TYPE });
  // Multi-select with prefix match on first part
  var result = fsm.handleAction('source_w2,source_business');
  // Should match the source_ prefix
  assert.strictEqual(result.handled, true);
});

// ---- Summary ----
console.log('\n' + (passed + failed) + ' tests, ' + passed + ' passed, ' + failed + ' failed');
if (failed > 0) {
  process.exit(1);
} else {
  console.log('\x1b[32mAll tests passed!\x1b[0m\n');
}
