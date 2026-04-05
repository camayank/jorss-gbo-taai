# Deductions, Credits, and Filing Wizard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build 5 remaining filing workflow screens (DeductionsScreen, CreditsScreen, FilingStatusOptimizer, ReviewScreen, SubmitScreen) with multi-step wizard navigation, breadcrumb tracking, and real-time tax calculations.

**Architecture:**
- Each screen is a standalone React component following the pattern established in MKW-63 (IncomeScreen, etc.)
- FilingWizard container component orchestrates navigation between screens, maintains shared state, persists to localStorage/API
- All screens use the existing CSS variable system and responsive design patterns (375px mobile-first)
- Real-time integration with `/api/optimize/*` and `/api/estimate` endpoints

**Tech Stack:**
- React 18, TypeScript, React Router
- Existing CSS variable system (`src/web/static/css/core/variables.css`)
- FastAPI backend routes in `src/web/routers/calculations.py`
- localStorage for client-side persistence, API auto-save every 30s

---

## Task 1: Create FilingWizard Container Component

**Files:**
- Create: `apps/web/src/pages/FilingWizard.tsx`
- Create: `apps/web/src/styles/FilingWizard.css`
- Modify: `apps/web/src/App.tsx` (add route)

**Step 1: Write the FilingWizard component with step tracking and navigation**

```typescript
// apps/web/src/pages/FilingWizard.tsx
import { useState, useCallback, useEffect } from 'react'
import '../styles/FilingWizard.css'
import IncomeScreen from './IncomeScreen'
import SelfEmploymentScreen from './SelfEmploymentScreen'
import InvestmentScreen from './InvestmentScreen'
import RealEstateScreen from './RealEstateScreen'
import DeductionsScreen from './DeductionsScreen'
import CreditsScreen from './CreditsScreen'
import FilingStatusOptimizer from './FilingStatusOptimizer'
import ReviewScreen from './ReviewScreen'
import SubmitScreen from './SubmitScreen'

interface FilingWizardState {
  income?: Record<string, any>
  selfEmployment?: Record<string, any>
  investment?: Record<string, any>
  realEstate?: Record<string, any>
  deductions?: Record<string, any>
  credits?: Record<string, any>
  filingStatus?: Record<string, any>
  taxEstimate?: number
}

const STEPS = [
  { id: 'income', label: 'Income', component: IncomeScreen },
  { id: 'selfEmployment', label: 'Self-Employment', component: SelfEmploymentScreen },
  { id: 'investment', label: 'Investments', component: InvestmentScreen },
  { id: 'realEstate', label: 'Real Estate', component: RealEstateScreen },
  { id: 'deductions', label: 'Deductions', component: DeductionsScreen },
  { id: 'credits', label: 'Credits', component: CreditsScreen },
  { id: 'filingStatus', label: 'Filing Status', component: FilingStatusOptimizer },
  { id: 'review', label: 'Review', component: ReviewScreen },
  { id: 'submit', label: 'Submit', component: SubmitScreen },
]

export default function FilingWizard() {
  const [currentStep, setCurrentStep] = useState(0)
  const [wizardState, setWizardState] = useState<FilingWizardState>(() => {
    const saved = localStorage.getItem('filingWizardState')
    return saved ? JSON.parse(saved) : {}
  })

  // Auto-save state every 30s
  useEffect(() => {
    const timer = setInterval(() => {
      localStorage.setItem('filingWizardState', JSON.stringify(wizardState))
      // TODO: Sync with API endpoint
    }, 30000)
    return () => clearInterval(timer)
  }, [wizardState])

  const handleNext = useCallback((data: Record<string, any>) => {
    const stepId = STEPS[currentStep].id
    setWizardState(prev => ({ ...prev, [stepId]: data }))
    if (currentStep < STEPS.length - 1) {
      setCurrentStep(prev => prev + 1)
    }
  }, [currentStep])

  const handleBack = useCallback(() => {
    if (currentStep > 0) {
      setCurrentStep(prev => prev - 1)
    }
  }, [currentStep])

  const CurrentComponent = STEPS[currentStep].component as any

  return (
    <div className="filing-wizard">
      {/* Progress Bar */}
      <div className="wizard-progress">
        <div className="progress-bar">
          <div
            className="progress-fill"
            style={{ width: `${((currentStep + 1) / STEPS.length) * 100}%` }}
          />
        </div>
        <p className="progress-text">Step {currentStep + 1} of {STEPS.length}</p>
      </div>

      {/* Breadcrumb Navigation */}
      <nav className="wizard-breadcrumb">
        <ol>
          {STEPS.map((step, index) => (
            <li key={step.id}>
              <button
                className={`breadcrumb-item ${index === currentStep ? 'active' : ''} ${index < currentStep ? 'completed' : ''}`}
                onClick={() => setCurrentStep(index)}
                disabled={index > currentStep}
              >
                {step.label}
              </button>
            </li>
          ))}
        </ol>
      </nav>

      {/* Current Step Component */}
      <div className="wizard-content">
        <CurrentComponent
          onNext={handleNext}
          onSave={(data) => handleNext(data)}
          initialData={wizardState[STEPS[currentStep].id as keyof FilingWizardState]}
        />
      </div>

      {/* Navigation Buttons */}
      <div className="wizard-footer">
        <button
          className="btn-secondary"
          onClick={handleBack}
          disabled={currentStep === 0}
        >
          Back
        </button>
      </div>
    </div>
  )
}
```

**Step 2: Add FilingWizard CSS**

```css
/* apps/web/src/styles/FilingWizard.css */
@import '../../static/css/core/variables.css';

.filing-wizard {
  min-height: 100vh;
  background: var(--color-gray-50);
  padding: 24px;
}

.wizard-progress {
  max-width: 800px;
  margin: 0 auto 32px;
}

.progress-bar {
  height: 4px;
  background: var(--color-gray-200);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 12px;
}

.progress-fill {
  height: 100%;
  background: var(--color-primary-600);
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 14px;
  color: var(--color-gray-600);
  margin: 0;
}

.wizard-breadcrumb {
  max-width: 800px;
  margin: 0 auto 32px;
}

.wizard-breadcrumb ol {
  display: flex;
  list-style: none;
  padding: 0;
  margin: 0;
  gap: 8px;
  flex-wrap: wrap;
}

.breadcrumb-item {
  padding: 8px 12px;
  border-radius: 4px;
  background: transparent;
  border: 1px solid var(--color-gray-300);
  color: var(--color-gray-600);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s ease;
}

.breadcrumb-item:hover:not(:disabled) {
  border-color: var(--color-primary-400);
  color: var(--color-primary-600);
}

.breadcrumb-item.active {
  background: var(--color-primary-600);
  color: white;
  border-color: var(--color-primary-600);
}

.breadcrumb-item.completed {
  background: var(--color-primary-100);
  color: var(--color-primary-700);
  border-color: var(--color-primary-400);
}

.breadcrumb-item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.wizard-content {
  max-width: 800px;
  margin: 0 auto;
}

.wizard-footer {
  max-width: 800px;
  margin: 32px auto 0;
  display: flex;
  justify-content: space-between;
}

@media (max-width: 600px) {
  .filing-wizard {
    padding: 16px;
  }

  .wizard-breadcrumb ol {
    gap: 4px;
  }

  .breadcrumb-item {
    padding: 6px 10px;
    font-size: 12px;
  }

  .progress-text {
    font-size: 12px;
  }
}
```

**Step 3: Update App.tsx to include FilingWizard route**

In `apps/web/src/App.tsx`, add the FilingWizard route after Dashboard:

```typescript
import FilingWizard from './pages/FilingWizard'

// In Routes component, add:
<Route
  path="/filing-wizard"
  element={
    <ProtectedRoute>
      <FilingWizard />
    </ProtectedRoute>
  }
/>
```

