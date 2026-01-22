# Step 1 Wizard Flattening - Implementation Plan

## Current Problem

Step 1 has a **wizard-within-a-wizard** pattern that confuses users:
- Main step progress bar (6 steps total)
- Nested wizard progress bar (4 substeps within Step 1)
- Users see double progress indicators
- Questions appear one at a time, requiring multiple clicks
- Difficult to go back and change answers

### Current Structure

```
Step 1: About You
├── Substep 1a: Marital status? (Progress: 1/4)
├── Substep 1b-widow: Death year? (Progress: 2/4) [if widowed]
├── Substep 1b-married: Joint or separate? (Progress: 2/4) [if married]
├── Substep 1c: Has dependents? (Progress: 3/4)
├── Substep 1c-dependents: Dependent details (Progress: 3/4) [if yes]
├── Substep 1d: Personal info form (Progress: 4/4)
└── (7+ clicks to complete)
```

## Proposed Solution

**Single-page progressive disclosure** - all questions visible but conditionally shown:

```
Step 1: About You
┌─────────────────────────────────────────────┐
│ 1. Marital status? [Visible always]        │
│    ✓ Answer selected                        │
│                                              │
│ 2. Death year? [Shows if widowed]          │
│    OR                                        │
│    Joint/Separate? [Shows if married]      │
│    ✓ Answer selected                        │
│                                              │
│ 3. Have dependents? [Visible always]       │
│    ✓ Answer selected                        │
│                                              │
│ 4. Dependent details [Shows if yes]        │
│    + Add dependent button                   │
│    ✓ 2 dependents added                     │
│                                              │
│ 5. Personal Information [Visible always]   │
│    Form fields auto-populated               │
│                                              │
│ [Continue to Next Step →]                   │
└─────────────────────────────────────────────┘
```

## Benefits

1. **Visibility**: Users see all questions at once (no surprises)
2. **Editability**: Easy to scroll up and change answers
3. **Progress**: Single progress indicator (main 6-step bar)
4. **Speed**: Fewer clicks (1 Continue vs 4-7 Continue buttons)
5. **Clarity**: No nested wizards to understand

## Implementation Steps

### Step 1: Backup Current Implementation

```bash
cp src/web/templates/index.html src/web/templates/index.html.backup.step1flatten
```

### Step 2: Create New Flattened HTML Structure

Replace substep divs with a single container using progressive disclosure:

```html
<div id="step1" class="step-view hidden">
  <div class="step-header">...</div>

  <div class="flattened-wizard">
    <!-- Question 1: Always visible -->
    <div class="fw-question" data-question="marital">
      <div class="fwq-label">
        <span class="fwq-number">1</span>
        <h3>Marital Status</h3>
      </div>
      <div class="fwq-options">...</div>
      <div class="fwq-check hidden">✓ Answered</div>
    </div>

    <!-- Question 2a: Conditional on widowed -->
    <div class="fw-question hidden" data-question="spouse_death" data-show-if="marital:widowed">
      ...
    </div>

    <!-- Question 2b: Conditional on married -->
    <div class="fw-question hidden" data-question="married_filing" data-show-if="marital:married">
      ...
    </div>

    <!-- Question 3: Always visible -->
    <div class="fw-question" data-question="has_dependents">
      ...
    </div>

    <!-- Question 4: Conditional on has dependents -->
    <div class="fw-question hidden" data-question="dependents" data-show-if="has_dependents:yes">
      ...
    </div>

    <!-- Question 5: Personal info form - Always visible -->
    <div class="fw-question" data-question="personal_info">
      ...
    </div>
  </div>

  <div class="nav-buttons">
    <button class="btn btn-secondary" onclick="goToWelcome()">Back</button>
    <button class="btn btn-primary" id="btnStep1Continue">Continue to Documents →</button>
  </div>
</div>
```

### Step 3: Add Progressive Disclosure Styles

```css
.flattened-wizard {
  display: flex;
  flex-direction: column;
  gap: 24px;
  margin-bottom: 32px;
}

.fw-question {
  background: white;
  border: 2px solid var(--gray-200);
  border-radius: 16px;
  padding: 24px;
  transition: all 0.3s ease;
}

.fw-question.answered {
  border-color: var(--success);
  background: rgba(72, 187, 120, 0.05);
}

.fwq-label {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.fwq-number {
  width: 32px;
  height: 32px;
  background: var(--primary);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  flex-shrink: 0;
}

.fw-question.answered .fwq-number {
  background: var(--success);
}

.fwq-check {
  margin-top: 12px;
  color: var(--success);
  font-weight: 600;
  font-size: 14px;
}
```

