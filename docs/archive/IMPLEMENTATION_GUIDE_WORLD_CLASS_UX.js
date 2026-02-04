// ========================================================================
// WORLD-CLASS UX ENHANCEMENTS - IMPLEMENTATION GUIDE
// ========================================================================
// Add these features to make this the world's most user-friendly tax advisor
// ========================================================================

// ========================================================================
// 1. NATURAL LANGUAGE PROCESSING - SMART ENTITY EXTRACTION
// ========================================================================

/**
 * Extracts tax-related entities from natural language input
 * Example: "I made 85k last year from my job and 15k freelancing"
 * Returns: { w2_income: 85000, business_income: 15000 }
 */
async function extractEntitiesFromText(text) {
  const entities = {};

  // Income patterns
  const incomePatterns = [
    /(?:made|earned|income|salary|wage).*?[\$]?(\d{1,3}(?:,\d{3})*(?:k|K)?)/gi,
    /(\d{1,3}(?:,\d{3})*(?:k|K)?)\s*(?:dollars?|income|salary)/gi
  ];

  incomePatterns.forEach(pattern => {
    const matches = text.matchAll(pattern);
    for (const match of matches) {
      let amount = match[1].replace(/,/g, '');
      if (amount.toLowerCase().endsWith('k')) {
        amount = parseFloat(amount) * 1000;
      } else {
        amount = parseFloat(amount);
      }
      if (!entities.total_income || amount > entities.total_income) {
        entities.total_income = amount;
      }
    }
  });

  // Dependents/children patterns
  const dependentsPatterns = [
    /(\d+)\s*(?:kids?|children|dependents)/gi,
    /(?:kids?|children|dependents)[:\s]*(\d+)/gi
  ];

  dependentsPatterns.forEach(pattern => {
    const match = text.match(pattern);
    if (match) {
      entities.dependents = parseInt(match[1]);
    }
  });

  // Filing status patterns
  if (/\b(?:married|spouse|wife|husband)\b/i.test(text)) {
    entities.filing_status = 'Married Filing Jointly';
  } else if (/\b(?:single|unmarried)\b/i.test(text)) {
    entities.filing_status = 'Single';
  } else if (/\bhead of household\b/i.test(text)) {
    entities.filing_status = 'Head of Household';
  }

  // Mortgage interest
  const mortgageMatch = text.match(/mortgage\s*(?:interest)?[:\s]*[\$]?(\d{1,3}(?:,\d{3})*)/i);
  if (mortgageMatch) {
    entities.mortgage_interest = parseFloat(mortgageMatch[1].replace(/,/g, ''));
  }

  // Charitable donations
  const charityMatch = text.match(/(?:charitable?|donat(?:ion|ed))[:\s]*[\$]?(\d{1,3}(?:,\d{3})*)/i);
  if (charityMatch) {
    entities.charitable = parseFloat(charityMatch[1].replace(/,/g, ''));
  }

  // State
  const stateMatch = text.match(/\b(Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|CA|NY|TX|FL|IL|PA|OH|GA|NC|MI)\b/i);
  if (stateMatch) {
    entities.state = stateMatch[1];
  }

  console.log('Extracted entities:', entities);
  return entities;
}

// ========================================================================
// 2. SMART AUTO-SUGGESTIONS AS USER TYPES
// ========================================================================

const SMART_SUGGESTIONS = {
  income: [
    { text: "I made $85,000 from my job last year", icon: "💼", category: "W-2 Income" },
    { text: "I earned $120,000 in total income", icon: "💰", category: "Total Income" },
    { text: "My salary was $95,000", icon: "💵", category: "Salary" }
  ],
  kids: [
    { text: "I have 2 children under 17", icon: "👶", category: "Dependents" },
    { text: "I have 1 dependent", icon: "👨‍👩‍👧", category: "Dependents" },
    { text: "I have 3 kids", icon: "👨‍👩‍👧‍👦", category: "Dependents" }
  ],
  mortgage: [
    { text: "I paid $12,000 in mortgage interest", icon: "🏠", category: "Deduction" },
    { text: "My mortgage interest was $8,500", icon: "🏡", category: "Deduction" }
  ],
  married: [
    { text: "I'm married filing jointly", icon: "💑", category: "Filing Status" },
    { text: "I'm single", icon: "👤", category: "Filing Status" }
  ],
  business: [
    { text: "I have self-employment income of $45,000", icon: "💼", category: "Business" },
    { text: "I made $30,000 from freelancing", icon: "💻", category: "Business" }
  ],
  charity: [
    { text: "I donated $5,000 to charity", icon: "💝", category: "Deduction" },
    { text: "My charitable donations were $3,200", icon: "❤️", category: "Deduction" }
  ]
};