**Step 4: Commit**

```bash
git add apps/web/src/pages/FilingWizard.tsx apps/web/src/styles/FilingWizard.css apps/web/src/App.tsx
git commit -m "feat: add FilingWizard container with step navigation and breadcrumbs"
```

---

## Task 2: Create DeductionsScreen Component

**Files:**
- Create: `apps/web/src/pages/DeductionsScreen.tsx`
- Create: `apps/web/src/styles/DeductionsScreen.css`

**Step 1: Write the DeductionsScreen component**

```typescript
// apps/web/src/pages/DeductionsScreen.tsx
import { useState, useEffect, useCallback } from 'react'
import '../styles/DeductionsScreen.css'

interface DeductionData {
  useStandard: boolean
  standardAmount: number
  scheduleATotal: number
  mortgageInterest: number
  propertyTaxes: number
  stateTaxes: number
  charitableDonations: number
  otherDeductions: number
}

interface DeductionsScreenProps {
  onNext?: () => void
  onSave?: (data: DeductionData) => void
  initialData?: DeductionData
}

export default function DeductionsScreen({ onNext, onSave, initialData }: DeductionsScreenProps) {
  const [data, setData] = useState<DeductionData>(
    initialData || {
      useStandard: true,
      standardAmount: 0,
      scheduleATotal: 0,
      mortgageInterest: 0,
      propertyTaxes: 0,
      stateTaxes: 0,
      charitableDonations: 0,
      otherDeductions: 0,
    }
  )
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [autoSaveStatus, setAutoSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle')

  const scheduleATotal = data.mortgageInterest + data.propertyTaxes + data.stateTaxes + data.charitableDonations + data.otherDeductions
  const recommendation = scheduleATotal > data.standardAmount ? 'Schedule A (Itemize)' : 'Standard Deduction'

  // Auto-save every 30s
  useEffect(() => {
    const timer = setInterval(() => {
      setAutoSaveStatus('saving')
      localStorage.setItem('deductionsScreen', JSON.stringify(data))
      setAutoSaveStatus('saved')
      setTimeout(() => setAutoSaveStatus('idle'), 2000)
    }, 30000)
    return () => clearInterval(timer)
  }, [data])

  const updateField = (field: keyof DeductionData, value: any) => {
    setData(prev => ({ ...prev, [field]: value }))
    if (errors[field]) {
      setErrors(prev => {
        const newErrors = { ...prev }
        delete newErrors[field]
        return newErrors
      })
    }
  }

  const handleNext = () => {
    const newErrors: Record<string, string> = {}

    if (data.mortgageInterest < 0 || data.propertyTaxes < 0 || data.stateTaxes < 0 ||
        data.charitableDonations < 0 || data.otherDeductions < 0) {
      newErrors.amounts = 'Deduction amounts must be non-negative'
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    if (onSave) {
      onSave({ ...data, scheduleATotal })
    }
    if (onNext) {
      onNext()
    }
  }

  return (
    <div className="deductions-screen">
      <div className="screen-header">
        <h1>Deductions</h1>
        <p>Choose between standard and itemized deductions</p>
      </div>

      {/* Deduction Comparison */}
      <div className="deduction-comparison">
        <div className={`comparison-card ${!data.useStandard ? 'highlighted' : ''}`}>
          <h3>Itemize Deductions</h3>
          <div className="deduction-value">${scheduleATotal.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
          <div className="deduction-label">Schedule A Total</div>
        </div>

        <div className={`comparison-card ${data.useStandard ? 'highlighted' : ''}`}>
          <h3>Standard Deduction</h3>
          <div className="deduction-value">${data.standardAmount.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
          <div className="deduction-label">2025 Standard</div>
        </div>

        <div className="recommendation-card">
          <strong>Recommendation:</strong> Use {recommendation}
          <span className="savings-value">
            Save: ${Math.abs(scheduleATotal - data.standardAmount).toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </span>
        </div>
      </div>

      {/* Auto-save Status */}
      {autoSaveStatus === 'saved' && (
        <div className="auto-save-status">✓ Saved</div>
      )}

      {/* Schedule A Entry (Itemized Deductions) */}
      <div className="schedule-a-section">
        <h2>Schedule A: Itemized Deductions</h2>

        <div className="form-section">
          <div className="form-group">
            <label htmlFor="mortgage">Mortgage Interest (Form 1098, Box 1)</label>
            <input
              id="mortgage"
              type="number"
              value={data.mortgageInterest}
              onChange={(e) => updateField('mortgageInterest', parseFloat(e.target.value) || 0)}
              step="0.01"
            />
          </div>

          <div className="form-group">
            <label htmlFor="property-tax">State & Local Property Taxes (SALT)</label>
            <input
              id="property-tax"
              type="number"
              value={data.propertyTaxes}
              onChange={(e) => updateField('propertyTaxes', parseFloat(e.target.value) || 0)}
              step="0.01"
            />
          </div>

          <div className="form-group">
            <label htmlFor="state-tax">State & Local Income Taxes</label>
            <input
              id="state-tax"
              type="number"
              value={data.stateTaxes}
              onChange={(e) => updateField('stateTaxes', parseFloat(e.target.value) || 0)}
              step="0.01"
            />
          </div>

          <div className="form-group">
            <label htmlFor="charitable">Charitable Donations (Form 8283, Schedule A)</label>
            <input
              id="charitable"
              type="number"
              value={data.charitableDonations}
              onChange={(e) => updateField('charitableDonations', parseFloat(e.target.value) || 0)}
              step="0.01"
            />
          </div>

          <div className="form-group">
            <label htmlFor="other">Other Deductions</label>
            <input
              id="other"
              type="number"
              value={data.otherDeductions}
              onChange={(e) => updateField('otherDeductions', parseFloat(e.target.value) || 0)}
              step="0.01"
            />
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div className="screen-footer">
        <button className="btn-secondary">Back</button>
        <button className="btn-primary" onClick={handleNext}>
          Continue
        </button>
      </div>
    </div>
  )
}
```

**Step 2: Add DeductionsScreen CSS**

```css
/* apps/web/src/styles/DeductionsScreen.css */
@import '../../static/css/core/variables.css';

.deductions-screen {
  background: white;
  border-radius: 8px;
  padding: 32px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.screen-header {
  margin-bottom: 32px;
}

.screen-header h1 {
  margin: 0 0 8px;
  color: var(--color-gray-900);
  font-size: 28px;
}

.screen-header p {
  margin: 0;
  color: var(--color-gray-600);
  font-size: 16px;
}

.deduction-comparison {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 32px;
}

.comparison-card {
  padding: 20px;
  border: 2px solid var(--color-gray-200);
  border-radius: 8px;
  background: var(--color-gray-50);
  transition: all 0.2s ease;
}

.comparison-card.highlighted {
  border-color: var(--color-primary-500);
  background: var(--color-primary-50);
}

.comparison-card h3 {
  margin: 0 0 12px;
  color: var(--color-gray-700);
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.deduction-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-primary-600);
  margin-bottom: 4px;
}

.deduction-label {
  font-size: 13px;
  color: var(--color-gray-600);
}

.recommendation-card {
  grid-column: 1 / -1;
  padding: 16px;
  background: var(--color-accent-50);
  border-left: 4px solid var(--color-accent-500);
  border-radius: 4px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
}

.savings-value {
  font-weight: 600;
  color: var(--color-accent-600);
}

.auto-save-status {
  position: fixed;
  top: 24px;
  right: 24px;
  padding: 8px 16px;
  background: var(--color-primary-100);
  color: var(--color-primary-700);
  border-radius: 4px;
  font-size: 13px;
  animation: fadeOut 0.3s ease 2s forwards;
}

@keyframes fadeOut {
  to { opacity: 0; }
}

.schedule-a-section {
  margin-bottom: 32px;
}

.schedule-a-section h2 {
  margin: 0 0 20px;
  color: var(--color-gray-900);
  font-size: 18px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-gray-700);
}

.form-group input {
  padding: 10px 12px;
  border: 1px solid var(--color-gray-300);
  border-radius: 4px;
  font-size: 14px;
  transition: border-color 0.2s ease;
}

.form-group input:focus {
  outline: none;
  border-color: var(--color-primary-500);
  box-shadow: 0 0 0 3px var(--color-primary-100);
}

.screen-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid var(--color-gray-200);
}

.btn-primary,
.btn-secondary {
  padding: 10px 24px;
  border-radius: 4px;
  border: none;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-primary {
  background: var(--color-primary-600);
  color: white;
}

.btn-primary:hover {
  background: var(--color-primary-700);
}

.btn-secondary {
  background: var(--color-gray-200);
  color: var(--color-gray-700);
}

.btn-secondary:hover {
  background: var(--color-gray-300);
}

@media (max-width: 600px) {
  .deductions-screen {
    padding: 20px;
  }

  .deduction-comparison {
    grid-template-columns: 1fr;
  }

  .recommendation-card {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .screen-footer {
    flex-direction: column-reverse;
  }

  .btn-primary,
  .btn-secondary {
    width: 100%;
  }
}
```

