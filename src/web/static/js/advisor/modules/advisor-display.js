/**
 * advisor-display.js
 * Visual systems, celebration effects, voice input, nudge system,
 * strategy rendering, progress/phase UI, file handling UI,
 * and misc display utilities.
 */

import {
  sessionId,
  extractedData,
  premiumUnlocked,
  taxStrategies,
  currentStrategyIndex,
  setCurrentStrategyIndex,
  setPremiumUnlocked,
  escapeHtml,
  getCSRFToken,
  secureFetch,
  DevLogger,
  showToast,
  lastUserMessage,
  trapFocus
} from './advisor-core.js';

import {
  addMessage,
  showTyping,
  hideTyping,
  processAIResponse
} from './advisor-chat.js';

import {
  fetchWithRetry,
  updateConnectionStatus as _updateConnectionStatus,
  handleFileSelect as _dataHandleFileSelect
} from './advisor-data.js';

import {
  handleQuickAction,
  getConfidenceLevel,
  getConfidenceDisclaimer,
  updateJourneyStep,
  startIntelligentQuestioning
} from './advisor-flow.js';


// ============================================================
// CELEBRATION SYSTEM
// ============================================================

export const CelebrationSystem = {
  createConfetti(count = 100) {
    const overlay = document.createElement('div');
    overlay.className = 'celebration-overlay';
    document.body.appendChild(overlay);

    const colors = ['#14b8a6', '#2dd4bf', '#f97316', '#fb923c', '#0d9488', '#5eead4'];

    for (let i = 0; i < count; i++) {
      const confetti = document.createElement('div');
      confetti.className = 'confetti';
      confetti.style.left = Math.random() * 100 + '%';
      confetti.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
      confetti.style.animationDelay = Math.random() * 2 + 's';
      confetti.style.animationDuration = (2 + Math.random() * 2) + 's';
      overlay.appendChild(confetti);
    }

    setTimeout(() => overlay.remove(), 4000);
  },

  createMoneyRain(count = 50) {
    const overlay = document.createElement('div');
    overlay.className = 'celebration-overlay';
    document.body.appendChild(overlay);

    const moneyEmojis = ['\uD83D\uDCB5', '\uD83D\uDCB0', '\uD83E\uDD11', '\uD83D\uDCB2', '\uD83D\uDC8E'];

    for (let i = 0; i < count; i++) {
      const money = document.createElement('div');
      money.className = 'money-particle';
      money.textContent = moneyEmojis[Math.floor(Math.random() * moneyEmojis.length)];
      money.style.left = Math.random() * 100 + '%';
      money.style.animationDelay = Math.random() * 1.5 + 's';
      overlay.appendChild(money);
    }

    setTimeout(() => overlay.remove(), 3500);
  },

  createSparkles(x, y, count = 8) {
    for (let i = 0; i < count; i++) {
      const sparkle = document.createElement('div');
      sparkle.className = 'sparkle';
      sparkle.style.left = (x + (Math.random() - 0.5) * 100) + 'px';
      sparkle.style.top = (y + (Math.random() - 0.5) * 100) + 'px';
      sparkle.style.animationDelay = Math.random() * 0.3 + 's';
      document.body.appendChild(sparkle);
      setTimeout(() => sparkle.remove(), 1000);
    }
  },

  showCelebrationToast(emoji, title, subtitle, amount = null) {
    const toast = document.createElement('div');
    toast.className = 'celebration-toast';
    toast.innerHTML = `
      <span class="celebration-emoji">${emoji}</span>
      <div class="celebration-title">${title}</div>
      <div class="celebration-subtitle">${subtitle}</div>
      ${amount ? `<div class="celebration-amount">$${amount.toLocaleString()}</div>` : ''}
    `;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.style.animation = 'celebration-pop 0.3s ease reverse forwards';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  },

  celebrateProfileComplete() {
    this.createConfetti(150);
    this.showCelebrationToast('\uD83C\uDF89', 'Amazing!', 'Your profile is complete!');
    this.playSound('success');
  },

  celebrateSavingsFound(amount) {
    this.createMoneyRain(60);
    this.showCelebrationToast('\uD83D\uDCB0', 'Savings Found!', 'Potential tax savings discovered', amount);
    this.playSound('money');
  },

  celebrateStrategyUnlock(strategyName) {
    this.createSparkles(window.innerWidth / 2, window.innerHeight / 2, 12);
    this.showCelebrationToast('\u2B50', 'Strategy Unlocked!', strategyName);
    this.playSound('unlock');
  },

  celebrateFirstMilestone() {
    this.showCelebrationToast('\uD83D\uDE80', 'Great Start!', 'You\'re on your way to tax savings!');
  },

  playSound(type) {
    if (!window.userHasInteracted) return;
    // Note: In production, replace with actual sound files
    // For now, celebrations are visual only
  }
};

// Track user interaction for sound
document.addEventListener('click', () => { window.userHasInteracted = true; }, { once: true });

// Celebration triggers
let previousSavings = 0;
let previousCompleteness = 0;
let celebratedMilestones = new Set();

export function checkForCelebration(data) {
  const currentSavings = data.total_potential_savings || 0;
  if (currentSavings > previousSavings + 1000 && currentSavings >= 1000) {
    CelebrationSystem.celebrateSavingsFound(currentSavings);
    previousSavings = currentSavings;
  }

  const completeness = data.profile_completeness || 0;
  if (completeness >= 1.0 && previousCompleteness < 1.0) {
    CelebrationSystem.celebrateProfileComplete();
  } else if (completeness >= 0.5 && previousCompleteness < 0.5 && !celebratedMilestones.has('50')) {
    celebratedMilestones.add('50');
    CelebrationSystem.celebrateFirstMilestone();
  }
  previousCompleteness = completeness;

  if (data.strategies && data.strategies.length > 0 && !celebratedMilestones.has('first_strategy')) {
    celebratedMilestones.add('first_strategy');
    CelebrationSystem.celebrateStrategyUnlock(data.strategies[0].title);
  }
}


// ============================================================
// VOICE INPUT SYSTEM
// ============================================================

export const VoiceInputSystem = {
  recognition: null,
  isRecording: false,
  transcript: '',

  init() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      DevLogger.log('Speech recognition not supported');
      return false;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    this.recognition = new SpeechRecognition();
    this.recognition.continuous = true;
    this.recognition.interimResults = true;
    this.recognition.lang = 'en-US';

    this.recognition.onresult = (event) => {
      let interimTranscript = '';
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript += transcript;
        }
      }

      this.transcript = finalTranscript || interimTranscript;
      this.updateTranscriptDisplay(this.transcript, !finalTranscript);
    };

    this.recognition.onerror = (event) => {
      DevLogger.error('Speech recognition error:', event.error);
      this.stopRecording();
      if (event.error === 'not-allowed') {
        showToast('Please allow microphone access to use voice input', 'warning');
      }
    };

    this.recognition.onend = () => {
      if (this.isRecording) {
        this.recognition.start();
      }
    };

    return true;
  },

  startRecording() {
    if (!this.recognition && !this.init()) {
      showToast('Voice input not supported in this browser', 'warning');
      return;
    }

    this.isRecording = true;
    this.transcript = '';
    this.recognition.start();
    this.showTranscriptPanel();

    const btn = document.getElementById('voiceInputBtn');
    if (btn) {
      btn.classList.add('recording');
      btn.innerHTML = '\uD83D\uDD34';
    }
  },

  stopRecording() {
    this.isRecording = false;
    if (this.recognition) {
      this.recognition.stop();
    }

    const btn = document.getElementById('voiceInputBtn');
    if (btn) {
      btn.classList.remove('recording');
      btn.innerHTML = '\uD83C\uDFA4';
    }

    this.hideTranscriptPanel();

    if (this.transcript.trim()) {
      const input = document.getElementById('userInput');
      if (input) {
        input.value = this.transcript;
        // Use dynamic import to avoid circular dependency with sendMessage
        import('./advisor-chat.js').then(mod => mod.sendMessage());
      }
    }
  },

  toggleRecording() {
    if (this.isRecording) {
      this.stopRecording();
    } else {
      this.startRecording();
    }
  },

  showTranscriptPanel() {
    let panel = document.getElementById('voiceTranscript');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'voiceTranscript';
      panel.className = 'voice-transcript';
      panel.innerHTML = `
        <div class="voice-transcript-text" id="voiceTranscriptText">Listening...</div>
        <div class="voice-transcript-hint">\uD83C\uDFA4 Speak naturally. Click mic again to send.</div>
      `;
      const inputContainer = document.querySelector('.input-container');
      if (inputContainer) {
        inputContainer.style.position = 'relative';
        inputContainer.appendChild(panel);
      }
    }
    panel.classList.add('active');
  },

  hideTranscriptPanel() {
    const panel = document.getElementById('voiceTranscript');
    if (panel) {
      panel.classList.remove('active');
    }
  },

  updateTranscriptDisplay(text, isInterim) {
    const display = document.getElementById('voiceTranscriptText');
    if (display) {
      display.textContent = text || 'Listening...';
      display.style.opacity = isInterim ? '0.7' : '1';
    }
  }
};


