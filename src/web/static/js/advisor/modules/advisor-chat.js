// ==========================================================================
// advisor-chat.js — Messaging, typing indicators, streaming, emotion, queue
// Extracted from intelligent-advisor.js (Sprint 1: Module Extraction)
// ==========================================================================

import {
  extractedData, sessionId, conversationHistory, isProcessing, taxCalculations,
  taxStrategies, premiumUnlocked, retryCount, questionNumber, isOnline,
  offlineQueue, isProcessingQueue,
  setSessionId, setIsProcessing, setTaxCalculations, setTaxStrategies,
  setPremiumUnlocked, setRetryCount, setQuestionNumber, setIsProcessingQueue,
  setConversationHistory, setLastUserMessage,
  secureFetch, escapeHtml, showToast, DevLogger, sanitizeInput, validateMessage,
  RobustnessConfig, rateLimitState, checkRateLimit, getCSRFToken,
  confirmedData, setConfirmedValue, setConfirmedValues, markUnsaved,
  updateQuestionCounter, handleError
} from './advisor-core.js';

import {
  fetchWithRetry, saveSessionData, updateLastActivity
} from './advisor-data.js';

import {
  handleQuickAction, startIntelligentQuestioning, resetQuestioningState,
  advanceJourneyBasedOnData, getConfidenceLevel, getConfidenceDisclaimer,
  calculateLeadScore
} from './advisor-flow.js';

import {
  renderStrategyCard, renderSafetySummary, renderConfidenceBadge,
  updateSavingsEstimate, LiveSavingsDisplay, showLoadingOverlay, hideLoadingOverlay,
  showErrorBanner, clearErrorBanner, updateProgress, updatePhaseFromData,
  updateInsights, updateStats, CelebrationSystem, checkForCelebration,
  renderTransitionCards, renderFreeFormIntake, renderParsedSummary,
  renderProfileConfirmation, renderTopicHeader,
  showShimmerLoading, hideShimmerLoading, triggerConfetti, updateJourneyStepperForHybrid, addManyOptionsClass
} from './advisor-display.js';

// ======================== FALLBACK RESPONSES ========================

export const FallbackResponses = {
  networkError: [
    "I'm having trouble connecting right now. Could you try again in a moment?",
    "Connection issues detected. Your data is safe - please try again shortly.",
    "Network hiccup! Don't worry, just click 'Retry' or try your message again."
  ],
  parseError: [
    "I didn't quite catch that. Could you rephrase your question?",
    "Let me make sure I understand - could you say that differently?",
    "I want to help, but I'm not sure what you mean. Can you clarify?"
  ],
  serverError: [
    "I'm experiencing some technical difficulties. Let me try a simpler approach.",
    "Something went wrong on my end. Let's continue with the basics.",
    "Technical issue detected. I'll work around it - please continue."
  ],
  unknown: [
    "I'm not sure how to respond to that. Let me ask you something instead.",
    "Interesting! Let's focus on your tax situation. What's your filing status?",
    "I want to help you save on taxes. Can you tell me about your income?"
  ],
  empty: [
    "I didn't receive your message. Please try typing again.",
    "It looks like your message was empty. What would you like to know?",
    "I'm ready to help! Just type your question or select an option above."
  ]
};

export function getFallbackResponse(type = 'unknown') {
  const responses = FallbackResponses[type] || FallbackResponses.unknown;
  return responses[Math.floor(Math.random() * responses.length)];
}

// ======================== GRACEFUL DEGRADATION ========================

export function attemptGracefulDegradation(originalRequest, error) {
  const degradedResponse = {
    success: false,
    message: getFallbackResponse('serverError'),
    quickActions: [
      { label: 'Tell me your filing status', value: 'filing_prompt' },
      { label: 'Enter your income', value: 'income_prompt' },
      { label: 'Start over', value: 'reset' }
    ]
  };
  return degradedResponse;
}

// ======================== MESSAGE QUEUE ========================

export const messageQueue = [];

export async function addToMessageQueue(message) {
  messageQueue.push({
    message: message,
    timestamp: Date.now(),
    retries: 0
  });

  if (!isProcessingQueue) {
    processMessageQueue();
  }
}

export async function processMessageQueue() {
  if (isProcessingQueue || messageQueue.length === 0) return;

  setIsProcessingQueue(true);

  while (messageQueue.length > 0) {
    const item = messageQueue[0];

    try {
      await processAIResponse(item.message);
      messageQueue.shift();
    } catch (error) {
      item.retries++;

      if (item.retries >= RobustnessConfig.maxRetries) {
        messageQueue.shift();
        addMessage('ai', getFallbackResponse('serverError'), [
          { label: 'Try again', value: 'retry_last' },
          { label: 'Start fresh', value: 'reset' }
        ]);
      } else {
        await new Promise(r => setTimeout(r, RobustnessConfig.retryDelay * item.retries));
      }
    }
  }

  setIsProcessingQueue(false);
}

// ======================== STREAMING DISPLAY ========================

export const StreamingDisplay = {
  async displayStreamingResponse(container, fullText, quickActions = []) {
    const bubble = container.querySelector('.bubble');
    if (!bubble) return;

    const cursor = document.createElement('span');
    cursor.className = 'streaming-cursor';

    const textSpan = document.createElement('span');
    textSpan.className = 'streaming-text';

    const copyBtn = bubble.querySelector('.copy-btn');
    const timestamp = bubble.querySelector('.message-time');
    bubble.innerHTML = '';
    bubble.appendChild(textSpan);
    bubble.appendChild(cursor);

    const words = fullText.split(' ');
    let currentText = '';

    for (let i = 0; i < words.length; i++) {
      currentText += (i > 0 ? ' ' : '') + words[i];
      textSpan.textContent = currentText;

      const messages = document.getElementById('messages');
      if (messages) {
        messages.scrollTop = messages.scrollHeight;
      }

      await new Promise(resolve => setTimeout(resolve, 20 + Math.random() * 30));
    }

    cursor.remove();
    bubble.innerHTML = typeof DOMPurify !== 'undefined' ? DOMPurify.sanitize(fullText) : fullText;

    if (copyBtn) bubble.appendChild(copyBtn);
    if (timestamp) bubble.appendChild(timestamp);
  }
};

// ======================== EMOTION DETECTOR ========================