**Step 3: Commit**

```bash
git add apps/web/src/pages/DeductionsScreen.tsx apps/web/src/styles/DeductionsScreen.css
git commit -m "feat: build DeductionsScreen with itemized vs standard deduction comparison"
```

---

## Task 3: Create CreditsScreen Component

**Files:**
- Create: `apps/web/src/pages/CreditsScreen.tsx`
- Create: `apps/web/src/styles/CreditsScreen.css`

**Step 1: Write the CreditsScreen component**

```typescript
// apps/web/src/pages/CreditsScreen.tsx
import { useState, useEffect } from 'react'
import '../styles/CreditsScreen.css'

interface Credit {
  id: string
  name: string
  description: string
  amount: number
  isRefundable: boolean
  incomeLimit?: number
  dependents?: number
}

interface CreditsScreenProps {
  onNext?: () => void
  onSave?: (data: { credits: Credit[]; totalCredits: number; totalRefundableCredits: number }) => void
  initialData?: { credits: Credit[] }
}

const AVAILABLE_CREDITS: Omit<Credit, 'amount'>[] = [
  {
    id: 'ctc',
    name: 'Child Tax Credit',
    description: '$2,000 per qualifying child under 17',
    isRefundable: true,
    dependents: 0,
  },
  {
    id: 'eitc',
    name: 'Earned Income Tax Credit (EITC)',
    description: 'Tax credit for low to moderate income workers',
    isRefundable: true,
  },
  {
    id: 'aotc',
    name: 'American Opportunity Tax Credit',
    description: 'Up to $2,500 for education expenses',
    isRefundable: true,
  },
  {
    id: 'llc',
    name: 'Lifetime Learning Credit',
    description: 'Up to $2,000 for continuing education',
    isRefundable: false,
  },
  {
    id: 'evc',
    name: 'Electric Vehicle Credit',
    description: 'Up to $7,500 for EV purchase',
    isRefundable: false,
  },
  {
    id: 'cdc',
    name: 'Child & Dependent Care Credit',
    description: 'Up to 35% of eligible expenses',
    isRefundable: false,
  },
]

export default function CreditsScreen({ onNext, onSave, initialData }: CreditsScreenProps) {
  const [credits, setCredits] = useState<Credit[]>(
    initialData?.credits || AVAILABLE_CREDITS.map(c => ({ ...c, amount: 0 }))
  )
  const [dependents, setDependents] = useState(0)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [autoSaveStatus, setAutoSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle')

  const totalCredits = credits.reduce((sum, c) => sum + c.amount, 0)
  const totalRefundable = credits
    .filter(c => c.isRefundable)
    .reduce((sum, c) => sum + c.amount, 0)

  // Auto-save every 30s
  useEffect(() => {
    const timer = setInterval(() => {
      setAutoSaveStatus('saving')
      localStorage.setItem('creditsScreen', JSON.stringify({ credits, dependents }))
      setAutoSaveStatus('saved')
      setTimeout(() => setAutoSaveStatus('idle'), 2000)
    }, 30000)
    return () => clearInterval(timer)
  }, [credits, dependents])

  const updateCredit = (id: string, amount: number) => {
    setCredits(prev =>
      prev.map(c => (c.id === id ? { ...c, amount: Math.max(0, amount) } : c))
    )
  }

  const handleNext = () => {
    const newErrors: Record<string, string> = {}

    if (credits.some(c => c.amount < 0)) {
      newErrors.amounts = 'Credit amounts must be non-negative'
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    if (onSave) {
      onSave({ credits, totalCredits, totalRefundableCredits: totalRefundable })
    }
    if (onNext) {
      onNext()
    }
  }

  return (
    <div className="credits-screen">
      <div className="screen-header">
        <h1>Tax Credits</h1>
        <p>Find and claim all eligible tax credits</p>
      </div>

      {/* Summary Cards */}
      <div className="credits-summary">
        <div className="summary-card">
          <label>Total Credits</label>
          <div className="summary-value">${totalCredits.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
        </div>
        <div className="summary-card">
          <label>Refundable Credits</label>
          <div className="summary-value">${totalRefundable.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
        </div>
      </div>

      {/* Auto-save Status */}
      {autoSaveStatus === 'saved' && (
        <div className="auto-save-status">✓ Saved</div>
      )}

      {/* Dependents Info */}
      <div className="dependents-section">
        <h2>Qualifying Dependents</h2>
        <div className="form-group">
          <label htmlFor="dependents">Number of Qualifying Dependents</label>
          <input
            id="dependents"
            type="number"
            value={dependents}
            onChange={(e) => setDependents(Math.max(0, parseInt(e.target.value) || 0))}
            min="0"
          />
        </div>
      </div>

      {/* Credits List */}
      <div className="credits-list">
        <h2>Available Credits</h2>
        {errors.amounts && <div className="error-message">{errors.amounts}</div>}

        {credits.map(credit => (
          <div key={credit.id} className={`credit-card ${credit.isRefundable ? 'refundable' : ''}`}>
            <div className="credit-info">
              <h3>{credit.name}</h3>
              <p>{credit.description}</p>
              {credit.isRefundable && <span className="refundable-badge">Refundable</span>}
            </div>

            <div className="credit-input">
              <label htmlFor={`credit-${credit.id}`}>Amount</label>
              <input
                id={`credit-${credit.id}`}
                type="number"
                value={credit.amount}
                onChange={(e) => updateCredit(credit.id, parseFloat(e.target.value) || 0)}
                step="0.01"
                placeholder="$0.00"
              />
            </div>
          </div>
        ))}
      </div>

      {/* Navigation */}
      <div className="screen-footer">
        <button className="btn-secondary">Back</button>
        <button className="btn-primary" onClick={handleNext}>
          Continue
        </button>
      </div>
    </div>
  )
}
```

**Step 2: Add CreditsScreen CSS**