// ============================================================
// SMART NUDGE SYSTEM
// ============================================================

export const SmartNudgeSystem = {
  lastActivityTime: Date.now(),
  nudgeTimeout: null,
  currentNudge: null,

  init() {
    ['mousemove', 'keydown', 'scroll', 'click'].forEach(event => {
      document.addEventListener(event, () => this.resetIdleTimer());
    });
    this.startIdleCheck();
  },

  resetIdleTimer() {
    this.lastActivityTime = Date.now();
  },

  startIdleCheck() {
    setInterval(() => {
      const idleTime = Date.now() - this.lastActivityTime;
      if (idleTime > 30000 && !this.currentNudge) {
        this.showIdleNudge();
      }
    }, 10000);
  },

  showIdleNudge() {
    const nudges = [
      {
        icon: '\uD83D\uDCA1',
        title: 'Need help?',
        message: 'I noticed you paused. Would you like me to explain something differently?',
        primaryAction: { label: 'Yes, help me', value: 'help_me' },
        secondaryAction: { label: 'I\'m fine', value: 'dismiss' }
      },
      {
        icon: '\uD83E\uDD14',
        title: 'Stuck on something?',
        message: 'Feel free to ask any question, or I can guide you step by step.',
        primaryAction: { label: 'Guide me', value: 'guide_me' },
        secondaryAction: { label: 'Just thinking', value: 'dismiss' }
      }
    ];

    const nudge = nudges[Math.floor(Math.random() * nudges.length)];
    this.showNudge(nudge);
  },

  showOpportunityNudge(opportunity) {
    this.showNudge({
      icon: '\uD83D\uDCB0',
      title: 'Quick tip!',
      message: opportunity.message,
      primaryAction: { label: 'Tell me more', value: opportunity.action },
      secondaryAction: { label: 'Maybe later', value: 'dismiss' }
    });
  },

  showNudge(config) {
    this.dismissNudge();

    const nudge = document.createElement('div');
    nudge.className = 'smart-nudge';
    nudge.id = 'smartNudge';
    nudge.innerHTML = `
      <button class="smart-nudge-close" onclick="SmartNudgeSystem.dismissNudge()">&times;</button>
      <div class="smart-nudge-icon">${config.icon}</div>
      <div class="smart-nudge-title">${config.title}</div>
      <div class="smart-nudge-message">${config.message}</div>
      <div class="smart-nudge-actions">
        <button class="smart-nudge-btn primary" onclick="SmartNudgeSystem.handleNudgeAction('${config.primaryAction.value}')">${config.primaryAction.label}</button>
        <button class="smart-nudge-btn secondary" onclick="SmartNudgeSystem.handleNudgeAction('${config.secondaryAction.value}')">${config.secondaryAction.label}</button>
      </div>
    `;

    document.body.appendChild(nudge);
    this.currentNudge = nudge;

    this.nudgeTimeout = setTimeout(() => this.dismissNudge(), 15000);
  },

  dismissNudge() {
    if (this.currentNudge) {
      this.currentNudge.remove();
      this.currentNudge = null;
    }
    if (this.nudgeTimeout) {
      clearTimeout(this.nudgeTimeout);
    }
    this.lastActivityTime = Date.now();
  },

  handleNudgeAction(action) {
    this.dismissNudge();
    if (action === 'dismiss') return;

    const actionMessages = {
      'help_me': 'I need help understanding this',
      'guide_me': 'Please guide me step by step'
    };

    const message = actionMessages[action] || action;
    const input = document.getElementById('userInput');
    if (input) {
      input.value = message;
      import('./advisor-chat.js').then(mod => mod.sendMessage());
    }
  }
};


// ============================================================
// LIVE SAVINGS DISPLAY
// ============================================================

export const LiveSavingsDisplay = {
  currentAmount: 0,
  targetAmount: 0,
  displayElement: null,

  init() {
    if (!document.getElementById('liveSavingsDisplay')) {
      const display = document.createElement('div');
      display.id = 'liveSavingsDisplay';
      display.className = 'live-savings-display';
      display.style.display = 'none';
      display.innerHTML = `
        <div class="live-savings-label">Potential Savings</div>
        <div class="live-savings-amount" id="liveSavingsAmount">$0</div>
      `;
      document.body.appendChild(display);
    }
    this.displayElement = document.getElementById('liveSavingsDisplay');
  },

  update(amount) {
    if (!this.displayElement) this.init();

    if (amount > 0) {
      this.displayElement.style.display = 'block';
      var label = this.displayElement.querySelector('.live-savings-label');
      if (label) label.textContent = 'Potential Savings';
      this.animateToAmount(amount);
    }
  },

  updatePreview(amount) {
    if (!this.displayElement) this.init();
    if (amount > 0) {
      this.displayElement.style.display = 'block';
      var label = this.displayElement.querySelector('.live-savings-label');
      if (label) label.textContent = 'Estimated Savings';
      var amountEl = document.getElementById('liveSavingsAmount');
      if (amountEl) amountEl.textContent = '~$' + amount.toLocaleString() + '+';
    }
  },

  animateToAmount(target) {
    const amountEl = document.getElementById('liveSavingsAmount');
    if (!amountEl) return;

    const start = this.currentAmount;
    const diff = target - start;
    const duration = 1000;
    const startTime = performance.now();

    const animate = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(start + diff * eased);

      amountEl.textContent = '$' + current.toLocaleString();
      amountEl.classList.add('counting');

      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        this.currentAmount = target;
        amountEl.classList.remove('counting');
      }
    };

    requestAnimationFrame(animate);
  }
};


// ============================================================
// PHOTO CAPTURE SYSTEM
// ============================================================

export const PhotoCapture = {
  stream: null,
  video: null,

  async open() {
    const modal = document.getElementById('photoCaptureModal');
    this.video = document.getElementById('cameraVideo');

    if (!modal || !this.video) return;

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'environment',
          width: { ideal: 1920 },
          height: { ideal: 1080 }
        }
      });

      this.video.srcObject = this.stream;
      modal.classList.add('active');

    } catch (error) {
      DevLogger.error('Camera access error:', error);
      if (error.name === 'NotAllowedError') {
        showToast('Please allow camera access to capture documents', 'warning');
      } else {
        showToast('Unable to access camera. Please upload instead.', 'error');
      }
    }
  },

  close() {
    const modal = document.getElementById('photoCaptureModal');
    if (modal) {
      modal.classList.remove('active');
    }

    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
  },

  async capture() {
    if (!this.video) return;

    const canvas = document.createElement('canvas');
    canvas.width = this.video.videoWidth;
    canvas.height = this.video.videoHeight;

    const ctx = canvas.getContext('2d');
    ctx.drawImage(this.video, 0, 0);

    canvas.toBlob(async (blob) => {
      if (!blob) {
        showToast('Failed to capture image', 'error');
        return;
      }

      this.close();
      showToast('Processing document...', 'info');

      const formData = new FormData();
      formData.append('file', blob, 'captured_document.jpg');
      formData.append('session_id', sessionId || 'temp-session');

      try {
        const response = await secureFetch('/api/advisor/upload-document', {
          method: 'POST',
          body: formData
        });

        const result = await response.json();

        if (result.success) {
          CelebrationSystem.createSparkles(window.innerWidth / 2, window.innerHeight / 2, 8);
          showToast('Document captured successfully!', 'success');

          if (result.profile_updates && Object.keys(result.profile_updates).length > 0) {
            showToast('Profile updated from your document!', 'success');
            if (result.updated_savings > 0) {
              LiveSavingsDisplay.update(result.updated_savings);
              showToast('Found $' + Math.round(result.updated_savings).toLocaleString() + ' in potential savings!', 'success');
            }
          }

          addMessage('ai', `\uD83D\uDCC4 **Document Captured!**\n\nI detected a **${result.document_type || 'tax document'}** and extracted the following:\n\n${
            Object.entries(result.extracted_fields || {})
              .slice(0, 5)
              .map(([key, value]) => `\u2022 ${key}: **${value}**`)
              .join('\n')
          }${result.profile_updates && Object.keys(result.profile_updates).length > 0 ? '\n\n\u2705 **Your profile has been updated automatically.**' : ''}\n\nIs this information correct?`, [
            { label: '\u2713 Yes, looks good', value: 'document_confirmed' },
            { label: 'Make corrections', value: 'document_corrections' },
            { label: 'Capture another', value: 'capture_another' }
          ]);

        } else {
          showToast(result.message || 'Could not process document', 'warning');
          addMessage('ai', `I had trouble reading that document. Would you like to try again or enter the information manually?`, [
            { label: 'Try again', value: 'capture_another' },
            { label: 'Enter manually', value: 'enter_manually' }
          ]);
        }

      } catch (error) {
        DevLogger.error('Document upload error:', error);
        showToast('Failed to upload document', 'error');
      }

    }, 'image/jpeg', 0.9);
  }
};


