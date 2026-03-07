/**
 * Comprehensive FSM Flow Tests
 *
 * Tests every complex user flow path through the FSM:
 * - State transitions are correct
 * - Data extraction works
 * - SideEffects are returned
 * - Multi-step flows complete without gaps
 *
 * Run: node tests/js/fsm-flow-tests.cjs
 */

var loadModule = require('./load-module.cjs');
var path = require('path');

// Load modules
var statesMod = loadModule(path.resolve(__dirname, '../../src/web/static/js/advisor/fsm/states.js'));
var configMod = loadModule(path.resolve(__dirname, '../../src/web/static/js/advisor/fsm/action-config.js'));
var controllerMod = loadModule(path.resolve(__dirname, '../../src/web/static/js/advisor/fsm/controller.js'));

var AdvisorState = statesMod.AdvisorState || statesMod.AdvisorFSMStates.AdvisorState;
var AdvisorFSM = controllerMod.AdvisorFSM || controllerMod.AdvisorFSMController;

// -------------------------------------------------------------------------
// Test framework
// -------------------------------------------------------------------------
var passed = 0;
var failed = 0;
var totalFlows = 0;

function assert(condition, msg) {
  if (!condition) throw new Error('ASSERT: ' + msg);
}

function testFlow(name, steps) {
  totalFlows++;
  try {
    var data = {
      contact: { name: null, email: null, phone: null, preferred_contact: null },
      tax_profile: { filing_status: null, total_income: null, w2_income: null, business_income: null, investment_income: null, rental_income: null, dependents: null, state: null },
      tax_items: { mortgage_interest: null, property_tax: null, charitable: null, medical: null, student_loan_interest: null, retirement_contributions: null, has_hsa: false, has_529: false },
      business: { type: null, revenue: null, expenses: null, entity_type: null },
      lead_data: { score: 0, complexity: 'simple', estimated_savings: 0, engagement_level: 0, ready_for_cpa: false, urgency: 'normal' },
      documents: [],
      deductions: []
    };

    var fsm = new AdvisorFSM(data, { initialState: steps[0].fromState || AdvisorState.WELCOME });

    for (var i = 0; i < steps.length; i++) {
      var step = steps[i];
      var actionValue = step.action;

      // Override state if specified (for mid-flow jumps)
      if (step.fromState && i > 0) {
        fsm.setState(step.fromState);
      }

      var result = fsm.handleAction(actionValue);

      // Check handled
      assert(result.handled, 'Step ' + (i+1) + ' (' + actionValue + ') was not handled by FSM');

      // Check sideEffect if expected
      if (step.expectedSideEffect) {
        assert(result.sideEffect === step.expectedSideEffect,
          'Step ' + (i+1) + ' (' + actionValue + '): expected sideEffect "' + step.expectedSideEffect + '" but got "' + result.sideEffect + '"');
      }

      // Check state transition if expected
      if (step.expectedState) {
        assert(fsm.getState() === step.expectedState,
          'Step ' + (i+1) + ' (' + actionValue + '): expected state "' + step.expectedState + '" but got "' + fsm.getState() + '"');
      }

      // Check data extraction if expected
      if (step.checkData) {
        step.checkData(data, 'Step ' + (i+1) + ' (' + actionValue + ')');
      }

      // Check userMessage if expected
      if (step.expectedUserMessage) {
        var msg = typeof result.userMessage === 'string' ? result.userMessage : result.userMessage;
        assert(msg === step.expectedUserMessage,
          'Step ' + (i+1) + ' (' + actionValue + '): expected userMessage "' + step.expectedUserMessage + '" but got "' + msg + '"');
      }
    }

    passed++;
    console.log('  \x1b[32m\u2713\x1b[0m ' + name + ' (' + steps.length + ' steps)');
  } catch (e) {
    failed++;
    console.log('  \x1b[31m\u2717\x1b[0m ' + name + ': ' + e.message);
  }
}

// -------------------------------------------------------------------------
// Helper to create a step
// -------------------------------------------------------------------------
function step(action, opts) {
  return Object.assign({ action: action }, opts || {});
}

// =========================================================================
// FLOW GROUP 1: FILING STATUS + DIVORCE PATHS
// =========================================================================
console.log('\n--- Filing Status & Divorce Flows ---');