export const EmotionDetector = {
  patterns: {
    frustrated: [
      /this (is |isn't |doesn't |does not )?(not |so )?work/i,
      /i('m| am) (so )?(confused|frustrated|lost|stuck)/i,
      /i don't (understand|get it|know)/i,
      /what(\?|!)+ *$/i,
      /ugh|argh|wtf|wth/i,
      /help!+/i
    ],
    confused: [
      /what does (that|this) mean/i,
      /i('m| am) not sure/i,
      /can you explain/i,
      /\?{2,}/,
      /huh\??/i
    ],
    anxious: [
      /worried|nervous|scared|afraid/i,
      /audit/i,
      /penalty|penalties/i,
      /am i (doing|getting) (this|it) right/i,
      /is this (correct|right|ok|okay)/i
    ],
    excited: [
      /wow|amazing|awesome|great|fantastic/i,
      /!{2,}/,
      /that's (so )?(cool|great|awesome)/i,
      /really\?!?/i
    ],
    rushed: [
      /quick(ly)?|fast|hurry|asap/i,
      /don't have (much )?time/i,
      /in a (rush|hurry)/i,
      /just (tell|give) me/i
    ]
  },

  detect(message) {
    for (const [emotion, patterns] of Object.entries(this.patterns)) {
      if (patterns.some(pattern => pattern.test(message))) {
        return emotion;
      }
    }
    return 'neutral';
  },

  getResponseModifier(emotion) {
    const modifiers = {
      frustrated: {
        prefix: "I completely understand - let me make this simpler. ",
        tone: "empathetic",
        style: "Use very simple language, be extra patient and supportive"
      },
      confused: {
        prefix: "Let me explain this more clearly. ",
        tone: "reassuring",
        style: "Break down into simple steps, use analogies"
      },
      anxious: {
        prefix: "Don't worry - you're doing great! ",
        tone: "reassuring",
        style: "Be calming, emphasize accuracy and safety"
      },
      excited: {
        prefix: "",
        tone: "encouraging",
        style: "Match their enthusiasm, celebrate with them"
      },
      rushed: {
        prefix: "Got it - here's the quick version: ",
        tone: "neutral",
        style: "Be concise, prioritize key information"
      },
      neutral: {
        prefix: "",
        tone: "neutral",
        style: "Normal helpful tone"
      }
    };
    return modifiers[emotion] || modifiers.neutral;
  }
};

// ======================== SHOW QUESTION HELPER ========================

export function showQuestion(html, quickActions, delay, opts) {
  showTyping();
  setTimeout(function() {
    hideTyping();
    if (opts) {
      addMessage('ai', html, quickActions || [], opts);
    } else {
      addMessage('ai', html, quickActions || []);
    }
  }, delay || 800);
}

// ======================== TYPING INDICATORS ========================

export function showTyping() {
  const messages = document.getElementById('messages');
  if (!messages) return;
  const typing = document.createElement('div');
  typing.className = 'message ai';
  typing.id = 'typing-indicator';
  typing.setAttribute('role', 'status');
  typing.setAttribute('aria-live', 'assertive');
  typing.setAttribute('aria-label', 'AI assistant is typing a response');
  typing.innerHTML = `
    <div class="avatar ai" aria-hidden="true">T</div>
    <div class="bubble">
      <div class="typing-indicator" role="img" aria-label="Typing">
        <span></span>
        <span></span>
        <span></span>
        <span class="typing-text sr-only">Please wait, the assistant is preparing a response...</span>
      </div>
    </div>
  `;
  messages.appendChild(typing);
  messages.scrollTop = messages.scrollHeight;
}

export function hideTyping() {
  const typing = document.getElementById('typing-indicator');
  if (typing) typing.remove();
}

// ======================== ADD MESSAGE ========================

export function addMessage(type, text, quickActions = [], options = {}) {
  DevLogger.log('====== addMessage CALLED ======');
  DevLogger.log('Type:', type);
  DevLogger.log('Text preview:', text.substring(0, 50));
  DevLogger.log('Quick actions count:', quickActions.length);

  if (type === 'user' && typeof markUnsaved === 'function') {
    markUnsaved();
  }

  if (type === 'ai') {
    setQuestionNumber(questionNumber + 1);
    updateQuestionCounter();
  }

  const messages = document.getElementById('messages');
  DevLogger.log('Messages container found:', !!messages);

  if (!messages) {
    DevLogger.error('Messages container not found!');
    showToast('Error displaying message', 'error');
    return;
  }

  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${type}`;
  messageDiv.setAttribute('role', 'article');
  messageDiv.setAttribute('aria-label', type === 'ai' ? 'AI assistant message' : 'Your message');

  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.setAttribute('aria-hidden', 'true');
  avatar.classList.add(type === 'ai' ? 'ai' : 'user');
  avatar.innerHTML = type === 'ai'
    ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 7h6M9 11h6M9 15h4"/><rect x="4" y="3" width="16" height="18" rx="2"/></svg>'
    : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';

  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  if (type === 'ai' && options.showConfidence === true) {
    const includeIRS = options.includeIRS || false;
    text += getConfidenceDisclaimer(includeIRS);
  }

  if (type === 'ai') {
    const sanitized = typeof DOMPurify !== 'undefined'
      ? DOMPurify.sanitize(text, {
          ALLOWED_TAGS: ['b','i','strong','em','br','div','span','ul','ol','li','a','p',
            'h3','h4','h5','table','thead','tbody','tr','th','td','svg','path','code','pre',
            'button','input'],
          ALLOWED_ATTR: ['href','target','rel','class','style','viewBox','d','fill',
            'stroke','stroke-width','width','height','aria-hidden',
            'data-action','id','type','placeholder','value']
        })
      : text.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
           .replace(/on\w+\s*=\s*["'][^"']*["']/gi, '')
           .replace(/javascript\s*:/gi, '');
    bubble.innerHTML = sanitized;
  } else {
    bubble.textContent = text;
  }

  // Add copy button for AI messages (hidden until hover)
  if (type === 'ai') {
    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-btn';
    copyBtn.textContent = 'Copy';
    copyBtn.setAttribute('aria-label', 'Copy this message');
    copyBtn.onclick = (e) => {
      e.stopPropagation();
      const textContent = bubble.innerText.replace(/\s*Copy$/, '').replace(/\s*Copied$/, '').trim();
      navigator.clipboard.writeText(textContent).then(() => {
        copyBtn.textContent = 'Copied';
        setTimeout(() => { copyBtn.textContent = 'Copy'; }, 2000);
      });
    };
    bubble.appendChild(copyBtn);
  }

  // Add timestamp
  const timestamp = document.createElement('span');
  timestamp.className = 'message-time';
  const now = new Date();
  const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  timestamp.textContent = timeStr;
  timestamp.setAttribute('aria-label', `Sent at ${timeStr}`);
  bubble.appendChild(timestamp);

  if (quickActions.length > 0 || options.inputType === 'dropdown') {
    const isMultiSelect = options.multiSelect === true;

    if (isMultiSelect) {
      // Render as checkboxes for multi-select
      const actionsDiv = document.createElement('div');
      actionsDiv.className = 'multi-select-actions';
      actionsDiv.setAttribute('role', 'group');
      actionsDiv.setAttribute('aria-label', 'Select all that apply');

      const selectedValues = new Set();

      quickActions.forEach((action, index) => {
        const optionDiv = document.createElement('div');
        optionDiv.className = 'multi-select-option';

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `multi-select-${index}`;
        checkbox.value = action.value;

        const label = document.createElement('label');
        label.htmlFor = `multi-select-${index}`;
        label.textContent = action.label;

        checkbox.onchange = () => {
          if (checkbox.checked) {
            selectedValues.add(action.value);
            optionDiv.classList.add('selected');
          } else {
            selectedValues.delete(action.value);
            optionDiv.classList.remove('selected');
          }
          const submitBtn = actionsDiv.querySelector('.submit-btn');
          if (submitBtn) {
            submitBtn.disabled = selectedValues.size === 0;
          }
        };

        optionDiv.onclick = (e) => {
          if (e.target !== checkbox) {
            checkbox.checked = !checkbox.checked;
            checkbox.dispatchEvent(new Event('change'));
          }
        };

        optionDiv.appendChild(checkbox);
        optionDiv.appendChild(label);
        actionsDiv.appendChild(optionDiv);
      });

      const submitDiv = document.createElement('div');
      submitDiv.className = 'multi-select-submit';

      const submitBtn = document.createElement('button');
      submitBtn.className = 'submit-btn';
      submitBtn.textContent = 'Continue with Selected';
      submitBtn.setAttribute('aria-label', 'Continue with selected options');
      submitBtn.disabled = true;
      submitBtn.onclick = () => {
        const selected = Array.from(selectedValues);
        if (selected.length > 0) {
          const labels = quickActions
            .filter(a => selected.includes(a.value))
            .map(a => a.label);
          handleQuickAction(selected.join(','), labels.join(', '));
        }
      };

      const skipBtn = document.createElement('button');
      skipBtn.className = 'skip-btn';
      skipBtn.textContent = 'Skip';
      skipBtn.setAttribute('aria-label', 'Skip this question');
      skipBtn.onclick = () => {
        handleQuickAction('skip_multi_select', 'None selected');
      };

      submitDiv.appendChild(submitBtn);
      submitDiv.appendChild(skipBtn);
      actionsDiv.appendChild(submitDiv);

      bubble.appendChild(actionsDiv);

    } else if (options.inputType === 'radio') {
      const actionsDiv = document.createElement('div');
      actionsDiv.className = 'radio-actions';
      actionsDiv.setAttribute('role', 'radiogroup');
      actionsDiv.setAttribute('aria-label', 'Select one option');

      const radioName = `radio-group-${Date.now()}`;

      quickActions.forEach((action, index) => {
        const optionDiv = document.createElement('div');
        optionDiv.className = 'radio-option';

        const radio = document.createElement('input');
        radio.type = 'radio';
        radio.name = radioName;
        radio.id = `radio-${radioName}-${index}`;
        radio.value = action.value;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'radio-content';

        const label = document.createElement('label');
        label.htmlFor = radio.id;
        label.textContent = action.label;
        contentDiv.appendChild(label);

        if (action.description) {
          const desc = document.createElement('div');
          desc.className = 'radio-description';
          desc.textContent = action.description;
          contentDiv.appendChild(desc);
        }

        radio.onchange = () => {
          actionsDiv.querySelectorAll('.radio-option').forEach(opt => opt.classList.remove('selected'));
          optionDiv.classList.add('selected');
          setTimeout(() => {
            handleQuickAction(action.value);
          }, 300);
        };

        optionDiv.onclick = (e) => {
          if (e.target !== radio) {
            radio.checked = true;
            radio.dispatchEvent(new Event('change'));
          }
        };

        optionDiv.appendChild(radio);
        optionDiv.appendChild(contentDiv);
        actionsDiv.appendChild(optionDiv);
      });

      bubble.appendChild(actionsDiv);

    } else if (options.inputType === 'dropdown') {
      const actionsDiv = document.createElement('div');
      actionsDiv.className = 'dropdown-actions';

      const allOptions = [];
      if (options.groups) {
        options.groups.forEach(group => {
          group.options.forEach(action => {
            allOptions.push({ ...action, group: group.label });
          });
        });
      } else {
        quickActions.forEach(action => allOptions.push(action));
      }

      const wrapper = document.createElement('div');
      wrapper.className = 'searchable-dropdown';

      const input = document.createElement('input');
      input.type = 'text';
      input.className = 'dropdown-search';
      input.placeholder = options.placeholder || 'Type to search...';
      input.setAttribute('aria-label', 'Search options');
      input.setAttribute('autocomplete', 'off');

      const listContainer = document.createElement('div');
      listContainer.className = 'dropdown-list';

      let selectedValue = null;

      function renderList(filter) {
        listContainer.innerHTML = '';
        const query = (filter || '').toLowerCase();
        let hasResults = false;
        let currentGroup = '';

        allOptions.forEach(opt => {
          if (query && !opt.label.toLowerCase().includes(query)) return;
          hasResults = true;

          if (opt.group && opt.group !== currentGroup) {
            currentGroup = opt.group;
            const groupHeader = document.createElement('div');
            groupHeader.className = 'dropdown-group-header';
            groupHeader.textContent = opt.group;
            listContainer.appendChild(groupHeader);
          }

          const item = document.createElement('div');
          item.className = 'dropdown-item' + (opt.value === selectedValue ? ' selected' : '');
          item.textContent = opt.label;
          item.addEventListener('click', () => {
            selectedValue = opt.value;
            input.value = opt.label;
            listContainer.classList.remove('open');
            ddSubmitBtn.disabled = false;
            listContainer.querySelectorAll('.dropdown-item').forEach(i => i.classList.remove('selected'));
            item.classList.add('selected');
          });
          listContainer.appendChild(item);
        });

        if (!hasResults) {
          const noResult = document.createElement('div');
          noResult.className = 'dropdown-no-results';
          noResult.textContent = 'No states found';
          listContainer.appendChild(noResult);
        }
      }

      input.addEventListener('focus', () => {
        renderList(input.value);
        listContainer.classList.add('open');
      });

      input.addEventListener('input', () => {
        selectedValue = null;
        ddSubmitBtn.disabled = true;
        renderList(input.value);
        listContainer.classList.add('open');
      });

      document.addEventListener('click', (e) => {
        if (!wrapper.contains(e.target)) {
          listContainer.classList.remove('open');
        }
      });

      wrapper.appendChild(input);
      wrapper.appendChild(listContainer);
      actionsDiv.appendChild(wrapper);

      renderList('');

      const submitDiv = document.createElement('div');
      submitDiv.className = 'dropdown-submit';

      const ddSubmitBtn = document.createElement('button');
      ddSubmitBtn.textContent = 'Continue \u2192';
      ddSubmitBtn.disabled = true;

      ddSubmitBtn.addEventListener('click', () => {
        if (selectedValue) {
          const selectedOption = allOptions.find(a => a.value === selectedValue);
          // Remove the dropdown UI before proceeding
          actionsDiv.remove();
          handleQuickAction(selectedValue, selectedOption?.label);
        }
      });

      submitDiv.appendChild(ddSubmitBtn);
      actionsDiv.appendChild(submitDiv);

      bubble.appendChild(actionsDiv);

    } else if (options.inputType === 'currency') {
      const currencyInput = createCurrencyInput(
        options.placeholder || 'Enter amount',
        (value) => {
          addMessage('user', '$' + value.toLocaleString());
          if (options.onSubmit) {
            options.onSubmit(value);
          } else if (options.field) {
            extractedData.tax_profile[options.field] = value;
            updateSavingsEstimate();
            startIntelligentQuestioning();
          }
        }
      );
      bubble.appendChild(currencyInput);
      bubble.appendChild(createSecurityNotice());

    } else if (options.inputType === 'slider') {
      const slider = createSliderInput(
        options.min || 0,
        options.max || 500000,
        options.step || 5000,
        options.default || (options.max / 2),
        (val) => '$' + val.toLocaleString(),
        (value) => {
          addMessage('user', '$' + value.toLocaleString());
          if (options.onSubmit) {
            options.onSubmit(value);
          } else if (options.field) {
            extractedData.tax_profile[options.field] = value;
            updateSavingsEstimate();
            startIntelligentQuestioning();
          }
        }
      );
      bubble.appendChild(slider);

    } else {
      // Regular single-select buttons (default)
      const actionsDiv = document.createElement('div');
      actionsDiv.className = 'quick-actions';
      actionsDiv.setAttribute('role', 'group');
      actionsDiv.setAttribute('aria-label', 'Quick response options');

      quickActions.forEach((action, index) => {
        const btn = document.createElement('button');
        if (action.style === 'quick_win') {
          btn.className = 'quick-action quick-action--quick-win';
          btn.innerHTML = action.label;
        } else {
          btn.className = action.primary ? 'quick-action primary' : 'quick-action';
          btn.textContent = action.label;
        }
        btn.setAttribute('aria-label', action.label.replace(/[^\w\s]/g, '').trim());
        btn.onclick = () => {
          // 1. Visual feedback: highlight selected, disable others
          actionsDiv.querySelectorAll('.quick-action').forEach(b => {
            b.disabled = true;
            b.style.opacity = '0.4';
            b.style.pointerEvents = 'none';
          });
          btn.style.opacity = '1';
          btn.classList.add('selected');
          btn.style.background = 'var(--amber)';
          btn.style.color = 'var(--white)';
          btn.style.borderColor = 'var(--amber)';

          // 2. Collapse previous actions after brief delay
          setTimeout(() => {
            actionsDiv.style.maxHeight = actionsDiv.scrollHeight + 'px';
            actionsDiv.style.transition = 'max-height 0.3s ease, opacity 0.3s ease';
            requestAnimationFrame(() => {
              actionsDiv.style.maxHeight = '0';
              actionsDiv.style.opacity = '0';
              actionsDiv.style.overflow = 'hidden';
            });
          }, 400);

          // 3. Process the action
          handleQuickAction(action.value, action.label);
        };
        actionsDiv.appendChild(btn);
      });
      bubble.appendChild(actionsDiv);
    }
  }

  messageDiv.appendChild(avatar);
  messageDiv.appendChild(bubble);
  messages.appendChild(messageDiv);

  DevLogger.log('Message added successfully. Total messages now:', messages.children.length);

  // Smooth scroll to new message + focus
  messageDiv.scrollIntoView({ behavior: 'smooth', block: 'end' });
  messages.scrollTop = messages.scrollHeight;
  return messageDiv;
}

// ======================== SEND MESSAGE ========================

export async function sendMessage() {
  const input = document.getElementById('userInput');
  let text = input.value.trim();

  if (!text || isProcessing) {
    if (!text) {
      // Show inline hint instead of toast
      let hint = document.getElementById('emptyMsgHint');
      if (!hint) {
        hint = document.createElement('div');
        hint.id = 'emptyMsgHint';
        hint.style.cssText = 'font-size:0.8rem;color:var(--amber,#c4975a);padding:4px 12px;text-align:center;';
        hint.textContent = 'Please share your answer to continue your analysis.';
        input.closest('.input-container')?.parentNode?.appendChild(hint);
      }
      hint.style.display = 'block';
      setTimeout(() => { if (hint) hint.style.display = 'none'; }, 3000);
    }
    return;
  }

  // Clear inline hint if present
  const hint = document.getElementById('emptyMsgHint');
  if (hint) hint.style.display = 'none';

  text = sanitizeInput(text);

  const validation = validateMessage(text);
  if (!validation.valid) {
    showToast(validation.errors[0], 'warning');
    return;
  }

  const rateCheck = checkRateLimit();
  if (!rateCheck.allowed) {
    showToast(rateCheck.reason, 'warning');
    return;
  }

  if (!isOnline) {
    addMessage('user', text);
    queueOfflineMessage(text);
    input.value = '';
    input.style.height = 'auto';
    return;
  }

  addMessage('user', text);
  input.value = '';
  input.style.height = 'auto';

  updateLastActivity();

  await processAIResponse(text);
}

// ======================== PROCESS AI RESPONSE ========================

export async function processAIResponse(userMessage) {
  setIsProcessing(true);
  setLastUserMessage(userMessage);
  showTyping();

  // Create session if not already created, or upgrade temp session
  const isTemporarySession = sessionId && sessionId.startsWith('temp-');
  if (!sessionId || isTemporarySession) {
    try {
      const sessionResponse = await fetchWithRetry('/api/sessions/create-session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow_type: 'intelligent_conversational',
          tax_year: 2025
        })
      }, 2);

      if (!sessionResponse.ok) {
        setSessionId('temp-' + crypto.randomUUID());
        DevLogger.warn('Using temporary session ID:', sessionId);
      } else {
        const sessionData = await sessionResponse.json();
        setSessionId(sessionData.session_id);
        sessionStorage.setItem('tax_session_id', sessionId);
        if (sessionData.session_token) {
          sessionStorage.setItem('advisor_session_token', sessionData.session_token);
        }
      }
    } catch (error) {
      DevLogger.error('Failed to create session:', error);
      setSessionId('temp-' + crypto.randomUUID());
    }
  }

  let thinkingTimer = null;
  let extendedTimer = null;
  try {
    const statusMap = {
      'Single': 'single',
      'Married Filing Jointly': 'married_joint',
      'Head of Household': 'head_of_household',
      'Married Filing Separately': 'married_separate',
      'Qualifying Surviving Spouse': 'qualifying_widow'
    };

    const tp = extractedData.tax_profile;
    const ti = extractedData.tax_items || {};
    const profile = {
      filing_status: statusMap[tp.filing_status] || tp.filing_status || null,
      total_income: tp.total_income != null ? tp.total_income : null,
      w2_income: tp.w2_income || null,
      business_income: tp.business_income || null,
      investment_income: tp.investment_income || null,
      rental_income: tp.rental_income || null,
      dependents: tp.dependents != null ? tp.dependents : null,
      dependents_under_17: tp.dependents_under_17 != null ? tp.dependents_under_17 : null,
      state: tp.state || null,
      income_type: tp.income_type || null,
      income_source: tp.income_source || null,
      is_self_employed: tp.is_self_employed || (tp.business_income || 0) > 0,
      age: tp.age || null,
      mortgage_interest: ti.mortgage_interest || tp.mortgage_interest || null,
      charitable_donations: ti.charitable || tp.charitable_donations || null,
      medical_expenses: ti.medical || tp.medical_expenses || null,
      student_loan_interest: tp.student_loan_interest || null,
      retirement_401k: tp.retirement_401k || null,
      retirement_ira: tp.retirement_ira || null,
      hsa_contributions: tp.hsa_contributions || null,
      federal_withholding: tp.federal_withholding || null,
    };

    thinkingTimer = setTimeout(() => {
      const typingEl = document.querySelector('.typing-indicator .typing-text');
      if (typingEl) typingEl.textContent = 'Thinking deeply...';
    }, 4000);
    extendedTimer = setTimeout(() => {
      const typingEl = document.querySelector('.typing-indicator .typing-text');
      if (typingEl) typingEl.textContent = 'Taking a bit longer than usual, still working...';
    }, 12000);

    const response = await fetchWithRetry('/api/advisor/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        message: userMessage,
        profile: profile.filing_status || profile.total_income ? profile : null,
        conversation_history: conversationHistory.slice(-10)
      })
    }, 3);

    clearTimeout(thinkingTimer);
    clearTimeout(extendedTimer);

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    const data = await response.json();
    hideTyping();
    setRetryCount(0);

    if (!data || typeof data !== 'object') {
      DevLogger.error('Invalid API response:', data);
      throw new Error('Received invalid response from server');
    }

    const responseContent = data.response || '';
    if (responseContent.trim()) {
      conversationHistory.push(
        { role: 'user', content: userMessage },
        { role: 'assistant', content: responseContent }
      );
    } else {
      conversationHistory.push({ role: 'user', content: userMessage });
      DevLogger.warn('Received empty response from API');
    }

    if (data.profile_completeness > 0) {
      if (data.tax_calculation) {
        setTaxCalculations(data.tax_calculation);
        // Show "View Full Results" link when calculation is ready
        var resultsLink = document.getElementById('results-link');
        if (!resultsLink) {
          resultsLink = document.createElement('a');
          resultsLink.id = 'results-link';
          resultsLink.style.cssText = 'display:block;text-align:center;padding:12px 24px;margin:12px auto;background:#2563eb;color:white;border-radius:8px;font-weight:700;text-decoration:none;max-width:300px;';
          resultsLink.textContent = 'View Full Tax Results';
          var msgs = document.getElementById('messages');
          if (msgs) msgs.parentNode.insertBefore(resultsLink, msgs.nextSibling);
        }
        if (!sessionId) {
          resultsLink.href = '#';
          resultsLink.onclick = (e) => { e.preventDefault(); showToast('Complete your analysis first to generate your report.', 'warning'); };
        } else {
          resultsLink.href = '/results?session_id=' + sessionId;
        }
      }
      if (data.strategies && data.strategies.length > 0) {
        setTaxStrategies(data.strategies);
        extractedData.lead_data.estimated_savings = taxStrategies.reduce((sum, s) => sum + (s.estimated_savings || 0), 0);
      }
      if (data.lead_score) {
        extractedData.lead_data.score = data.lead_score;
      }
      DevLogger.log('API updated profile, completeness:', data.profile_completeness);
      markUnsaved();
    }

    let aiResponse = data.response || "I'm here to help. Could you please clarify?";
    const quickActions = data.quick_actions || generateSmartQuickActions();

    // ── Hybrid flow: handle new response types ──────────────────────
    if (data.response_type === 'transition') {
      renderTransitionCards(data);
      return;
    }
    if (data.response_type === 'freeform_intake') {
      renderFreeFormIntake(data);
      return;
    }
    if (data.response_type === 'summary') {
      hideShimmerLoading();
      renderParsedSummary(data);
      return;
    }
    if (data.response_type === 'confirmation') {
      renderProfileConfirmation(data);
      return;
    }
    // Topic headers for guided mode questions
    if (data.response_type === 'question' && data.topic_name && data.topic_number) {
      renderTopicHeader(data.topic_name, data.topic_number, data.topic_total || 6);
    }

    // ── Live tax estimate banner (Feature 1) ──────────────────────────
    if (data.live_tax_estimate != null && data.live_estimate_confidence !== 'none') {
      const isRefund = data.live_tax_estimate >= 0;
      const amount = Math.abs(data.live_tax_estimate).toLocaleString();
      const cls = isRefund ? 'refund' : 'owed';
      let banner = document.getElementById('live-estimate-banner');
      if (!banner) {
        banner = document.createElement('div');
        banner.id = 'live-estimate-banner';
        banner.className = 'live-estimate-banner';
        const chatContainer = document.getElementById('chat-messages');
        if (chatContainer) chatContainer.parentElement.insertBefore(banner, chatContainer);
      }
      banner.innerHTML = `
        <div class="live-estimate-left">
          <span class="live-estimate-amount ${cls}">${isRefund ? '+' : '-'}$${amount}</span>
          <span class="live-estimate-type">${isRefund ? 'Estimated Refund' : 'Estimated Owed'}</span>
        </div>
        <span class="live-estimate-confidence">${data.live_estimate_confidence} confidence</span>
      `;
      banner.style.display = 'flex';
      // Animate the amount change
      const amtEl = banner.querySelector('.live-estimate-amount');
      if (amtEl) { amtEl.classList.remove('updating'); void amtEl.offsetWidth; amtEl.classList.add('updating'); }
    }

    // Confetti on positive moments (CTC, credits, savings)
    if (data.response && (data.response.includes('qualify for $') || data.response.includes('credit —') || data.response.includes('off your tax bill'))) {
      setTimeout(triggerConfetti, 300);
    }

    // Apply grid layout for 7+ buttons after render
    setTimeout(addManyOptionsClass, 100);

    // Journey stepper update based on topic
    if (data.topic_number) {
      if (data.topic_number <= 2) updateJourneyStepperForHybrid('details');
      else if (data.topic_number <= 5) updateJourneyStepperForHybrid('details');
      else updateJourneyStepperForHybrid('details');
    }

    // ── Progress confidence hint ────────────────────────────────────────
    if (data.completion_hint) {
      const hint = document.getElementById('completion-hint');
      if (hint) {
        hint.textContent = data.completion_hint;
      } else {
        const chatContainer = document.getElementById('chat-messages');
        if (chatContainer) {
          const h = document.createElement('div');
          h.id = 'completion-hint';
          h.className = 'completion-hint';
          h.textContent = data.completion_hint;
          chatContainer.parentElement.insertBefore(h, chatContainer);
        }
      }
    }

    if (data.response_type === 'calculation' || data.response_type === 'strategy' || data.response_type === 'report') {
      aiResponse += renderConfidenceBadge(data.response_confidence, data.confidence_reason);
    }

    if (data.response_type === 'ai_response') {
      aiResponse = '<span class="ai-badge" style="display:inline-block;background:#e0e7ff;color:#4338ca;font-size:0.7rem;font-weight:600;padding:2px 8px;border-radius:9999px;margin-bottom:6px;">AI-Powered</span>\n' + aiResponse;
    }

    if (data.response_type === 'ai_research') {
      aiResponse = '<span class="ai-badge" style="display:inline-block;background:#ecfdf5;color:#065f46;font-size:0.7rem;font-weight:600;padding:2px 8px;border-radius:9999px;margin-bottom:6px;">Research</span>\n' + aiResponse;
    }

    if (data.safety_checks) {
      const sc = data.safety_checks;
      const isClean = (!sc.fraud || sc.fraud.risk_level === 'MINIMAL' || sc.fraud.risk_level === 'LOW')
        && (!sc.compliance || sc.compliance.risk_level === 'LOW');
      const badgeColor = isClean ? '#065f46' : '#b91c1c';
      const badgeBg = isClean ? '#ecfdf5' : '#fef2f2';
      const badgeText = isClean ? 'Compliance Verified' : 'Review Recommended';
      aiResponse += `\n<span class="safety-badge" style="display:inline-block;background:${badgeBg};color:${badgeColor};font-size:0.7rem;font-weight:600;padding:2px 8px;border-radius:9999px;margin-top:8px;">${badgeText}</span>`;

      if (sc.audit_risk) {
        const ar = sc.audit_risk;
        const riskLevel = (ar.overall_risk || 'low').toLowerCase();
        const safeRiskLevel = ['low', 'medium', 'high'].includes(riskLevel) ? riskLevel : 'low';
        const safeScore = Number(ar.risk_score) || 0;
        aiResponse += `\n<span class="audit-risk-badge-card audit-risk-badge-card--${safeRiskLevel}">Audit Risk: ${escapeHtml(safeRiskLevel.charAt(0).toUpperCase() + safeRiskLevel.slice(1))} (${safeScore}/100)</span>`;
      }
    }

    if (data.entity_comparison && data.entity_comparison.ai_analysis) {
      const ec = data.entity_comparison;
      aiResponse += `\n\n<div class="ai-entity-card" style="background:var(--bg-secondary, #f8fafc);border:1px solid var(--border-color, #e2e8f0);border-radius:8px;padding:12px;margin-top:12px;">`;
      aiResponse += `<div style="font-weight:600;margin-bottom:8px;color:var(--primary, #4338ca);">Business Entity Analysis</div>`;
      aiResponse += `<div style="font-size:0.85rem;margin-bottom:8px;">${escapeHtml(ec.ai_analysis)}</div>`;
      if (ec.recommendation) {
        aiResponse += `<div style="font-weight:600;font-size:0.85rem;margin-bottom:4px;">Recommendation: ${escapeHtml(ec.recommendation)}</div>`;
      }
      if (ec.action_items && ec.action_items.length > 0) {
        aiResponse += `<div style="font-size:0.8rem;margin-top:6px;"><strong>Action Items:</strong><ul style="margin:4px 0;padding-left:18px;">`;
        ec.action_items.forEach(item => { aiResponse += `<li>${escapeHtml(item)}</li>`; });
        aiResponse += `</ul></div>`;
      }
      if (ec.confidence) {
        aiResponse += `<span style="display:inline-block;background:#e0e7ff;color:#4338ca;font-size:0.65rem;font-weight:600;padding:1px 6px;border-radius:9999px;margin-top:4px;">Confidence: ${Math.round(ec.confidence * 100)}%</span>`;
      }
      aiResponse += `</div>`;
    }

    if (data.strategies && data.strategies.length > 0 && data.response_type === 'calculation') {
      const premiumCount = data.strategies.filter(function(s) { return (s.tier || 'free') === 'premium'; }).length;
      const freeCount = data.strategies.length - premiumCount;

      if (premiumCount > 0 && !premiumUnlocked) {
        aiResponse += '\n\n<div style="font-size:0.85rem;color:var(--color-gray-600);margin-bottom:8px;">' + freeCount + ' strategies you can implement yourself + ' + premiumCount + ' CPA-recommended strategies</div>';
      }

      data.strategies.slice(0, 5).forEach(function(strategy, i) {
        aiResponse += renderStrategyCard(strategy, i);
      });

      if (premiumCount > 0 && !premiumUnlocked) {
        const bookingUrl = (typeof window.__cpaBookingUrl !== 'undefined' && window.__cpaBookingUrl) ? window.__cpaBookingUrl : '/for-cpas';
        aiResponse += '<div class="cpa-soft-prompt"><div class="cpa-soft-prompt__text">Unlock ' + premiumCount + ' CPA-recommended strategies to see your full savings potential</div>';
        aiResponse += '<div class="cpa-soft-prompt__actions"><a class="cpa-soft-prompt__btn-primary" href="/upgrade">Unlock All Strategies →</a>';
        aiResponse += '<a class="cpa-soft-prompt__btn-secondary" href="' + bookingUrl + '">Talk to a CPA</a></div></div>';
      }
    }

    if (data.premium_unlocked !== undefined) {
      setPremiumUnlocked(data.premium_unlocked);
    }

    if (data.safety_summary && data.response_type === 'calculation') {
      aiResponse += renderSafetySummary(data.safety_summary);
    }

    // IRS Circular 230 disclaimer — shown on tax calculation and strategy responses
    if (data.response_type === 'calculation' || data.response_type === 'strategy' || data.response_type === 'report') {
      aiResponse += '<p class="circular230-disclaimer">Any tax advice contained in this communication was not intended or written to be used, and cannot be used, for the purpose of avoiding penalties under the Internal Revenue Code.</p>';
    }

    addMessage('ai', aiResponse, quickActions, { multiSelect: data.multi_select || false });

    if (data.profile_completeness !== undefined) {
      updateProgress(
        Math.round(data.profile_completeness * 100),
        data.missing_fields || [],
        data.completion_hint || null
      );
    }

    updatePhaseFromData();

    if (data.key_insights && data.key_insights.length > 0) {
      updateInsights(data.key_insights);
    }
    if (data.warnings && data.warnings.length > 0) {
      data.warnings.forEach(w => DevLogger.warn('Tax warning:', w));
    }

    saveSessionData();
    updateSavingsEstimate();

    if (data.estimated_savings_preview && data.estimated_savings_preview > 0 && !data.total_potential_savings) {
      LiveSavingsDisplay.updatePreview(data.estimated_savings_preview);
    }

    const displaySavings = data.detected_savings || data.total_potential_savings;
    if (displaySavings) {
      LiveSavingsDisplay.update(displaySavings);
    }

    if (data.new_opportunities && data.new_opportunities.length > 0) {
      data.new_opportunities.forEach(function(opp) {
        const alertText = opp.title || opp.summary || 'New savings opportunity detected!';
        const savingsText = opp.estimated_savings ? ' \u2014 Save $' + Number(opp.estimated_savings).toLocaleString() : '';
        showToast(alertText + savingsText, 'success');
      });
    }

    checkForCelebration(data);

  } catch (error) {
    clearTimeout(thinkingTimer);
    clearTimeout(extendedTimer);
    hideTyping();
    DevLogger.error('AI response error:', error);

    let errorMessage = '';
    let quickActions = generateSmartQuickActions();

    if (error.message && error.message.includes('429')) {
      errorMessage = "I'm getting a lot of requests right now. Please wait a moment before sending another message.";
      quickActions = [
        { label: 'Wait 30 seconds', value: 'wait_retry' },
        { label: 'Start over', value: 'reset_conversation' }
      ];
    } else if (error.message && error.message.includes('404')) {
      setSessionId(null);
      sessionStorage.removeItem('tax_session_id');
      setConversationHistory([]);
      resetQuestioningState();
      setRetryCount(0);
      errorMessage = "Your session expired. I've preserved your tax data, but let's start our conversation fresh. How can I help you?";
      quickActions = [
        { label: 'Continue with my data', value: 'no_manual' },
        { label: 'Start completely fresh', value: 'reset_conversation' }
      ];
    } else if ((error.message && error.message.includes('504')) || (error.message && error.message.includes('timeout'))) {
      errorMessage = "That's taking longer than expected. Could you try rephrasing your question or asking something simpler?";
    } else if (!navigator.onLine) {
      errorMessage = "It looks like you're offline. Please check your internet connection and try again.";
      quickActions = [
        { label: 'Try again', value: 'retry_message' }
      ];
    } else {
      errorMessage = generateIntelligentFallback(userMessage);
    }

    addMessage('ai', errorMessage, quickActions);
  } finally {
    setIsProcessing(false);
  }
}

// ======================== KEY HANDLER ========================

export function handleKeyDown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
}

// ======================== HELPER: SMART QUICK ACTIONS ========================

function getCurrentProgress() {
  const progressFill = document.getElementById('progressFill');
  if (progressFill) {
    const width = progressFill.style.width;
    return parseInt(width) || 0;
  }
  return 0;
}

function generateSmartQuickActions() {
  const progress = getCurrentProgress();

  if (progress < 20) {
    return [
      { label: 'Tell you my situation', value: 'no_manual' },
      { label: 'Upload documents', value: 'yes_upload' },
      { label: '\u2753 How does this work?', value: 'how_it_works' }
    ];
  } else if (progress < 50) {
    return [
      { label: 'Continue the assessment', value: 'continue_assessment' },
      { label: '\u2753 I have a question', value: 'ask_question' },
      { label: 'Add documents', value: 'add_documents' }
    ];
  } else if (progress < 90) {
    return [
      { label: '\u2705 Continue to report', value: 'continue_to_report' },
      { label: 'Ask something else', value: 'ask_question' },
      { label: 'Review what we covered', value: 'review_summary' }
    ];
  } else {
    return [
      { label: 'Generate my report', value: 'generate_report' },
      { label: 'Schedule consultation', value: 'schedule_consult' },
      { label: 'I have questions', value: 'more_questions' }
    ];
  }
}

function generateIntelligentFallback(userMessage) {
  const lowerMessage = userMessage.toLowerCase();

  if (lowerMessage.includes('deduction') || lowerMessage.includes('deduct')) {
    return `Great question about deductions! Deductions reduce your taxable income. Common ones include:<br><br>\u2022 Mortgage interest<br>\u2022 Charitable donations<br>\u2022 State and local taxes<br>\u2022 Medical expenses (if over 7.5% of income)<br>\u2022 Business expenses<br><br>To provide specific guidance for your situation, I need to know a bit more about you. <strong>What's your filing status?</strong>`;
  }

  if (lowerMessage.includes('credit')) {
    return `Tax credits are even better than deductions - they reduce your tax bill dollar-for-dollar! Common credits include:<br><br>\u2022 Child Tax Credit<br>\u2022 Earned Income Credit<br>\u2022 Education credits<br>\u2022 Energy efficiency credits<br><br>Let me learn more about your situation so I can identify which credits you qualify for. <strong>Shall we continue with your assessment?</strong>`;
  }

  if (lowerMessage.includes('save') || lowerMessage.includes('savings')) {
    return `I love that you're focused on savings! The amount you can save depends on your specific situation. On average, strategic tax planning saves our clients $2,000-$15,000 annually.<br><br><strong>Would you like to complete a quick assessment so I can estimate your savings?</strong>`;
  }

  if (lowerMessage.includes('confused') || lowerMessage.includes("don't understand") || lowerMessage.includes('help')) {
    return `I'm sorry for any confusion! Let me make this simpler.<br><br>I'm here to help you save money on your taxes. All you need to do is answer a few quick questions about your situation, and I'll provide personalized recommendations.<br><br><strong>Would you like to start with something simple? What's your filing status?</strong>`;
  }

  return `I appreciate your question! While I'm here primarily to help with your tax advisory needs, I want to make sure I address your concern properly.<br><br>To give you the most accurate guidance, let me learn more about your tax situation.<br><br><strong>Would you like to continue with your tax assessment, or do you have other specific questions?</strong>`;
}

// ======================== OFFLINE QUEUE ========================

export function queueOfflineMessage(message) {
  if (offlineQueue.length >= RobustnessConfig.offlineQueueMax) {
    showToast('Offline queue full. Please wait for connection.', 'error');
    return false;
  }
  offlineQueue.push(message);
  showToast(`Message queued. ${offlineQueue.length} message(s) waiting.`, 'info');
  return true;
}

// ======================== UX INPUT HELPERS ========================

function createCurrencyInput(placeholder = 'Enter amount', onSubmit) {
  const wrapper = document.createElement('div');
  wrapper.className = 'currency-input-wrapper';
  wrapper.style.marginTop = '16px';

  const symbol = document.createElement('span');
  symbol.className = 'currency-symbol';
  symbol.textContent = '$';

  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'currency-input';
  input.placeholder = placeholder;
  input.inputMode = 'numeric';

  input.addEventListener('input', (e) => {
    let value = e.target.value.replace(/[^\d]/g, '');
    if (value) {
      e.target.value = parseInt(value).toLocaleString();
    }
  });

  input.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && input.value) {
      const numValue = parseInt(input.value.replace(/[^\d]/g, ''));
      if (onSubmit) onSubmit(numValue);
    }
  });

  wrapper.appendChild(symbol);
  wrapper.appendChild(input);

  const submitDiv = document.createElement('div');
  submitDiv.className = 'dropdown-submit';

  const submitBtn = document.createElement('button');
  submitBtn.textContent = 'Continue \u2192';
  submitBtn.onclick = () => {
    if (input.value) {
      const numValue = parseInt(input.value.replace(/[^\d]/g, ''));
      if (onSubmit) onSubmit(numValue);
    }
  };

  submitDiv.appendChild(submitBtn);

  const container = document.createElement('div');
  container.appendChild(wrapper);
  container.appendChild(submitDiv);

  return container;
}