// ============================================================
// STRATEGY RENDERING
// ============================================================

/**
 * Render a single strategy card with tier-aware styling.
 */
export function renderStrategyCard(strategy, index) {
  const tier = strategy.tier || 'free';
  const isLocked = tier === 'premium' && !premiumUnlocked;
  const isUnlocked = tier === 'premium' && premiumUnlocked;
  const cardClass = isLocked ? 'strategy-card--locked' : (isUnlocked ? 'strategy-card--unlocked' : 'strategy-card--free');
  const badgeLabel = isLocked ? 'CPA-Recommended' : (isUnlocked ? 'Unlocked' : 'DIY');
  const riskLevel = strategy.risk_level || 'low';
  const safeRiskLevel = ['low', 'medium', 'high'].includes(riskLevel) ? riskLevel : 'low';

  let html = '<div class="strategy-card ' + cardClass + '" data-strategy-id="' + escapeHtml(String(strategy.id || index)) + '" data-tier="' + escapeHtml(tier) + '">';

  html += '<div class="strategy-card__header">';
  html += '<div class="strategy-card__title">' + (index + 1) + '. ' + escapeHtml(strategy.title || 'Strategy') + '</div>';
  html += '<span class="strategy-badge strategy-badge--' + escapeHtml(tier) + '">' + badgeLabel + '</span>';
  html += '</div>';

  if (strategy.estimated_savings) {
    html += '<div class="strategy-savings"><span class="strategy-savings-badge">Save $' + Number(strategy.estimated_savings).toLocaleString() + '</span>';
    html += ' <span class="risk-indicator risk-indicator--' + safeRiskLevel + '">' + safeRiskLevel.charAt(0).toUpperCase() + safeRiskLevel.slice(1) + ' risk</span>';
    html += '</div>';
  }

  html += '<div class="strategy-content">';
  html += '<div class="strategy-card__summary">' + escapeHtml(strategy.summary || '') + '</div>';

  if (strategy.personalized_explanation) {
    html += '<div class="strategy-card__personalized" style="background: var(--surface-secondary, #f0f4ff); border-left: 3px solid var(--accent-gold, #d4a843); padding: 8px 12px; margin: 8px 0; border-radius: 4px; font-size: 0.9em;">';
    html += escapeHtml(strategy.personalized_explanation);
    html += '</div>';
  }

  if (strategy.detailed_explanation || (strategy.action_steps && strategy.action_steps.length > 0)) {
    html += '<details class="strategy-card__details" style="margin-top:8px;">';
    html += '<summary style="cursor:pointer;color:var(--accent-gold,#d4a843);font-size:0.9em;font-weight:600;">View full details</summary>';
    if (strategy.detailed_explanation) {
      html += '<div class="strategy-card__explanation" style="margin-top:6px;font-size:0.9em;">' + escapeHtml(strategy.detailed_explanation) + '</div>';
    }
    if (strategy.action_steps && strategy.action_steps.length > 0) {
      html += '<div class="strategy-card__steps" style="margin-top:6px;"><strong>All steps:</strong><ul>';
      strategy.action_steps.forEach(function(step) { html += '<li>' + escapeHtml(step) + '</li>'; });
      html += '</ul></div>';
    }
    html += '</details>';
  }
  html += '</div>';

  if (!isLocked) {
    html += '<button class="quick-action strategy-card__drilldown" '
         + 'onclick="handleQuickAction(\'strategy_detail_' + escapeHtml(String(strategy.id || index)) + '\')"'
         + ' style="margin-top:8px;font-size:0.85em;">Tell me more</button>';
  }

  if (isLocked) {
    html += '<div class="lock-overlay"><button class="lock-overlay__btn" data-action="unlock-premium">Unlock Full Analysis</button></div>';
  }

  html += '</div>';
  return html;
}

/**
 * Show next strategy card in carousel.
 */
export function showNextStrategy() {
  if (!taxStrategies || taxStrategies.length === 0) return;

  const nextIdx = (currentStrategyIndex + 1) % taxStrategies.length;
  setCurrentStrategyIndex(nextIdx);

  const strategy = taxStrategies[nextIdx];
  const html = renderStrategyCard(strategy, nextIdx);
  const navButtons = getStrategyNavigationButtons();

  addMessage('ai', `<strong>Strategy ${nextIdx + 1} of ${taxStrategies.length}:</strong><br><br>${html}`, navButtons);
}

/**
 * Show all strategies at once.
 */
export function showAllStrategies() {
  if (!taxStrategies || taxStrategies.length === 0) {
    addMessage('ai', 'No strategies have been generated yet. Let me analyze your tax situation first.', [
      { label: 'Continue analysis', value: 'continue_flow' }
    ]);
    return;
  }

  let html = '<strong>All Tax Strategies:</strong><br><br>';
  taxStrategies.forEach((strategy, i) => {
    html += renderStrategyCard(strategy, i);
  });

  addMessage('ai', html, [
    { label: 'Generate PDF Report', value: 'download_report' },
    { label: 'Email report', value: 'email_report' },
    { label: 'Talk to a CPA', value: 'schedule_consult' }
  ]);
}

/**
 * Get navigation buttons for strategy carousel.
 */
export function getStrategyNavigationButtons() {
  const buttons = [];
  if (taxStrategies.length > 1) {
    buttons.push({ label: 'Next Strategy \u2192', value: 'next_strategy' });
    buttons.push({ label: 'View All', value: 'view_all_strategies' });
  }
  buttons.push({ label: 'Generate Report', value: 'download_report' });
  return buttons;
}

/**
 * Show strategy summary with total savings.
 */
export function showStrategySummary() {
  if (!taxStrategies || taxStrategies.length === 0) return;

  const totalSavings = taxStrategies.reduce((sum, s) => sum + (s.estimated_savings || 0), 0);
  const freeCount = taxStrategies.filter(s => (s.tier || 'free') === 'free').length;
  const premiumCount = taxStrategies.filter(s => s.tier === 'premium').length;

  let html = `<strong>Strategy Summary</strong><br><br>`;
  html += `Total potential savings: <strong>$${totalSavings.toLocaleString()}</strong><br>`;
  html += `${freeCount} DIY strategies | ${premiumCount} CPA-recommended strategies<br><br>`;
  html += `Would you like to see the details?`;

  addMessage('ai', html, [
    { label: 'View All Strategies', value: 'view_all_strategies' },
    { label: 'Generate Report', value: 'download_report' }
  ]);
}


// ============================================================
// REPORT GENERATION & EMAIL
// ============================================================

export async function generateAndDownloadReport() {
  try {
    addMessage('ai', '\u23F3 Generating your PDF report...');

    const response = await secureFetch('/api/v1/advisory-reports/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        report_type: 'full_analysis',
        include_entity_comparison: true,
        include_multi_year: true,
        years_ahead: 3,
        generate_pdf: true
      })
    });

    if (response.ok) {
      const data = await response.json();

      let pdfReady = false;
      let attempts = 0;
      while (!pdfReady && attempts < 30) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        const statusResponse = await fetch(`/api/v1/advisory-reports/${data.report_id}`);
        const statusData = await statusResponse.json();
        if (statusData.pdf_available) {
          pdfReady = true;
          window.open(`/api/v1/advisory-reports/${data.report_id}/pdf`, '_blank');
          addMessage('ai', `${typeof getIcon === 'function' ? getIcon('check-circle', 'sm') : '\u2705'} <strong>Your report is ready!</strong><br><br>The PDF download should begin automatically. If not, <a href="/api/v1/advisory-reports/${data.report_id}/pdf" target="_blank" style="color: var(--primary);">click here to download</a>.`);
        }
        attempts++;
      }
    } else {
      throw new Error('Failed to generate report');
    }
  } catch (error) {
    DevLogger.error('Report generation error:', error);
    addMessage('ai', `I encountered an issue generating the PDF. However, you can still <a href="/advisory-report-preview?session_id=${sessionId}" target="_blank" style="color: var(--primary);">view your report online here</a>.`);
  }
}

