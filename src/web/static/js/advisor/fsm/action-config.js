/**
 * Action Configuration Table
 *
 * Replaces the monolithic handleQuickAction() if-else chain with a declarative config.
 *
 * Each entry defines:
 * - action: The value from the quick-action button click (exact match)
 * - prefix: Alternative to action — matches values starting with this string
 * - fromStates: Array of states this action is valid in (or '*' for any)
 * - toState: State to transition to after handling (null = stay in current state)
 * - extract: Function(value, data) that extracts/sets data from the action
 * - userMessage: What to show as the user's message in chat (string or function)
 * - sideEffect: Optional function(value, data, ctx) for UI effects (showTyping, addMessage, etc.)
 *               When present, the FSM bridge calls this instead of processAIResponse.
 *
 * Entries are populated in phases:
 * - Phase 1 (this file): Structure + initial entries to prove pattern
 * - Task 7: personal_info actions
 * - Task 8: income/deduction actions
 * - Task 9: special/remaining actions
 */

// Use window globals since this is a script-tag environment (no ES modules)
var AdvisorState = (typeof window !== 'undefined' && window.AdvisorFSMStates)
  ? window.AdvisorFSMStates.AdvisorState
  : (typeof require !== 'undefined' ? require('./states.js').AdvisorState : {});