### Step 4: Update JavaScript Logic

Replace substep navigation with progressive disclosure:

```javascript
// Track answers
const step1Answers = {
  marital: null,
  spouse_death: null,
  married_filing: null,
  has_dependents: null,
  dependents: [],
  // ... personal info fields
};

// Handle answer selection
document.querySelectorAll('.fw-question .wizard-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const question = btn.closest('.fw-question').dataset.question;
    const value = btn.dataset.value;

    // Save answer
    step1Answers[question] = value;

    // Mark question as answered
    const questionDiv = btn.closest('.fw-question');
    questionDiv.classList.add('answered');
    questionDiv.querySelector('.fwq-check').classList.remove('hidden');

    // Show/hide conditional questions
    updateConditionalQuestions();

    // Scroll to next unanswered question
    scrollToNextQuestion();
  });
});

function updateConditionalQuestions() {
  document.querySelectorAll('.fw-question[data-show-if]').forEach(q => {
    const condition = q.dataset.showIf;
    const [condQuestion, condValue] = condition.split(':');

    if (step1Answers[condQuestion] === condValue) {
      q.classList.remove('hidden');
    } else {
      q.classList.add('hidden');
      // Clear answer if hidden
      const qName = q.dataset.question;
      step1Answers[qName] = null;
      q.classList.remove('answered');
    }
  });
}

function scrollToNextQuestion() {
  const unanswered = document.querySelector('.fw-question:not(.answered):not(.hidden)');
  if (unanswered) {
    unanswered.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

// Validation before continue
document.getElementById('btnStep1Continue').addEventListener('click', () => {
  if (validateStep1()) {
    showStep(2);
  } else {
    alert('Please answer all required questions');
  }
});

function validateStep1() {
  // Check required answers
  if (!step1Answers.marital) return false;

  // Conditional validations
  if (step1Answers.marital === 'widowed' && !step1Answers.spouse_death) return false;
  if (step1Answers.marital === 'married' && !step1Answers.married_filing) return false;

  if (!step1Answers.has_dependents) return false;
  if (step1Answers.has_dependents === 'yes' && step1Answers.dependents.length === 0) return false;

  // Personal info validation
  // ... validate form fields

  return true;
}
```

### Step 5: Remove Old Substep Functions

Delete or comment out:
- `showSubstep()`
- `hideAllSubsteps()`
- Individual substep navigation handlers

### Step 6: Update State Management

Ensure `state.wizard` object captures all Step 1 answers in flattened format.

### Step 7: Testing Checklist

- [ ] Marital status question appears first
- [ ] Widow path: Shows death year question
- [ ] Married path: Shows joint/separate question
- [ ] Single path: Skips spouse questions
- [ ] Dependents question always shows
- [ ] Dependent details only show if "yes"
- [ ] Personal info form always shows
- [ ] Can edit previous answers by scrolling up
- [ ] Validation prevents incomplete submission
- [ ] All answers saved to state correctly
- [ ] Step 2 receives correct data
- [ ] Mobile responsive layout works
- [ ] Keyboard navigation works
- [ ] Screen readers can navigate questions

## Risk Mitigation

### Rollback Plan

If issues occur:
```bash
cp src/web/templates/index.html.backup.step1flatten src/web/templates/index.html
```

### Gradual Rollout

1. Implement behind feature flag: `FLATTEN_STEP1=true/false`
2. A/B test with 10% of users
3. Monitor completion rates and time-to-complete
4. Full rollout if metrics improve

### Metrics to Track

- **Step 1 completion rate** (before vs after)
- **Time to complete Step 1** (should decrease)
- **Back button usage** (should increase - easier to edit)
- **Drop-off rate** (should decrease)
- **User feedback** (survey after filing)

## Estimated Effort

- HTML restructuring: 4 hours
- CSS updates: 2 hours
- JavaScript refactoring: 6 hours
- Testing & bug fixes: 4 hours
- **Total: 16 hours**

## Success Criteria

- ✅ Single progress indicator (main 6-step bar)
- ✅ All questions visible in one scroll
- ✅ Conditional questions show/hide based on answers
- ✅ Visual feedback when questions answered
- ✅ Smooth scrolling to next question
- ✅ Easy to edit previous answers
- ✅ Single "Continue" button
- ✅ Validation before proceeding
- ✅ No regression in data collection
- ✅ Faster completion time (target: <2 minutes for Step 1)