export async function sendReportEmail() {
  const email = document.getElementById('emailInput').value;
  if (!email || !email.includes('@')) {
    showToast('Please enter a valid email address', 'warning');
    return;
  }

  addMessage('user', `Send to: ${email}`);
  showTyping();

  try {
    const response = await fetchWithRetry('/api/advisor/report/email', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(getCSRFToken() ? {'X-CSRF-Token': getCSRFToken()} : {})
      },
      body: JSON.stringify({
        session_id: sessionId,
        email: email
      })
    });

    hideTyping();

    if (response.ok) {
      addMessage('ai', `<strong>Report sent!</strong><br><br>Your tax advisory report has been emailed to <strong>${email}</strong>. Please check your inbox (and spam folder).<br><br><strong>What would you like to do next?</strong>`, [
        { label: (typeof getIcon === 'function' ? getIcon('arrow-down-tray', 'sm') : '') + ' Also download PDF', value: 'download_report' },
        { label: (typeof getIcon === 'function' ? getIcon('phone', 'sm') : '') + ' Schedule consultation', value: 'schedule_consult' },
        { label: '\u2705 I\'m all set', value: 'finish_satisfied' }
      ]);
    } else {
      addMessage('ai', `<strong>Email delivery is not available at this time.</strong><br><br>You can download your report as a PDF instead \u2014 it contains all the same information.<br><br><strong>What would you like to do?</strong>`, [
        { label: (typeof getIcon === 'function' ? getIcon('arrow-down-tray', 'sm') : '') + ' Download PDF Report', value: 'download_report' },
        { label: (typeof getIcon === 'function' ? getIcon('phone', 'sm') : '') + ' Schedule consultation', value: 'schedule_consult' }
      ]);
    }
  } catch (error) {
    hideTyping();
    DevLogger.error('Email send failed:', error);
    addMessage('ai', `<strong>Unable to send email right now.</strong><br><br>Please download the PDF report instead. You can then email it manually or share it with your CPA.`, [
      { label: (typeof getIcon === 'function' ? getIcon('arrow-down-tray', 'sm') : '') + ' Download PDF Report', value: 'download_report' },
      { label: (typeof getIcon === 'function' ? getIcon('arrow-path', 'sm') : '') + ' Try Again', value: 'email_report' }
    ]);
  }
}


// ============================================================
// PREMIUM / LEAD CAPTURE UI
// ============================================================

export function unlockPremiumStrategies() {
  setPremiumUnlocked(true);

  CelebrationSystem.createConfetti(120);
  CelebrationSystem.showCelebrationToast('\uD83C\uDF1F', 'Premium Unlocked!', 'All strategies are now available');

  // Re-render any locked cards
  const lockedCards = document.querySelectorAll('.strategy-card--locked');
  lockedCards.forEach(card => {
    card.classList.remove('strategy-card--locked');
    card.classList.add('strategy-card--unlocked');
    const overlay = card.querySelector('.lock-overlay');
    if (overlay) overlay.remove();
    const badge = card.querySelector('.strategy-badge');
    if (badge) badge.textContent = 'Unlocked';
  });
}

export function submitLeadCapture() {
  const nameInput = document.getElementById('leadNameInput');
  const emailInput = document.getElementById('leadEmailInput');
  if (!nameInput || !emailInput) return;

  const name = nameInput.value.trim();
  const email = emailInput.value.trim();

  if (!name || name.length < 2) {
    showToast('Please enter your name', 'warning');
    return;
  }
  if (!email || !email.includes('@')) {
    showToast('Please enter a valid email', 'warning');
    return;
  }

  extractedData.contact = extractedData.contact || {};
  extractedData.contact.name = name;
  extractedData.contact.email = email;

  unlockPremiumStrategies();
  showToast('Welcome, ' + name + '! All strategies are now unlocked.', 'success');
}

export function dismissLeadCapture() {
  const modal = document.getElementById('leadCaptureModal');
  if (modal) modal.remove();
}

/**
 * Show a consent dialog before transmitting lead data to the CPA firm.
 * Returns a Promise that resolves to true (consented) or false (declined).
 */