function createSliderInput(min, max, step, defaultValue, formatFn, onSubmit) {
  const wrapper = document.createElement('div');
  wrapper.className = 'slider-input-wrapper';

  const display = document.createElement('div');
  display.className = 'slider-value-display';
  display.textContent = formatFn(defaultValue);

  const slider = document.createElement('input');
  slider.type = 'range';
  slider.className = 'slider-input';
  slider.min = min;
  slider.max = max;
  slider.step = step;
  slider.value = defaultValue;

  slider.addEventListener('input', () => {
    display.textContent = formatFn(parseInt(slider.value));
  });

  const labels = document.createElement('div');
  labels.className = 'slider-labels';
  labels.innerHTML = `<span>${formatFn(min)}</span><span>${formatFn(max)}</span>`;

  wrapper.appendChild(display);
  wrapper.appendChild(slider);
  wrapper.appendChild(labels);

  const submitDiv = document.createElement('div');
  submitDiv.className = 'dropdown-submit';
  submitDiv.style.textAlign = 'center';

  const submitBtn = document.createElement('button');
  submitBtn.textContent = 'Confirm Amount \u2192';
  submitBtn.onclick = () => {
    if (onSubmit) onSubmit(parseInt(slider.value));
  };

  submitDiv.appendChild(submitBtn);
  wrapper.appendChild(submitDiv);

  return wrapper;
}

function createSecurityNotice() {
  const notice = document.createElement('div');
  notice.className = 'security-notice';
  notice.innerHTML = `
    <span class="security-notice-icon">\uD83D\uDD12</span>
    <span>Your data is encrypted and never shared. We follow IRS data protection guidelines.</span>
  `;
  return notice;
}

// ======================== BUILD SYSTEM CONTEXT ========================

export function buildSystemContext() {
  const progress = getCurrentProgress();
  const confidence = getConfidenceLevel();

  return {
    role: 'system',
    content: `You are a premium CPA tax advisor AI assistant specializing in individual tax advisory.

Tax Year: 2025
Data Confidence: ${confidence.level} (${confidence.percentage}% complete)
Progress: ${progress}%
Filing Status: ${extractedData.filing_status || 'Not yet provided'}

RESPONSE GUIDELINES:
1. Maintain a warm, experienced advisor tone
2. ALWAYS use 2025 IRS rules with source citations when specific
3. Always recommend consulting a licensed CPA for final decisions`
  };
}
