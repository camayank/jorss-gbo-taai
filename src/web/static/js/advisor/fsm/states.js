/**
 * FSM States for the Intelligent Advisor conversation flow.
 * Maps to backend phases: personal_info, income, deductions, review, ready_to_file
 */

const AdvisorState = Object.freeze({
  // Phase: personal_info
  WELCOME: 'welcome',
  COLLECT_NAME: 'collect_name',
  COLLECT_FILING_STATUS: 'collect_filing_status',

  // Phase: income
  COLLECT_INCOME_TYPE: 'collect_income_type',
  COLLECT_W2: 'collect_w2',
  COLLECT_BUSINESS_INCOME: 'collect_business_income',
  COLLECT_INVESTMENT_INCOME: 'collect_investment_income',
  COLLECT_RENTAL_INCOME: 'collect_rental_income',

  // Phase: deductions
  COLLECT_DEDUCTIONS: 'collect_deductions',
  COLLECT_MORTGAGE: 'collect_mortgage',
  COLLECT_CHARITABLE: 'collect_charitable',
  COLLECT_RETIREMENT: 'collect_retirement',

  // Phase: review
  REVIEW_SUMMARY: 'review_summary',
  EDIT_PROFILE: 'edit_profile',

  // Phase: ready_to_file
  GENERATE_REPORT: 'generate_report',
  CPA_HANDOFF: 'cpa_handoff',

  // Special states
  AI_CONVERSATION: 'ai_conversation',
  DOCUMENT_UPLOAD: 'document_upload',
  ERROR: 'error',
});

/** Map FSM states back to the 5-phase model used by the progress bar */
const STATE_TO_PHASE = {
  [AdvisorState.WELCOME]: 'personal_info',
  [AdvisorState.COLLECT_NAME]: 'personal_info',
  [AdvisorState.COLLECT_FILING_STATUS]: 'personal_info',
  [AdvisorState.COLLECT_INCOME_TYPE]: 'income',
  [AdvisorState.COLLECT_W2]: 'income',
  [AdvisorState.COLLECT_BUSINESS_INCOME]: 'income',
  [AdvisorState.COLLECT_INVESTMENT_INCOME]: 'income',
  [AdvisorState.COLLECT_RENTAL_INCOME]: 'income',
  [AdvisorState.COLLECT_DEDUCTIONS]: 'deductions',
  [AdvisorState.COLLECT_MORTGAGE]: 'deductions',
  [AdvisorState.COLLECT_CHARITABLE]: 'deductions',
  [AdvisorState.COLLECT_RETIREMENT]: 'deductions',
  [AdvisorState.REVIEW_SUMMARY]: 'review',
  [AdvisorState.EDIT_PROFILE]: 'review',
  [AdvisorState.GENERATE_REPORT]: 'ready_to_file',
  [AdvisorState.CPA_HANDOFF]: 'ready_to_file',
  [AdvisorState.AI_CONVERSATION]: null,  // doesn't change phase
  [AdvisorState.DOCUMENT_UPLOAD]: null,
  [AdvisorState.ERROR]: null,
};

/**
 * Check if a transition is valid.
 * @param {string} from - Current state
 * @param {string} to - Target state
 * @returns {boolean}
 */
function isValidTransition(from, to) {
  // AI_CONVERSATION, ERROR, and DOCUMENT_UPLOAD are reachable from any state
  if (to === AdvisorState.AI_CONVERSATION || to === AdvisorState.ERROR) return true;
  if (to === AdvisorState.DOCUMENT_UPLOAD) return true;

  // Normal forward flow: any state in the same or next phase is valid
  var phases = ['personal_info', 'income', 'deductions', 'review', 'ready_to_file'];
  var fromPhase = STATE_TO_PHASE[from];
  var toPhase = STATE_TO_PHASE[to];
  if (!fromPhase || !toPhase) return true;  // special states

  var fromIdx = phases.indexOf(fromPhase);
  var toIdx = phases.indexOf(toPhase);

  // Allow forward and same-phase, plus one-phase back (for edits)
  return toIdx >= fromIdx - 1;
}

// Export for both ES modules and script-tag usage
if (typeof window !== 'undefined') {
  window.AdvisorFSMStates = { AdvisorState: AdvisorState, STATE_TO_PHASE: STATE_TO_PHASE, isValidTransition: isValidTransition };
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { AdvisorState: AdvisorState, STATE_TO_PHASE: STATE_TO_PHASE, isValidTransition: isValidTransition };
}