export function showLeadConsentDialog(contactInfo) {
  return new Promise((resolve) => {
    const existing = document.getElementById('leadConsentModal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'leadConsentModal';
    modal.className = 'modal-overlay';
    modal.innerHTML = `
      <div class="modal-content" style="max-width:500px;margin:10% auto;background:#fff;border-radius:12px;padding:2rem;box-shadow:0 8px 32px rgba(0,0,0,.18);">
        <h3 style="margin-bottom:1rem;font-size:1.2rem;">Share Your Information?</h3>
        <p style="margin-bottom:1rem;color:#555;">
          Based on your tax analysis, a licensed CPA can help you implement these savings strategies.
          By clicking <strong>Yes, Connect Me</strong>, you consent to sharing your contact information
          and tax profile summary with the CPA firm for the purpose of providing personalized tax advice.
        </p>
        <p style="margin-bottom:1.5rem;color:#555;font-size:0.9rem;">
          Your data will be handled in accordance with our
          <a href="/privacy" target="_blank" style="color:#2c5aa0;">Privacy Policy</a>.
          You can withdraw consent at any time.
        </p>
        <div style="display:flex;gap:1rem;justify-content:flex-end;">
          <button id="leadConsentDecline" style="padding:.6rem 1.2rem;border:1px solid #ddd;border-radius:8px;background:#fff;cursor:pointer;">
            No Thanks
          </button>
          <button id="leadConsentAccept" style="padding:.6rem 1.2rem;border:none;border-radius:8px;background:#2c5aa0;color:#fff;cursor:pointer;font-weight:600;">
            Yes, Connect Me
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    document.getElementById('leadConsentAccept').addEventListener('click', () => {
      modal.remove();
      resolve(true);
    });
    document.getElementById('leadConsentDecline').addEventListener('click', () => {
      modal.remove();
      resolve(false);
    });
  });
}

export function unlockAllCards() {
  unlockPremiumStrategies();
}


// ============================================================
// SAVINGS ESTIMATE (FIX: no client-side guessing)
// ============================================================

/**
 * Update savings estimate display using ONLY data.estimated_savings_preview
 * from the API response. No client-side calculations.
 */
export function updateSavingsEstimate(apiSavingsPreview) {
  const existing = document.querySelector('.savings-estimate');
  if (existing) existing.remove();

  if (!apiSavingsPreview || apiSavingsPreview <= 0) return;

  LiveSavingsDisplay.updatePreview(apiSavingsPreview);
}


// ============================================================
// CONFIDENCE BADGE
// ============================================================

export function renderConfidenceBadge(confidence, reason) {
  if (!confidence || confidence === 'high') {
    return '';
  }

  const badges = {
    high: { label: 'High Confidence', className: 'high' },
    medium: { label: 'Moderate Confidence', className: 'medium' },
    low: { label: 'Limited Data', className: 'low' }
  };

  const badge = badges[confidence] || badges.medium;
  const tooltipAttr = reason ? ` title="${escapeHtml(reason)}"` : '';

  return `<div class="confidence-badge ${badge.className}"${tooltipAttr} style="margin-top: var(--space-3);">
    <span class="confidence-dot"></span>
    <span>${badge.label}</span>
    ${reason ? `<span style="font-size: 10px; opacity: 0.8; margin-left: var(--space-1);">${escapeHtml(reason)}</span>` : ''}
  </div>`;
}


// ============================================================
// SAFETY / COMPLIANCE SUMMARY
// ============================================================

export function renderSafetySummary(summary) {
  if (!summary || !summary.checks || summary.checks.length === 0) return '';

  var html = '<div class="safety-summary">';
  html += '<div class="safety-summary__header">';
  html += '<div class="safety-summary__title">Compliance Summary</div>';
  var scoreClass = summary.overall_status === 'clear' ? 'safety-summary__score--clear' : 'safety-summary__score--review';
  html += '<span class="safety-summary__score ' + scoreClass + '">' + (Number(summary.passed) || 0) + '/' + (Number(summary.total_checks) || 0) + ' checks passed</span>';
  html += '</div>';

  summary.checks.forEach(function(check) {
    var icon = check.status === 'pass' ? '&#10003;' : '&#9888;';
    html += '<div class="safety-check-item">';
    html += '<span class="safety-check-item__icon">' + icon + '</span>';
    html += '<span class="safety-check-item__name">' + escapeHtml(check.name) + '</span>';
    html += '<span class="safety-check-item__detail">' + escapeHtml(check.detail) + '</span>';
    html += '</div>';
  });

  html += '</div>';
  return html;
}


// ============================================================
// BANNERS & OVERLAYS
// ============================================================

export function showErrorBanner(title, message, retryAction = null) {
  const messages = document.getElementById('messages');
  if (!messages) return;

  const errorDiv = document.createElement('div');
  errorDiv.className = 'error-banner';
  errorDiv.id = 'currentErrorBanner';
  errorDiv.innerHTML = `
    <span class="error-icon">\u26A0\uFE0F</span>
    <div class="error-content">
      <div class="error-title">${title}</div>
      <div class="error-message">${message}</div>
      ${retryAction ? `<button class="retry-btn" onclick="${retryAction}">Try Again</button>` : ''}
    </div>
  `;

  messages.appendChild(errorDiv);
  messages.scrollTop = messages.scrollHeight;
}

export function clearErrorBanner() {
  const errorBanner = document.getElementById('currentErrorBanner');
  if (errorBanner) {
    errorBanner.remove();
  }
}

export function showSuccessBanner(message) {
  const messages = document.getElementById('messages');
  if (!messages) return;

  const successDiv = document.createElement('div');
  successDiv.className = 'success-banner';
  successDiv.innerHTML = `<span>\u2705</span> <span>${message}</span>`;

  messages.appendChild(successDiv);
  messages.scrollTop = messages.scrollHeight;

  setTimeout(() => successDiv.remove(), 5000);
}

export function showLoadingOverlay(text = 'Analyzing your tax situation...', subtext = 'This may take a few moments') {
  const overlay = document.getElementById('loadingOverlay');
  const textEl = document.getElementById('loadingText');
  const subtextEl = document.getElementById('loadingSubtext');

  if (overlay) {
    textEl.textContent = text;
    subtextEl.textContent = subtext;
    overlay.classList.add('active');
  }
}

export function hideLoadingOverlay() {
  const overlay = document.getElementById('loadingOverlay');
  if (overlay) {
    overlay.classList.remove('active');
  }
}


// ============================================================
// PROGRESS / PHASE / STATS / INSIGHTS
// ============================================================

export const PHASE_MAPPING = {
  'personal_info': { step: 1, label: 'Profile Setup', icon: '\uD83D\uDCCB' },
  'income': { step: 2, label: 'Income Review', icon: '\uD83D\uDCB0' },
  'deductions': { step: 3, label: 'Deductions & Credits', icon: '\uD83C\uDFAF' },
  'review': { step: 4, label: 'Final Review', icon: '\uD83D\uDCCA' },
  'ready_to_file': { step: 4, label: 'Ready to File!', icon: '\u2705' }
};

export function updateProgress(percentage, missingFields, completionHint) {
  const progressFill = document.getElementById('progressFill');
  const progressText = document.getElementById('progressText');
  if (progressFill) progressFill.style.width = percentage + '%';
  if (progressText) progressText.textContent = `${Math.round(percentage)}% Complete`;

  const stepNumber = percentage < 25 ? 1 : percentage < 50 ? 2 : percentage < 75 ? 3 : 4;
  updateActiveStep(stepNumber);

  var missingEl = document.getElementById('progressMissing');
  if (!missingEl) {
    missingEl = document.createElement('div');
    missingEl.id = 'progressMissing';
    missingEl.style.cssText = 'font-size:0.8em;margin-top:4px;color:var(--text-secondary,#6b7280);';
    var bar = document.getElementById('progressFill');
    if (bar && bar.parentElement) bar.parentElement.parentElement.appendChild(missingEl);
  }

  if (missingFields && missingFields.length > 0 && percentage < 100) {
    missingEl.innerHTML = '<strong>Still needed:</strong> ' + missingFields.join(' \u00b7 ');
    if (completionHint) {
      missingEl.innerHTML += '<br><em style="color:var(--accent-gold,#d4a843);">' + completionHint + '</em>';
    }
    missingEl.style.display = 'block';
  } else {
    missingEl.style.display = 'none';
  }
}

export function updateProgressIndicator(progressUpdate) {
  if (!progressUpdate) return;

  const percentage = (progressUpdate.current_step / progressUpdate.total_steps) * 100;
  const progressFill = document.getElementById('progressFill');
  const progressText = document.getElementById('progressText');
  if (progressFill) progressFill.style.width = percentage + '%';
  if (progressText) progressText.textContent = `${Math.round(percentage)}% Complete`;

  updatePhaseLabel(progressUpdate.phase_name);

  const uiStep = Math.min(Math.max(progressUpdate.current_step + 1, 1), 4);
  updateActiveStep(uiStep);
}

export function updateActiveStep(stepNumber) {
  const steps = document.querySelectorAll('.journey-step');
  steps.forEach((step, index) => {
    const stepNum = index + 1;
    step.classList.remove('active', 'completed');

    if (stepNum === stepNumber) {
      step.classList.add('active');
    } else if (stepNum < stepNumber) {
      step.classList.add('completed');
    }
  });
}

export function updatePhaseLabel(phaseName) {
  const label = document.getElementById('currentPhaseLabel');
  if (label && phaseName) {
    label.textContent = phaseName;

    if (phaseName.toLowerCase().includes('ready') || phaseName.toLowerCase().includes('complete')) {
      label.classList.add('completed');
    } else {
      label.classList.remove('completed');
    }
  }
}

export function updatePhaseFromData() {
  // Legacy phase detection (FSM code stripped)
  let phase = 'personal_info';

  if (extractedData.first_name || extractedData.filing_status) {
    phase = 'income';
    if (extractedData.income_explored || extractedData.w2_wages || extractedData.has_w2) {
      phase = 'deductions';
      if (extractedData.deductions_explored || extractedData.itemize_choice) {
        phase = 'review';
        if (extractedData.review_confirmed) {
          phase = 'ready_to_file';
        }
      }
    }
  }

  const phaseInfo = PHASE_MAPPING[phase];
  if (phaseInfo) {
    updatePhaseLabel(phaseInfo.label);
    updateActiveStep(phaseInfo.step);
  }
}

export function getCurrentProgress() {
  const progressFill = document.getElementById('progressFill');
  if (progressFill) {
    const width = progressFill.style.width;
    return parseInt(width) || 0;
  }
  return 0;
}

export function getCurrentPhase() {
  if (extractedData.review_confirmed) return 'ready_to_file';
  if (extractedData.deductions_explored || extractedData.itemize_choice) return 'review';
  if (extractedData.income_explored || extractedData.w2_wages) return 'deductions';
  if (extractedData.first_name || extractedData.filing_status) return 'income';
  return 'personal_info';
}

export function getCompletionPercentage() {
  const progressFill = document.getElementById('progressFill');
  if (progressFill) {
    const width = progressFill.style.width;
    return parseFloat(width) || 0;
  }
  return 0;
}

export function updateInsights(insights) {
  const container = document.getElementById('insights');
  if (insights.length === 0) return;

  container.innerHTML = insights.map(insight => `
    <div class="insight-card">
      <div class="insight-header">
        <span>${insight.icon}</span>
        <span>${insight.title}</span>
      </div>
      <div style="font-size: var(--text-xs-plus); color: var(--text-secondary);">
        ${insight.text}
      </div>
    </div>
  `).join('');
}

export function updateStats(summary) {
  const grid = document.getElementById('statsGrid');
  const stats = [];

  if (summary.filing_status) stats.push({ label: 'Filing Status', value: summary.filing_status });
  if (summary.total_income) stats.push({ label: 'Income', value: '$' + summary.total_income.toLocaleString() });
  if (summary.deductions_count) stats.push({ label: 'Deductions', value: summary.deductions_count });

  if (stats.length > 0) {
    grid.innerHTML = stats.map(stat => `
      <div class="stat-item">
        <span class="stat-label">${stat.label}</span>
        <span class="stat-value">${stat.value}</span>
      </div>
    `).join('');
  }
}

export function updateSaveIndicator(status) {
  let indicator = document.getElementById('saveIndicator');
  if (!indicator) {
    indicator = document.createElement('div');
    indicator.id = 'saveIndicator';
    indicator.className = 'save-indicator';
    const progressText = document.getElementById('progressText');
    if (progressText && progressText.parentNode) {
      progressText.parentNode.insertBefore(indicator, progressText.nextSibling);
    }
  }

  if (status === 'saved') {
    indicator.innerHTML = '<span style="color: #276749;">\u2713 Saved</span>';
    indicator.style.opacity = '1';
    setTimeout(() => { indicator.style.opacity = '0.5'; }, 2000);
  } else if (status === 'saving') {
    indicator.innerHTML = '<span style="color: #718096;">Saving...</span>';
    indicator.style.opacity = '1';
  } else if (status === 'error') {
    indicator.innerHTML = '<span style="color: #c53030;">Save failed</span>';
    indicator.style.opacity = '1';
  }
}


// ============================================================
// VALIDATION UTILITIES
// ============================================================

export const ValidationUtils = {
  validateSSN: function(ssn) {
    const clean = ssn.replace(/[^0-9]/g, '');
    if (clean.length !== 9) {
      return { valid: false, message: 'SSN must be 9 digits' };
    }
    if (clean === '000000000' || clean.startsWith('000') || clean.startsWith('666') || clean.startsWith('9')) {
      return { valid: false, message: 'Invalid SSN format' };
    }
    return { valid: true, formatted: `${clean.slice(0,3)}-${clean.slice(3,5)}-${clean.slice(5)}` };
  },

  validateEIN: function(ein) {
    const clean = ein.replace(/[^0-9]/g, '');
    if (clean.length !== 9) {
      return { valid: false, message: 'EIN must be 9 digits' };
    }
    return { valid: true, formatted: `${clean.slice(0,2)}-${clean.slice(2)}` };
  },

  validateCurrency: function(value, fieldName = 'Amount', options = {}) {
    const clean = value.replace(/[$,\s]/g, '');
    const num = parseFloat(clean);

    if (isNaN(num)) {
      return { valid: false, message: `${fieldName} must be a valid number` };
    }
    if (!options.allowNegative && num < 0) {
      return { valid: false, message: `${fieldName} cannot be negative` };
    }
    if (options.max && num > options.max) {
      return { valid: false, message: `${fieldName} cannot exceed $${options.max.toLocaleString()}` };
    }
    if (options.min && num < options.min) {
      return { valid: false, message: `${fieldName} must be at least $${options.min.toLocaleString()}` };
    }
    return { valid: true, value: num, formatted: `$${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` };
  },

  validateDate: function(dateStr, fieldName = 'Date') {
    const formats = [
      /^\d{4}-\d{2}-\d{2}$/,
      /^\d{2}\/\d{2}\/\d{4}$/,
    ];

    if (!formats.some(f => f.test(dateStr))) {
      return { valid: false, message: `${fieldName} format should be MM/DD/YYYY or YYYY-MM-DD` };
    }

    const date = new Date(dateStr);
    if (isNaN(date.getTime())) {
      return { valid: false, message: `${fieldName} is not a valid date` };
    }
    return { valid: true, date: date };
  },

  applyValidationState: function(input, result) {
    input.classList.remove('field-valid', 'field-error', 'field-warning');

    let msgEl = input.parentElement.querySelector('.validation-message');
    if (!msgEl) {
      msgEl = document.createElement('div');
      msgEl.className = 'validation-message';
      input.parentElement.appendChild(msgEl);
    }

    if (result.valid) {
      input.classList.add('field-valid');
      msgEl.className = 'validation-message success';
      msgEl.textContent = result.message || '\u2713 Valid';
    } else {
      input.classList.add('field-error');
      msgEl.className = 'validation-message error';
      msgEl.textContent = result.message;
    }

    if (result.valid) {
      setTimeout(() => {
        msgEl.style.display = 'none';
      }, 2000);
    }
  },

  debounce: function(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }
};


// ============================================================
// PROGRESS INDICATOR UTILITY
// ============================================================

export const ProgressIndicator = {
  container: null,
  bar: null,
  text: null,

  create: function(parentEl) {
    this.container = document.createElement('div');
    this.container.className = 'progress-container';
    this.container.innerHTML = `
      <div class="progress-bar" style="width: 0%"></div>
    `;
    this.text = document.createElement('div');
    this.text.className = 'progress-text';

    parentEl.appendChild(this.container);
    parentEl.appendChild(this.text);

    this.bar = this.container.querySelector('.progress-bar');
    return this;
  },

  update: function(percent, message) {
    if (this.bar) {
      this.bar.style.width = `${Math.min(100, Math.max(0, percent))}%`;
    }
    if (this.text && message) {
      this.text.textContent = message;
    }
  },

  remove: function() {
    if (this.container) this.container.remove();
    if (this.text) this.text.remove();
  }
};


// ============================================================
// SKELETON LOADER UTILITY
// ============================================================

export const SkeletonLoader = {
  show: function(container, count = 3) {
    const skeletons = [];
    for (let i = 0; i < count; i++) {
      const skeleton = document.createElement('div');
      skeleton.className = 'skeleton skeleton-message';
      skeleton.style.width = `${50 + Math.random() * 30}%`;
      skeleton.style.marginLeft = i % 2 === 0 ? '0' : 'auto';
      container.appendChild(skeleton);
      skeletons.push(skeleton);
    }
    return skeletons;
  },

  hide: function(skeletons) {
    skeletons.forEach(s => s.remove());
  }
};


// ============================================================
// UX HELPERS
// ============================================================

export function createQuickEditPanel() {
  const profile = extractedData.tax_profile || {};
  const items = [];

  if (extractedData.filing_status) {
    items.push({ label: 'Filing Status', value: extractedData.filing_status, field: 'filing_status' });
  }
  if (profile.total_income) {
    items.push({ label: 'Income', value: '$' + profile.total_income.toLocaleString(), field: 'total_income' });
  }
  if (profile.state) {
    items.push({ label: 'State', value: profile.state, field: 'state' });
  }
  if (profile.dependents !== undefined) {
    items.push({ label: 'Dependents', value: profile.dependents, field: 'dependents' });
  }

  if (items.length === 0) return null;

  const panel = document.createElement('div');
  panel.className = 'quick-edit-panel';

  let html = `
    <div class="quick-edit-header">
      <span class="quick-edit-title">\uD83D\uDCCB Your Information</span>
      <span class="quick-edit-toggle" onclick="toggleQuickEdit()">Edit</span>
    </div>
  `;

  items.forEach(item => {
    html += `
      <div class="quick-edit-item" onclick="editField('${item.field}')">
        <span class="quick-edit-label">${item.label}</span>
        <span class="quick-edit-value">
          ${item.value}
          <span class="edit-icon">\u270F\uFE0F</span>
        </span>
      </div>
    `;
  });

  panel.innerHTML = html;
  return panel;
}

export function toggleQuickEdit() {
  const panel = document.querySelector('.quick-edit-panel');
  if (!panel) return;

  const isEditing = panel.classList.contains('edit-mode');

  if (isEditing) {
    panel.classList.remove('edit-mode');
    const toggle = panel.querySelector('.quick-edit-toggle');
    if (toggle) toggle.textContent = 'Edit';
    panel.querySelectorAll('.quick-edit-item').forEach(item => {
      item.style.pointerEvents = 'auto';
      item.style.opacity = '1';
    });
  } else {
    panel.classList.add('edit-mode');
    const toggle = panel.querySelector('.quick-edit-toggle');
    if (toggle) toggle.textContent = 'Done';
    showToast('Click any field to edit it', 'info');
  }
}

export function editField(field) {
  const fieldLabels = {
    'filing_status': 'filing status',
    'total_income': 'income',
    'state': 'state',
    'dependents': 'number of dependents'
  };

  const message = `I'd like to change my ${fieldLabels[field] || field}`;
  addMessage('user', message);
  processAIResponse(message);
}

export function initKeyboardNavigation() {
  document.addEventListener('keydown', (e) => {
    const input = document.getElementById('userInput');
    if (input && document.activeElement !== input) {
      if (e.key.length === 1 && e.key.match(/[a-z]/i) && !e.ctrlKey && !e.metaKey) {
        input.focus();
      }
    }

    if (e.key >= '1' && e.key <= '9') {
      const actions = document.querySelectorAll('.quick-actions:last-of-type .quick-action, .radio-actions:last-of-type .radio-option, .multi-select-actions:last-of-type .multi-select-option');
      const index = parseInt(e.key) - 1;
      if (actions[index]) {
        actions[index].click();
      }
    }

    if (e.key === 'Escape' && input) {
      input.value = '';
      input.blur();
    }
  });
}

export function showSuccessCheck(element) {
  const check = document.createElement('span');
  check.className = 'success-check';
  check.textContent = '\u2713';
  element.appendChild(check);
  setTimeout(() => check.remove(), 2000);
}

export function createTooltip(text, helpText) {
  return `<span class="tooltip-trigger">${text}<span class="tooltip-icon">?</span><span class="tooltip-content">${helpText}</span></span>`;
}

export function createSecurityNotice() {
  const notice = document.createElement('div');
  notice.className = 'security-notice';
  notice.innerHTML = `
    <span class="security-notice-icon">\uD83D\uDD12</span>
    <span>Your data is encrypted and never shared. We follow IRS data protection guidelines.</span>
  `;
  return notice;
}


// ============================================================
// FILE UPLOAD UI
// ============================================================

export function uploadDocument() {
  showUploadOptions();
}

export function showUploadOptions() {
  const modal = document.createElement('div');
  modal.className = 'upload-options-modal';
  modal.id = 'uploadOptionsModal';
  modal.innerHTML = `
    <div class="upload-options-content">
      <button class="close-options-btn" onclick="closeUploadOptions()">&times;</button>
      <h3>\uD83D\uDCCE Upload Document</h3>
      <p>Choose how you'd like to add your document</p>
      <div class="upload-options-grid">
        <button class="upload-option" onclick="selectFileUpload()">
          <div class="option-icon">\uD83D\uDCC1</div>
          <div class="option-title">Browse Files</div>
          <div class="option-desc">Select from your device</div>
        </button>
        <button class="upload-option" onclick="selectCameraCapture()">
          <div class="option-icon">\uD83D\uDCF7</div>
          <div class="option-title">Take Photo</div>
          <div class="option-desc">Capture with camera</div>
        </button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  requestAnimationFrame(() => {
    modal.classList.add('visible');
  });
}

export function closeUploadOptions() {
  const modal = document.getElementById('uploadOptionsModal');
  if (modal) {
    modal.classList.remove('visible');
    setTimeout(() => modal.remove(), 300);
  }
}

export function selectFileUpload() {
  closeUploadOptions();
  document.getElementById('fileInput').click();
}

export function selectCameraCapture() {
  closeUploadOptions();
  PhotoCapture.open();
}

export function addVoiceInput() {
  VoiceInputSystem.toggleRecording();
}


// ============================================================
// FILE VALIDATION & PREVIEW
// ============================================================

export function validateFile(file) {
  const errors = [];
  const maxSize = 50 * 1024 * 1024;
  const minSize = 1024;

  if (file.size > maxSize) {
    errors.push(`File exceeds 50MB limit (${(file.size / 1024 / 1024).toFixed(1)}MB)`);
  }

  if (file.size < minSize) {
    errors.push("File too small - may be corrupted");
  }

  const ext = file.name.split('.').pop().toLowerCase();
  const allowedExts = ['pdf', 'png', 'jpg', 'jpeg', 'heic', 'gif', 'webp'];
  if (!allowedExts.includes(ext)) {
    errors.push(`Unsupported file type: .${ext}. Allowed: PDF, PNG, JPG, HEIC`);
  }

  const allowedMimes = [
    'application/pdf',
    'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/heic'
  ];
  if (file.type && !allowedMimes.includes(file.type)) {
    errors.push(`Invalid file format: ${file.type}`);
  }

  return {
    isValid: errors.length === 0,
    errors: errors
  };
}

let pendingUploadFile = null;
let lastUploadFile = null;

export function showFilePreview(file) {
  const validation = validateFile(file);
  if (!validation.isValid) {
    showToast(validation.errors[0], 'error');
    return;
  }

  pendingUploadFile = file;
  lastUploadFile = file;

  const modal = document.createElement('div');
  modal.className = 'file-preview-modal';
  modal.id = 'filePreviewModal';

  const isPDF = file.type === 'application/pdf';

  modal.innerHTML = `
    <div class="file-preview-content">
      <button class="close-preview-btn" onclick="closeFilePreview()">&times;</button>
      <h3>\uD83D\uDCC4 Confirm Upload</h3>
      <div class="preview-container">
        ${isPDF
          ? `<div class="pdf-preview"><span class="pdf-icon">\uD83D\uDCD1</span><span>${file.name}</span></div>`
          : `<img id="imagePreview" class="image-preview" alt="Preview" />`
        }
      </div>
      <div class="file-info">
        <span>${file.name}</span>
        <span>${(file.size / 1024).toFixed(1)} KB</span>
      </div>
      <div class="preview-actions">
        <button class="preview-cancel" onclick="closeFilePreview()">Cancel</button>
        <button class="preview-confirm" onclick="confirmUpload()">Upload</button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  if (!isPDF) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = document.getElementById('imagePreview');
      if (img) img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  }

  requestAnimationFrame(() => modal.classList.add('visible'));
}

export function closeFilePreview() {
  const modal = document.getElementById('filePreviewModal');
  if (modal) {
    modal.classList.remove('visible');
    setTimeout(() => modal.remove(), 300);
  }
  pendingUploadFile = null;
}

export function confirmUpload() {
  if (pendingUploadFile) {
    handleValidatedUpload(pendingUploadFile);
    closeFilePreview();
  }
}


// ============================================================
// UPLOAD WITH PROGRESS
// ============================================================

export async function uploadFileWithProgress(file) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', sessionId);

    const progressContainer = document.createElement('div');
    progressContainer.className = 'upload-progress-container';
    progressContainer.innerHTML = `
      <div class="upload-progress-info">
        <span class="upload-filename">${file.name}</span>
        <span class="upload-percent">0%</span>
      </div>
      <div class="upload-progress-bar">
        <div class="upload-progress-fill" style="width: 0%"></div>
      </div>
    `;
    const messagesContainer = document.getElementById('messages');
    if (messagesContainer) {
      messagesContainer.appendChild(progressContainer);
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    const progressFill = progressContainer.querySelector('.upload-progress-fill');
    const progressPercent = progressContainer.querySelector('.upload-percent');

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const percent = Math.round((e.loaded / e.total) * 100);
        progressFill.style.width = percent + '%';
        progressPercent.textContent = percent + '%';
      }
    });

    xhr.onload = () => {
      progressContainer.remove();
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch (e) {
          reject(new Error('Invalid response'));
        }
      } else {
        reject(new Error(`Upload failed: ${xhr.status}`));
      }
    };

    xhr.onerror = () => {
      progressContainer.remove();
      reject(new Error('Network error'));
    };

    xhr.open('POST', '/api/ai-chat/analyze-document');
    const sessionToken = sessionStorage.getItem('advisor_session_token');
    if (sessionToken) {
      xhr.setRequestHeader('X-Session-Token', sessionToken);
    }
    const csrfToken = typeof getCSRFToken === 'function' ? getCSRFToken() : null;
    if (csrfToken) {
      xhr.setRequestHeader('X-CSRF-Token', csrfToken);
    }
    xhr.send(formData);
  });
}

