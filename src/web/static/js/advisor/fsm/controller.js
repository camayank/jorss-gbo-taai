/**
 * FSM Controller for the Intelligent Advisor.
 *
 * Manages current state, processes actions via the config table,
 * validates transitions, and emits events for the UI to react to.
 *
 * Usage:
 *   var fsm = new AdvisorFSM(extractedData);
 *   fsm.onTransition(function(from, to, action) { updateUI(to); });
 *   fsm.handleAction('filing_single');
 */

// Resolve dependencies from window globals (script-tag environment)
var _states = (typeof window !== 'undefined' && window.AdvisorFSMStates)
  ? window.AdvisorFSMStates
  : (typeof require !== 'undefined' ? require('./states.js') : {});

var _actionConfig = (typeof window !== 'undefined' && window.AdvisorFSMActionConfig)
  ? window.AdvisorFSMActionConfig
  : (typeof require !== 'undefined' ? require('./action-config.js') : {});

var AdvisorState = _states.AdvisorState || {};
var STATE_TO_PHASE = _states.STATE_TO_PHASE || {};
var isValidTransition = _states.isValidTransition || function() { return true; };
var ACTION_CONFIG = _actionConfig.ACTION_CONFIG || [];
var buildActionIndex = _actionConfig.buildActionIndex || function() { return { exact: {}, prefixes: [] }; };
var findActionEntry = _actionConfig.findActionEntry || function() { return null; };

/**
 * @constructor
 * @param {Object} data - Reference to extractedData (or Proxy-wrapped version)
 * @param {Object} [options]
 * @param {string} [options.initialState] - Starting state (default: WELCOME)
 */
function AdvisorFSM(data, options) {
  options = options || {};
  this.state = options.initialState || AdvisorState.WELCOME;
  this.data = data;
  this.history = [];
  this.listeners = { transition: [], error: [], phaseChange: [] };
  this.actionIndex = buildActionIndex(ACTION_CONFIG);
}

/** Get current state */
AdvisorFSM.prototype.getState = function() {
  return this.state;
};

/** Get current phase (for progress bar) */
AdvisorFSM.prototype.getPhase = function() {
  return STATE_TO_PHASE[this.state] || 'personal_info';
};

/**
 * Register event listener.
 * @param {string} event - 'transition', 'error', or 'phaseChange'
 * @param {Function} callback
 * @returns {Function} Unsubscribe function
 */
AdvisorFSM.prototype.on = function(event, callback) {
  if (this.listeners[event]) {
    this.listeners[event].push(callback);
  }
  var self = this;
  return function() {
    self.listeners[event] = self.listeners[event].filter(function(cb) {
      return cb !== callback;
    });
  };
};

/** Alias for on('transition', cb) */
AdvisorFSM.prototype.onTransition = function(callback) {
  return this.on('transition', callback);
};

/** Emit event to listeners */
AdvisorFSM.prototype._emit = function(event) {
  var args = Array.prototype.slice.call(arguments, 1);
  var callbacks = this.listeners[event] || [];
  for (var i = 0; i < callbacks.length; i++) {
    try {
      callbacks[i].apply(null, args);
    } catch (e) {
      console.error('[FSM] Listener error:', e);
    }
  }
};

/**
 * Process a quick-action value.
 * @param {string} actionValue - The value from the clicked button
 * @returns {{ handled: boolean, userMessage: string|null, toState: string|null, sideEffect: string|null, entry: Object|null }}
 */
AdvisorFSM.prototype.handleAction = function(actionValue) {
  // Handle comma-separated multi-select values
  if (actionValue.indexOf(',') !== -1) {
    // Multi-select: check if there's a prefix match for the first part
    var firstPart = actionValue.split(',')[0].trim();
    var entry = findActionEntry(this.actionIndex, firstPart, this.state);
    if (!entry) {
      // Try matching the full value as well
      entry = findActionEntry(this.actionIndex, actionValue, this.state);
    }
    if (!entry) {
      return { handled: false, userMessage: null, toState: null, sideEffect: null, entry: null };
    }
  } else {
    var entry = findActionEntry(this.actionIndex, actionValue, this.state);
  }

  if (!entry) {
    return { handled: false, userMessage: null, toState: null, sideEffect: null, entry: null };
  }

  // Validate transition if toState is specified
  if (entry.toState && !isValidTransition(this.state, entry.toState)) {
    this._emit('error', {
      type: 'invalid_transition',
      from: this.state,
      to: entry.toState,
      action: actionValue
    });
    return { handled: false, userMessage: null, toState: null, sideEffect: null, entry: null };
  }

  // Extract data
  if (entry.extract) {
    entry.extract(actionValue, this.data);
  }

  // Transition
  var fromState = this.state;
  var fromPhase = this.getPhase();

  if (entry.toState) {
    this.history.push(fromState);
    this.state = entry.toState;
  }

  var toPhase = this.getPhase();

  // Emit events
  this._emit('transition', fromState, this.state, actionValue);
  if (fromPhase !== toPhase && toPhase) {
    this._emit('phaseChange', fromPhase, toPhase);
  }

  // Resolve userMessage
  var userMessage = null;
  if (typeof entry.userMessage === 'function') {
    userMessage = entry.userMessage(actionValue);
  } else {
    userMessage = entry.userMessage;
  }

  return {
    handled: true,
    userMessage: userMessage,
    toState: this.state,
    sideEffect: entry.sideEffect || null,
    entry: entry
  };
};

/** Go back to previous state */
AdvisorFSM.prototype.goBack = function() {
  if (this.history.length === 0) return false;
  var prev = this.history.pop();
  var from = this.state;
  this.state = prev;
  this._emit('transition', from, prev, 'back');
  return true;
};

/** Force state (for session restore) */
AdvisorFSM.prototype.setState = function(newState) {
  var validStates = Object.values ? Object.values(AdvisorState) : Object.keys(AdvisorState).map(function(k) { return AdvisorState[k]; });
  if (validStates.indexOf(newState) !== -1) {
    var from = this.state;
    this.state = newState;
    this._emit('transition', from, newState, 'restore');
  }
};

/** Serialize for session persistence */
AdvisorFSM.prototype.toJSON = function() {
  return {
    state: this.state,
    history: this.history
  };
};

/**
 * Restore from serialized data.
 * @param {Object} json - { state, history }
 * @param {Object} data - extractedData reference
 * @param {Object} [options]
 * @returns {AdvisorFSM}
 */
AdvisorFSM.fromJSON = function(json, data, options) {
  options = options || {};
  options.initialState = json.state;
  var fsm = new AdvisorFSM(data, options);
  fsm.history = json.history || [];
  return fsm;
};

// Export
if (typeof window !== 'undefined') {
  window.AdvisorFSM = AdvisorFSM;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { AdvisorFSM: AdvisorFSM };
}
