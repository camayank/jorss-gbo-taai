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
  // TASK 7: PERSONAL_INFO HANDLERS
  // =================================================================

  // --- Divorce Year (affects alimony treatment) ---
  {
    prefix: 'divorce_year_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      data.tax_profile.divorce_year_type = val.replace('divorce_year_', '');
      if (val === 'divorce_year_post2019') data.tax_profile.alimony_taxable = false;
    },
    userMessage: function(val) {
      return val === 'divorce_year_pre2019' ? 'Before 2019' : '2019 or later';
    },
    sideEffect: 'handle_divorce_year',
  },

  // --- Alimony Amount ---
  {
    prefix: 'alimony_amt_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var parts = val.replace('alimony_amt_', '').split('_');
      var type = parts[0];
      var amtKey = parts.slice(1).join('_');
      var amtValues = { 'under10k': 5000, '10_25k': 17500, '25_50k': 37500, 'over50k': 75000 };
      if (type === 'paid') {
        data.tax_profile.alimony_paid = amtValues[amtKey] || 10000;
        data.tax_profile.alimony_deduction = data.tax_profile.alimony_paid;
      } else {
        data.tax_profile.alimony_received = amtValues[amtKey] || 10000;
        data.tax_profile.alimony_income = data.tax_profile.alimony_received;
      }
    },
    userMessage: function(val) {
      var amtKey = val.replace('alimony_amt_', '').split('_').slice(1).join('_');
      var labels = { 'under10k': 'Under $10,000', '10_25k': '$10,000-$25,000', '25_50k': '$25,000-$50,000', 'over50k': 'Over $50,000' };
      return labels[amtKey] || amtKey;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Alimony type ---
  {
    prefix: 'alimony_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      data.tax_profile.alimony_type = val.replace('alimony_', '');
    },
    userMessage: function(val) {
      var type = val.replace('alimony_', '');
      var labels = { 'paid': 'I paid alimony', 'received': 'I received alimony', 'none': 'No alimony' };
      return labels[type] || type;
    },
    sideEffect: 'handle_alimony',
  },

  // --- Custody ---
  {
    prefix: 'custody_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      data.tax_profile.custody_arrangement = val.replace('custody_', '');
    },
    userMessage: function(val) {
      var type = val.replace('custody_', '');
      var labels = { 'primary': 'Primary custody', 'shared': 'Shared custody', 'ex': 'Ex has primary custody', 'none': 'No children' };
      return labels[type] || type;
    },
    sideEffect: 'handle_custody',
  },

  // --- Form 8332 ---
  {
    prefix: 'form8332_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var type = val.replace('form8332_', '');
      data.tax_profile.form_8332_status = type;
      if (type === 'signed') data.tax_profile.released_dependency_claim = true;
      if (type === 'alternate') data.tax_profile.alternates_dependency_claim = true;
    },
    userMessage: function(val) {
      var type = val.replace('form8332_', '');
      var labels = { 'signed': 'Signed Form 8332', 'no': 'I will claim my children', 'alternate': 'We alternate years', 'unsure': 'Not sure' };
      return labels[type] || type;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Separated living ---
  {
    prefix: 'separated_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var type = val.replace('separated_', '');
      data.tax_profile.separated_living_apart = (type === 'live_apart');
    },
    userMessage: function(val) {
      return val === 'separated_live_apart' ? 'Living separately' : 'Same home';
    },
    sideEffect: 'handle_separated',
  },

  // --- 6 months apart ---
  {
    prefix: 'apart_6months_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var apart = val.replace('apart_6months_', '');
      data.tax_profile.apart_6_months = (apart === 'yes');
      if (apart === 'yes') data.tax_profile.may_qualify_hoh = true;
    },
    userMessage: function(val) {
      return val === 'apart_6months_yes' ? '6+ months apart' : 'Less than 6 months';
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Widowed ---
  {
    prefix: 'widowed_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var type = val.replace('widowed_', '');
      if (type === 'with_deps') {
        data.tax_profile.qualifies_qss = true;
        data.tax_profile.filing_status = 'Qualifying Surviving Spouse';
      }
    },
    userMessage: function(val) {
      return val === 'widowed_with_deps' ? 'Dependents in my home' : 'No dependents';
    },
    sideEffect: 'handle_widowed',
  },

  // --- Dependents count ---
  {
    prefix: 'dependents_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var depCount = val.replace('dependents_', '');
      var depNum = depCount === '3plus' ? 3 : parseInt(depCount);
      data.tax_profile.dependents = depNum;
      data.lead_data.score += 10;
    },
    userMessage: function(val) {
      var depCount = val.replace('dependents_', '');
      var depNum = depCount === '3plus' ? 3 : parseInt(depCount);
      return depNum === 0 ? 'No dependents' : depNum === 1 ? '1 dependent' : depNum + '+ dependents';
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- State selection ---
  {
    prefix: 'state_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var stateCode = val.replace('state_', '');
      data.tax_profile.state = stateCode === 'other' ? 'OTHER' : stateCode;
      data.lead_data.score += 5;
      var noIncomeTaxStates = ['AK', 'FL', 'NV', 'SD', 'TN', 'TX', 'WA', 'WY', 'NH'];
      if (noIncomeTaxStates.indexOf(stateCode) !== -1) data.tax_profile.no_state_income_tax = true;
      var highTaxStates = ['CA', 'NY', 'NJ', 'CT', 'MA', 'OR', 'MN', 'HI'];
      if (highTaxStates.indexOf(stateCode) !== -1) data.tax_profile.high_tax_state = true;
    },
    userMessage: function(val, displayLabel) { return displayLabel || val.replace('state_', ''); },
    sideEffect: 'handle_state_selection',
  },

  // --- Local tax ---
  {
    prefix: 'localtax_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) { data.tax_profile.local_tax_explored = true; },
    userMessage: function(val) { return val.indexOf('unsure') !== -1 ? 'Not sure about local taxes' : val; },
    sideEffect: 'handle_local_tax',
  },

  // --- Status (consolidated) ---
  {
    prefix: 'status_',
    fromStates: '*',
    toState: AdvisorState.COLLECT_INCOME_TYPE,
    extract: function(val, data) {
      var status = val.replace('status_', '').replace('_', ' ');
      var statusMap = {
        'single': 'Single', 'married filing jointly': 'Married Filing Jointly',
        'married_filing_jointly': 'Married Filing Jointly',
        'head of household': 'Head of Household',
        'married filing separately': 'Married Filing Separately',
        'qualifying surviving spouse': 'Qualifying Surviving Spouse'
      };
      var displayStatus = statusMap[status] || status.charAt(0).toUpperCase() + status.slice(1);
      data.tax_profile.filing_status = displayStatus;
      data.lead_data.score += 10;
    },
    userMessage: function(val) {
      var status = val.replace('status_', '').replace('_', ' ');
      var statusMap = {
        'single': 'Single', 'married filing jointly': 'Married Filing Jointly',
        'married_filing_jointly': 'Married Filing Jointly',
        'head of household': 'Head of Household',
        'married filing separately': 'Married Filing Separately',
        'qualifying surviving spouse': 'Qualifying Surviving Spouse'
      };
      return statusMap[status] || status.charAt(0).toUpperCase() + status.slice(1);
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // =================================================================
  // TASK 8: INCOME & DEDUCTION HANDLERS
  // =================================================================

  // --- Income source ---
  {
    prefix: 'source_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var source = val.replace('source_', '');
      var sourceLabels = { 'w2': 'W-2 Employee', 'self_employed': 'Self-Employed / 1099', 'business': 'Business Owner', 'investments': 'Investments / Retirement', 'multiple': 'Multiple sources' };
      data.tax_profile.income_source = sourceLabels[source] || source;
      if (source === 'self_employed' || source === 'business') data.tax_profile.is_self_employed = true;
      data.lead_data.score += 10;
    },
    userMessage: function(val) {
      var source = val.replace('source_', '');
      var labels = { 'w2': 'W-2 Employee', 'self_employed': 'Self-Employed / 1099', 'business': 'Business Owner', 'investments': 'Investments / Retirement', 'multiple': 'Multiple sources' };
      return labels[source] || source;
    },
    sideEffect: 'handle_income_source',
  },

  // --- Retirement income type ---
  {
    prefix: 'retire_income_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var type = val.replace('retire_income_', '');
      data.tax_profile.retirement_income_type = type;
      if (type === 'ss' || type === 'multiple') data.tax_profile.has_social_security = true;
      if (type === 'pension') data.tax_profile.has_pension = true;
      if (type === 'ira') data.tax_profile.has_ira_withdrawals = true;
    },
    userMessage: function(val) {
      var type = val.replace('retire_income_', '');
      var labels = { 'ss': 'Social Security', 'pension': 'Pension', 'ira': 'IRA/401k withdrawals', 'invest': 'Investment income', 'multiple': 'Multiple types' };
      return labels[type] || type;
    },
    sideEffect: 'handle_retirement_income',
  },

  // --- Social Security amount ---
  {
    prefix: 'ss_amt_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var amt = val.replace('ss_amt_', '');
      var amounts = { 'under20k': 15000, '20_35k': 27500, '35_50k': 42500, 'over50k': 60000 };
      data.tax_profile.social_security_amount = amounts[amt] || 27500;
    },
    userMessage: function(val) {
      var amt = val.replace('ss_amt_', '');
      var labels = { 'under20k': 'Under $20,000', '20_35k': '$20,000-$35,000', '35_50k': '$35,000-$50,000', 'over50k': 'Over $50,000' };
      return labels[amt] || amt;
    },
    sideEffect: 'handle_ss_amount',
  },

  // --- SS Strategy response ---
  {
    action: 'ss_strategy_yes',
    fromStates: '*',
    toState: null,
    extract: function(val, data) { data.tax_profile.wants_ss_strategies = true; },
    userMessage: 'Show me strategies',
    sideEffect: 'start_intelligent_questioning',
  },
  {
    action: 'ss_strategy_no',
    fromStates: '*',
    toState: null,
    extract: null,
    userMessage: 'Continue',
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Pension amount ---
  {
    prefix: 'pension_amt_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var amt = val.replace('pension_amt_', '');
      var amounts = { 'under25k': 15000, '25_50k': 37500, '50_100k': 75000, 'over100k': 125000 };
      data.tax_profile.pension_amount = amounts[amt] || 37500;
    },
    userMessage: function(val) {
      var amt = val.replace('pension_amt_', '');
      var amounts = { 'under25k': 15000, '25_50k': 37500, '50_100k': 75000, 'over100k': 125000 };
      return '$' + (amounts[amt] || 37500).toLocaleString();
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- RMD ---
  {
    prefix: 'rmd_amt_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var amt = val.replace('rmd_amt_', '');
      var amounts = { 'under10k': 7500, '10_30k': 20000, '30_75k': 52500, 'over75k': 100000 };
      data.tax_profile.rmd_amount = amounts[amt] || 20000;
    },
    userMessage: function(val) {
      var amt = val.replace('rmd_amt_', '');
      var amounts = { 'under10k': 7500, '10_30k': 20000, '30_75k': 52500, 'over75k': 100000 };
      return '$' + (amounts[amt] || 20000).toLocaleString();
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'rmd_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var status = val.replace('rmd_', '');
      data.tax_profile.rmd_status = status;
      if (status === 'yes') data.tax_profile.takes_rmds = true;
      if (status === 'soon') data.tax_profile.approaching_rmd_age = true;
    },
    userMessage: function(val) {
      var status = val.replace('rmd_', '');
      var labels = { 'yes': 'Yes, I take RMDs', 'no': 'Not yet 73', 'soon': 'Close to RMD age' };
      return labels[status] || status;
    },
    sideEffect: 'handle_rmd',
  },

  // --- Mortgage amount ---
  {
    prefix: 'mortgageamt_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var amt = val.replace('mortgageamt_', '');
      var amounts = { 'under5k': 3000, '5_15k': 10000, '15_30k': 22500, 'over30k': 40000, 'none': 0 };
      data.tax_items.mortgage_interest = amounts[amt] || 10000;
    },
    userMessage: function(val) {
      var amt = val.replace('mortgageamt_', '');
      var labels = { 'under5k': 'Under $5,000', '5_15k': '$5,000-$15,000', '15_30k': '$15,000-$30,000', 'over30k': 'Over $30,000', 'none': 'No mortgage' };
      return labels[amt] || amt;
    },
    sideEffect: 'handle_mortgage_amount',
  },

  // --- Property tax amount ---
  {
    prefix: 'proptaxamt_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var amt = val.replace('proptaxamt_', '');
      var amounts = { 'under3k': 2000, '3_8k': 5500, '8_15k': 11500, 'over15k': 20000 };
      data.tax_items.property_tax = amounts[amt] || 5500;
      data.tax_profile.deductions_explored = true;
    },
    userMessage: function(val) {
      var amt = val.replace('proptaxamt_', '');
      var labels = { 'under3k': 'Under $3,000', '3_8k': '$3,000-$8,000', '8_15k': '$8,000-$15,000', 'over15k': 'Over $15,000' };
      return labels[amt] || amt;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Charitable amount ---
  {
    prefix: 'charityamt_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var amt = val.replace('charityamt_', '');
      var amounts = { 'under500': 250, '500_2500': 1500, '2500_10k': 6000, 'over10k': 15000 };
      data.tax_items.charitable = amounts[amt] || 1500;
      data.tax_profile.deductions_explored = true;
    },
    userMessage: function(val) {
      var amt = val.replace('charityamt_', '');
      var labels = { 'under500': 'Under $500', '500_2500': '$500-$2,500', '2500_10k': '$2,500-$10,000', 'over10k': 'Over $10,000' };
      return labels[amt] || amt;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Medical expense amount ---
  {
    prefix: 'medical_amount_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var level = val.replace('medical_amount_', '');
      var amounts = { 'low': 2500, 'medium': 10000, 'high': 22500, 'very_high': 40000 };
      data.tax_items.medical = amounts[level] || 10000;
      data.tax_profile.deductions_explored = true;
    },
    userMessage: function(val) {
      var level = val.replace('medical_amount_', '');
      var labels = { 'low': 'Under $5,000', 'medium': '$5,000-$15,000', 'high': '$15,000-$30,000', 'very_high': 'Over $30,000' };
      return labels[level] || level;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Medical amount skip ---
  {
    action: 'medical_amt_skip',
    fromStates: '*',
    toState: null,
    extract: function(val, data) { data.tax_profile.medical_explored = true; },
    userMessage: 'Skip medical expenses',
    sideEffect: 'continue_to_deductions',
  },

  // --- Tax goals ---
  {
    prefix: 'goal_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      data.tax_profile.primary_goal = val.replace('goal_', '');
      data.tax_profile.goals_explored = true;
      data.lead_data.score += 10;
    },
    userMessage: function(val) {
      var goal = val.replace('goal_', '');
      var labels = { 'reduce_taxes': 'Reduce my current tax bill', 'retirement': 'Maximize retirement savings', 'life_event': 'Plan for a major life event', 'wealth': 'Build long-term wealth tax-efficiently', 'optimize': 'General tax optimization' };
      return labels[goal] || goal;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Withholding ---
  {
    prefix: 'withhold_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var type = val.replace('withhold_', '');
      data.tax_profile.withholding_explored = true;
      data.tax_profile.withholding_status = type;
      if (type === 'large_refund' || type === 'owe') data.tax_profile.may_need_w4_adjustment = true;
      if (type === 'owe') data.tax_profile.possible_underpayment_penalty = true;
      data.lead_data.score += 5;
    },
    userMessage: function(val) {
      var type = val.replace('withhold_', '');
      var labels = { 'strategic': 'Yes, I adjust it strategically', 'default': 'No, I use the default settings', 'large_refund': 'I usually get a large refund', 'owe': 'I usually owe taxes', 'skip': 'Skip' };
      return labels[type] || type;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Prior year ---
  {
    prefix: 'prior_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var type = val.replace('prior_', '');
      data.tax_profile.prior_year_explored = true;
      data.tax_profile.prior_year_result = type;
      if (type === 'large_refund') data.tax_profile.prior_had_large_refund = true;
      if (type === 'owed') data.tax_profile.prior_owed_taxes = true;
      data.lead_data.score += 5;
    },
    userMessage: function(val) {
      var type = val.replace('prior_', '');
      var labels = { 'large_refund': 'Got a large refund (over $2,000)', 'small_refund': 'Got a small refund (under $2,000)', 'owed': 'Owed money to the IRS', 'breakeven': 'About break-even', 'skip': 'First time filing / Skip' };
      return labels[type] || type;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Spouse income ---
  {
    prefix: 'spouse_',
    fromStates: '*',
    toState: null,
    extract: function(val, data) {
      var type = val.replace('spouse_', '');
      data.tax_profile.spouse_income_explored = true;
      data.tax_profile.spouse_income_type = type;
      if (type === 'w2' || type === 'both') data.tax_profile.spouse_has_w2 = true;
      if (type === 'self_employed' || type === 'both') {
        data.tax_profile.spouse_is_self_employed = true;
        data.lead_data.complexity = 'complex';
      }
      data.lead_data.score += 5;
    },
    userMessage: function(val) {
      var type = val.replace('spouse_', '');
      var labels = { 'w2': 'Yes, W-2 employment', 'self_employed': 'Yes, self-employed', 'both': 'Yes, both W-2 and self-employed', 'none': "No, spouse doesn't work", 'skip': 'Skip' };
      return labels[type] || type;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // =================================================================
  // TASK 8: BUSINESS, INVESTMENT, & DETAILED HANDLERS
  // =================================================================

  // --- Business type (industry) ---
  {
    action: 'biz_professional', fromStates: '*', toState: null,
    extract: function(val, data) { data.tax_profile.business_type = 'professional'; data.lead_data.score += 5; },
    userMessage: 'Professional Services', sideEffect: 'start_intelligent_questioning',
  },
  {
    action: 'biz_retail', fromStates: '*', toState: null,
    extract: function(val, data) { data.tax_profile.business_type = 'retail'; data.lead_data.score += 5; },
    userMessage: 'Retail / E-commerce', sideEffect: 'start_intelligent_questioning',
  },
  {
    action: 'biz_realestate', fromStates: '*', toState: null,
    extract: function(val, data) { data.tax_profile.business_type = 'realestate'; data.lead_data.score += 5; },
    userMessage: 'Real Estate', sideEffect: 'start_intelligent_questioning',
  },
  {
    action: 'biz_tech', fromStates: '*', toState: null,
    extract: function(val, data) { data.tax_profile.business_type = 'tech'; data.lead_data.score += 5; },
    userMessage: 'Tech / Software', sideEffect: 'start_intelligent_questioning',
  },
  {
    action: 'biz_service', fromStates: '*', toState: null,
    extract: function(val, data) { data.tax_profile.business_type = 'service'; data.lead_data.score += 5; },
    userMessage: 'Other Service Business', sideEffect: 'start_intelligent_questioning',
  },
  {
    action: 'biz_farm', fromStates: '*', toState: null,
    extract: function(val, data) {
      data.tax_profile.business_type = 'farm';
      data.tax_profile.uses_schedule_f = true;
      data.lead_data.complexity = 'complex';
      data.lead_data.score += 5;
    },
    userMessage: 'Farming / Agriculture', sideEffect: 'handle_farm',
  },

  // --- Farm type ---
  {
    prefix: 'farm_type_',
    fromStates: '*', toState: null,
    extract: function(val, data) { data.tax_profile.farm_type = val.replace('farm_type_', ''); },
    userMessage: function(val) {
      var type = val.replace('farm_type_', '');
      var labels = { 'crops': 'Crop production', 'livestock': 'Livestock', 'dairy': 'Dairy', 'mixed': 'Mixed farming', 'timber': 'Timber/forestry' };
      return labels[type] || type;
    },
    sideEffect: 'handle_farm_type',
  },

  // --- Farm income ---
  {
    prefix: 'farm_income_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('farm_income_', '');
      var amounts = { 'under50k': 35000, '50_150k': 100000, '150_500k': 325000, 'over500k': 750000 };
      data.tax_profile.farm_gross_income = amounts[amt] || 100000;
    },
    userMessage: function(val) {
      var amt = val.replace('farm_income_', '');
      var amounts = { 'under50k': 35000, '50_150k': 100000, '150_500k': 325000, 'over500k': 750000 };
      return '$' + (amounts[amt] || 100000).toLocaleString();
    },
    sideEffect: 'handle_farm_income',
  },

  // --- Farm expense ---
  {
    prefix: 'farm_exp_',
    fromStates: '*', toState: null,
    extract: function(val, data) { data.lead_data.score += 2; },
    userMessage: function(val) {
      var type = val.replace('farm_exp_', '');
      var labels = { 'supplies': 'Seeds/feed/fertilizer', 'equipment': 'Equipment', 'labor': 'Labor', 'land': 'Land rent', 'fuel': 'Fuel & utilities' };
      return labels[type] || type;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Entity type ---
  {
    prefix: 'entity_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('entity_', '');
      data.tax_profile.entity_type = type;
      data.lead_data.score += 5;
      if (type === 'scorp' || type === 'ccorp') {
        data.lead_data.complexity = 'complex';
        data.lead_data.score += 10;
      }
    },
    userMessage: function(val) {
      var type = val.replace('entity_', '');
      var labels = { 'sole': 'Sole Proprietorship', 'llc_single': 'Single-Member LLC', 'llc_multi': 'Multi-Member LLC / Partnership', 'scorp': 'S-Corporation', 'ccorp': 'C-Corporation' };
      return labels[type] || type;
    },
    sideEffect: 'handle_entity_type',
  },

  // --- S-Corp salary ---
  {
    prefix: 'scorp_salary_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var status = val.replace('scorp_salary_', '');
      data.tax_profile.scorp_salary_status = status;
      if (status === 'no') data.tax_profile.scorp_compliance_risk = true;
    },
    userMessage: function(val) {
      var status = val.replace('scorp_salary_', '');
      var labels = { 'yes': 'Yes, I take a W-2 salary', 'no': 'Only distributions', 'unsure': 'Not sure' };
      return labels[status] || status;
    },
    sideEffect: 'handle_scorp_salary',
  },

  // --- S-Corp W-2/distributions amounts ---
  {
    prefix: 'scorp_w2_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('scorp_w2_', '');
      var amounts = { 'under50k': 35000, '50_80k': 65000, '80_120k': 100000, '120_160k': 140000, 'over160k': 200000 };
      data.tax_profile.scorp_w2_salary = amounts[amt] || 50000;
    },
    userMessage: function(val) {
      var amt = val.replace('scorp_w2_', '');
      var amounts = { 'under50k': 35000, '50_80k': 65000, '80_120k': 100000, '120_160k': 140000, 'over160k': 200000 };
      return '$' + (amounts[amt] || 50000).toLocaleString();
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'scorp_dist_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('scorp_dist_', '');
      var amounts = { 'under50k': 35000, '50_100k': 75000, '100_200k': 150000, 'over200k': 250000 };
      data.tax_profile.scorp_distributions = amounts[amt] || 50000;
      data.tax_profile.needs_salary_review = true;
    },
    userMessage: function(val) {
      var amt = val.replace('scorp_dist_', '');
      var amounts = { 'under50k': 35000, '50_100k': 75000, '100_200k': 150000, 'over200k': 250000 };
      return '$' + (amounts[amt] || 50000).toLocaleString();
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Revenue ---
  {
    prefix: 'revenue_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var range = val.replace('revenue_', '');
      var amounts = { 'under50k': 35000, '50_100k': 75000, '100_250k': 175000, '250_500k': 375000, 'over500k': 750000 };
      data.tax_profile.business_revenue = amounts[range] || 100000;
      data.lead_data.score += 10;
      if ((amounts[range] || 0) >= 250000) data.lead_data.complexity = 'complex';
    },
    userMessage: function(val) {
      var range = val.replace('revenue_', '');
      var labels = { 'under50k': 'Under $50,000', '50_100k': '$50,000-$100,000', '100_250k': '$100,000-$250,000', '250_500k': '$250,000-$500,000', 'over500k': 'Over $500,000' };
      return labels[range] || range;
    },
    sideEffect: 'handle_revenue',
  },

  // --- COGS ---
  {
    prefix: 'cogs_pct_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var pct = val.replace('cogs_pct_', '');
      var pctAmounts = { 'under25': 0.20, '25_40': 0.325, '40_60': 0.50, 'over60': 0.70 };
      data.tax_profile.cogs_percentage = pctAmounts[pct] || 0.325;
      var revenue = data.tax_profile.business_revenue || 100000;
      data.tax_profile.estimated_cogs = Math.round(revenue * (pctAmounts[pct] || 0.325));
      data.tax_profile.gross_profit = revenue - data.tax_profile.estimated_cogs;
    },
    userMessage: function(val) {
      var pct = val.replace('cogs_pct_', '');
      var labels = { 'under25': 'Under 25%', '25_40': '25-40%', '40_60': '40-60%', 'over60': 'Over 60%' };
      return labels[pct] || pct;
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'cogs_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var level = val.replace('cogs_', '');
      data.tax_profile.cogs_status = level;
      if (level === 'yes_high' || level === 'yes_moderate') data.tax_profile.has_cogs = true;
    },
    userMessage: function(val) {
      var level = val.replace('cogs_', '');
      var labels = { 'yes_high': 'Significant inventory', 'yes_moderate': 'Moderate inventory', 'minimal': 'Minimal', 'none': 'No inventory' };
      return labels[level] || level;
    },
    sideEffect: 'handle_cogs',
  },

  // --- Net business income ---
  {
    prefix: 'netincome_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('netincome_', '');
      var amounts = { 'under25k': 15000, '25_75k': 50000, '75_150k': 112500, '150_250k': 200000, 'over250k': 350000 };
      data.tax_profile.net_business_income = amounts[amt] || 50000;
      data.tax_profile.net_income_explored = true;
      var netIncome = amounts[amt] || 50000;
      data.tax_profile.estimated_se_tax = Math.round(netIncome * 0.9235 * 0.153);
    },
    userMessage: function(val) {
      var amt = val.replace('netincome_', '');
      var labels = { 'under25k': 'Under $25,000', '25_75k': '$25,000-$75,000', '75_150k': '$75,000-$150,000', '150_250k': '$150,000-$250,000', 'over250k': 'Over $250,000' };
      return labels[amt] || amt;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- QBI ---
  {
    action: 'qbi_noted', fromStates: '*', toState: null,
    extract: function(val, data) { data.tax_profile.qbi_interest = true; },
    userMessage: "I'll look into this", sideEffect: 'start_intelligent_questioning',
  },
  {
    action: 'qbi_cpa_help', fromStates: '*', toState: null,
    extract: function(val, data) { data.tax_profile.qbi_interest = true; },
    userMessage: 'My CPA can help', sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'qbi_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var status = val.replace('qbi_', '');
      data.tax_profile.qbi_explored = true;
      data.tax_profile.qbi_status = status;
      if (status === 'yes') data.tax_profile.claims_qbi = true;
    },
    userMessage: function(val) {
      var status = val.replace('qbi_', '');
      var labels = { 'yes': 'Yes, I claim QBI deduction', 'learn': 'No, I want to learn more', 'cpa': 'My CPA handles this', 'unsure': 'Not sure if I qualify' };
      return labels[status] || status;
    },
    sideEffect: 'handle_qbi',
  },

  // --- Business expense handlers ---
  {
    prefix: 'bizexp_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('bizexp_', '');
      if (type !== 'skip') {
        data.tax_profile.business_expenses = data.tax_profile.business_expenses || [];
        data.tax_profile.business_expenses.push(type);
        data.lead_data.score += 5;
        if (type === 'home_office') data.tax_profile.has_home_office = true;
        if (type === 'vehicle') data.tax_profile.has_vehicle_expenses = true;
      } else {
        data.tax_profile.business_expenses_explored = true;
      }
    },
    userMessage: function(val) {
      var type = val.replace('bizexp_', '');
      var labels = { 'home_office': 'Home Office', 'vehicle': 'Vehicle / Mileage', 'equipment': 'Equipment & Software', 'marketing': 'Marketing & Advertising', 'supplies': 'Supplies & Materials', 'training': 'Training & Education', 'skip': 'Continue without specifying' };
      return labels[type] || type;
    },
    sideEffect: 'handle_business_expense',
  },

  // --- Home office ---
  {
    prefix: 'homeoffice_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var size = val.replace('homeoffice_', '');
      var amounts = { 'under100': 75, '100_300': 200, '300_500': 400, 'over500': 600 };
      data.tax_items.home_office_sqft = amounts[size] || 200;
      data.tax_items.home_office_deduction = (amounts[size] || 200) * 5;
      data.tax_profile.business_expenses_explored = true;
    },
    userMessage: function(val) {
      var size = val.replace('homeoffice_', '');
      var labels = { 'under100': 'Under 100 sq ft', '100_300': '100-300 sq ft', '300_500': '300-500 sq ft', 'over500': 'Over 500 sq ft' };
      return labels[size] || size;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Vehicle mileage ---
  {
    prefix: 'vehicle_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var miles = val.replace('vehicle_', '');
      var amounts = { 'under5k': 3000, '5_15k': 10000, '15_30k': 22500, 'over30k': 40000 };
      data.tax_items.business_miles = amounts[miles] || 10000;
      data.tax_items.vehicle_deduction = (amounts[miles] || 10000) * 0.67;
      data.tax_profile.business_expenses_explored = true;
    },
    userMessage: function(val) {
      var miles = val.replace('vehicle_', '');
      var labels = { 'under5k': 'Under 5,000 miles', '5_15k': '5,000-15,000 miles', '15_30k': '15,000-30,000 miles', 'over30k': 'Over 30,000 miles' };
      return labels[miles] || miles;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Equipment ---
  {
    prefix: 'equipment_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('equipment_', '');
      var amounts = { 'under2500': 1500, '2500_10k': 6000, '10_50k': 30000, 'over50k': 75000 };
      data.tax_items.equipment_expense = amounts[amt] || 6000;
      data.tax_profile.business_expenses_explored = true;
    },
    userMessage: function(val) {
      var amt = val.replace('equipment_', '');
      var labels = { 'under2500': 'Under $2,500', '2500_10k': '$2,500-$10,000', '10_50k': '$10,000-$50,000', 'over50k': 'Over $50,000' };
      return labels[amt] || amt;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Marketing ---
  {
    prefix: 'marketing_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('marketing_', '');
      var amounts = { 'under1k': 500, '1_5k': 3000, '5_20k': 12500, 'over20k': 30000 };
      data.tax_items.marketing_expense = amounts[amt] || 3000;
      data.tax_profile.business_expenses_explored = true;
    },
    userMessage: function(val) {
      var amt = val.replace('marketing_', '');
      var labels = { 'under1k': 'Under $1,000', '1_5k': '$1,000-$5,000', '5_20k': '$5,000-$20,000', 'over20k': 'Over $20,000' };
      return labels[amt] || amt;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Multiple income sources ---
  {
    prefix: 'multi_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('multi_', '');
      data.tax_profile.income_sources_detailed = type;
      data.lead_data.complexity = 'moderate';
      data.lead_data.score += 10;
      if (type === 'w2_biz' || type === 'self_rental') data.tax_profile.is_self_employed = true;
      if (type === 'self_rental') data.tax_profile.has_rental_income = true;
      if (type === 'w2_invest') data.tax_profile.has_investment_income = true;
    },
    userMessage: function(val) {
      var type = val.replace('multi_', '');
      var labels = { 'w2_biz': 'W-2 + Side Business', 'w2_invest': 'W-2 + Investments', 'self_rental': 'Self-Employment + Rental', 'retire_work': 'Retirement + Part-time', 'other': 'Other combination' };
      return labels[type] || type;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Investment types ---
  {
    prefix: 'invest_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('invest_', '');
      data.tax_profile.investment_type = type;
      data.tax_profile.investment_explored = true;
      data.tax_profile.has_investment_income = true;
      if (type === 'rental') data.tax_profile.has_rental_income = true;
      if (type === 'k1') { data.lead_data.complexity = 'complex'; data.lead_data.score += 15; }
      data.lead_data.score += 10;
    },
    userMessage: function(val) {
      var type = val.replace('invest_', '');
      var labels = { 'stocks': 'Stock dividends & capital gains', 'rental': 'Rental property income', 'interest': 'Interest income', 'k1': 'Partnership/K-1 income', 'crypto': 'Cryptocurrency', 'multiple': 'Multiple investment types' };
      return labels[type] || type;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Rental ---
  {
    prefix: 'rental_exp_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var exp = val.replace('rental_exp_', '');
      var amounts = { 'under5k': 3000, '5_15k': 10000, '15_30k': 22500, 'over30k': 40000 };
      data.tax_profile.rental_expenses = amounts[exp] || 10000;
    },
    userMessage: function(val) {
      var exp = val.replace('rental_exp_', '');
      var labels = { 'under5k': 'Under $5,000', '5_15k': '$5,000-$15,000', '15_30k': '$15,000-$30,000', 'over30k': 'Over $30,000' };
      return labels[exp] || exp;
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'rental_basis_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var basis = val.replace('rental_basis_', '');
      var amounts = { 'under200k': 150000, '200_500k': 350000, '500k_1m': 750000, 'over1m': 1500000 };
      data.tax_profile.rental_property_basis = amounts[basis] || 350000;
      var buildingValue = (amounts[basis] || 350000) * 0.80;
      data.tax_profile.estimated_annual_depreciation = Math.round(buildingValue / 27.5);
    },
    userMessage: function(val) {
      var basis = val.replace('rental_basis_', '');
      var labels = { 'under200k': 'Under $200,000', '200_500k': '$200,000-$500,000', '500k_1m': '$500,000-$1M', 'over1m': 'Over $1,000,000' };
      return labels[basis] || basis;
    },
    sideEffect: 'handle_rental_basis',
  },
  {
    prefix: 'rental_deprec_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var status = val.replace('rental_deprec_', '');
      data.tax_profile.rental_depreciation_status = status;
      if (status === 'yes' || status === 'cpa') data.tax_profile.claims_rental_depreciation = true;
      if (status === 'no') data.tax_profile.missing_depreciation_deduction = true;
    },
    userMessage: function(val) {
      var status = val.replace('rental_deprec_', '');
      var labels = { 'yes': 'Yes, I claim depreciation', 'no': 'No depreciation', 'cpa': 'CPA handles it', 'unsure': 'Not sure' };
      return labels[status] || status;
    },
    sideEffect: 'handle_rental_depreciation',
  },
  {
    prefix: 'rental_income_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var level = val.replace('rental_income_', '');
      var amounts = { 'under20k': 15000, '20_50k': 35000, '50_100k': 75000, 'over100k': 150000 };
      data.tax_profile.rental_income = amounts[level] || 0;
    },
    userMessage: function(val) {
      var level = val.replace('rental_income_', '');
      var labels = { 'under20k': 'Under $20,000', '20_50k': '$20,000-$50,000', '50_100k': '$50,000-$100,000', 'over100k': 'Over $100,000' };
      return labels[level] || level;
    },
    sideEffect: 'continue_to_deductions',
  },
  {
    prefix: 'rental_props_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      data.tax_profile.rental_property_count = val.replace('rental_props_', '');
      data.tax_profile.has_rental_income = true;
    },
    userMessage: function(val) {
      var count = val.replace('rental_props_', '');
      var labels = { '1': '1 property', '2_4': '2-4 properties', '5plus': '5+ properties' };
      return labels[count] || count;
    },
    sideEffect: 'handle_rental_props',
  },
  {
    prefix: 'rental_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var count = val.replace('rental_', '');
      data.tax_profile.rental_property_count = count;
      data.tax_profile.rental_explored = true;
      if (count === '5plus') { data.lead_data.complexity = 'complex'; data.lead_data.score += 20; }
      else if (count === '2_4') data.lead_data.score += 10;
    },
    userMessage: function(val) {
      var count = val.replace('rental_', '');
      var labels = { '1': '1 property', '2_4': '2-4 properties', '5plus': '5+ properties' };
      return labels[count] || count;
    },
    sideEffect: 'handle_rental_count',
  },

  // =================================================================
  // TASK 9: CAPITAL GAINS, CREDITS, CRYPTO, FOREIGN, & REMAINING
  // =================================================================

  // --- Capital gains ---
  {
    prefix: 'capgainamt_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('capgainamt_', '');
      var amounts = { 'under10k': 5000, '10_50k': 30000, '50_100k': 75000, 'over100k': 150000 };
      data.tax_profile.capital_gains_amount = amounts[amt] || 30000;
      data.tax_profile.capital_gains_amount_explored = true;
      data.lead_data.score += 10;
    },
    userMessage: function(val) {
      var amt = val.replace('capgainamt_', '');
      var labels = { 'under10k': 'Under $10,000', '10_50k': '$10,000-$50,000', '50_100k': '$50,000-$100,000', 'over100k': 'Over $100,000' };
      return labels[amt] || amt;
    },
    sideEffect: 'handle_capgain_amount',
  },
  {
    prefix: 'capgain_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('capgain_', '');
      data.tax_profile.capital_gains_explored = true;
      if (type === 'gains') data.tax_profile.has_capital_gains = true;
      if (type === 'losses') data.tax_profile.has_capital_losses = true;
      if (type === 'shortterm') data.tax_profile.has_short_term_gains = true;
      if (type === 'longterm' || type === 'shortterm' || type === 'mixed' || type === 'unsure') {
        data.tax_profile.capital_gains_holding = type;
      }
      data.lead_data.score += 5;
    },
    userMessage: function(val) {
      var type = val.replace('capgain_', '');
      var labels = { 'gains': 'Yes, net gains (profit)', 'losses': 'Yes, net losses', 'even': 'About break-even', 'none': "Haven't sold anything", 'longterm': 'Mostly long-term', 'shortterm': 'Mostly short-term', 'mixed': 'Mix of both', 'unsure': 'Not sure' };
      return labels[type] || type;
    },
    sideEffect: 'handle_capgain',
  },
  {
    prefix: 'caplossamt_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('caplossamt_', '');
      var amounts = { 'under3k': 1500, '3_10k': 6500, 'over10k': 15000 };
      data.tax_profile.capital_losses_amount = amounts[amt] || 3000;
      data.lead_data.score += 5;
    },
    userMessage: function(val) {
      var amt = val.replace('caplossamt_', '');
      var labels = { 'under3k': 'Under $3,000', '3_10k': '$3,000-$10,000', 'over10k': 'Over $10,000' };
      return labels[amt] || amt;
    },
    sideEffect: 'handle_cap_loss_amount',
  },

  // --- Wash sales ---
  {
    prefix: 'washsale_pct_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var pct = val.replace('washsale_pct_', '');
      var amounts = { 'under25': 0.15, '25_50': 0.375, 'over50': 0.60, 'unsure': 0.25 };
      data.tax_profile.washsale_percentage = amounts[pct] || 0.25;
      var totalLosses = data.tax_profile.capital_losses_amount || 0;
      data.tax_profile.washsale_disallowed = Math.round(totalLosses * (amounts[pct] || 0.25));
      data.tax_profile.deductible_losses = totalLosses - data.tax_profile.washsale_disallowed;
    },
    userMessage: function(val) {
      var pct = val.replace('washsale_pct_', '');
      var labels = { 'under25': 'Under 25%', '25_50': '25-50%', 'over50': 'Over 50%', 'unsure': 'Not sure' };
      return labels[pct] || pct;
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'washsale_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var status = val.replace('washsale_', '');
      data.tax_profile.washsale_status = status;
      if (status === 'yes') data.tax_profile.has_wash_sales = true;
    },
    userMessage: function(val) {
      var status = val.replace('washsale_', '');
      var labels = { 'yes': 'Yes, repurchased some', 'no': 'No, did not repurchase', 'unsure': 'Not sure' };
      return labels[status] || status;
    },
    sideEffect: 'handle_wash_sale',
  },

  // --- Dependents & family ---
  {
    prefix: 'dep_age_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var group = val.replace('dep_age_', '');
      data.tax_profile.dependent_ages = group;
      data.tax_profile.dependent_ages_explored = true;
      if (group === 'under6' || group === 'mixed') data.tax_profile.has_young_children = true;
      if (group === 'college') data.tax_profile.has_college_students = true;
      data.lead_data.score += 5;
    },
    userMessage: function(val) {
      var group = val.replace('dep_age_', '');
      var labels = { 'under6': 'All under 6 years old', '6_17': 'Children 6-17', 'college': 'College students (18-24)', 'adult': 'Adult dependents / elderly parents', 'mixed': 'Mix of ages' };
      return labels[group] || group;
    },
    sideEffect: 'handle_dep_age',
  },
  {
    prefix: 'kiddie_amt_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('kiddie_amt_', '');
      var amounts = { 'under1250': 750, '1250_2500': 1875, '2500_10k': 6000, 'over10k': 15000 };
      data.tax_profile.child_unearned_income = amounts[amt] || 3000;
      if (amt === '2500_10k' || amt === 'over10k') data.tax_profile.kiddie_tax_applies = true;
    },
    userMessage: function(val) {
      var amt = val.replace('kiddie_amt_', '');
      var labels = { 'under1250': 'Under $1,250', '1250_2500': '$1,250-$2,500', '2500_10k': '$2,500-$10,000', 'over10k': 'Over $10,000' };
      return labels[amt] || amt;
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'kiddie_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var status = val.replace('kiddie_', '');
      data.tax_profile.kiddie_tax_status = status;
      if (status === 'yes' || status === 'trust') data.tax_profile.has_kiddie_tax_situation = true;
    },
    userMessage: function(val) {
      var status = val.replace('kiddie_', '');
      var labels = { 'yes': 'Child has investment income', 'trust': 'Child has trust income', 'no': 'No unearned income' };
      return labels[status] || status;
    },
    sideEffect: 'handle_kiddie',
  },
  {
    prefix: 'childcare_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var level = val.replace('childcare_', '');
      var amounts = { 'high': 8000, 'low': 3000, 'none': 0 };
      data.tax_items.childcare = amounts[level] || 0;
      data.tax_profile.childcare_explored = true;
      data.lead_data.score += 5;
    },
    userMessage: function(val) {
      var level = val.replace('childcare_', '');
      var labels = { 'high': 'Yes, over $5,000/year', 'low': 'Yes, under $5,000/year', 'none': 'No childcare expenses' };
      return labels[level] || level;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Retirement ---
  {
    prefix: 'retire_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('retire_', '');
      data.tax_profile.retirement_type = type;
      data.tax_profile.retirement_detailed = true;
      if (type === '401k' || type === 'both') data.tax_profile.has_401k = true;
      if (type === 'sep') data.lead_data.score += 10;
      data.lead_data.score += 5;
    },
    userMessage: function(val) {
      var type = val.replace('retire_', '');
      var labels = { '401k': '401(k) through employer', 'trad_ira': 'Traditional IRA', 'roth_ira': 'Roth IRA', 'both': '401(k) and IRA', 'sep': 'SEP-IRA or Solo 401(k)' };
      return labels[type] || type;
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: '401k_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amount = val.replace('401k_', '');
      var amountValues = { 'under10k': 7500, '10_15k': 12500, '15_23k': 19000, 'max': 23500, 'unsure': 15000 };
      data.tax_profile.retirement_401k = amountValues[amount] || 15000;
      data.lead_data.score += 5;
    },
    userMessage: function(val) {
      var amount = val.replace('401k_', '');
      var labels = { 'under10k': 'Less than $10,000', '10_15k': '$10,000-$15,000', '15_23k': '$15,000-$23,000', 'max': 'Maxing out ($23,500)', 'unsure': 'Not sure' };
      return labels[amount] || amount;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- HSA ---
  {
    prefix: 'hsaamt_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('hsaamt_', '');
      var amounts = { 'under2k': 1500, '2_4k': 3000, 'max': 4150, 'unsure': 2500 };
      data.tax_items.hsa_contributions = amounts[amt] || 2500;
      data.tax_profile.hsa_amount_explored = true;
      data.lead_data.score += 5;
    },
    userMessage: function(val) {
      var amt = val.replace('hsaamt_', '');
      var labels = { 'under2k': 'Under $2,000', '2_4k': '$2,000-$4,000', 'max': 'Maxing out', 'unsure': 'Not sure' };
      return labels[amt] || amt;
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'hsa_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('hsa_', '');
      data.tax_profile.hsa_explored = true;
      if (type === 'yes') { data.tax_profile.has_hsa = true; data.lead_data.score += 5; }
      // Also handles focus-flow HSA amounts
      var hsaAmounts = { 'under2k': 1500, '2_4k': 3000, 'max': 4150, 'unsure': 2000 };
      if (hsaAmounts[type]) {
        data.tax_items.hsa_contributions = hsaAmounts[type];
        data.tax_profile.has_hsa = true;
      }
    },
    userMessage: function(val) {
      var type = val.replace('hsa_', '');
      var labels = { 'yes': 'Yes, I contribute to an HSA', 'no': 'No HSA', 'unsure': 'Not sure', 'under2k': 'Under $2,000', '2_4k': '$2,000-$4,000', 'max': 'Maxing out' };
      return labels[type] || type;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Student loans ---
  {
    prefix: 'studentloanamt_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('studentloanamt_', '');
      var amounts = { 'under1k': 500, '1_2500': 1750, 'over2500': 2500 };
      data.tax_items.student_loan_interest = Math.min(amounts[amt] || 1750, 2500);
      data.lead_data.score += 5;
    },
    userMessage: function(val) {
      var amt = val.replace('studentloanamt_', '');
      var labels = { 'under1k': 'Under $1,000', '1_2500': '$1,000-$2,500', 'over2500': 'Over $2,500' };
      return labels[amt] || amt;
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'studentloan_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('studentloan_', '');
      data.tax_profile.student_loan_explored = true;
      if (type === 'yes') { data.tax_profile.has_student_loans = true; data.lead_data.score += 5; }
    },
    userMessage: function(val) {
      var type = val.replace('studentloan_', '');
      var labels = { 'yes': 'Yes, I pay student loan interest', 'no': 'No student loans' };
      return labels[type] || type;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Energy credits ---
  {
    prefix: 'energy_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('energy_', '');
      data.tax_profile.energy_explored = true;
      if (type !== 'none') {
        data.tax_profile.has_energy_credits = true;
        data.tax_profile.energy_credit_type = type;
        data.lead_data.score += 10;
        if (type === 'solar') { data.tax_profile.has_solar_credit = true; data.lead_data.complexity = 'moderate'; }
        if (type === 'ev') data.tax_profile.has_ev_credit = true;
        if (type === 'hvac' || type === 'home_improve') data.tax_profile.has_home_energy_credit = true;
      }
    },
    userMessage: function(val) {
      var type = val.replace('energy_', '');
      var labels = { 'solar': 'Solar panels installed', 'ev': 'Electric vehicle purchased', 'hvac': 'Heat pump / HVAC upgrade', 'home_improve': 'Windows / insulation / doors', 'none': 'None of these' };
      return labels[type] || type;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Life events ---
  {
    prefix: 'event_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('event_', '');
      data.tax_profile.life_event_type = type;
      data.lead_data.score += 10;
      if (type === 'business' || type === 'sale') { data.lead_data.complexity = 'complex'; data.lead_data.score += 10; }
    },
    userMessage: function(val) {
      var type = val.replace('event_', '');
      var labels = { 'marriage': 'Getting married', 'baby': 'Having a baby', 'home': 'Buying a home', 'business': 'Starting a business', 'retirement': 'Retiring soon', 'sale': 'Selling a home or major asset' };
      return labels[type] || type;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Advanced strategies ---
  {
    prefix: 'adv_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      data.tax_profile.advanced_interest = val.replace('adv_', '');
      data.tax_profile.advanced_explored = true;
      data.lead_data.complexity = 'complex';
      data.lead_data.score += 15;
    },
    userMessage: function(val) {
      var type = val.replace('adv_', '');
      var labels = { 'backdoor': 'Backdoor Roth IRA strategies', 'charitable': 'Charitable giving optimization', 'deferred': 'Deferred compensation plans', 'estate': 'Estate planning considerations', 'all': 'Show all tax-saving opportunities' };
      return labels[type] || type;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Cryptocurrency ---
  {
    prefix: 'crypto_earned_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('crypto_earned_', '');
      var amounts = { 'under1k': 500, '1_5k': 3000, '5_20k': 12500, 'over20k': 35000 };
      data.tax_profile.crypto_earned_value = amounts[amt] || 5000;
    },
    userMessage: function(val) {
      var amt = val.replace('crypto_earned_', '');
      var labels = { 'under1k': 'Under $1,000', '1_5k': '$1,000-$5,000', '5_20k': '$5,000-$20,000', 'over20k': 'Over $20,000' };
      return labels[amt] || amt;
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'crypto_earn_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('crypto_earn_', '');
      data.tax_profile.crypto_earning_type = type;
      if (type === 'mining') data.tax_profile.crypto_mining_se_tax = true;
    },
    userMessage: function(val) {
      var type = val.replace('crypto_earn_', '');
      var labels = { 'mining': 'Mining', 'staking': 'Staking rewards', 'defi': 'DeFi yield farming', 'airdrops': 'Airdrops/rewards', 'payment': 'Payment for services' };
      return labels[type] || type;
    },
    sideEffect: 'handle_crypto_earn',
  },
  {
    prefix: 'crypto_trades_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var count = val.replace('crypto_trades_', '');
      data.tax_profile.crypto_trade_count = count;
      if (count === 'over200' || count === '50_200') data.tax_profile.needs_crypto_software = true;
    },
    userMessage: function(val) {
      var count = val.replace('crypto_trades_', '');
      var labels = { 'under10': 'Under 10 trades', '10_50': '10-50 trades', '50_200': '50-200 trades', 'over200': 'Over 200 trades' };
      return labels[count] || count;
    },
    sideEffect: 'handle_crypto_trades',
  },
  {
    prefix: 'crypto_gl_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('crypto_gl_', '');
      var amounts = { 'gain_under5k': 2500, 'gain_5_25k': 15000, 'gain_over25k': 50000, 'loss_under10k': -5000, 'loss_over10k': -15000, 'even': 0 };
      data.tax_profile.crypto_gain_loss = amounts[type] || 0;
      if (type.indexOf('loss_') === 0) data.tax_profile.has_crypto_losses = true;
    },
    userMessage: function(val) {
      var type = val.replace('crypto_gl_', '');
      var labels = { 'gain_under5k': 'Net gain under $5,000', 'gain_5_25k': 'Net gain $5,000-$25,000', 'gain_over25k': 'Net gain over $25,000', 'loss_under10k': 'Net loss under $10,000', 'loss_over10k': 'Net loss over $10,000', 'even': 'About break-even' };
      return labels[type] || type;
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'crypto_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('crypto_', '');
      data.tax_profile.crypto_explored = true;
      if (type !== 'none') {
        data.tax_profile.has_crypto = true;
        data.tax_profile.crypto_activity = type;
        data.lead_data.score += 10;
        if (type === 'sold') { data.tax_profile.has_crypto_gains = true; data.lead_data.complexity = 'complex'; }
        if (type === 'earned') { data.tax_profile.has_crypto_income = true; data.lead_data.complexity = 'complex'; }
      }
    },
    userMessage: function(val) {
      var type = val.replace('crypto_', '');
      var labels = { 'hold': "Yes, I hold crypto but haven't sold", 'sold': 'Yes, I sold/traded crypto', 'earned': 'Yes, I earned crypto', 'none': 'No cryptocurrency' };
      return labels[type] || type;
    },
    sideEffect: 'handle_crypto',
  },

  // --- Stock options ---
  {
    prefix: 'iso_spread_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('iso_spread_', '');
      var amounts = { 'under50k': 25000, '50_150k': 100000, '150_500k': 325000, 'over500k': 750000 };
      data.tax_profile.iso_spread = amounts[amt] || 100000;
      data.tax_profile.potential_amt_liability = Math.round((amounts[amt] || 100000) * 0.28);
      if ((amounts[amt] || 0) >= 150000) data.tax_profile.high_amt_risk = true;
    },
    userMessage: function(val) {
      var amt = val.replace('iso_spread_', '');
      var labels = { 'under50k': 'Under $50,000', '50_150k': '$50,000-$150,000', '150_500k': '$150,000-$500,000', 'over500k': 'Over $500,000' };
      return labels[amt] || amt;
    },
    sideEffect: 'handle_iso_spread',
  },
  {
    prefix: 'iso_exercised_',
    fromStates: '*', toState: null,
    extract: function(val, data) { data.tax_profile.iso_exercise_status = val.replace('iso_exercised_', ''); },
    userMessage: function(val) {
      var status = val.replace('iso_exercised_', '');
      var labels = { 'yes': 'Yes, exercised ISOs', 'no': "Haven't exercised", 'planning': 'Planning to exercise' };
      return labels[status] || status;
    },
    sideEffect: 'handle_iso_exercise',
  },
  {
    prefix: 'amt_estimated_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var status = val.replace('amt_estimated_', '');
      data.tax_profile.amt_estimated_status = status;
      if (status === 'no') data.tax_profile.needs_amt_planning = true;
    },
    userMessage: function(val) {
      var status = val.replace('amt_estimated_', '');
      var labels = { 'yes': 'Yes, made AMT payments', 'no': 'Need to plan for this', 'cpa': 'CPA handling it' };
      return labels[status] || status;
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'options_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('options_', '');
      data.tax_profile.stock_options_explored = true;
      if (type !== 'none') {
        data.tax_profile.has_equity_compensation = true;
        data.tax_profile.equity_type = type;
        data.lead_data.score += 10;
        data.lead_data.complexity = 'complex';
        if (type === 'iso') { data.tax_profile.has_iso = true; data.tax_profile.may_have_amt = true; }
      }
    },
    userMessage: function(val) {
      var type = val.replace('options_', '');
      var labels = { 'iso': 'Yes, I have ISOs', 'nso': 'Yes, I have NSOs', 'rsu': 'Yes, I have RSUs', 'espp': 'Yes, I have ESPP', 'none': 'No equity compensation' };
      return labels[type] || type;
    },
    sideEffect: 'handle_options',
  },

  // --- Estimated tax payments ---
  {
    prefix: 'estamt_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('estamt_', '');
      var amounts = { 'under5k': 2500, '5_15k': 10000, '15_30k': 22500, '30_50k': 40000, 'over50k': 75000, 'skip': 0 };
      data.tax_profile.estimated_payments_amount = amounts[amt] || 0;
      data.tax_profile.estimated_amount_explored = true;
    },
    userMessage: function(val) {
      var amt = val.replace('estamt_', '');
      var labels = { 'under5k': 'Under $5,000', '5_15k': '$5,000-$15,000', '15_30k': '$15,000-$30,000', '30_50k': '$30,000-$50,000', 'over50k': 'Over $50,000', 'skip': 'Skip for now' };
      return labels[amt] || amt;
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'estimated_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('estimated_', '');
      data.tax_profile.estimated_explored = true;
      data.tax_profile.makes_estimated_payments = (type === 'yes');
      data.tax_profile.estimated_payment_status = type;
    },
    userMessage: function(val) {
      var type = val.replace('estimated_', '');
      var labels = { 'yes': 'Yes, I make regular estimated payments', 'sometimes': 'Sometimes, but not consistently', 'no': "No, I don't make estimated payments", 'unsure': 'Not sure if I should be' };
      return labels[type] || type;
    },
    sideEffect: 'handle_estimated_payments',
  },

  // --- Foreign income ---
  {
    prefix: 'foreign_housing_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('foreign_housing_', '');
      var amounts = { 'under20k': 15000, '20_40k': 30000, 'over40k': 50000 };
      data.tax_profile.foreign_housing_expense = amounts[amt] || 30000;
    },
    userMessage: function(val) {
      var amt = val.replace('foreign_housing_', '');
      var amounts = { 'under20k': 15000, '20_40k': 30000, 'over40k': 50000 };
      return '$' + (amounts[amt] || 30000).toLocaleString();
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'foreign_earned_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('foreign_earned_', '');
      var amounts = { 'under50k': 35000, '50_100k': 75000, '100_126k': 113000, 'over126k': 175000 };
      data.tax_profile.foreign_earned_income = amounts[amt] || 75000;
      if (amt === 'over126k') data.tax_profile.excess_foreign_income = true;
    },
    userMessage: function(val) {
      var amt = val.replace('foreign_earned_', '');
      var amounts = { 'under50k': 35000, '50_100k': 75000, '100_126k': 113000, 'over126k': 175000 };
      return '$' + (amounts[amt] || 75000).toLocaleString();
    },
    sideEffect: 'handle_foreign_earned',
  },
  {
    prefix: 'foreign_type_',
    fromStates: '*', toState: null,
    extract: function(val, data) { data.tax_profile.foreign_income_type = val.replace('foreign_type_', ''); },
    userMessage: function(val) {
      var type = val.replace('foreign_type_', '');
      var labels = { 'wages': 'Foreign wages', 'self': 'Self-employment abroad', 'rental': 'Foreign rental', 'invest': 'Foreign investments', 'pension': 'Foreign pension' };
      return labels[type] || type;
    },
    sideEffect: 'handle_foreign_income_type',
  },
  {
    prefix: 'foreign_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('foreign_', '');
      data.tax_profile.foreign_explored = true;
      if (type !== 'none') {
        data.tax_profile.has_foreign_income = (type === 'income' || type === 'both');
        data.tax_profile.has_foreign_accounts = (type === 'accounts' || type === 'both');
        data.tax_profile.may_need_fbar = true;
        data.lead_data.complexity = 'complex';
      }
    },
    userMessage: function(val) {
      var type = val.replace('foreign_', '');
      var labels = { 'income': 'Yes, I have foreign income', 'accounts': 'Yes, foreign bank accounts only', 'both': 'Both foreign income and accounts', 'none': 'No foreign income or accounts' };
      return labels[type] || type;
    },
    sideEffect: 'handle_foreign',
  },
  {
    prefix: 'feie_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var status = val.replace('feie_', '');
      data.tax_profile.feie_status = status;
      if (status === 'full_year' || status === '330_days') {
        data.tax_profile.qualifies_feie = true;
        data.tax_profile.feie_exclusion = 126500;
      }
    },
    userMessage: function(val) {
      var status = val.replace('feie_', '');
      var labels = { 'full_year': 'Lived abroad full year', '330_days': '330+ days abroad', 'partial': 'Partial year abroad', 'remote_us': 'Worked remotely from US' };
      return labels[status] || status;
    },
    sideEffect: 'handle_feie',
  },
  {
    prefix: 'ftc_amt_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('ftc_amt_', '');
      var amounts = { 'under1k': 500, '1_5k': 3000, '5_20k': 12500, 'over20k': 35000 };
      data.tax_profile.foreign_tax_paid = amounts[amt] || 3000;
    },
    userMessage: function(val) {
      var amt = val.replace('ftc_amt_', '');
      var amounts = { 'under1k': 500, '1_5k': 3000, '5_20k': 12500, 'over20k': 35000 };
      return '$' + (amounts[amt] || 3000).toLocaleString();
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'ftc_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var status = val.replace('ftc_', '');
      data.tax_profile.ftc_status = status;
      if (status === 'yes') data.tax_profile.has_foreign_tax_credit = true;
    },
    userMessage: function(val) {
      var status = val.replace('ftc_', '');
      var labels = { 'yes': 'Yes, taxes withheld/paid', 'no': 'No foreign taxes', 'unsure': 'Not sure' };
      return labels[status] || status;
    },
    sideEffect: 'handle_ftc',
  },
  {
    prefix: 'fbar_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('fbar_', '');
      data.tax_profile.fbar_balance_range = amt;
      if (amt !== 'under10k') {
        data.tax_profile.fbar_required = true;
        if (amt === '50_200k' || amt === 'over200k') data.tax_profile.fatca_8938_may_apply = true;
      }
    },
    userMessage: function(val) {
      var amt = val.replace('fbar_', '');
      var labels = { 'under10k': 'Under $10,000', '10_50k': '$10,000-$50,000', '50_200k': '$50,000-$200,000', 'over200k': 'Over $200,000' };
      return labels[amt] || amt;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Multi-state ---
  {
    prefix: 'multistate_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('multistate_', '');
      data.tax_profile.multistate_status = type;
      if (type !== 'no') { data.tax_profile.is_multistate_filer = true; data.lead_data.complexity = 'complex'; }
    },
    userMessage: function(val) {
      var type = val.replace('multistate_', '');
      var labels = { 'no': 'Just one state', 'work': 'Worked in another state', 'moved': 'Moved to a new state', 'remote': 'Multiple states (remote)' };
      return labels[type] || type;
    },
    sideEffect: 'handle_multistate',
  },
  {
    prefix: 'moved_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var q = val.replace('moved_', '');
      data.tax_profile.move_quarter = q;
      var days = { 'q1': 75, 'q2': 150, 'q3': 225, 'q4': 300 };
      data.tax_profile.days_in_old_state = days[q] || 180;
      data.tax_profile.days_in_new_state = 365 - (days[q] || 180);
    },
    userMessage: function(val) {
      var q = val.replace('moved_', '');
      var labels = { 'q1': 'January-March', 'q2': 'April-June', 'q3': 'July-September', 'q4': 'October-December' };
      return labels[q] || q;
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'workdays_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var w = val.replace('workdays_', '');
      var amounts = { 'under10': 5, '10_30': 20, '30_60': 45, 'over60': 90 };
      data.tax_profile.workdays_other_state = amounts[w] || 20;
      if (w !== 'under10') data.tax_profile.likely_need_nonresident_return = true;
    },
    userMessage: function(val) {
      var w = val.replace('workdays_', '');
      var labels = { 'under10': 'Under 10 days', '10_30': '10-30 days', '30_60': '30-60 days', 'over60': 'Over 60 days' };
      return labels[w] || w;
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'remote_states_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var count = val.replace('remote_states_', '');
      var amounts = { '2': 2, '3': 3, '4plus': 5 };
      data.tax_profile.remote_work_states = amounts[count] || 2;
      data.tax_profile.needs_multistate_planning = true;
    },
    userMessage: function(val) {
      var count = val.replace('remote_states_', '');
      var labels = { '2': '2 states', '3': '3 states', '4plus': '4+ states' };
      return labels[count] || count;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Focus area ---
  {
    prefix: 'focus_',
    fromStates: '*', toState: null,
    extract: function(val, data) { data.focus_area = val.replace('focus_', '').replace('_', ' '); },
    userMessage: function(val) {
      var focus = val.replace('focus_', '').replace('_', ' ');
      return focus.charAt(0).toUpperCase() + focus.slice(1);
    },
    sideEffect: 'handle_focus',
  },

  // --- Homeowner ---
  {
    prefix: 'homeowner_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      data.details = data.details || {};
      data.details[val] = true;
    },
    userMessage: function(val) {
      var type = val.replace('homeowner_', '');
      var labels = { 'yes': 'Yes, I own my home', 'no': 'No, I rent', 'rental': 'I own rental properties' };
      return labels[type] || type;
    },
    sideEffect: 'handle_homeowner',
  },

  // --- Education ---
  {
    prefix: 'educredit_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('educredit_', '');
      data.tax_profile.education_credits_explored = true;
      if (type === 'dependents' || type === 'self') {
        data.tax_profile.has_education_expenses = true;
        data.tax_profile.education_type = type;
      }
      if (type === '529') { data.tax_profile.has_529 = true; data.tax_items.has_529 = true; }
    },
    userMessage: function(val) {
      var type = val.replace('educredit_', '');
      var labels = { 'dependents': 'College tuition for dependents', 'self': 'Education for myself', '529': 'I contribute to a 529 plan', 'none': 'No education expenses' };
      return labels[type] || type;
    },
    sideEffect: 'handle_educredit',
  },
  {
    prefix: 'students_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var count = val.replace('students_', '');
      data.tax_profile.college_students = count === '3plus' ? 3 : parseInt(count);
      data.tax_profile.potential_aotc = (count === '3plus' ? 3 : parseInt(count)) * 2500;
    },
    userMessage: function(val) {
      var count = val.replace('students_', '');
      var labels = { '1': '1 student', '2': '2 students', '3plus': '3+ students' };
      return labels[count] || count;
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'selfed_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      data.tax_profile.self_education_type = val.replace('selfed_', '');
      data.tax_profile.potential_llc = 2000;
    },
    userMessage: function(val) {
      var type = val.replace('selfed_', '');
      var labels = { 'degree': 'College degree', 'graduate': 'Graduate school', 'cert': 'Professional certifications', 'courses': 'Job-related courses' };
      return labels[type] || type;
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: '529amt_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('529amt_', '');
      var amounts = { 'under5k': 2500, '5_15k': 10000, 'over15k': 20000 };
      data.tax_profile.contribution_529 = amounts[amt] || 5000;
    },
    userMessage: function(val) {
      var amt = val.replace('529amt_', '');
      var labels = { 'under5k': 'Under $5,000', '5_15k': '$5,000-$15,000', 'over15k': 'Over $15,000' };
      return labels[amt] || amt;
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'itemize_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var choice = val.replace('itemize_', '');
      data.tax_profile.itemize_decision_explored = true;
      data.tax_profile.itemize_choice = choice;
      if (choice === 'yes') data.tax_profile.itemizes_deductions = true;
      if (choice === 'standard') data.tax_profile.itemizes_deductions = false;
    },
    userMessage: function(val) {
      var choice = val.replace('itemize_', '');
      var labels = { 'yes': 'I itemize deductions', 'standard': 'I take the standard deduction', 'cpa': 'My CPA decides', 'unsure': 'Not sure' };
      return labels[choice] || choice;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Focus-flow education handlers ---
  {
    prefix: 'edu_expense_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var level = val.replace('edu_expense_', '');
      var amounts = { 'under5k': 3000, '5_15k': 10000, 'over15k': 20000 };
      data.tax_items.education_expenses = amounts[level] || 0;
    },
    userMessage: function(val) {
      var level = val.replace('edu_expense_', '');
      var labels = { 'under5k': 'Under $5,000', '5_15k': '$5,000-$15,000', 'over15k': 'Over $15,000' };
      return labels[level] || level;
    },
    sideEffect: 'continue_to_deductions',
  },
  {
    prefix: 'edu_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      data.details = data.details || {};
      data.details[val] = true;
    },
    userMessage: function(val) {
      var type = val.replace('edu_', '');
      var labels = { 'self': 'Yes, for myself', 'dependents': 'Yes, for dependents', 'loans': 'I have student loan interest', 'multiple': 'Multiple of these' };
      return labels[type] || type;
    },
    sideEffect: 'handle_edu',
  },
  {
    prefix: 'student_loan_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var level = val.replace('student_loan_', '');
      var amounts = { 'under1k': 500, '1_2.5k': 1750, 'over2.5k': 2500, 'unsure': 1500 };
      data.tax_items.student_loan_interest = amounts[level] || 0;
    },
    userMessage: function(val) {
      var level = val.replace('student_loan_', '');
      var labels = { 'under1k': 'Under $1,000', '1_2.5k': '$1,000-$2,500', 'over2.5k': 'Over $2,500', 'unsure': 'Not sure' };
      return labels[level] || level;
    },
    sideEffect: 'continue_to_deductions',
  },
  {
    prefix: 'college_students_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var count = val.replace('college_students_', '');
      data.tax_profile.college_students = count === '3plus' ? 3 : parseInt(count);
      data.tax_profile.has_college_students = true;
    },
    userMessage: function(val) {
      var count = val.replace('college_students_', '');
      var labels = { '1': '1 student', '2': '2 students', '3plus': '3+ students' };
      return labels[count] || count;
    },
    sideEffect: 'continue_to_deductions',
  },

  // --- Medical amount (focus flow) ---
  {
    prefix: 'medical_amt_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var level = val.replace('medical_amt_', '');
      var amounts = { 'under2k': 1000, '2_5k': 3500, '5_10k': 7500, '10_25k': 17500, '25_50k': 37500, 'over50k': 60000, 'skip': 0 };
      data.tax_items.medical = amounts[level] || 0;
    },
    userMessage: function(val) {
      var level = val.replace('medical_amt_', '');
      var labels = { 'under2k': 'Under $2,000', '2_5k': '$2,000-$5,000', '5_10k': '$5,000-$10,000', '10_25k': '$10,000-$25,000', '25_50k': '$25,000-$50,000', 'over50k': 'Over $50,000', 'skip': 'Skip' };
      return labels[level] || level;
    },
    sideEffect: 'continue_to_deductions',
  },

  // --- Focus-flow medical ---
  {
    action: 'medical_high', fromStates: '*', toState: null,
    extract: function(val, data) { data.details = data.details || {}; data.details.medical_high = true; },
    userMessage: 'Yes, over $5,000 annually', sideEffect: 'handle_medical_focus',
  },
  {
    action: 'medical_moderate', fromStates: '*', toState: null,
    extract: function(val, data) { data.details = data.details || {}; data.details.medical_moderate = true; },
    userMessage: 'Moderate expenses', sideEffect: 'handle_medical_focus',
  },
  {
    action: 'medical_hsa', fromStates: '*', toState: null,
    extract: function(val, data) { data.details = data.details || {}; data.details.medical_hsa = true; },
    userMessage: 'I have an HSA', sideEffect: 'handle_medical_focus',
  },
  {
    action: 'medical_ltc', fromStates: '*', toState: null,
    extract: function(val, data) { data.details = data.details || {}; data.details.medical_ltc = true; },
    userMessage: 'Long-term care expenses', sideEffect: 'handle_medical_focus',
  },

  // --- Investment focus flow ---
  {
    prefix: 'inv_',
    fromStates: '*', toState: null,
    extract: function(val, data) { data.details = data.details || {}; data.details[val] = true; },
    userMessage: function(val) {
      var type = val.replace('inv_', '');
      var labels = { 'traditional': '401(k) / Traditional IRA', 'roth': 'Roth IRA', 'brokerage': 'Brokerage / Taxable accounts', 'multiple': 'Multiple account types' };
      return labels[type] || type;
    },
    sideEffect: 'handle_inv_focus',
  },
  {
    prefix: 'trad_contrib_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var level = val.replace('trad_contrib_', '');
      var amounts = { 'under10k': 7500, '10_20k': 15000, 'max401k': 23500, 'maxira': 7000 };
      if (level === 'max401k' || level === '10_20k' || level === 'under10k') {
        data.tax_profile.retirement_401k = amounts[level];
        data.tax_profile.has_401k = true;
      } else {
        data.tax_profile.retirement_ira = amounts[level];
      }
    },
    userMessage: function(val) {
      var level = val.replace('trad_contrib_', '');
      var labels = { 'under10k': 'Under $10,000', '10_20k': '$10,000-$20,000', 'max401k': 'Maxing out 401(k)', 'maxira': 'Maxing out IRA' };
      return labels[level] || level;
    },
    sideEffect: 'continue_to_deductions',
  },
  {
    prefix: 'roth_contrib_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      data.tax_profile.has_roth = true;
      if (val === 'roth_contrib_backdoor') data.tax_profile.uses_backdoor_roth = true;
    },
    userMessage: function(val) {
      var level = val.replace('roth_contrib_', '');
      var labels = { 'under3k': 'Under $3,000', '3_7k': '$3,000-$7,000', 'max': 'Maxing out ($7,000)', 'backdoor': 'Using Backdoor Roth' };
      return labels[level] || level;
    },
    sideEffect: 'continue_to_deductions',
  },

  // --- Business focus flow ---
  {
    action: 'biz_sole', fromStates: '*', toState: null,
    extract: function(val, data) { data.tax_profile.is_self_employed = true; data.tax_profile.entity_type = 'sole'; },
    userMessage: 'Sole Proprietor / Freelancer', sideEffect: 'handle_biz_focus',
  },
  {
    action: 'biz_llc', fromStates: '*', toState: null,
    extract: function(val, data) { data.tax_profile.is_self_employed = true; data.tax_profile.entity_type = 'llc_single'; },
    userMessage: 'LLC / Partnership', sideEffect: 'handle_biz_focus',
  },
  {
    action: 'biz_corp', fromStates: '*', toState: null,
    extract: function(val, data) { data.tax_profile.is_self_employed = true; data.tax_profile.entity_type = 'scorp'; },
    userMessage: 'S-Corp / C-Corp', sideEffect: 'handle_biz_focus',
  },
  {
    action: 'biz_side', fromStates: '*', toState: null,
    extract: function(val, data) { data.tax_profile.is_self_employed = true; data.tax_profile.has_side_business = true; },
    userMessage: 'Side business / Gig work', sideEffect: 'handle_biz_focus',
  },
  {
    prefix: 'bizinc_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var level = val.replace('bizinc_', '');
      var amounts = { 'under25k': 15000, '25_75k': 50000, '75_150k': 112500, 'over150k': 200000 };
      data.tax_profile.business_income = amounts[level] || 0;
    },
    userMessage: function(val) {
      var level = val.replace('bizinc_', '');
      var labels = { 'under25k': 'Under $25,000', '25_75k': '$25,000-$75,000', '75_150k': '$75,000-$150,000', 'over150k': 'Over $150,000' };
      return labels[level] || level;
    },
    sideEffect: 'continue_to_deductions',
  },

  // --- Deductions/Credits flow ---
  {
    prefix: 'deduct_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      if (val !== 'deduct_skip') {
        var deduction = val.replace('deduct_', '').replace('_', ' ');
        data.deductions = data.deductions || [];
        data.deductions.push(deduction);
      }
    },
    userMessage: function(val) {
      if (val === 'deduct_skip') return "Let's continue";
      var deduction = val.replace('deduct_', '').replace('_', ' ');
      return deduction.charAt(0).toUpperCase() + deduction.slice(1);
    },
    sideEffect: 'handle_deduct_flow',
  },
  {
    prefix: 'credit_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      if (val !== 'credit_skip') {
        var credit = val.replace('credit_', '').replace('_', ' ');
        data.credits = data.credits || [];
        data.credits.push(credit);
      }
    },
    userMessage: function(val) {
      if (val === 'credit_skip') return "Let's continue";
      var credit = val.replace('credit_', '').replace('_', ' ');
      return credit.charAt(0).toUpperCase() + credit.slice(1);
    },
    sideEffect: 'handle_credit_flow',
  },
  {
    prefix: 'has_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var type = val.replace('has_', '');
      data.deductions = data.deductions || [];
      data.deductions.push(type);
      data.lead_data.score += 5;
    },
    userMessage: function(val) {
      var type = val.replace('has_', '');
      var labels = { 'mortgage': 'Mortgage interest', 'charity': 'Charitable donations', 'medical': 'Medical expenses', 'education': 'Education expenses', 'business': 'Business expenses', 'retirement': 'Retirement contributions' };
      return labels[type] || type;
    },
    sideEffect: 'handle_has_deduction',
  },
  {
    prefix: 'amount_',
    fromStates: '*', toState: null,
    extract: null,
    userMessage: function(val) {
      var parts = val.split('_');
      var level = parts[parts.length - 1];
      var amountMap = { 'low': '$2,500', 'mid': '$10,000', 'high': '$20,000+' };
      return amountMap[level] || 'Estimated';
    },
    sideEffect: 'handle_amount_selection',
  },
  {
    action: 'deduction_next', fromStates: '*', toState: null,
    extract: null, userMessage: 'Skip', sideEffect: 'handle_deduction_next',
  },
  {
    action: 'deductions_done', fromStates: '*', toState: null,
    extract: null, userMessage: 'Continue', sideEffect: 'handle_deductions_done',
  },

  // --- NSO/RSU value (regex match in original) ---
  // These use a pattern like nso_value_* or rsu_value_*
  {
    prefix: 'nso_value_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('nso_value_', '');
      var amounts = { 'under25k': 15000, '25_100k': 62500, '100_250k': 175000, 'over250k': 400000 };
      data.tax_profile.nso_value = amounts[amt] || 62500;
      data.tax_profile.equity_income = amounts[amt] || 62500;
    },
    userMessage: function(val) {
      var amt = val.replace('nso_value_', '');
      var labels = { 'under25k': 'Under $25,000', '25_100k': '$25,000-$100,000', '100_250k': '$100,000-$250,000', 'over250k': 'Over $250,000' };
      return labels[amt] || amt;
    },
    sideEffect: 'start_intelligent_questioning',
  },
  {
    prefix: 'rsu_value_',
    fromStates: '*', toState: null,
    extract: function(val, data) {
      var amt = val.replace('rsu_value_', '');
      var amounts = { 'under25k': 15000, '25_100k': 62500, '100_250k': 175000, 'over250k': 400000 };
      data.tax_profile.rsu_value = amounts[amt] || 62500;
      data.tax_profile.equity_income = amounts[amt] || 62500;
    },
    userMessage: function(val) {
      var amt = val.replace('rsu_value_', '');
      var labels = { 'under25k': 'Under $25,000', '25_100k': '$25,000-$100,000', '100_250k': '$100,000-$250,000', 'over250k': 'Over $250,000' };
      return labels[amt] || amt;
    },
    sideEffect: 'start_intelligent_questioning',
  },

  // --- Remaining exact-match actions ---
  {
    action: 'more_questions', fromStates: '*', toState: null,
    extract: null, userMessage: 'I have more questions first', sideEffect: 'start_intelligent_questioning',
  },
  {
    action: 'add_documents', fromStates: '*', toState: AdvisorState.DOCUMENT_UPLOAD,
    extract: null, userMessage: 'Let me add documents', sideEffect: 'trigger_file_input',
  },
  {
    action: 'continue_flow', fromStates: '*', toState: null,
    extract: null, userMessage: 'Continue', sideEffect: 'start_intelligent_questioning',
  },
  {
    action: 'finish_satisfied', fromStates: '*', toState: null,
    extract: null, userMessage: "I'm satisfied, thanks!", sideEffect: null,
  },
  {
    action: 'download_report', fromStates: '*', toState: null,
    extract: null, userMessage: 'Download Full Report (PDF)', sideEffect: 'handle_download_report',
  },
  {
    action: 'view_report', fromStates: '*', toState: null,
    extract: null, userMessage: 'View Report Online', sideEffect: 'handle_view_report',
  },
  {
    action: 'email_report', fromStates: '*', toState: null,
    extract: null, userMessage: 'Email Report to Me', sideEffect: 'handle_email_report',
  },
  {
    action: 'schedule_consult', fromStates: '*', toState: AdvisorState.CPA_HANDOFF,
    extract: null, userMessage: 'Schedule CPA Consultation', sideEffect: 'schedule_cpa',
  },
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

  // Sort prefixes longest-first so more specific prefixes match before generic ones
  // e.g. 'divorce_year_' matches before 'divorce_'
  prefixes.sort(function(a, b) { return b.prefix.length - a.prefix.length; });

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