var ACTION_CONFIG = [
  // =================================================================
  // SPECIAL ACTIONS (any state)
  // =================================================================
  {
    action: 'unlock_strategies',
    fromStates: '*',
    toState: null,
    extract: null,
    userMessage: null,  // handled entirely by sideEffect
    sideEffect: 'unlock_strategies',  // maps to window.unlockPremiumStrategies()
  },
  {
    action: 'skip_multi_select',
    fromStates: '*',
    toState: null,
    extract: null,
    userMessage: 'None / Skip',
    sideEffect: 'process_ai',  // process via AI with value 'none'
  },

  // =================================================================
  // LEAD CAPTURE — Name & Email (personal_info phase)
  // Populated in Task 7
  // =================================================================
  {
    action: 'enter_name',
    fromStates: [AdvisorState.WELCOME, AdvisorState.COLLECT_NAME],
    toState: AdvisorState.COLLECT_NAME,
    extract: null,
    userMessage: "I'll enter my name",
    sideEffect: 'show_name_input',
  },
  {
    action: 'skip_name',
    fromStates: [AdvisorState.WELCOME, AdvisorState.COLLECT_NAME],
    toState: AdvisorState.COLLECT_FILING_STATUS,
    extract: function(val, data) { data.lead_data.score += 5; },
    userMessage: "I'll skip for now",
    sideEffect: 'proceed_to_data_gathering',
  },
  {
    action: 'enter_email',
    fromStates: [AdvisorState.COLLECT_NAME, AdvisorState.COLLECT_FILING_STATUS],
    toState: AdvisorState.COLLECT_NAME,
    extract: null,
    userMessage: "I'll enter my email",
    sideEffect: 'show_email_input',
  },
  {
    action: 'skip_email',
    fromStates: [AdvisorState.COLLECT_NAME, AdvisorState.COLLECT_FILING_STATUS],
    toState: AdvisorState.COLLECT_FILING_STATUS,
    extract: function(val, data) { data.lead_data.score += 10; },
    userMessage: "I'll skip for now",
    sideEffect: 'proceed_to_data_gathering',
  },

  // =================================================================
  // QUALIFICATION MODE (personal_info phase)
  // =================================================================
  {
    action: 'upload_docs_qualified',
    fromStates: '*',
    toState: AdvisorState.DOCUMENT_UPLOAD,
    extract: null,
    userMessage: 'Upload Docs',
    sideEffect: 'show_upload_ui',
  },
  {
    action: 'conversational_qualified',
    fromStates: '*',
    toState: AdvisorState.COLLECT_FILING_STATUS,
    extract: null,
    userMessage: 'Conversational',
    sideEffect: 'start_intelligent_questioning',
  },
  {
    action: 'hybrid_qualified',
    fromStates: '*',
    toState: AdvisorState.DOCUMENT_UPLOAD,
    extract: null,
    userMessage: 'Hybrid',
    sideEffect: 'show_upload_ui',
  },

  // =================================================================
  // DOCUMENT UPLOAD
  // =================================================================
  {
    action: 'yes_upload',
    fromStates: '*',
    toState: AdvisorState.DOCUMENT_UPLOAD,
    extract: null,
    userMessage: 'Upload my documents',
    sideEffect: 'show_smart_upload',
  },
  {
    action: 'no_manual',
    fromStates: '*',
    toState: AdvisorState.COLLECT_FILING_STATUS,
    extract: null,
    userMessage: "No, I'd prefer to discuss my situation first",
    sideEffect: 'show_filing_status_question',
  },
  {
    action: 'what_docs',
    fromStates: '*',
    toState: null,
    extract: null,
    userMessage: 'What kind of documents would help?',
    sideEffect: 'show_doc_help',
  },
  {
    action: 'upload_w2',
    fromStates: '*',
    toState: AdvisorState.DOCUMENT_UPLOAD,
    extract: null,
    userMessage: 'I want to upload a document',
    sideEffect: 'trigger_file_input',
  },
  {
    action: 'upload_1099',
    fromStates: '*',
    toState: AdvisorState.DOCUMENT_UPLOAD,
    extract: null,
    userMessage: 'I want to upload a document',
    sideEffect: 'trigger_file_input',
  },
  {
    action: 'upload_other',
    fromStates: '*',
    toState: AdvisorState.DOCUMENT_UPLOAD,
    extract: null,
    userMessage: 'I want to upload a document',
    sideEffect: 'trigger_file_input',
  },

  // =================================================================
  // FILING STATUS (prefix-based: filing_*)
  // Populated fully in Task 7
  // =================================================================
  {
    prefix: 'filing_',
    fromStates: [AdvisorState.COLLECT_FILING_STATUS, AdvisorState.WELCOME],
    toState: AdvisorState.COLLECT_INCOME_TYPE,
    extract: function(val, data) {
      var status = val.replace('filing_', '');
      var statusMap = {
        'single': 'Single',
        'married': 'Married Filing Jointly',
        'hoh': 'Head of Household',
        'mfs': 'Married Filing Separately',
        'qss': 'Qualifying Surviving Spouse'
      };
      data.tax_profile.filing_status = statusMap[status] || status;
      data.lead_data.score += 10;
    },
    userMessage: function(val) {
      var status = val.replace('filing_', '');
      var statusMap = {
        'single': 'Single',
        'married': 'Married Filing Jointly',
        'hoh': 'Head of Household',
        'mfs': 'Married Filing Separately',
        'qss': 'Qualifying Surviving Spouse'
      };
      return statusMap[status] || status;
    },
    sideEffect: 'handle_filing_status',
  },

  // =================================================================
  // DIVORCE SCENARIO (prefix-based: divorce_*)
  // Populated fully in Task 7
  // =================================================================
  {
    prefix: 'divorce_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var type = val.replace('divorce_', '');
      data.tax_profile.divorce_explored = true;
      data.tax_profile.marital_change = type;
    },
    userMessage: function(val) {
      var type = val.replace('divorce_', '');
      var labels = { 'recent': 'Recently divorced', 'separated': 'Legally separated', 'widowed': 'Widowed this year', 'none': 'No change' };
      return labels[type] || type;
    },
    sideEffect: 'handle_divorce',
  },

  // =================================================================
  // INCOME (prefix-based: income_*)
  // Populated fully in Task 8
  // =================================================================
  {
    prefix: 'income_',
    fromStates: [AdvisorState.COLLECT_INCOME_TYPE, AdvisorState.COLLECT_W2],
    toState: AdvisorState.COLLECT_DEDUCTIONS,
    extract: function(val, data) {
      var incomeAmounts = {
        'income_0_50k': 35000,
        'income_50_100k': 75000,
        'income_100_200k': 150000,
        'income_200_500k': 350000,
        'income_500k_plus': 750000
      };
      if (val !== 'income_custom' && incomeAmounts[val]) {
        data.tax_profile.total_income = incomeAmounts[val];
        data.tax_profile.w2_income = incomeAmounts[val];
        data.lead_data.score += 15;
      }
    },
    userMessage: function(val) {
      var labels = {
        'income_custom': "I'll type my exact income",
        'income_0_50k': '$0 - $50,000',
        'income_50_100k': '$50,000 - $100,000',
        'income_100_200k': '$100,000 - $200,000',
        'income_200_500k': '$200,000 - $500,000',
        'income_500k_plus': 'Over $500,000'
      };
      return labels[val] || val;
    },
    sideEffect: 'handle_income',
  },

  // =================================================================
  // DEDUCTIONS (prefix-based: deduction_*)
  // Populated fully in Task 8
  // =================================================================
  {
    prefix: 'deduction_',
    fromStates: [AdvisorState.COLLECT_DEDUCTIONS],
    toState: null,
    extract: function(val, data) {
      var deduction = val.replace('deduction_', '');
      if (deduction === 'none') {
        data.tax_profile.deductions_explored = true;
      } else {
        data.deductions = data.deductions || [];
        if (data.deductions.indexOf(deduction) === -1) {
          data.deductions.push(deduction);
          data.lead_data.score += 5;
        }
      }
    },
    userMessage: function(val) {
      var deduction = val.replace('deduction_', '');
      var labels = { 'mortgage': 'Own a home', 'charity': 'Make charitable donations', 'medical': 'Have high medical expenses', 'retirement': 'Contribute to retirement', 'none': 'None of these apply' };
      return labels[deduction] || deduction;
    },
    sideEffect: 'handle_deduction',
  },

  // =================================================================
  // REVIEW & REPORT ACTIONS
  // =================================================================
  {
    action: 'run_full_analysis',
    fromStates: '*',
    toState: AdvisorState.REVIEW_SUMMARY,
    extract: null,
    userMessage: 'Run full analysis',
    sideEffect: 'perform_tax_calculation',
  },
  {
    action: 'edit_profile',
    fromStates: '*',
    toState: AdvisorState.EDIT_PROFILE,
    extract: function(val, data) {
      data.tax_profile.deductions_explored = false;
      data.tax_profile.goals_explored = false;
    },
    userMessage: 'I want to edit my information',
    sideEffect: 'show_edit_options',
  },
  {
    action: 'edit_filing',
    fromStates: [AdvisorState.EDIT_PROFILE],
    toState: AdvisorState.COLLECT_FILING_STATUS,
    extract: function(val, data) { data.tax_profile.filing_status = null; },
    userMessage: null,
    sideEffect: 'start_intelligent_questioning',
  },
  {
    action: 'edit_income',
    fromStates: [AdvisorState.EDIT_PROFILE],
    toState: AdvisorState.COLLECT_INCOME_TYPE,
    extract: function(val, data) { data.tax_profile.total_income = null; },
    userMessage: null,
    sideEffect: 'start_intelligent_questioning',
  },
  {
    action: 'edit_state',
    fromStates: [AdvisorState.EDIT_PROFILE],
    toState: AdvisorState.COLLECT_FILING_STATUS,
    extract: function(val, data) { data.tax_profile.state = null; },
    userMessage: null,
    sideEffect: 'start_intelligent_questioning',
  },
  {
    action: 'generate_report',
    fromStates: '*',
    toState: AdvisorState.GENERATE_REPORT,
    extract: null,
    userMessage: 'Yes, please generate my comprehensive tax advisory report',
    sideEffect: 'generate_report',
  },
  {
    action: 'generate_report_early',
    fromStates: '*',
    toState: AdvisorState.GENERATE_REPORT,
    extract: null,
    userMessage: 'Generate my full report',
    sideEffect: 'generate_report',
  },

  // =================================================================
  // STRATEGY REVIEW
  // =================================================================
  {
    action: 'analyze_deductions',
    fromStates: '*',
    toState: null,
    extract: null,
    userMessage: 'Yes, find more savings',
    sideEffect: 'analyze_deductions',
  },
  {
    action: 'show_all_strategies',
    fromStates: '*',
    toState: null,
    extract: null,
    userMessage: 'Show me all strategies',
    sideEffect: 'show_all_strategies',
  },
  {
    action: 'explore_strategies',
    fromStates: '*',
    toState: null,
    extract: null,
    userMessage: 'Yes, show me the strategies',
    sideEffect: 'explore_strategies',
  },
  {
    action: 'quick_summary',
    fromStates: '*',
    toState: null,
    extract: null,
    userMessage: 'Skip to summary',
    sideEffect: 'show_strategy_summary',
  },
  {
    action: 'next_strategy',
    fromStates: '*',
    toState: null,
    extract: null,
    userMessage: null,
    sideEffect: 'next_strategy',
  },
  {
    action: 'previous_strategy',
    fromStates: '*',
    toState: null,
    extract: null,
    userMessage: null,
    sideEffect: 'previous_strategy',
  },
  {
    action: 'finish_strategies',
    fromStates: '*',
    toState: null,
    extract: null,
    userMessage: "I've reviewed all strategies",
    sideEffect: 'show_strategy_summary',
  },

  // =================================================================
  // CPA HANDOFF
  // =================================================================
  {
    action: 'schedule_time',
    fromStates: '*',
    toState: AdvisorState.CPA_HANDOFF,
    extract: null,
    userMessage: 'Schedule a consultation',
    sideEffect: 'schedule_cpa',
  },
  {
    action: 'email_only',
    fromStates: '*',
    toState: null,
    extract: null,
    userMessage: 'Just email me',
    sideEffect: 'email_cpa',
  },
  {
    action: 'request_cpa_early',
    fromStates: '*',
    toState: AdvisorState.CPA_HANDOFF,
    extract: null,
    userMessage: 'I want to speak with a CPA',
    sideEffect: 'request_cpa_connection',
  },

  // =================================================================
  // More prefix-based handlers will be added in Tasks 7-9:
  // - divorce_year_*, alimony_*, alimony_amt_*, custody_*, form8332_*
  // - separated_*, apart_6months_*, widowed_*
  // - dependents_*, state_*, localtax_*, source_*
  // - retire_income_*, ss_amt_*, pension_amt_*, rmd_*, rmd_amt_*
  // - mortgageamt_*, proptaxamt_*, charityamt_*, medical_amount_*
  // - goal_*, withhold_*, prior_*, spouse_*
  // - biz_*, entity_*, revenue_*, scorp_*, netincome_*, qbi_*
  // - farm_type_*, farm_income_*, farm_exp_*
  // - bizexp_*, homeoffice_*, vehicle_*, equipment_*, marketing_*
  // - multi_*, invest_*, rental_*, rental_deprec_*, rental_basis_*, rental_exp_*
  // - capgain_*, capgainamt_*, caplossamt_*, washsale_*
  // - dep_age_*, kiddie_*, childcare_*
  // - retire_*, 401k_*, hsa_*, hsaamt_*, studentloan_*, studentloanamt_*
  // - energy_*, event_*, adv_*, crypto_*, options_*, iso_*, amt_estimated_*
  // - nso_value_*, rsu_value_*, estimated_*, estamt_*
  // - foreign_*, feie_*, foreign_earned_*, foreign_housing_*
  // - ftc_*, fbar_*, multistate_*, moved_*, workdays_*, remote_states_*
  // - status_*, focus_*, homeowner_*, rental_props_*, rental_income_*
  // - edu_*, student_loan_*, college_students_*, edu_expense_*
  // - medical_*, hsa_*, medical_amt_*, inv_*, trad_contrib_*, roth_contrib_*
  // - biz_sole/llc/corp/side, bizinc_*, deduct_*, credit_*
  // - has_*, amount_*, deduction_next, deductions_done
  // - educredit_*, students_*, selfed_*, 529amt_*, itemize_*
  // - cogs_*, cogs_pct_*, ss_strategy_*, medical_amt_skip
  // =================================================================
];