```css
/* apps/web/src/styles/CreditsScreen.css */
@import '../../static/css/core/variables.css';

.credits-screen {
  background: white;
  border-radius: 8px;
  padding: 32px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.screen-header {
  margin-bottom: 32px;
}

.screen-header h1 {
  margin: 0 0 8px;
  color: var(--color-gray-900);
  font-size: 28px;
}

.screen-header p {
  margin: 0;
  color: var(--color-gray-600);
  font-size: 16px;
}

.credits-summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 32px;
}

.summary-card {
  padding: 20px;
  background: var(--color-primary-50);
  border: 1px solid var(--color-primary-200);
  border-radius: 8px;
}

.summary-card label {
  display: block;
  font-size: 13px;
  color: var(--color-gray-600);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.summary-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-primary-600);
}

.auto-save-status {
  position: fixed;
  top: 24px;
  right: 24px;
  padding: 8px 16px;
  background: var(--color-primary-100);
  color: var(--color-primary-700);
  border-radius: 4px;
  font-size: 13px;
  animation: fadeOut 0.3s ease 2s forwards;
}

@keyframes fadeOut {
  to { opacity: 0; }
}

.dependents-section {
  margin-bottom: 32px;
  padding: 20px;
  background: var(--color-gray-50);
  border-radius: 8px;
}

.dependents-section h2 {
  margin: 0 0 16px;
  color: var(--color-gray-900);
  font-size: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-gray-700);
}

.form-group input {
  padding: 10px 12px;
  border: 1px solid var(--color-gray-300);
  border-radius: 4px;
  font-size: 14px;
}

.form-group input:focus {
  outline: none;
  border-color: var(--color-primary-500);
  box-shadow: 0 0 0 3px var(--color-primary-100);
}

.credits-list {
  margin-bottom: 32px;
}

.credits-list h2 {
  margin: 0 0 20px;
  color: var(--color-gray-900);
  font-size: 18px;
}

.credit-card {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding: 16px;
  margin-bottom: 12px;
  border: 1px solid var(--color-gray-200);
  border-radius: 6px;
  background: white;
  transition: all 0.2s ease;
}

.credit-card:hover {
  border-color: var(--color-primary-300);
  box-shadow: 0 2px 8px rgba(20, 184, 166, 0.08);
}

.credit-card.refundable {
  border-left: 4px solid var(--color-accent-500);
}

.credit-info {
  flex: 1;
}

.credit-info h3 {
  margin: 0 0 4px;
  color: var(--color-gray-900);
  font-size: 15px;
  font-weight: 600;
}

.credit-info p {
  margin: 0 0 8px;
  color: var(--color-gray-600);
  font-size: 13px;
  line-height: 1.4;
}

.refundable-badge {
  display: inline-block;
  padding: 2px 8px;
  background: var(--color-accent-100);
  color: var(--color-accent-700);
  border-radius: 3px;
  font-size: 11px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.credit-input {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-left: 20px;
  min-width: 140px;
}

.credit-input label {
  font-size: 12px;
  color: var(--color-gray-600);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.credit-input input {
  padding: 8px 10px;
  border: 1px solid var(--color-gray-300);
  border-radius: 4px;
  font-size: 13px;
  text-align: right;
}

.credit-input input:focus {
  outline: none;
  border-color: var(--color-primary-500);
  box-shadow: 0 0 0 3px var(--color-primary-100);
}

.error-message {
  padding: 12px;
  background: #fef2f2;
  border-left: 4px solid #dc2626;
  border-radius: 4px;
  color: #991b1b;
  font-size: 13px;
  margin-bottom: 16px;
}

.screen-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid var(--color-gray-200);
}

.btn-primary,
.btn-secondary {
  padding: 10px 24px;
  border-radius: 4px;
  border: none;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-primary {
  background: var(--color-primary-600);
  color: white;
}

.btn-primary:hover {
  background: var(--color-primary-700);
}

.btn-secondary {
  background: var(--color-gray-200);
  color: var(--color-gray-700);
}

.btn-secondary:hover {
  background: var(--color-gray-300);
}

@media (max-width: 600px) {
  .credits-screen {
    padding: 20px;
  }

  .credits-summary {
    grid-template-columns: 1fr;
  }

  .credit-card {
    flex-direction: column;
    align-items: flex-start;
  }

  .credit-input {
    margin-left: 0;
    margin-top: 12px;
    width: 100%;
  }

  .credit-input input {
    width: 100%;
  }

  .screen-footer {
    flex-direction: column-reverse;
  }

  .btn-primary,
  .btn-secondary {
    width: 100%;
  }
}
```

**Step 3: Commit**

```bash
git add apps/web/src/pages/CreditsScreen.tsx apps/web/src/styles/CreditsScreen.css
git commit -m "feat: build CreditsScreen with credit eligibility checker and child dependent tracking"
```

---

## Task 4: Create FilingStatusOptimizer Component

**Files:**
- Create: `apps/web/src/pages/FilingStatusOptimizer.tsx`
- Create: `apps/web/src/styles/FilingStatusOptimizer.css`

**Step 1: Write the FilingStatusOptimizer component**

```typescript
// apps/web/src/pages/FilingStatusOptimizer.tsx
import { useState, useEffect, useCallback } from 'react'
import '../styles/FilingStatusOptimizer.css'

type FilingStatus = 'single' | 'mfj' | 'mfs' | 'hoh' | 'qw'

interface FilingStatusScenario {
  status: FilingStatus
  label: string
  estimatedTax: number
  advantages: string[]
  disadvantages: string[]
}

interface FilingStatusOptimizerProps {
  onNext?: () => void
  onSave?: (data: { filingStatus: FilingStatus; spouseIncome: number; scenario: FilingStatusScenario }) => void
  initialData?: { filingStatus: FilingStatus; spouseIncome: number }
}

export default function FilingStatusOptimizer({ onNext, onSave, initialData }: FilingStatusOptimizerProps) {
  const [filingStatus, setFilingStatus] = useState<FilingStatus>(initialData?.filingStatus || 'single')
  const [spouseIncome, setSpouseIncome] = useState(initialData?.spouseIncome || 0)
  const [scenarios, setScenarios] = useState<FilingStatusScenario[]>([])
  const [loadingScenarios, setLoadingScenarios] = useState(false)
  const [autoSaveStatus, setAutoSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle')

  // Fetch scenarios from API
  const fetchScenarios = useCallback(async () => {
    setLoadingScenarios(true)
    try {
      const response = await fetch('/api/optimize/filing-status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tax_year: 2025,
          spouse_income: spouseIncome,
        }),
      })
      if (response.ok) {
        const data = await response.json()
        setScenarios(data.scenarios || [])
      }
    } catch (error) {
      console.error('Failed to fetch scenarios:', error)
    } finally {
      setLoadingScenarios(false)
    }
  }, [spouseIncome])

  useEffect(() => {
    const timer = setTimeout(() => fetchScenarios(), 500)
    return () => clearTimeout(timer)
  }, [spouseIncome, fetchScenarios])

  // Auto-save every 30s
  useEffect(() => {
    const timer = setInterval(() => {
      setAutoSaveStatus('saving')
      localStorage.setItem('filingStatusOptimizer', JSON.stringify({ filingStatus, spouseIncome }))
      setAutoSaveStatus('saved')
      setTimeout(() => setAutoSaveStatus('idle'), 2000)
    }, 30000)
    return () => clearInterval(timer)
  }, [filingStatus, spouseIncome])

  const selectedScenario = scenarios.find(s => s.status === filingStatus)

  const handleNext = () => {
    if (onSave && selectedScenario) {
      onSave({ filingStatus, spouseIncome, scenario: selectedScenario })
    }
    if (onNext) {
      onNext()
    }
  }

  return (
    <div className="filing-status-optimizer">
      <div className="screen-header">
        <h1>Filing Status</h1>
        <p>Choose the filing status that minimizes your tax liability</p>
      </div>

      {/* Spouse Income Input (for MFJ/MFS scenarios) */}
      {(filingStatus === 'mfj' || filingStatus === 'mfs') && (
        <div className="spouse-income-section">
          <h2>Spouse Income Information</h2>
          <div className="form-group">
            <label htmlFor="spouse-income">Spouse W-2 & Other Income</label>
            <input
              id="spouse-income"
              type="number"
              value={spouseIncome}
              onChange={(e) => setSpouseIncome(parseFloat(e.target.value) || 0)}
              step="0.01"
              placeholder="$0.00"
            />
          </div>
        </div>
      )}

      {/* Auto-save Status */}
      {autoSaveStatus === 'saved' && (
        <div className="auto-save-status">✓ Saved</div>
      )}

      {/* Filing Status Scenarios */}
      <div className="scenarios-container">
        <h2>Comparison</h2>
        {loadingScenarios && <p>Calculating scenarios...</p>}

        <div className="scenarios-grid">
          {[
            { status: 'single' as FilingStatus, label: 'Single' },
            { status: 'mfj' as FilingStatus, label: 'Married Filing Jointly' },
            { status: 'mfs' as FilingStatus, label: 'Married Filing Separately' },
            { status: 'hoh' as FilingStatus, label: 'Head of Household' },
            { status: 'qw' as FilingStatus, label: 'Qualifying Widow(er)' },
          ].map(option => (
            <button
              key={option.status}
              className={`scenario-card ${filingStatus === option.status ? 'selected' : ''}`}
              onClick={() => setFilingStatus(option.status)}
              disabled={loadingScenarios}
            >
              <h3>{option.label}</h3>
              {selectedScenario?.status === option.status && (
                <div className="scenario-details">
                  <div className="tax-estimate">
                    Est. Tax: ${selectedScenario.estimatedTax.toLocaleString('en-US', { minimumFractionDigits: 0 })}
                  </div>
                  <div className="advantages">
                    <strong>Advantages:</strong>
                    <ul>
                      {selectedScenario.advantages.map((adv, i) => (
                        <li key={i}>{adv}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="disadvantages">
                    <strong>Disadvantages:</strong>
                    <ul>
                      {selectedScenario.disadvantages.map((dis, i) => (
                        <li key={i}>{dis}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Navigation */}
      <div className="screen-footer">
        <button className="btn-secondary">Back</button>
        <button className="btn-primary" onClick={handleNext}>
          Continue
        </button>
      </div>
    </div>
  )
}
```