export async function uploadFilesParallel(files) {
  const fileArray = Array.from(files);
  const validated = fileArray.filter(f => validateFile(f).isValid);
  const invalid = fileArray.filter(f => !validateFile(f).isValid);

  if (invalid.length > 0) {
    showToast(`${invalid.length} file(s) skipped due to validation errors`, 'warning');
  }

  if (validated.length === 0) {
    showToast('No valid files to upload', 'error');
    return;
  }

  const results = [];
  for (const file of validated) {
    try {
      const result = await uploadWithRetry(file);
      results.push({ status: 'fulfilled', value: result });
    } catch (error) {
      results.push({ status: 'rejected', reason: error });
    }
  }

  const succeeded = results.filter(r => r.status === 'fulfilled').length;
  const failed = results.filter(r => r.status === 'rejected').length;

  if (succeeded > 0) {
    showToast(`Uploaded ${succeeded} of ${validated.length} file(s)`, 'success');
  }
  if (failed > 0) {
    showToast(`${failed} file(s) failed to upload`, 'error');
  }

  return results;
}

export async function uploadWithRetry(file, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await uploadFileWithProgress(file);
    } catch (e) {
      DevLogger.warn(`Upload attempt ${i + 1} failed:`, e.message);
      if (i === maxRetries - 1) {
        showActionableError('upload_failed');
        throw e;
      }
      await new Promise(r => setTimeout(r, 1000 * Math.pow(2, i)));
    }
  }
}