testFlow('1. Single → divorce question (recent) → year → alimony → amount', [
  step('no_manual', { fromState: AdvisorState.WELCOME, expectedSideEffect: 'show_filing_status_question' }),
  step('filing_single', { fromState: AdvisorState.COLLECT_FILING_STATUS, expectedSideEffect: 'handle_filing_status',
    checkData: function(d, ctx) { assert(d.tax_profile.filing_status === 'Single', ctx + ': filing_status should be Single'); }
  }),
  step('divorce_recent', { expectedSideEffect: 'handle_divorce',
    checkData: function(d, ctx) { assert(d.tax_profile.marital_change === 'recent', ctx + ': marital_change should be recent'); }
  }),
  step('divorce_year_pre2019', { expectedSideEffect: 'handle_divorce_year',
    checkData: function(d, ctx) { assert(d.tax_profile.divorce_year_type === 'pre2019', ctx + ': divorce_year_type'); }
  }),
  step('alimony_paid', { expectedSideEffect: 'handle_alimony',
    checkData: function(d, ctx) { assert(d.tax_profile.alimony_type === 'paid', ctx + ': alimony_type'); }
  }),
  step('alimony_amt_paid_25_50k', { expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('2. Single → divorce (none) → continues', [
  step('filing_single', { fromState: AdvisorState.COLLECT_FILING_STATUS, expectedSideEffect: 'handle_filing_status' }),
  step('divorce_none', { expectedSideEffect: 'handle_divorce',
    checkData: function(d, ctx) { assert(d.tax_profile.divorce_explored === true, ctx + ': divorce_explored'); }
  }),
]);

testFlow('3. Head of Household → divorce (separated) → live apart → 6 months', [
  step('filing_hoh', { fromState: AdvisorState.COLLECT_FILING_STATUS, expectedSideEffect: 'handle_filing_status' }),
  step('divorce_separated', { expectedSideEffect: 'handle_divorce',
    checkData: function(d, ctx) { assert(d.tax_profile.marital_change === 'separated', ctx); }
  }),
  step('separated_live_apart', { expectedSideEffect: 'handle_separated' }),
  step('apart_6months_yes', { expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('4. MFS → divorce (separated) → same home', [
  step('filing_mfs', { fromState: AdvisorState.COLLECT_FILING_STATUS, expectedSideEffect: 'handle_filing_status' }),
  step('divorce_separated', { expectedSideEffect: 'handle_divorce' }),
  step('separated_same_home', { expectedSideEffect: 'handle_separated' }),
]);

testFlow('5. Single → divorce (widowed) → with dependents → QSS', [
  step('filing_single', { fromState: AdvisorState.COLLECT_FILING_STATUS, expectedSideEffect: 'handle_filing_status' }),
  step('divorce_widowed', { expectedSideEffect: 'handle_divorce' }),
  step('widowed_with_deps', { expectedSideEffect: 'handle_widowed',
    checkData: function(d, ctx) { assert(d.tax_profile.qualifies_qss === true, ctx); }
  }),
]);

testFlow('6. Single → divorce (widowed) → no dependents', [
  step('filing_single', { fromState: AdvisorState.COLLECT_FILING_STATUS, expectedSideEffect: 'handle_filing_status' }),
  step('divorce_widowed', { expectedSideEffect: 'handle_divorce' }),
  step('widowed_no_deps', { expectedSideEffect: 'handle_widowed' }),
]);

testFlow('7. Married Filing Jointly → no divorce question → straight to income', [
  step('filing_married', { fromState: AdvisorState.COLLECT_FILING_STATUS, expectedSideEffect: 'handle_filing_status',
    expectedState: AdvisorState.COLLECT_INCOME_TYPE,
    checkData: function(d, ctx) { assert(d.tax_profile.filing_status === 'Married Filing Jointly', ctx); }
  }),
]);

testFlow('8. QSS filing status', [
  step('filing_qss', { fromState: AdvisorState.COLLECT_FILING_STATUS, expectedSideEffect: 'handle_filing_status',
    checkData: function(d, ctx) { assert(d.tax_profile.filing_status === 'Qualifying Surviving Spouse', ctx); }
  }),
]);

testFlow('9. Divorce → post-2019 → custody (primary) → Form 8332', [
  step('filing_single', { fromState: AdvisorState.COLLECT_FILING_STATUS, expectedSideEffect: 'handle_filing_status' }),
  step('divorce_recent', { expectedSideEffect: 'handle_divorce' }),
  step('divorce_year_post2019', { expectedSideEffect: 'handle_divorce_year' }),
  step('custody_primary', { expectedSideEffect: 'handle_custody' }),
  step('form8332_signed', { expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('10. Divorce → post-2019 → custody (shared) → Form 8332 alternate', [
  step('filing_hoh', { fromState: AdvisorState.COLLECT_FILING_STATUS, expectedSideEffect: 'handle_filing_status' }),
  step('divorce_recent', { expectedSideEffect: 'handle_divorce' }),
  step('divorce_year_post2019', { expectedSideEffect: 'handle_divorce_year' }),
  step('custody_shared', { expectedSideEffect: 'handle_custody' }),
  step('form8332_alternate', { expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('11. Divorce → custody (ex has primary)', [
  step('filing_single', { fromState: AdvisorState.COLLECT_FILING_STATUS, expectedSideEffect: 'handle_filing_status' }),
  step('divorce_recent', { expectedSideEffect: 'handle_divorce' }),
  step('divorce_year_post2019', { expectedSideEffect: 'handle_divorce_year' }),
  step('custody_ex', { expectedSideEffect: 'handle_custody' }),
]);

testFlow('12. Divorce → no children', [
  step('filing_single', { fromState: AdvisorState.COLLECT_FILING_STATUS, expectedSideEffect: 'handle_filing_status' }),
  step('divorce_recent', { expectedSideEffect: 'handle_divorce' }),
  step('divorce_year_pre2019', { expectedSideEffect: 'handle_divorce_year' }),
  step('alimony_none', { expectedSideEffect: 'handle_alimony' }),
]);

// =========================================================================
// FLOW GROUP 2: INCOME PATHS
// =========================================================================
console.log('\n--- Income Flows ---');

testFlow('13. Income bracket: $0-$50k', [
  step('income_0_50k', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_income',
    checkData: function(d, ctx) { assert(d.tax_profile.total_income === 35000, ctx + ': income should be 35000'); }
  }),
]);

testFlow('14. Income bracket: $50k-$100k', [
  step('income_50_100k', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_income',
    checkData: function(d, ctx) { assert(d.tax_profile.total_income === 75000, ctx); }
  }),
]);

testFlow('15. Income bracket: $100k-$200k', [
  step('income_100_200k', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_income',
    checkData: function(d, ctx) { assert(d.tax_profile.total_income === 150000, ctx); }
  }),
]);

testFlow('16. Income bracket: $200k-$500k', [
  step('income_200_500k', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_income',
    checkData: function(d, ctx) { assert(d.tax_profile.total_income === 350000, ctx); }
  }),
]);

testFlow('17. Income bracket: $500k+', [
  step('income_500k_plus', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_income',
    checkData: function(d, ctx) { assert(d.tax_profile.total_income === 750000, ctx); }
  }),
]);

testFlow('18. Income custom entry', [
  step('income_custom', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_income' }),
]);

testFlow('19. Dependents: 0', [
  step('dependents_0', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'start_intelligent_questioning',
    checkData: function(d, ctx) { assert(d.tax_profile.dependents === 0, ctx); }
  }),
]);

testFlow('20. Dependents: 2', [
  step('dependents_2', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'start_intelligent_questioning',
    checkData: function(d, ctx) { assert(d.tax_profile.dependents === 2, ctx); }
  }),
]);

testFlow('21. Dependents: 3+', [
  step('dependents_3plus', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'start_intelligent_questioning',
    checkData: function(d, ctx) { assert(d.tax_profile.dependents === 3, ctx); }
  }),
]);

// =========================================================================
// FLOW GROUP 3: INCOME SOURCE + RETIREMENT
// =========================================================================
console.log('\n--- Income Source & Retirement Flows ---');

testFlow('22. Income source: W-2 employee', [
  step('source_w2', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_income_source' }),
]);

testFlow('23. Income source: Self-employed', [
  step('source_self_employed', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_income_source',
    checkData: function(d, ctx) { assert(d.tax_profile.is_self_employed === true, ctx); }
  }),
]);

testFlow('24. Income source: Investments → SS → amount → strategy', [
  step('source_investments', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_income_source' }),
  step('retire_income_ss', { expectedSideEffect: 'handle_retirement_income' }),
  step('ss_amt_35_50k', { expectedSideEffect: 'handle_ss_amount' }),
  step('ss_strategy_yes', { expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('25. Income source: Investments → SS → low amount (no strategy question)', [
  step('source_investments', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_income_source' }),
  step('retire_income_ss', { expectedSideEffect: 'handle_retirement_income' }),
  step('ss_amt_under20k', { expectedSideEffect: 'handle_ss_amount' }),
]);

testFlow('26. Retirement → pension → amount', [
  step('source_investments', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_income_source' }),
  step('retire_income_pension', { expectedSideEffect: 'handle_retirement_income' }),
  step('pension_amt_50_100k', { expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('27. Retirement → IRA → RMD yes → amount', [
  step('source_investments', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_income_source' }),
  step('retire_income_ira', { expectedSideEffect: 'handle_retirement_income' }),
  step('rmd_yes', { expectedSideEffect: 'handle_rmd' }),
  step('rmd_amt_30_75k', { expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('28. Retirement → IRA → RMD soon', [
  step('source_investments', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_income_source' }),
  step('retire_income_ira', { expectedSideEffect: 'handle_retirement_income' }),
  step('rmd_soon', { expectedSideEffect: 'handle_rmd' }),
]);

testFlow('29. Retirement → multiple types', [
  step('source_investments', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_income_source' }),
  step('retire_income_multiple', { expectedSideEffect: 'handle_retirement_income' }),
]);

// =========================================================================
// FLOW GROUP 4: STATE SELECTION + LOCAL TAX
// =========================================================================
console.log('\n--- State & Local Tax Flows ---');

testFlow('30. State: New York → local tax city', [
  step('state_NY', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_state_selection',
    checkData: function(d, ctx) { assert(d.tax_profile.state === 'NY', ctx); }
  }),
  step('localtax_NY_0', { expectedSideEffect: 'handle_local_tax' }),
]);

testFlow('31. State: Ohio → local tax', [
  step('state_OH', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_state_selection' }),
  step('localtax_OH_unsure', { expectedSideEffect: 'handle_local_tax' }),
]);

testFlow('32. State: Florida (no income tax)', [
  step('state_FL', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_state_selection',
    checkData: function(d, ctx) { assert(d.tax_profile.state === 'FL', ctx); }
  }),
]);

testFlow('33. State: Texas (no income tax)', [
  step('state_TX', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_state_selection' }),
]);

testFlow('34. State: California (high tax)', [
  step('state_CA', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_state_selection',
    checkData: function(d, ctx) { assert(d.tax_profile.state === 'CA', ctx); }
  }),
]);

testFlow('35. State: Pennsylvania → local tax city', [
  step('state_PA', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_state_selection' }),
  step('localtax_PA_0', { expectedSideEffect: 'handle_local_tax' }),
]);

testFlow('36. State: Maryland → county', [
  step('state_MD', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_state_selection' }),
  step('localtax_MD_1', { expectedSideEffect: 'handle_local_tax' }),
]);

testFlow('37. State: Other', [
  step('state_other', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_state_selection' }),
]);

// =========================================================================
// FLOW GROUP 5: DEDUCTIONS
// =========================================================================
console.log('\n--- Deduction Flows ---');

testFlow('38. Deduction: mortgage → amount → property tax', [
  step('deduction_mortgage', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_deduction' }),
  step('mortgageamt_15_30k', { expectedSideEffect: 'handle_mortgage_amount' }),
  step('proptaxamt_8_15k', { expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('39. Deduction: charity → amount', [
  step('deduction_charity', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_deduction' }),
  step('charityamt_2500_10k', { expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('40. Deduction: medical → amount', [
  step('deduction_medical', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_deduction' }),
  step('medical_amount_high', { expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('41. Deduction: retirement', [
  step('deduction_retirement', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_deduction' }),
]);

testFlow('42. Deduction: none', [
  step('deduction_none', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_deduction' }),
]);

testFlow('43. Mortgage: under $5k', [
  step('deduction_mortgage', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_deduction' }),
  step('mortgageamt_under5k', { expectedSideEffect: 'handle_mortgage_amount' }),
  step('proptaxamt_under3k', { expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('44. Mortgage: over $30k → property tax over $15k', [
  step('deduction_mortgage', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_deduction' }),
  step('mortgageamt_over30k', { expectedSideEffect: 'handle_mortgage_amount' }),
  step('proptaxamt_over15k', { expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('45. Charity: under $500', [
  step('deduction_charity', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_deduction' }),
  step('charityamt_under500', { expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('46. Charity: over $10k', [
  step('deduction_charity', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_deduction' }),
  step('charityamt_over10k', { expectedSideEffect: 'start_intelligent_questioning' }),
]);

// =========================================================================
// FLOW GROUP 6: BUSINESS FLOWS
// =========================================================================
console.log('\n--- Business Flows ---');

testFlow('47. Business: farm', [
  step('biz_farm', { fromState: AdvisorState.COLLECT_BUSINESS_INCOME, expectedSideEffect: 'handle_farm' }),
]);

testFlow('48. Business: farm (terminal)', [
  step('biz_farm', { fromState: AdvisorState.COLLECT_BUSINESS_INCOME, expectedSideEffect: 'handle_farm' }),
]);

testFlow('49. Business: entity type → S-Corp → salary', [
  step('entity_scorp', { fromState: AdvisorState.COLLECT_BUSINESS_INCOME, expectedSideEffect: 'handle_entity_type' }),
  step('scorp_salary_yes', { expectedSideEffect: 'handle_scorp_salary' }),
]);

testFlow('50. Business: entity type → S-Corp → no salary', [
  step('entity_scorp', { fromState: AdvisorState.COLLECT_BUSINESS_INCOME, expectedSideEffect: 'handle_entity_type' }),
  step('scorp_salary_no', { expectedSideEffect: 'handle_scorp_salary' }),
]);

testFlow('51. Business: entity type → LLC', [
  step('entity_llc', { fromState: AdvisorState.COLLECT_BUSINESS_INCOME, expectedSideEffect: 'handle_entity_type' }),
]);

testFlow('52. Business: revenue → COGS', [
  step('revenue_100_500k', { fromState: AdvisorState.COLLECT_BUSINESS_INCOME, expectedSideEffect: 'handle_revenue' }),
  step('cogs_yes', { expectedSideEffect: 'handle_cogs' }),
]);

testFlow('53. Business: revenue → no COGS', [
  step('revenue_under100k', { fromState: AdvisorState.COLLECT_BUSINESS_INCOME, expectedSideEffect: 'handle_revenue' }),
  step('cogs_no', { expectedSideEffect: 'handle_cogs' }),
]);

testFlow('54. Business: QBI eligible', [
  step('qbi_eligible', { fromState: AdvisorState.COLLECT_BUSINESS_INCOME, expectedSideEffect: 'handle_qbi' }),
]);

testFlow('55. Business: QBI learn more', [
  step('qbi_learn', { fromState: AdvisorState.COLLECT_BUSINESS_INCOME, expectedSideEffect: 'handle_qbi' }),
]);

testFlow('56. Business: expense multi-select', [
  step('bizexp_home_office', { fromState: AdvisorState.COLLECT_BUSINESS_INCOME, expectedSideEffect: 'handle_business_expense' }),
]);

// =========================================================================
// FLOW GROUP 7: RENTAL PROPERTY
// =========================================================================
console.log('\n--- Rental Property Flows ---');

testFlow('57. Rental: has properties → count → depreciation → basis', [
  step('rental_props_1', { fromState: AdvisorState.COLLECT_RENTAL_INCOME, expectedSideEffect: 'handle_rental_props' }),
  step('rental_count_1', { expectedSideEffect: 'handle_rental_count' }),
  step('rental_deprec_yes', { expectedSideEffect: 'handle_rental_depreciation' }),
  step('rental_basis_under200k', { expectedSideEffect: 'handle_rental_basis' }),
]);

testFlow('58. Rental: count 3+ (complexity bump)', [
  step('rental_props_5plus', { fromState: AdvisorState.COLLECT_RENTAL_INCOME, expectedSideEffect: 'handle_rental_props' }),
  step('rental_count_3plus', { expectedSideEffect: 'handle_rental_count' }),
]);

testFlow('59. Rental: no depreciation', [
  step('rental_props_1', { fromState: AdvisorState.COLLECT_RENTAL_INCOME, expectedSideEffect: 'handle_rental_props' }),
  step('rental_count_1', { expectedSideEffect: 'handle_rental_count' }),
  step('rental_deprec_no', { expectedSideEffect: 'handle_rental_depreciation' }),
]);

// =========================================================================
// FLOW GROUP 8: CAPITAL GAINS & LOSSES
// =========================================================================
console.log('\n--- Capital Gains & Loss Flows ---');

testFlow('60. Capital gains: has gains → amount', [
  step('capgain_gains', { fromState: AdvisorState.COLLECT_INVESTMENT_INCOME, expectedSideEffect: 'handle_capgain' }),
  step('capgainamt_10_50k', { expectedSideEffect: 'handle_capgain_amount' }),
]);

testFlow('61. Capital gains: large gains', [
  step('capgain_gains', { fromState: AdvisorState.COLLECT_INVESTMENT_INCOME, expectedSideEffect: 'handle_capgain' }),
  step('capgainamt_over100k', { expectedSideEffect: 'handle_capgain_amount' }),
]);

testFlow('62. Capital losses → amount → wash sale yes', [
  step('capgain_losses', { fromState: AdvisorState.COLLECT_INVESTMENT_INCOME, expectedSideEffect: 'handle_capgain' }),
  step('caplossamt_under3k', { expectedSideEffect: 'handle_cap_loss_amount' }),
  step('washsale_yes', { expectedSideEffect: 'handle_wash_sale' }),
]);

testFlow('63. Capital losses → amount → no wash sale', [
  step('capgain_losses', { fromState: AdvisorState.COLLECT_INVESTMENT_INCOME, expectedSideEffect: 'handle_capgain' }),
  step('caplossamt_3_10k', { expectedSideEffect: 'handle_cap_loss_amount' }),
  step('washsale_no', { expectedSideEffect: 'handle_wash_sale' }),
]);

// =========================================================================
// FLOW GROUP 9: DEPENDENTS
// =========================================================================
console.log('\n--- Dependent Flows ---');

testFlow('64. Dependent: under 17 (CTC eligible)', [
  step('dep_age_under17', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_dep_age' }),
]);

testFlow('65. Dependent: 17-18 → kiddie tax yes', [
  step('dep_age_17_18', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_dep_age' }),
  step('kiddie_yes', { expectedSideEffect: 'handle_kiddie' }),
]);

testFlow('66. Dependent: 17-18 → kiddie tax no', [
  step('dep_age_17_18', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_dep_age' }),
  step('kiddie_no', { expectedSideEffect: 'handle_kiddie' }),
]);

testFlow('67. Dependent: 19-23 college', [
  step('dep_age_19_23', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_dep_age' }),
]);

testFlow('68. Dependent: adult/elderly', [
  step('dep_age_adult', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_dep_age' }),
]);

// =========================================================================
// FLOW GROUP 10: CRYPTO
// =========================================================================
console.log('\n--- Crypto Flows ---');

testFlow('69. Crypto: trading → count → gain amount', [
  step('crypto_trading', { fromState: AdvisorState.COLLECT_INVESTMENT_INCOME, expectedSideEffect: 'handle_crypto' }),
  step('crypto_trades_1_10', { expectedSideEffect: 'handle_crypto_trades' }),
]);

testFlow('70. Crypto: trading → heavy trading', [
  step('crypto_trading', { fromState: AdvisorState.COLLECT_INVESTMENT_INCOME, expectedSideEffect: 'handle_crypto' }),
  step('crypto_trades_100plus', { expectedSideEffect: 'handle_crypto_trades' }),
]);

testFlow('71. Crypto: earning → staking', [
  step('crypto_earning', { fromState: AdvisorState.COLLECT_INVESTMENT_INCOME, expectedSideEffect: 'handle_crypto' }),
  step('crypto_earn_staking', { expectedSideEffect: 'handle_crypto_earn' }),
]);

testFlow('72. Crypto: earning → mining', [
  step('crypto_earning', { fromState: AdvisorState.COLLECT_INVESTMENT_INCOME, expectedSideEffect: 'handle_crypto' }),
  step('crypto_earn_mining', { expectedSideEffect: 'handle_crypto_earn' }),
]);

testFlow('73. Crypto: DeFi', [
  step('crypto_defi', { fromState: AdvisorState.COLLECT_INVESTMENT_INCOME, expectedSideEffect: 'handle_crypto' }),
]);

testFlow('74. Crypto: NFT', [
  step('crypto_nft', { fromState: AdvisorState.COLLECT_INVESTMENT_INCOME, expectedSideEffect: 'handle_crypto' }),
]);

// =========================================================================
// FLOW GROUP 11: STOCK OPTIONS
// =========================================================================
console.log('\n--- Stock Options Flows ---');

testFlow('75. ISO → exercised → spread (AMT trigger)', [
  step('options_iso', { fromState: AdvisorState.COLLECT_INVESTMENT_INCOME, expectedSideEffect: 'handle_options' }),
  step('iso_exercised_yes', { expectedSideEffect: 'handle_iso_exercise' }),
  step('iso_spread_over100k', { expectedSideEffect: 'handle_iso_spread' }),
]);

testFlow('76. ISO → not exercised', [
  step('options_iso', { fromState: AdvisorState.COLLECT_INVESTMENT_INCOME, expectedSideEffect: 'handle_options' }),
  step('iso_exercised_no', { expectedSideEffect: 'handle_iso_exercise' }),
]);

testFlow('77. NSO options', [
  step('options_nso', { fromState: AdvisorState.COLLECT_INVESTMENT_INCOME, expectedSideEffect: 'handle_options' }),
]);

testFlow('78. RSU options', [
  step('options_rsu', { fromState: AdvisorState.COLLECT_INVESTMENT_INCOME, expectedSideEffect: 'handle_options' }),
]);

testFlow('79. ESPP options', [
  step('options_espp', { fromState: AdvisorState.COLLECT_INVESTMENT_INCOME, expectedSideEffect: 'handle_options' }),
]);

// =========================================================================
// FLOW GROUP 12: ESTIMATED PAYMENTS
// =========================================================================
console.log('\n--- Estimated Payments ---');

testFlow('80. Estimated payments: yes', [
  step('estimated_yes', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_estimated_payments' }),
]);

testFlow('81. Estimated payments: no', [
  step('estimated_no', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_estimated_payments' }),
]);

// =========================================================================
// FLOW GROUP 13: FOREIGN INCOME
// =========================================================================
console.log('\n--- Foreign Income Flows ---');

testFlow('82. Foreign: earned income → FEIE qualified', [
  step('foreign_earned', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_foreign' }),
  step('foreign_type_wages', { expectedSideEffect: 'handle_foreign_income_type' }),
  step('feie_qualified', { expectedSideEffect: 'handle_feie' }),
  step('foreign_earned_under100k', { expectedSideEffect: 'handle_foreign_earned' }),
]);

testFlow('83. Foreign: earned income → FEIE not qualified', [
  step('foreign_earned', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_foreign' }),
  step('foreign_type_wages', { expectedSideEffect: 'handle_foreign_income_type' }),
  step('feie_not_qualified', { expectedSideEffect: 'handle_feie' }),
]);

testFlow('84. Foreign: investment → FTC → paid taxes', [
  step('foreign_investment', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_foreign' }),
  step('ftc_paid_taxes', { expectedSideEffect: 'handle_ftc' }),
]);

testFlow('85. Foreign: investment → FTC → no taxes', [
  step('foreign_investment', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_foreign' }),
  step('ftc_no_taxes', { expectedSideEffect: 'handle_ftc' }),
]);

testFlow('86. Foreign: bank accounts', [
  step('foreign_bank', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_foreign' }),
]);

// =========================================================================
// FLOW GROUP 14: MULTI-STATE
// =========================================================================
console.log('\n--- Multi-State Flows ---');

testFlow('87. Multi-state: remote worker', [
  step('multistate_remote', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_multistate' }),
]);

testFlow('88. Multi-state: relocated', [
  step('multistate_relocated', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_multistate' }),
]);

testFlow('89. Multi-state: commuter', [
  step('multistate_commuter', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_multistate' }),
]);

// =========================================================================
// FLOW GROUP 15: EDUCATION
// =========================================================================
console.log('\n--- Education Flows ---');

testFlow('90. Education: AOTC credit', [
  step('educredit_aotc', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_educredit' }),
]);

testFlow('91. Education: LLC credit', [
  step('educredit_llc', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_educredit' }),
]);

testFlow('92. Education: 529 plan', [
  step('edu_529', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_edu' }),
]);

testFlow('93. Education: student loan', [
  step('edu_student_loan', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_edu' }),
]);

// =========================================================================
// FLOW GROUP 16: FOCUS AREAS (Smart Intake)
// =========================================================================
console.log('\n--- Focus Area Flows ---');

testFlow('94. Focus: homeowner', [
  step('focus_homeowner', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_focus' }),
  step('homeowner_mortgage_yes', { expectedSideEffect: 'handle_homeowner' }),
]);

testFlow('95. Focus: medical expenses (high)', [
  step('focus_medical', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_focus' }),
  step('medical_high', { expectedSideEffect: 'handle_medical_focus' }),
]);

testFlow('96. Focus: investments', [
  step('focus_investments', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_focus' }),
  step('inv_focus_stocks', { expectedSideEffect: 'handle_inv_focus' }),
]);

testFlow('97. Focus: business (sole prop)', [
  step('focus_business', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_focus' }),
  step('biz_sole', { expectedSideEffect: 'handle_biz_focus' }),
]);

testFlow('98. Focus: business (LLC)', [
  step('focus_business', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_focus' }),
  step('biz_llc', { expectedSideEffect: 'handle_biz_focus' }),
]);

// =========================================================================
// FLOW GROUP 17: DEDUCTION/CREDIT FLOW (Guided)
// =========================================================================
console.log('\n--- Guided Deduction/Credit Flows ---');

testFlow('99. Deduction flow: has deduction → amount → next → done', [
  step('deduct_mortgage', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_deduct_flow' }),
  step('has_deduction_yes', { expectedSideEffect: 'handle_has_deduction' }),
  step('amount_moderate', { expectedSideEffect: 'handle_amount_selection' }),
  step('deduct_skip', { expectedSideEffect: 'handle_deduct_flow' }),
  step('deductions_done', { expectedSideEffect: 'handle_deductions_done' }),
]);

testFlow('100. Credit flow', [
  step('credit_education', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_credit_flow' }),
]);

// =========================================================================
// FLOW GROUP 18: REPORT & CPA
// =========================================================================
console.log('\n--- Report & CPA Flows ---');

testFlow('101. Generate report', [
  step('generate_report', { fromState: AdvisorState.REVIEW_SUMMARY, expectedSideEffect: 'generate_report' }),
]);

testFlow('102. View report', [
  step('view_report', { fromState: AdvisorState.GENERATE_REPORT, expectedSideEffect: 'handle_view_report' }),
]);

testFlow('103. Download report', [
  step('download_report', { fromState: AdvisorState.GENERATE_REPORT, expectedSideEffect: 'handle_download_report' }),
]);

testFlow('104. Email report', [
  step('email_report', { fromState: AdvisorState.GENERATE_REPORT, expectedSideEffect: 'handle_email_report' }),
]);

testFlow('105. Schedule CPA', [
  step('schedule_consult', { fromState: AdvisorState.CPA_HANDOFF, expectedSideEffect: 'schedule_cpa' }),
]);

testFlow('106. Email CPA', [
  step('email_only', { fromState: AdvisorState.CPA_HANDOFF, expectedSideEffect: 'email_cpa' }),
]);

// =========================================================================
// FLOW GROUP 19: UI MODALS & SPECIAL ACTIONS
// =========================================================================
console.log('\n--- UI Modals & Special Actions ---');

testFlow('107. Enter name', [
  step('enter_name', { fromState: AdvisorState.COLLECT_NAME, expectedSideEffect: 'show_name_input' }),
]);

testFlow('108. Skip name → proceed', [
  step('skip_name', { fromState: AdvisorState.COLLECT_NAME, expectedSideEffect: 'proceed_to_data_gathering' }),
]);

testFlow('109. Enter email', [
  step('enter_email', { fromState: AdvisorState.COLLECT_NAME, expectedSideEffect: 'show_email_input' }),
]);

testFlow('110. Skip email → proceed', [
  step('skip_email', { fromState: AdvisorState.COLLECT_NAME, expectedSideEffect: 'proceed_to_data_gathering' }),
]);

testFlow('111. Upload docs (qualified)', [
  step('upload_docs_qualified', { fromState: AdvisorState.WELCOME, expectedSideEffect: 'show_upload_ui' }),
]);

testFlow('112. Conversational (qualified)', [
  step('conversational_qualified', { fromState: AdvisorState.WELCOME, expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('113. Yes upload → show smart upload', [
  step('yes_upload', { fromState: AdvisorState.WELCOME, expectedSideEffect: 'show_smart_upload' }),
]);

testFlow('114. No manual → filing status question', [
  step('no_manual', { fromState: AdvisorState.WELCOME, expectedSideEffect: 'show_filing_status_question' }),
]);

testFlow('115. What docs → doc help', [
  step('what_docs', { fromState: AdvisorState.WELCOME, expectedSideEffect: 'show_doc_help' }),
]);

testFlow('116. Upload W-2 → trigger file input', [
  step('upload_w2', { fromState: AdvisorState.DOCUMENT_UPLOAD, expectedSideEffect: 'trigger_file_input' }),
]);

testFlow('117. Upload 1099 → trigger file input', [
  step('upload_1099', { fromState: AdvisorState.DOCUMENT_UPLOAD, expectedSideEffect: 'trigger_file_input' }),
]);

testFlow('118. Unlock strategies', [
  step('unlock_strategies', { fromState: AdvisorState.REVIEW_SUMMARY, expectedSideEffect: 'unlock_strategies' }),
]);

testFlow('119. Skip multi-select', [
  step('skip_multi_select', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'process_ai' }),
]);

testFlow('120. Show edit options', [
  step('edit_profile', { fromState: AdvisorState.REVIEW_SUMMARY, expectedSideEffect: 'show_edit_options' }),
]);

// =========================================================================
// FLOW GROUP 20: STRATEGY NAVIGATION
// =========================================================================
console.log('\n--- Strategy Navigation ---');

testFlow('121. Explore strategies → next → next → previous → summary', [
  step('explore_strategies', { fromState: AdvisorState.REVIEW_SUMMARY, expectedSideEffect: 'explore_strategies' }),
  step('next_strategy', { expectedSideEffect: 'next_strategy' }),
  step('next_strategy', { expectedSideEffect: 'next_strategy' }),
  step('previous_strategy', { expectedSideEffect: 'previous_strategy' }),
  step('finish_strategies', { expectedSideEffect: 'show_strategy_summary' }),
]);

testFlow('122. Show all strategies', [
  step('show_all_strategies', { fromState: AdvisorState.REVIEW_SUMMARY, expectedSideEffect: 'show_all_strategies' }),
]);

// =========================================================================
// FLOW GROUP 21: CONTINUE-TO-DEDUCTIONS TRANSITIONS
// =========================================================================
console.log('\n--- Phase Transitions ---');

testFlow('123. Continue to deductions', [
  step('medical_amt_skip', { fromState: AdvisorState.COLLECT_W2, expectedSideEffect: 'continue_to_deductions' }),
]);

testFlow('124. Perform tax calculation', [
  step('run_full_analysis', { fromState: AdvisorState.REVIEW_SUMMARY, expectedSideEffect: 'perform_tax_calculation' }),
]);

testFlow('125. Analyze deductions', [
  step('analyze_deductions', { fromState: AdvisorState.REVIEW_SUMMARY, expectedSideEffect: 'analyze_deductions' }),
]);

testFlow('126. Request CPA connection', [
  step('request_cpa_early', { fromState: AdvisorState.CPA_HANDOFF, expectedSideEffect: 'request_cpa_connection' }),
]);

// =========================================================================
// FLOW GROUP 22: BUSINESS TYPE VARIANTS
// =========================================================================
console.log('\n--- Business Type Variants ---');

testFlow('127. Professional services', [
  step('biz_professional', { fromState: AdvisorState.COLLECT_BUSINESS_INCOME, expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('128. Retail / E-commerce', [
  step('biz_retail', { fromState: AdvisorState.COLLECT_BUSINESS_INCOME, expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('129. Real estate business', [
  step('biz_realestate', { fromState: AdvisorState.COLLECT_BUSINESS_INCOME, expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('130. Tech / Software', [
  step('biz_tech', { fromState: AdvisorState.COLLECT_BUSINESS_INCOME, expectedSideEffect: 'start_intelligent_questioning' }),
]);

// =========================================================================
// FLOW GROUP 23: ALIMONY AMOUNT VARIANTS
// =========================================================================
console.log('\n--- Alimony Amount Variants ---');

testFlow('131. Alimony paid: under $10k', [
  step('alimony_amt_paid_under10k', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('132. Alimony received: $25-$50k', [
  step('alimony_amt_received_25_50k', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('133. Alimony paid: over $50k', [
  step('alimony_amt_paid_over50k', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'start_intelligent_questioning' }),
]);

// =========================================================================
// FLOW GROUP 24: FULL END-TO-END JOURNEYS
// =========================================================================
console.log('\n--- Full End-to-End Journeys ---');

testFlow('134. Complete simple journey: name → filing → income → state → deductions → report', [
  step('enter_name', { fromState: AdvisorState.COLLECT_NAME, expectedSideEffect: 'show_name_input' }),
  step('filing_married', { fromState: AdvisorState.COLLECT_FILING_STATUS, expectedSideEffect: 'handle_filing_status',
    expectedState: AdvisorState.COLLECT_INCOME_TYPE }),
  step('income_100_200k', { expectedSideEffect: 'handle_income',
    checkData: function(d) { assert(d.tax_profile.total_income === 150000); } }),
  step('state_TX', { expectedSideEffect: 'handle_state_selection' }),
  step('deduction_mortgage', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_deduction' }),
  step('mortgageamt_15_30k', { expectedSideEffect: 'handle_mortgage_amount' }),
  step('proptaxamt_8_15k', { expectedSideEffect: 'start_intelligent_questioning' }),
  step('generate_report', { fromState: AdvisorState.REVIEW_SUMMARY, expectedSideEffect: 'generate_report' }),
]);

testFlow('135. Complex journey: single→divorce→alimony→income→crypto→report', [
  step('no_manual', { fromState: AdvisorState.WELCOME, expectedSideEffect: 'show_filing_status_question' }),
  step('filing_single', { fromState: AdvisorState.COLLECT_FILING_STATUS, expectedSideEffect: 'handle_filing_status' }),
  step('divorce_recent', { expectedSideEffect: 'handle_divorce' }),
  step('divorce_year_pre2019', { expectedSideEffect: 'handle_divorce_year' }),
  step('alimony_paid', { expectedSideEffect: 'handle_alimony' }),
  step('alimony_amt_paid_10_25k', { expectedSideEffect: 'start_intelligent_questioning' }),
  step('income_200_500k', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_income' }),
  step('crypto_trading', { fromState: AdvisorState.COLLECT_INVESTMENT_INCOME, expectedSideEffect: 'handle_crypto' }),
  step('crypto_trades_10_50', { expectedSideEffect: 'handle_crypto_trades' }),
  step('generate_report', { fromState: AdvisorState.REVIEW_SUMMARY, expectedSideEffect: 'generate_report' }),
]);

testFlow('136. Complex journey: HOH→widowed→QSS→retirement→SS→RMD→foreign→report', [
  step('filing_hoh', { fromState: AdvisorState.COLLECT_FILING_STATUS, expectedSideEffect: 'handle_filing_status' }),
  step('divorce_widowed', { expectedSideEffect: 'handle_divorce' }),
  step('widowed_with_deps', { expectedSideEffect: 'handle_widowed' }),
  step('source_investments', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_income_source' }),
  step('retire_income_ira', { expectedSideEffect: 'handle_retirement_income' }),
  step('rmd_yes', { expectedSideEffect: 'handle_rmd' }),
  step('rmd_amt_over75k', { expectedSideEffect: 'start_intelligent_questioning' }),
  step('foreign_earned', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_foreign' }),
  step('foreign_type_wages', { expectedSideEffect: 'handle_foreign_income_type' }),
  step('feie_qualified', { expectedSideEffect: 'handle_feie' }),
  step('foreign_earned_over100k', { expectedSideEffect: 'handle_foreign_earned' }),
]);

testFlow('137. Business owner journey: S-Corp→salary→revenue→COGS→QBI→expenses', [
  step('entity_scorp', { fromState: AdvisorState.COLLECT_BUSINESS_INCOME, expectedSideEffect: 'handle_entity_type' }),
  step('scorp_salary_yes', { expectedSideEffect: 'handle_scorp_salary' }),
  step('revenue_500k_plus', { fromState: AdvisorState.COLLECT_BUSINESS_INCOME, expectedSideEffect: 'handle_revenue' }),
  step('cogs_yes', { expectedSideEffect: 'handle_cogs' }),
  step('qbi_eligible', { fromState: AdvisorState.COLLECT_BUSINESS_INCOME, expectedSideEffect: 'handle_qbi' }),
  step('bizexp_home_office', { fromState: AdvisorState.COLLECT_BUSINESS_INCOME, expectedSideEffect: 'handle_business_expense' }),
]);

testFlow('138. Stock options journey: ISO→exercise→high spread (AMT warning)', [
  step('options_iso', { fromState: AdvisorState.COLLECT_INVESTMENT_INCOME, expectedSideEffect: 'handle_options' }),
  step('iso_exercised_yes', { expectedSideEffect: 'handle_iso_exercise' }),
  step('iso_spread_over100k', { expectedSideEffect: 'handle_iso_spread' }),
]);

testFlow('139. Multi-state + local tax: NY → NYC → deductions → charity', [
  step('state_NY', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_state_selection' }),
  step('localtax_NY_0', { expectedSideEffect: 'handle_local_tax' }),
  step('multistate_commuter', { fromState: AdvisorState.COLLECT_INCOME_TYPE, expectedSideEffect: 'handle_multistate' }),
  step('deduction_charity', { fromState: AdvisorState.COLLECT_DEDUCTIONS, expectedSideEffect: 'handle_deduction' }),
  step('charityamt_over10k', { expectedSideEffect: 'start_intelligent_questioning' }),
]);

testFlow('140. Upload-first journey: docs → upload W-2 → conversational fallback', [
  step('yes_upload', { fromState: AdvisorState.WELCOME, expectedSideEffect: 'show_smart_upload' }),
  step('upload_w2', { fromState: AdvisorState.DOCUMENT_UPLOAD, expectedSideEffect: 'trigger_file_input' }),
  step('no_manual', { fromState: AdvisorState.WELCOME, expectedSideEffect: 'show_filing_status_question' }),
]);

// =========================================================================
// SUMMARY
// =========================================================================
console.log('\n========================================');
console.log(totalFlows + ' flows tested, ' + passed + ' passed, ' + failed + ' failed');
if (failed === 0) {
  console.log('\x1b[32mAll flows passed!\x1b[0m');
} else {
  console.log('\x1b[31m' + failed + ' flows FAILED\x1b[0m');
  process.exit(1);
}