function showSmartSuggestions(inputText) {
  const text = inputText.toLowerCase();
  let matchedSuggestions = [];

  // Match keywords
  if (text.includes('income') || text.includes('made') || text.includes('earn') || text.includes('salary')) {
    matchedSuggestions = SMART_SUGGESTIONS.income;
  } else if (text.includes('kid') || text.includes('child') || text.includes('dependent')) {
    matchedSuggestions = SMART_SUGGESTIONS.kids;
  } else if (text.includes('mortgage') || text.includes('house') || text.includes('home')) {
    matchedSuggestions = SMART_SUGGESTIONS.mortgage;
  } else if (text.includes('married') || text.includes('single') || text.includes('filing')) {
    matchedSuggestions = SMART_SUGGESTIONS.married;
  } else if (text.includes('business') || text.includes('freelanc') || text.includes('self-employ')) {
    matchedSuggestions = SMART_SUGGESTIONS.business;
  } else if (text.includes('donat') || text.includes('charity') || text.includes('charitable')) {
    matchedSuggestions = SMART_SUGGESTIONS.charity;
  }

  if (matchedSuggestions.length > 0) {
    displaySuggestions(matchedSuggestions);
  } else {
    hideSuggestions();
  }
}

function displaySuggestions(suggestions) {
  const container = document.getElementById('smartSuggestions');
  if (!container) return;

  container.innerHTML = suggestions.map(s => `
    <div class="suggestion-item" onclick="useSuggestion('${s.text.replace(/'/g, "\\'")}')">
      <span class="suggestion-icon">${s.icon}</span>
      <div class="suggestion-text">
        <div>${s.text}</div>
        <div class="suggestion-hint">${s.category}</div>
      </div>
    </div>
  `).join('');

  container.classList.add('active');
}

function hideSuggestions() {
  const container = document.getElementById('smartSuggestions');
  if (container) {
    container.classList.remove('active');
  }
}

function useSuggestion(text) {
  const input = document.getElementById('userInput');
  if (input) {
    input.value = text;
    input.focus();
    hideSuggestions();

    // Optionally auto-send
    setTimeout(() => sendMessage(), 300);
  }
}

// ========================================================================
// 3. REAL-TIME CALCULATION PREVIEW
// ========================================================================

let calculationTimeout = null;

async function showLiveCalculationPreview(extractedData) {
  // Debounce calculations
  clearTimeout(calculationTimeout);

  calculationTimeout = setTimeout(async () => {
    if (!extractedData.tax_profile.total_income || !extractedData.tax_profile.filing_status) {
      return;
    }

    try {
      const response = await fetch('/api/calculate-tax', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filing_status: extractedData.tax_profile.filing_status,
          total_income: extractedData.tax_profile.total_income,
          w2_income: extractedData.tax_profile.w2_income || extractedData.tax_profile.total_income,
          deductions: extractedData.tax_items,
          dependents: extractedData.tax_profile.dependents || 0,
          tax_year: 2025
        })
      });

      if (response.ok) {
        const calc = await response.json();
        displayLivePreview(calc);
      }
    } catch (error) {
      console.error('Live calculation error:', error);
    }
  }, 500); // Wait 500ms after user stops typing
}

function displayLivePreview(calculation) {
  // Create or update floating preview
  let preview = document.getElementById('livePreview');

  if (!preview) {
    preview = document.createElement('div');
    preview.id = 'livePreview';
    preview.style.cssText = `
      position: fixed;
      bottom: 120px;
      right: 40px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 20px;
      border-radius: 16px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.3);
      min-width: 250px;
      z-index: 1000;
      animation: slideInUp 0.3s ease;
    `;
    document.body.appendChild(preview);
  }

  preview.innerHTML = `
    <div style="font-size: 12px; opacity: 0.9; margin-bottom: 8px;">Live Preview</div>
    <div style="font-size: 24px; font-weight: 700;">$${Math.round(calculation.total_tax).toLocaleString()}</div>
    <div style="font-size: 14px; opacity: 0.9; margin-top: 4px;">Est. Tax Liability</div>
    ${calculation.potential_savings > 0 ? `
      <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.3);">
        <div style="color: #10b981; font-weight: 600;">💰 Save $${Math.round(calculation.potential_savings).toLocaleString()}</div>
      </div>
    ` : ''}
  `;
}

// ========================================================================
// 4. VOICE INPUT INTEGRATION
// ========================================================================

let recognition = null;