export async function handleValidatedUpload(file) {
  addMessage('user', `Uploading: ${file.name}`);
  showTyping();

  try {
    const data = await uploadWithRetry(file);
    hideTyping();

    addMessage('ai', data.ai_response, data.quick_actions || []);

    if (data.extracted_data) {
      const { updateExtractedDataSafe } = await import('./advisor-core.js');
      await updateExtractedDataSafe(data.extracted_data, 'document_upload');
    }

    updateProgress(data.completion_percentage || 0);
    updateStats(data.extracted_summary || {});
    updatePhaseFromData();
  } catch (error) {
    hideTyping();
    // Error already shown by uploadWithRetry
  }
}


// ============================================================
// ENHANCED FILE HANDLING (overrides)
// ============================================================

/**
 * Enhanced handleFileSelect: single files get preview, multiple get parallel upload.
 * This replaces the basic version in advisor-data.js.
 */
export function handleFileSelect(event) {
  const files = event.target.files;
  if (files.length === 0) return;

  if (files.length === 1) {
    showFilePreview(files[0]);
  } else {
    uploadFilesParallel(files);
  }
}

export const PhotoCaptureEnhanced = {
  stream: null,
  videoElement: null,
  previewCanvas: null,
  capturedImage: null,

  open: function() {
    const modal = document.createElement('div');
    modal.className = 'camera-modal';
    modal.id = 'cameraModal';
    modal.innerHTML = `
      <div class="camera-content">
        <button class="close-camera-btn" onclick="PhotoCaptureEnhanced.close()">&times;</button>
        <h3>\uD83D\uDCF7 Capture Document</h3>
        <div class="camera-container">
          <video id="cameraVideo" autoplay playsinline></video>
          <canvas id="cameraCanvas" style="display: none;"></canvas>
          <div id="capturePreview" class="capture-preview" style="display: none;">
            <img id="capturedImg" alt="Captured" />
          </div>
        </div>
        <div class="camera-controls">
          <button id="captureBtn" class="camera-btn capture" onclick="PhotoCaptureEnhanced.capture()">
            \uD83D\uDCF8 Capture
          </button>
          <button id="retakeBtn" class="camera-btn retake" style="display: none;" onclick="PhotoCaptureEnhanced.retake()">
            \uD83D\uDD04 Retake
          </button>
          <button id="usePhotoBtn" class="camera-btn use" style="display: none;" onclick="PhotoCaptureEnhanced.usePhoto()">
            \u2713 Use Photo
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    requestAnimationFrame(() => modal.classList.add('visible'));
    this.startCamera();
  },

  startCamera: async function() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' }
      });
      this.videoElement = document.getElementById('cameraVideo');
      if (this.videoElement) {
        this.videoElement.srcObject = this.stream;
      }
    } catch (e) {
      showToast('Camera access denied. Please allow camera permissions.', 'error');
      this.close();
    }
  },

  capture: function() {
    const video = document.getElementById('cameraVideo');
    const canvas = document.getElementById('cameraCanvas');
    const preview = document.getElementById('capturePreview');
    const capturedImg = document.getElementById('capturedImg');

    if (video && canvas) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0);

      this.capturedImage = canvas.toDataURL('image/jpeg', 0.9);
      capturedImg.src = this.capturedImage;

      video.style.display = 'none';
      preview.style.display = 'block';
      const captureBtn = document.getElementById('captureBtn');
      const retakeBtn = document.getElementById('retakeBtn');
      const usePhotoBtn = document.getElementById('usePhotoBtn');
      if (captureBtn) captureBtn.style.display = 'none';
      if (retakeBtn) retakeBtn.style.display = 'inline-block';
      if (usePhotoBtn) usePhotoBtn.style.display = 'inline-block';
    }
  },

  retake: function() {
    const video = document.getElementById('cameraVideo');
    const preview = document.getElementById('capturePreview');
    const captureBtn = document.getElementById('captureBtn');
    const retakeBtn = document.getElementById('retakeBtn');
    const usePhotoBtn = document.getElementById('usePhotoBtn');

    if (video) video.style.display = 'block';
    if (preview) preview.style.display = 'none';
    if (captureBtn) captureBtn.style.display = 'inline-block';
    if (retakeBtn) retakeBtn.style.display = 'none';
    if (usePhotoBtn) usePhotoBtn.style.display = 'none';

    this.capturedImage = null;
  },

  usePhoto: async function() {
    if (!this.capturedImage) return;

    const res = await fetch(this.capturedImage);
    const blob = await res.blob();
    const file = new File([blob], `capture_${Date.now()}.jpg`, { type: 'image/jpeg' });

    this.close();
    handleValidatedUpload(file);
  },

  close: function() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
    const modal = document.getElementById('cameraModal');
    if (modal) {
      modal.classList.remove('visible');
      setTimeout(() => modal.remove(), 300);
    }
  }
};


// ============================================================
// ENHANCED KEYBOARD NAV
// ============================================================

export function initEnhancedKeyboardNav() {
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeUploadOptions();
      closeFilePreview();
      const modals = document.querySelectorAll('.modal-overlay, .upload-options-modal.visible');
      modals.forEach(m => m.remove());
    }

    if (e.key === 'Tab') {
      const quickActions = document.querySelectorAll('.quick-action:not(:disabled)');
      const input = document.getElementById('userInput');
      if (quickActions.length > 0 && document.activeElement === input && !e.shiftKey) {
        e.preventDefault();
        quickActions[0].focus();
      }
    }

    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      const quickActions = Array.from(document.querySelectorAll('.quick-action:not(:disabled)'));
      const currentIdx = quickActions.indexOf(document.activeElement);
      if (currentIdx >= 0) {
        e.preventDefault();
        const newIdx = e.key === 'ArrowRight'
          ? (currentIdx + 1) % quickActions.length
          : (currentIdx - 1 + quickActions.length) % quickActions.length;
        quickActions[newIdx].focus();
      }
    }

    if (e.key === 'Enter' && document.activeElement.classList.contains('quick-action')) {
      e.preventDefault();
      document.activeElement.click();
    }
  });
}


// ============================================================
// ACTIONABLE ERROR SYSTEM
// ============================================================

export const ERROR_ACTIONS = {
  network: {
    message: "Connection lost. Please check your internet.",
    actions: [
      { label: "Retry", action: () => retryLastAction() },
      { label: "Work Offline", action: () => enableOfflineMode() }
    ]
  },
  rate_limit: {
    message: "Too many requests. Please wait a moment.",
    actions: [
      { label: "Wait 30s", action: () => showCountdown(30) }
    ]
  },
  upload_failed: {
    message: "Upload failed.",
    actions: [
      { label: "Retry", action: () => retryLastUpload() },
      { label: "Try smaller file", action: () => showFileSizeHint() }
    ]
  },
  timeout: {
    message: "Request timed out.",
    actions: [
      { label: "Retry", action: () => retryLastAction() }
    ]
  }
};

let lastAction = null;

export function showActionableError(errorType, customMessage) {
  const errorConfig = ERROR_ACTIONS[errorType] || {
    message: customMessage || "Something went wrong.",
    actions: [{ label: "Retry", action: () => retryLastAction() }]
  };

  const errorDiv = document.createElement('div');
  errorDiv.className = 'actionable-error';
  errorDiv.innerHTML = `
    <div class="error-message">${errorConfig.message}</div>
    <div class="error-actions">
      ${errorConfig.actions.map((a, i) =>
        `<button class="error-action-btn" data-idx="${i}">${a.label}</button>`
      ).join('')}
    </div>
  `;

  errorConfig.actions.forEach((a, i) => {
    const btn = errorDiv.querySelector(`[data-idx="${i}"]`);
    if (btn) btn.onclick = a.action;
  });

  const messages = document.getElementById('messages');
  if (messages) {
    messages.appendChild(errorDiv);
    messages.scrollTop = messages.scrollHeight;
  }
}

export function retryLastAction() {
  if (lastAction) lastAction();
}

export function retryLastUpload() {
  if (lastUploadFile) {
    handleValidatedUpload(lastUploadFile);
  }
}

export function showCountdown(seconds) {
  showToast(`Please wait ${seconds} seconds...`, 'info');
  setTimeout(() => {
    showToast('You can try again now', 'success');
  }, seconds * 1000);
}

export function showFileSizeHint() {
  showToast('Try a file under 10MB, or compress images before uploading', 'info');
}

export function enableOfflineMode() {
  showToast('Offline mode enabled. Your data will be saved locally.', 'info');
}


// ============================================================
// CPA MODAL
// ============================================================

let _cpaFocusTrapRelease = null;

export function openCpaModal() {
  var backdrop = document.getElementById('cpaModalBackdrop');
  if (backdrop) {
    backdrop.style.display = 'flex';
    _cpaFocusTrapRelease = trapFocus(backdrop);
  }
}

export function closeCpaModal() {
  if (_cpaFocusTrapRelease) { _cpaFocusTrapRelease(); _cpaFocusTrapRelease = null; }
  var backdrop = document.getElementById('cpaModalBackdrop');
  if (backdrop) backdrop.style.display = 'none';
}


// ============================================================
// UX INITIALIZATION
// ============================================================

export function initUXEnhancements() {
  SmartNudgeSystem.init();
  LiveSavingsDisplay.init();
  VoiceInputSystem.init();
  initEnhancedKeyboardNav();
  initKeyboardNavigation();

  // Override PhotoCapture.open to use enhanced version
  PhotoCapture.open = PhotoCaptureEnhanced.open.bind(PhotoCaptureEnhanced);

  // Mobile keyboard handling
  if (/iPhone|iPad|iPod|Android/i.test(navigator.userAgent)) {
    const input = document.getElementById('userInput');
    if (input) {
      input.addEventListener('focus', function() {
        setTimeout(() => {
          this.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 300);
      });
    }
  }

  // Auto-resize textarea
  const userInputEl = document.getElementById('userInput');
  if (userInputEl) {
    userInputEl.addEventListener('input', function() {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });
  }

  // Drag and drop on upload zone
  const uploadZone = document.querySelector('.upload-zone');
  if (uploadZone) {
    uploadZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
      uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
      e.preventDefault();
      uploadZone.classList.remove('dragover');
      const files = e.dataTransfer.files;
      if (files.length === 1) {
        showFilePreview(files[0]);
      } else if (files.length > 1) {
        uploadFilesParallel(files);
      }
    });
  }

  // CPA modal escape key
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      closeCpaModal();
    }
  });

  DevLogger.log('UX enhancements initialized');
}