**Step 2: Add FilingStatusOptimizer CSS**

```css
/* apps/web/src/styles/FilingStatusOptimizer.css */
@import '../../static/css/core/variables.css';

.filing-status-optimizer {
  background: white;
  border-radius: 8px;
  padding: 32px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.screen-header {
  margin-bottom: 32px;
}

.screen-header h1 {
  margin: 0 0 8px;
  color: var(--color-gray-900);
  font-size: 28px;
}

.screen-header p {
  margin: 0;
  color: var(--color-gray-600);
  font-size: 16px;
}

.spouse-income-section {
  margin-bottom: 32px;
  padding: 20px;
  background: var(--color-primary-50);
  border-radius: 8px;
}

.spouse-income-section h2 {
  margin: 0 0 16px;
  color: var(--color-gray-900);
  font-size: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-gray-700);
}

.form-group input {
  padding: 10px 12px;
  border: 1px solid var(--color-gray-300);
  border-radius: 4px;
  font-size: 14px;
}

.form-group input:focus {
  outline: none;
  border-color: var(--color-primary-500);
  box-shadow: 0 0 0 3px var(--color-primary-100);
}

.auto-save-status {
  position: fixed;
  top: 24px;
  right: 24px;
  padding: 8px 16px;
  background: var(--color-primary-100);
  color: var(--color-primary-700);
  border-radius: 4px;
  font-size: 13px;
  animation: fadeOut 0.3s ease 2s forwards;
}

@keyframes fadeOut {
  to { opacity: 0; }
}

.scenarios-container {
  margin-bottom: 32px;
}

.scenarios-container h2 {
  margin: 0 0 20px;
  color: var(--color-gray-900);
  font-size: 18px;
}

.scenarios-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.scenario-card {
  padding: 16px;
  border: 2px solid var(--color-gray-200);
  border-radius: 6px;
  background: white;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}

.scenario-card:hover {
  border-color: var(--color-primary-300);
  box-shadow: 0 2px 8px rgba(20, 184, 166, 0.08);
}

.scenario-card.selected {
  border-color: var(--color-primary-600);
  background: var(--color-primary-50);
  box-shadow: 0 4px 12px rgba(20, 184, 166, 0.12);
}

.scenario-card h3 {
  margin: 0 0 12px;
  color: var(--color-gray-900);
  font-size: 14px;
  font-weight: 600;
}

.scenario-details {
  padding-top: 12px;
  border-top: 1px solid var(--color-gray-200);
}

.tax-estimate {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-primary-600);
  margin-bottom: 12px;
}

.advantages,
.disadvantages {
  margin-bottom: 12px;
  font-size: 13px;
}

.advantages strong,
.disadvantages strong {
  display: block;
  color: var(--color-gray-700);
  margin-bottom: 4px;
}

.advantages ul,
.disadvantages ul {
  margin: 0;
  padding-left: 16px;
  color: var(--color-gray-600);
}

.advantages li,
.disadvantages li {
  margin-bottom: 4px;
  line-height: 1.4;
}

.screen-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid var(--color-gray-200);
}

.btn-primary,
.btn-secondary {
  padding: 10px 24px;
  border-radius: 4px;
  border: none;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-primary {
  background: var(--color-primary-600);
  color: white;
}

.btn-primary:hover {
  background: var(--color-primary-700);
}

.btn-secondary {
  background: var(--color-gray-200);
  color: var(--color-gray-700);
}

.btn-secondary:hover {
  background: var(--color-gray-300);
}

@media (max-width: 600px) {
  .filing-status-optimizer {
    padding: 20px;
  }

  .scenarios-grid {
    grid-template-columns: 1fr;
  }

  .screen-footer {
    flex-direction: column-reverse;
  }

  .btn-primary,
  .btn-secondary {
    width: 100%;
  }
}
```

**Step 3: Commit**

```bash
git add apps/web/src/pages/FilingStatusOptimizer.tsx apps/web/src/styles/FilingStatusOptimizer.css
git commit -m "feat: build FilingStatusOptimizer with MFJ vs MFS comparison and scenario toggle"
```

---

## Task 5: Create ReviewScreen Component

**Files:**
- Create: `apps/web/src/pages/ReviewScreen.tsx`
- Create: `apps/web/src/styles/ReviewScreen.css`

**Step 1: Write the ReviewScreen component**