function startVoiceInput() {
  const btn = document.getElementById('voiceBtn');

  // Check browser support
  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    alert('Voice input is not supported in your browser. Please use Chrome or Edge.');
    return;
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();

  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = 'en-US';

  recognition.onstart = () => {
    btn.textContent = '🔴'; // Recording indicator
    btn.style.animation = 'pulse 1s infinite';
  };

  recognition.onresult = (event) => {
    const transcript = Array.from(event.results)
      .map(result => result[0])
      .map(result => result.transcript)
      .join('');

    document.getElementById('userInput').value = transcript;

    // Show live suggestions as they speak
    showSmartSuggestions(transcript);
  };

  recognition.onend = () => {
    btn.textContent = '🎤';
    btn.style.animation = '';

    // Auto-send if we have content
    const input = document.getElementById('userInput').value;
    if (input.trim()) {
      setTimeout(() => sendMessage(), 500);
    }
  };

  recognition.onerror = (event) => {
    console.error('Speech recognition error:', event.error);
    btn.textContent = '🎤';
    btn.style.animation = '';

    if (event.error === 'no-speech') {
      alert('No speech detected. Please try again.');
    }
  };

  recognition.start();
}

// ========================================================================
// 5. ENHANCED MESSAGE PROCESSING WITH AUTO-EXTRACTION
// ========================================================================

async function processMessageWithNLU(userMessage) {
  // Extract entities from natural language
  const entities = await extractEntitiesFromText(userMessage);

  // Merge entities into extractedData
  if (Object.keys(entities).length > 0) {
    mergeExtractedData(entities);

    // Show what we understood
    const understood = Object.keys(entities).map(key => {
      if (key === 'total_income') return `Income: $${entities[key].toLocaleString()}`;
      if (key === 'dependents') return `${entities[key]} dependent(s)`;
      if (key === 'filing_status') return entities[key];
      if (key === 'mortgage_interest') return `Mortgage interest: $${entities[key].toLocaleString()}`;
      if (key === 'charitable') return `Charitable: $${entities[key].toLocaleString()}`;
      if (key === 'state') return `State: ${entities[key]}`;
      return `${key}: ${entities[key]}`;
    }).join(', ');

    // Show confirmation
    addMessage('ai', `✓ Got it! I understood: <strong>${understood}</strong>`, [], true);

    // Update live preview
    showLiveCalculationPreview(extractedData);

    // Update progress
    calculateLeadScore();
  }

  // Send to OpenAI for conversational response
  await processAIResponse(userMessage);
}

// ========================================================================
// 6. SMART INPUT HANDLER (Main Entry Point)
// ========================================================================

function handleSmartInput(textarea) {
  const text = textarea.value;

  // Auto-resize
  textarea.style.height = 'auto';
  textarea.style.height = (textarea.scrollHeight) + 'px';

  // Show smart suggestions (debounced)
  clearTimeout(window.suggestionTimeout);
  window.suggestionTimeout = setTimeout(() => {
    if (text.length > 2) {
      showSmartSuggestions(text);
    } else {
      hideSuggestions();
    }
  }, 300);
}

// ========================================================================
// 7. COMPARISON SCENARIOS
// ========================================================================

async function showComparisonScenarios() {
  const currentTax = taxCalculations.total_tax;
  const currentIncome = extractedData.tax_profile.total_income;

  // Scenario 1: With 401k contribution
  const scenario1 = await calculateScenario({
    ...extractedData,
    tax_items: {
      ...extractedData.tax_items,
      retirement_contributions: 10000
    }
  });

  // Scenario 2: With HSA
  const scenario2 = await calculateScenario({
    ...extractedData,
    tax_items: {
      ...extractedData.tax_items,
      hsa_contribution: 4150
    }
  });

  addMessage('ai', `
    <div class="insight-card">
      <strong style="font-size: 18px;">💡 Optimization Scenarios</strong>

      <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 16px 0;">
        <div style="background: rgba(255,255,255,0.05); padding: 16px; border-radius: 8px;">
          <div style="font-size: 12px; opacity: 0.7;">Current</div>
          <div style="font-size: 20px; font-weight: 700;">$${Math.round(currentTax).toLocaleString()}</div>
          <div style="font-size: 12px; margin-top: 8px;">Tax owed</div>
        </div>

        <div style="background: rgba(16,185,129,0.1); padding: 16px; border-radius: 8px; border: 2px solid #10b981;">
          <div style="font-size: 12px; opacity: 0.7;">+ 401(k) $10k</div>
          <div style="font-size: 20px; font-weight: 700; color: #10b981;">$${Math.round(scenario1.total_tax).toLocaleString()}</div>
          <div style="font-size: 12px; margin-top: 8px; color: #10b981;">Save $${Math.round(currentTax - scenario1.total_tax).toLocaleString()}</div>
        </div>

        <div style="background: rgba(16,185,129,0.1); padding: 16px; border-radius: 8px; border: 2px solid #10b981;">
          <div style="font-size: 12px; opacity: 0.7;">+ HSA $4,150</div>
          <div style="font-size: 20px; font-weight: 700; color: #10b981;">$${Math.round(scenario2.total_tax).toLocaleString()}</div>
          <div style="font-size: 12px; margin-top: 8px; color: #10b981;">Save $${Math.round(currentTax - scenario2.total_tax).toLocaleString()}</div>
        </div>
      </div>

      <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.1);">
        <strong>Want to implement these strategies?</strong>
      </div>
    </div>
  `, [
    { label: '✅ Yes, optimize my taxes', value: 'implement_optimization' },
    { label: '📊 Show more scenarios', value: 'more_scenarios' },
    { label: '🤝 Discuss with CPA', value: 'request_cpa_early' }
  ]);
}