/**
 * Build a lookup map for O(1) action resolution.
 * Exact-match actions go into 'exact' map; prefix-based go into 'prefixes' array.
 * @param {Array} config
 * @returns {{ exact: Map, prefixes: Array }}
 */
function buildActionIndex(config) {
  var exact = {};
  var prefixes = [];

  for (var i = 0; i < config.length; i++) {
    var entry = config[i];
    if (entry.action) {
      if (!exact[entry.action]) {
        exact[entry.action] = [];
      }
      exact[entry.action].push(entry);
    } else if (entry.prefix) {
      prefixes.push(entry);
    }
  }

  return { exact: exact, prefixes: prefixes };
}

/**
 * Find the matching config entry for a given action value and current state.
 * @param {{ exact: Object, prefixes: Array }} index
 * @param {string} actionValue
 * @param {string} currentState
 * @returns {Object|null}
 */
function findActionEntry(index, actionValue, currentState) {
  // Check exact matches first
  var candidates = index.exact[actionValue] || [];
  for (var i = 0; i < candidates.length; i++) {
    var c = candidates[i];
    if (c.fromStates === '*' || c.fromStates.indexOf(currentState) !== -1) {
      return c;
    }
  }

  // Check prefix matches
  for (var j = 0; j < index.prefixes.length; j++) {
    var p = index.prefixes[j];
    if (actionValue.indexOf(p.prefix) === 0) {
      if (p.fromStates === '*' || p.fromStates.indexOf(currentState) !== -1) {
        return p;
      }
    }
  }

  return null;
}

// Export for both script-tag and module usage
if (typeof window !== 'undefined') {
  window.AdvisorFSMActionConfig = {
    ACTION_CONFIG: ACTION_CONFIG,
    buildActionIndex: buildActionIndex,
    findActionEntry: findActionEntry
  };
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    ACTION_CONFIG: ACTION_CONFIG,
    buildActionIndex: buildActionIndex,
    findActionEntry: findActionEntry
  };
}