```typescript
// apps/web/src/pages/ReviewScreen.tsx
import { useState, useEffect } from 'react'
import '../styles/ReviewScreen.css'

interface ReturnSummary {
  totalIncome: number
  totalDeductions: number
  adjustedGrossIncome: number
  totalCredits: number
  taxLiability: number
  totalWithholding: number
  refundOrOwed: number
  refundAmount?: number
  amountOwed?: number
  warnings: Array<{ severity: 'warning' | 'error' | 'info'; message: string }>
  aiSuggestions: Array<{ title: string; description: string; confidenceScore: number }>
}

interface ReviewScreenProps {
  onNext?: () => void
  onSave?: (approved: boolean) => void
  summary?: ReturnSummary
}

const mockSummary: ReturnSummary = {
  totalIncome: 125000,
  totalDeductions: 18500,
  adjustedGrossIncome: 106500,
  totalCredits: 2000,
  taxLiability: 18500,
  totalWithholding: 19200,
  refundOrOwed: 700,
  refundAmount: 700,
  warnings: [
    { severity: 'warning', message: 'Your charitable donations exceed 50% of AGI' },
    { severity: 'info', message: 'Consider estimated tax payments next year' },
  ],
  aiSuggestions: [
    { title: 'Max out 401(k) contributions', description: 'You could defer up to $23,500 in 2025', confidenceScore: 0.92 },
    { title: 'Bundle deductible items', description: 'Timing of charitable donations could save taxes', confidenceScore: 0.78 },
  ],
}

export default function ReviewScreen({ onNext, onSave, summary = mockSummary }: ReviewScreenProps) {
  const [approved, setApproved] = useState(false)
  const [expandedSection, setExpandedSection] = useState<string | null>(null)

  const handleApprove = () => {
    setApproved(true)
    if (onSave) {
      onSave(true)
    }
    if (onNext) {
      onNext()
    }
  }

  return (
    <div className="review-screen">
      <div className="screen-header">
        <h1>Return Summary</h1>
        <p>Review your filing details before submission</p>
      </div>

      {/* Summary Cards */}
      <div className="summary-cards">
        <div className="summary-card primary">
          <label>Adjusted Gross Income</label>
          <div className="amount">${summary.adjustedGrossIncome.toLocaleString('en-US', { minimumFractionDigits: 0 })}</div>
        </div>

        <div className="summary-card">
          <label>Total Tax Liability</label>
          <div className="amount">${summary.taxLiability.toLocaleString('en-US', { minimumFractionDigits: 0 })}</div>
        </div>

        <div className="summary-card">
          <label>Total Withholding</label>
          <div className="amount">${summary.totalWithholding.toLocaleString('en-US', { minimumFractionDigits: 0 })}</div>
        </div>

        <div className={`summary-card refund ${summary.refundOrOwed >= 0 ? 'refund' : 'owed'}`}>
          <label>{summary.refundOrOwed >= 0 ? 'Refund' : 'Amount Owed'}</label>
          <div className="amount">
            ${Math.abs(summary.refundOrOwed).toLocaleString('en-US', { minimumFractionDigits: 0 })}
          </div>
        </div>
      </div>

      {/* Line-by-Line Breakdown */}
      <section className="breakdown-section">
        <h2>Line-by-Line Breakdown</h2>

        <div className="breakdown-row">
          <span>Total Income</span>
          <span className="amount">${summary.totalIncome.toLocaleString('en-US', { minimumFractionDigits: 0 })}</span>
        </div>

        <div className="breakdown-row highlight">
          <span>Less: Deductions</span>
          <span className="amount">−${summary.totalDeductions.toLocaleString('en-US', { minimumFractionDigits: 0 })}</span>
        </div>

        <div className="breakdown-row subtotal">
          <span>Adjusted Gross Income</span>
          <span className="amount">${summary.adjustedGrossIncome.toLocaleString('en-US', { minimumFractionDigits: 0 })}</span>
        </div>

        <div className="breakdown-row highlight">
          <span>Tentative Tax on AGI</span>
          <span className="amount">${summary.taxLiability.toLocaleString('en-US', { minimumFractionDigits: 0 })}</span>
        </div>

        <div className="breakdown-row highlight">
          <span>Less: Credits</span>
          <span className="amount">−${summary.totalCredits.toLocaleString('en-US', { minimumFractionDigits: 0 })}</span>
        </div>

        <div className="breakdown-row subtotal">
          <span>Total Tax Liability</span>
          <span className="amount">${(summary.taxLiability - summary.totalCredits).toLocaleString('en-US', { minimumFractionDigits: 0 })}</span>
        </div>

        <div className="breakdown-row highlight">
          <span>Less: Total Withholding & Estimated Taxes</span>
          <span className="amount">−${summary.totalWithholding.toLocaleString('en-US', { minimumFractionDigits: 0 })}</span>
        </div>

        <div className={`breakdown-row total ${summary.refundOrOwed >= 0 ? 'refund' : 'owed'}`}>
          <span>{summary.refundOrOwed >= 0 ? 'Refund' : 'Balance Due'}</span>
          <span className="amount">
            ${Math.abs(summary.refundOrOwed).toLocaleString('en-US', { minimumFractionDigits: 0 })}
          </span>
        </div>
      </section>

      {/* Warnings */}
      {summary.warnings.length > 0 && (
        <section className="warnings-section">
          <h2>Notices & Warnings</h2>
          {summary.warnings.map((warning, i) => (
            <div key={i} className={`warning-card ${warning.severity}`}>
              <span className="severity-icon">
                {warning.severity === 'warning' ? '⚠️' : warning.severity === 'error' ? '❌' : 'ℹ️'}
              </span>
              <span>{warning.message}</span>
            </div>
          ))}
        </section>
      )}

      {/* AI Suggestions */}
      {summary.aiSuggestions.length > 0 && (
        <section className="ai-suggestions-section">
          <h2>AI-Powered Suggestions</h2>
          {summary.aiSuggestions.map((suggestion, i) => (
            <button
              key={i}
              className="suggestion-card"
              onClick={() => setExpandedSection(expandedSection === `suggestion-${i}` ? null : `suggestion-${i}`)}
            >
              <div className="suggestion-header">
                <h3>{suggestion.title}</h3>
                <span className="confidence-badge" style={{ '--confidence': `${suggestion.confidenceScore * 100}%` }}>
                  {Math.round(suggestion.confidenceScore * 100)}% likely
                </span>
              </div>
              {expandedSection === `suggestion-${i}` && (
                <p className="suggestion-description">{suggestion.description}</p>
              )}
            </button>
          ))}
        </section>
      )}

      {/* Approval Checkbox */}
      <div className="approval-section">
        <label className="checkbox-group">
          <input
            type="checkbox"
            checked={approved}
            onChange={(e) => setApproved(e.target.checked)}
          />
          <span>I have reviewed my return and approve it for submission</span>
        </label>
      </div>

      {/* Navigation */}
      <div className="screen-footer">
        <button className="btn-secondary">Back</button>
        <button className="btn-primary" onClick={handleApprove} disabled={!approved}>
          Continue to E-File
        </button>
      </div>
    </div>
  )
}
```

**Step 2: Add ReviewScreen CSS**