// ========================================================================
// 8. MOBILE OPTIMIZATIONS
// ========================================================================

// Detect mobile
const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

if (isMobile) {
  // Add mobile-specific styles
  document.body.classList.add('mobile');

  // Enable touch gestures
  let touchStartX = 0;
  let touchEndX = 0;

  document.addEventListener('touchstart', e => {
    touchStartX = e.changedTouches[0].screenX;
  });

  document.addEventListener('touchend', e => {
    touchEndX = e.changedTouches[0].screenX;
    handleGesture();
  });

  function handleGesture() {
    const swipeThreshold = 50;
    if (touchEndX < touchStartX - swipeThreshold) {
      // Swipe left - next question
      console.log('Swiped left');
    }
    if (touchEndX > touchStartX + swipeThreshold) {
      // Swipe right - previous question
      console.log('Swiped right');
    }
  }
}

// ========================================================================
// 9. PROGRESS PERSISTENCE
// ========================================================================

function saveProgress() {
  localStorage.setItem('tax_advisory_progress', JSON.stringify({
    extractedData,
    conversationHistory,
    sessionId,
    timestamp: Date.now()
  }));
}

function loadProgress() {
  const saved = localStorage.getItem('tax_advisory_progress');
  if (!saved) return false;

  const data = JSON.parse(saved);

  // Check if less than 7 days old
  const ageInDays = (Date.now() - data.timestamp) / (1000 * 60 * 60 * 24);
  if (ageInDays > 7) {
    localStorage.removeItem('tax_advisory_progress');
    return false;
  }

  // Restore data
  extractedData = data.extractedData;
  conversationHistory = data.conversationHistory;
  sessionId = data.sessionId;

  // Show resume message
  const completion = getCurrentProgress();
  addMessage('ai', `
    <div class="insight-card">
      <strong>👋 Welcome back!</strong><br><br>
      I found your saved progress from ${new Date(data.timestamp).toLocaleDateString()}.
      You were ${completion}% complete with your tax analysis.<br><br>
      Would you like to continue where you left off?
    </div>
  `, [
    { label: '✅ Yes, continue', value: 'resume_progress' },
    { label: '🔄 Start fresh', value: 'start_fresh' }
  ]);

  return true;
}

// Auto-save every 30 seconds
setInterval(saveProgress, 30000);

// ========================================================================
// 10. ENHANCED STATS UPDATE WITH ANIMATIONS
// ========================================================================

function updateStatsWithAnimation(stats) {
  if (stats.filing_status) {
    animateStatValue('Filing Status', stats.filing_status);
  }
  if (stats.total_income) {
    animateNumberValue('Total Income', stats.total_income, '$');
  }
  if (stats.dependents !== undefined) {
    animateNumberValue('Dependents', stats.dependents, '');
  }
}

function animateNumberValue(label, targetValue, prefix = '') {
  const duration = 1000;
  const startValue = 0;
  const startTime = Date.now();

  const animate = () => {
    const now = Date.now();
    const progress = Math.min((now - startTime) / duration, 1);
    const currentValue = Math.floor(startValue + (targetValue - startValue) * easeOutCubic(progress));

    updateStatsDisplay(label, prefix + currentValue.toLocaleString());

    if (progress < 1) {
      requestAnimationFrame(animate);
    }
  };

  animate();
}

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

// ========================================================================
// USAGE INSTRUCTIONS
// ========================================================================

/*
TO IMPLEMENT THESE FEATURES:

1. Add to HTML (before closing </script>):
   - Include this entire file

2. Update event handlers:
   - Change: oninput="autoResize(this)"
   - To: oninput="handleSmartInput(this)"

3. Update sendMessage():
   - Change: await processAIResponse(text);
   - To: await processMessageWithNLU(text);

4. Add styles for suggestions (in <style> section):
   - Copy the smart-suggestions CSS from WORLD_CLASS_UX_ENHANCEMENTS.md

5. Add voice button to HTML:
   - Add: <button onclick="startVoiceInput()" id="voiceBtn">🎤</button>

6. Initialize on load:
   - Add: if (!loadProgress()) { sendInitialGreeting(); }

7. Test features:
   - Type "I made 85k" → See suggestions
   - Click 🎤 → Speak your tax info
   - Type income → See live calculation
   - Close and reopen → See saved progress
*/