```css
/* apps/web/src/styles/ReviewScreen.css */
@import '../../static/css/core/variables.css';

.review-screen {
  background: white;
  border-radius: 8px;
  padding: 32px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.screen-header {
  margin-bottom: 32px;
}

.screen-header h1 {
  margin: 0 0 8px;
  color: var(--color-gray-900);
  font-size: 28px;
}

.screen-header p {
  margin: 0;
  color: var(--color-gray-600);
  font-size: 16px;
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}

.summary-card {
  padding: 20px;
  background: var(--color-gray-50);
  border: 1px solid var(--color-gray-200);
  border-radius: 8px;
  text-align: center;
}

.summary-card.primary {
  background: var(--color-primary-50);
  border-color: var(--color-primary-200);
}

.summary-card.refund.refund {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.summary-card.refund.owed {
  background: #fef2f2;
  border-color: #fecaca;
}

.summary-card label {
  display: block;
  font-size: 13px;
  color: var(--color-gray-600);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.summary-card .amount {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-primary-600);
}

.summary-card.refund.refund .amount {
  color: #15803d;
}

.summary-card.refund.owed .amount {
  color: #dc2626;
}

.breakdown-section {
  margin-bottom: 32px;
  padding: 24px;
  background: var(--color-gray-50);
  border-radius: 8px;
}

.breakdown-section h2 {
  margin: 0 0 20px;
  color: var(--color-gray-900);
  font-size: 18px;
}

.breakdown-row {
  display: flex;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid var(--color-gray-200);
  font-size: 14px;
  color: var(--color-gray-700);
}

.breakdown-row.highlight {
  background: var(--color-gray-100);
  padding: 12px;
  margin: 0 -24px;
  padding-left: 24px;
  padding-right: 24px;
}

.breakdown-row.subtotal {
  font-weight: 600;
  border-bottom: 2px solid var(--color-gray-400);
  padding-bottom: 16px;
  margin-bottom: 16px;
}

.breakdown-row.total {
  font-weight: 700;
  font-size: 16px;
  padding: 16px 0 0;
  border: none;
  border-top: 3px solid var(--color-primary-600);
}

.breakdown-row.total.refund {
  color: #15803d;
}

.breakdown-row.total.owed {
  color: #dc2626;
}

.breakdown-row .amount {
  text-align: right;
  font-weight: 500;
}

.warnings-section {
  margin-bottom: 32px;
}

.warnings-section h2 {
  margin: 0 0 16px;
  color: var(--color-gray-900);
  font-size: 18px;
}

.warning-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 4px;
  font-size: 13px;
}

.warning-card.warning {
  background: #fef3c7;
  color: #92400e;
  border-left: 4px solid #f59e0b;
}

.warning-card.error {
  background: #fee2e2;
  color: #7f1d1d;
  border-left: 4px solid #ef4444;
}

.warning-card.info {
  background: #dbeafe;
  color: #1e3a8a;
  border-left: 4px solid #3b82f6;
}

.severity-icon {
  flex-shrink: 0;
  font-size: 16px;
  line-height: 1;
}

.ai-suggestions-section {
  margin-bottom: 32px;
}

.ai-suggestions-section h2 {
  margin: 0 0 16px;
  color: var(--color-gray-900);
  font-size: 18px;
}

.suggestion-card {
  display: block;
  width: 100%;
  padding: 16px;
  margin-bottom: 12px;
  background: var(--color-accent-50);
  border: 1px solid var(--color-accent-200);
  border-radius: 6px;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}

.suggestion-card:hover {
  border-color: var(--color-accent-400);
  box-shadow: 0 2px 8px rgba(249, 115, 22, 0.08);
}

.suggestion-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.suggestion-card h3 {
  margin: 0;
  color: var(--color-accent-900);
  font-size: 15px;
  font-weight: 600;
}

.confidence-badge {
  flex-shrink: 0;
  padding: 2px 8px;
  background: var(--color-accent-200);
  color: var(--color-accent-900);
  border-radius: 3px;
  font-size: 12px;
  font-weight: 500;
}

.suggestion-description {
  margin: 12px 0 0;
  color: var(--color-accent-800);
  font-size: 13px;
  line-height: 1.4;
}

.approval-section {
  padding: 24px;
  background: var(--color-primary-50);
  border: 1px solid var(--color-primary-200);
  border-radius: 6px;
  margin-bottom: 32px;
}

.checkbox-group {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  cursor: pointer;
  font-size: 14px;
  color: var(--color-gray-700);
}

.checkbox-group input {
  cursor: pointer;
  margin-top: 2px;
  width: 18px;
  height: 18px;
  accent-color: var(--color-primary-600);
}

.screen-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid var(--color-gray-200);
}

.btn-primary,
.btn-secondary {
  padding: 10px 24px;
  border-radius: 4px;
  border: none;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-primary {
  background: var(--color-primary-600);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-700);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--color-gray-200);
  color: var(--color-gray-700);
}

.btn-secondary:hover {
  background: var(--color-gray-300);
}

@media (max-width: 600px) {
  .review-screen {
    padding: 20px;
  }

  .summary-cards {
    grid-template-columns: 1fr;
  }

  .breakdown-section {
    padding: 16px;
    margin: 0 -20px;
    border-radius: 0;
  }

  .breakdown-row.highlight {
    margin: 0;
    padding: 12px 0;
  }

  .suggestion-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .screen-footer {
    flex-direction: column-reverse;
  }

  .btn-primary,
  .btn-secondary {
    width: 100%;
  }
}
```

**Step 3: Commit**

```bash
git add apps/web/src/pages/ReviewScreen.tsx apps/web/src/styles/ReviewScreen.css
git commit -m "feat: build ReviewScreen with full return summary, warnings, and AI suggestions"
```

---

## Task 6: Create SubmitScreen Component

**Files:**
- Create: `apps/web/src/pages/SubmitScreen.tsx`
- Create: `apps/web/src/styles/SubmitScreen.css`

**Step 1: Write the SubmitScreen component**

```typescript
// apps/web/src/pages/SubmitScreen.tsx
import { useState } from 'react'
import '../styles/SubmitScreen.css'

interface SubmitData {
  efinConsent: boolean
  ipPin: string
  bankName: string
  routingNumber: string
  accountNumber: string
  accountType: 'checking' | 'savings'
}

interface SubmitScreenProps {
  onNext?: () => void
  onSave?: (data: SubmitData) => void
  initialData?: Partial<SubmitData>
}

export default function SubmitScreen({ onNext, onSave, initialData }: SubmitScreenProps) {
  const [data, setData] = useState<SubmitData>({
    efinConsent: false,
    ipPin: '',
    bankName: '',
    routingNumber: '',
    accountNumber: '',
    accountType: 'checking',
    ...initialData,
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)

  const updateField = (field: keyof SubmitData, value: any) => {
    setData(prev => ({ ...prev, [field]: value }))
    if (errors[field]) {
      setErrors(prev => {
        const newErrors = { ...prev }
        delete newErrors[field]
        return newErrors
      })
    }
  }

  const handleSubmit = async () => {
    const newErrors: Record<string, string> = {}

    if (!data.efinConsent) {
      newErrors.efinConsent = 'You must consent to e-file'
    }

    if (data.routingNumber && !/^\d{9}$/.test(data.routingNumber)) {
      newErrors.routingNumber = 'Routing number must be 9 digits'
    }

    if (data.accountNumber && !/^\d{8,17}$/.test(data.accountNumber)) {
      newErrors.accountNumber = 'Account number must be 8-17 digits'
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    setSubmitting(true)
    try {
      // TODO: Call API to submit return
      if (onSave) {
        onSave(data)
      }
      if (onNext) {
        onNext()
      }
    } catch (error) {
      console.error('Submission failed:', error)
      setErrors({ submit: 'Failed to submit return. Please try again.' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="submit-screen">
      <div className="screen-header">
        <h1>E-File Authorization</h1>
        <p>Authorize and submit your federal tax return electronically</p>
      </div>

      {/* E-File Consent */}
      <section className="consent-section">
        <h2>E-File Authorization</h2>
        <div className="consent-box">
          <p>
            <strong>Form 8879 — IRS e-file Signature Authorization</strong>
          </p>
          <p>
            I authorize the IRS to electronically receive my 2025 U.S. Individual Income Tax Return (Form 1040).
            I understand that a copy of Form 8879 will be retained in the electronic record by the Authorized e-filer.
          </p>
          <label className="checkbox-group">
            <input
              type="checkbox"
              checked={data.efinConsent}
              onChange={(e) => updateField('efinConsent', e.target.checked)}
            />
            <span>I consent to e-file my return</span>
          </label>
          {errors.efinConsent && <span className="field-error">{errors.efinConsent}</span>}
        </div>
      </section>

      {/* IP PIN / Self-Select PIN */}
      <section className="ip-pin-section">
        <h2>Identity PIN (Optional)</h2>
        <div className="form-group">
          <label htmlFor="ip-pin">
            IP PIN (If you received one from the IRS)
          </label>
          <input
            id="ip-pin"
            type="password"
            value={data.ipPin}
            onChange={(e) => updateField('ipPin', e.target.value)}
            placeholder="6-digit PIN"
            maxLength={6}
          />
          <p className="form-hint">If you don't have an IP PIN, you may be able to create one at IRS.gov</p>
        </div>
      </section>

      {/* Bank Routing for Refund Direct Deposit */}
      <section className="refund-section">
        <h2>Refund Direct Deposit</h2>
        <p className="section-hint">Fastest way to receive your refund (typically 21 days vs 4+ weeks by check)</p>

        <div className="form-group">
          <label htmlFor="bank-name">Bank Name</label>
          <input
            id="bank-name"
            type="text"
            value={data.bankName}
            onChange={(e) => updateField('bankName', e.target.value)}
            placeholder="Name of your financial institution"
          />
        </div>

        <div className="form-group">
          <label htmlFor="routing">Routing Number *</label>
          <input
            id="routing"
            type="text"
            value={data.routingNumber}
            onChange={(e) => updateField('routingNumber', e.target.value)}
            placeholder="9-digit routing number"
            maxLength={9}
          />
          {errors.routingNumber && <span className="field-error">{errors.routingNumber}</span>}
          <p className="form-hint">Find your routing number at the bottom-left of your checks</p>
        </div>

        <div className="form-group">
          <label htmlFor="account">Account Number *</label>
          <input
            id="account"
            type="text"
            value={data.accountNumber}
            onChange={(e) => updateField('accountNumber', e.target.value)}
            placeholder="Account number"
          />
          {errors.accountNumber && <span className="field-error">{errors.accountNumber}</span>}
        </div>

        <div className="form-group">
          <label htmlFor="account-type">Account Type *</label>
          <select
            id="account-type"
            value={data.accountType}
            onChange={(e) => updateField('accountType', e.target.value as 'checking' | 'savings')}
          >
            <option value="checking">Checking</option>
            <option value="savings">Savings</option>
          </select>
        </div>
      </section>

      {/* Error Message */}
      {errors.submit && (
        <div className="error-section">
          <p>{errors.submit}</p>
        </div>
      )}

      {/* Navigation */}
      <div className="screen-footer">
        <button className="btn-secondary" disabled={submitting}>
          Back
        </button>
        <button
          className="btn-primary"
          onClick={handleSubmit}
          disabled={submitting || !data.efinConsent}
        >
          {submitting ? 'Submitting...' : 'Submit Return'}
        </button>
      </div>
    </div>
  )
}
```

**Step 2: Add SubmitScreen CSS**

```css
/* apps/web/src/styles/SubmitScreen.css */
@import '../../static/css/core/variables.css';

.submit-screen {
  background: white;
  border-radius: 8px;
  padding: 32px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.screen-header {
  margin-bottom: 32px;
}

.screen-header h1 {
  margin: 0 0 8px;
  color: var(--color-gray-900);
  font-size: 28px;
}

.screen-header p {
  margin: 0;
  color: var(--color-gray-600);
  font-size: 16px;
}

section {
  margin-bottom: 32px;
  padding-bottom: 32px;
  border-bottom: 1px solid var(--color-gray-200);
}

section:last-of-type {
  border-bottom: none;
}

section h2 {
  margin: 0 0 16px;
  color: var(--color-gray-900);
  font-size: 18px;
}

.section-hint {
  margin: 0 0 16px;
  color: var(--color-gray-600);
  font-size: 13px;
  font-style: italic;
}

.consent-box {
  padding: 20px;
  background: var(--color-primary-50);
  border: 1px solid var(--color-primary-200);
  border-radius: 6px;
  margin-bottom: 16px;
}

.consent-box p {
  margin: 0 0 12px;
  color: var(--color-gray-700);
  font-size: 13px;
  line-height: 1.6;
}

.consent-box p:last-child {
  margin-bottom: 0;
}

.consent-box strong {
  color: var(--color-gray-900);
}

.checkbox-group {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  cursor: pointer;
  margin-top: 16px;
  font-size: 14px;
  color: var(--color-gray-700);
}

.checkbox-group input {
  cursor: pointer;
  margin-top: 2px;
  width: 18px;
  height: 18px;
  accent-color: var(--color-primary-600);
  flex-shrink: 0;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.form-group label {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-gray-700);
}

.form-group input,
.form-group select {
  padding: 10px 12px;
  border: 1px solid var(--color-gray-300);
  border-radius: 4px;
  font-size: 14px;
  transition: border-color 0.2s ease;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: var(--color-primary-500);
  box-shadow: 0 0 0 3px var(--color-primary-100);
}

.form-group input:disabled,
.form-group select:disabled {
  background: var(--color-gray-100);
  color: var(--color-gray-600);
  cursor: not-allowed;
}

.form-hint {
  font-size: 12px;
  color: var(--color-gray-600);
  margin: 0;
  font-style: italic;
}

.field-error {
  font-size: 12px;
  color: #dc2626;
  margin-top: 4px;
}

.error-section {
  padding: 16px;
  background: #fef2f2;
  border-left: 4px solid #dc2626;
  border-radius: 4px;
  color: #7f1d1d;
  font-size: 13px;
  margin-bottom: 16px;
}

.error-section p {
  margin: 0;
}

.screen-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid var(--color-gray-200);
}

.btn-primary,
.btn-secondary {
  padding: 10px 24px;
  border-radius: 4px;
  border: none;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-primary {
  background: var(--color-primary-600);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-700);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--color-gray-200);
  color: var(--color-gray-700);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--color-gray-300);
}

.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 600px) {
  .submit-screen {
    padding: 20px;
  }

  section {
    margin-bottom: 24px;
    padding-bottom: 24px;
  }

  .screen-footer {
    flex-direction: column-reverse;
  }

  .btn-primary,
  .btn-secondary {
    width: 100%;
  }
}
```

**Step 3: Commit**

```bash
git add apps/web/src/pages/SubmitScreen.tsx apps/web/src/styles/SubmitScreen.css
git commit -m "feat: build SubmitScreen with e-file consent and refund direct deposit"
```

---

## Task 7: Update Existing Screens to Support Wizard Navigation

**Files:**
- Modify: `apps/web/src/pages/IncomeScreen.tsx` - add support for wizard integration
- Modify: `apps/web/src/pages/SelfEmploymentScreen.tsx` - add support for wizard integration
- Modify: `apps/web/src/pages/InvestmentScreen.tsx` - add support for wizard integration
- Modify: `apps/web/src/pages/RealEstateScreen.tsx` - add support for wizard integration

**Step 1: Check existing screens for required props**

Each existing screen should already support `onNext` and `onSave` props from MKW-63. Verify compatibility:

```bash
grep -n "onNext\|onSave" apps/web/src/pages/IncomeScreen.tsx
```

Expected: Props should be defined in component interface. No changes needed if already present.

**Step 2: Commit**

```bash
git add -A
git commit -m "feat: verify existing screens support wizard navigation"
```

---

## Task 8: Integration Testing & Polish

**Files:**
- Test: `apps/web/src/__tests__/FilingWizard.test.tsx` (new)
- Modify: `apps/web/src/App.tsx` - ensure routing works

**Step 1: Verify all components render and navigate correctly**

Run locally:
```bash
cd apps/web
npm run dev
```

Navigate to `/filing-wizard` and test:
- Step navigation (forward/backward)
- Breadcrumb clicking
- Progress bar updates
- Data persistence (localStorage)
- Mobile responsiveness (375px viewport)

**Step 2: Fix any styling issues**

Review CSS across all screens:
- Button alignment and sizing
- Form input consistency
- Mobile breakpoints
- Color variable usage

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: complete filing wizard screens (MKW-64) - ready for API integration"
```

---

## Summary

This plan builds 5 new filing workflow screens + wizard container (9 components total):
- **FilingWizard** — orchestrator with step tracking, breadcrumbs, progress bar
- **DeductionsScreen** — itemized vs standard deduction comparison
- **CreditsScreen** — credit eligibility and claim entry
- **FilingStatusOptimizer** — MFJ vs MFS scenario comparison
- **ReviewScreen** — full return summary with line-by-line breakdown
- **SubmitScreen** — e-file authorization and refund direct deposit

Each screen follows MKW-63 patterns (auto-save, real-time calculations, mobile-first), uses the design system, and integrates with existing FastAPI backend routes.

**Next Phase:** After these components are built and tested locally, integrate with actual `/api/optimize/*` endpoints for real tax calculations and rule-based warnings.

---

## Execution Options

**Plan complete and saved to `docs/plans/2026-04-05-deductions-credits-filing-wizard.md`.**

Two execution approaches:

**1. Subagent-Driven (this session)** — I'll dispatch fresh subagent per task, review code between tasks, fast iteration.

**2. Parallel Session** — Open new session with `superpowers:executing-plans` for batch execution with checkpoints.

**Which approach would you prefer?**