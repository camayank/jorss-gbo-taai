import { useState, useEffect, useCallback, useMemo } from 'react'
import '../styles/IncomeScreen.css'
import { useTaxCalcWebSocket, type TaxCalcResult } from '../api/useTaxCalcWebSocket'

interface W2 {
  id: string
  employer: string
  employerEin: string
  box1Wages: number
  box2FederalWithholding: number
  box3SocialSecurityWages: number
  box4SocialSecurityTax: number
  box5MedicareWages: number
  box6MedicareTax: number
  box12a: number
  box12b: number
  box12c: number
  box12d: number
  box14Other: string
  stateTaxWithheld: number
  localTaxWithheld: number
}

interface IncomeScreenProps {
  onNext?: () => void
  onSave?: (data: { w2s: W2[]; totalIncome: number }) => void
  initialData?: { w2s: W2[] }
  /** Auth token for WebSocket real-time calc. Falls back to HTTP polling if absent. */
  wsToken?: string | null
  /** Return session id for WebSocket co-editing channel. */
  sessionId?: string
}

const defaultW2: Omit<W2, 'id'> = {
  employer: '',
  employerEin: '',
  box1Wages: 0,
  box2FederalWithholding: 0,
  box3SocialSecurityWages: 0,
  box4SocialSecurityTax: 0,
  box5MedicareWages: 0,
  box6MedicareTax: 0,
  box12a: 0,
  box12b: 0,
  box12c: 0,
  box12d: 0,
  box14Other: '',
  stateTaxWithheld: 0,
  localTaxWithheld: 0,
}

export default function IncomeScreen({ onNext, onSave, initialData, wsToken = null, sessionId }: IncomeScreenProps) {
  const [w2s, setW2s] = useState<W2[]>(
    initialData?.w2s || [
      {
        id: '1',
        ...defaultW2,
      },
    ]
  )
  const [taxEstimate, setTaxEstimate] = useState<number>(0)
  const [estimateLoading, setEstimateLoading] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [activeW2Index, setActiveW2Index] = useState(0)
  const [autoSaveStatus, setAutoSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle')

  // Calculate total wages
  const totalWages = w2s.reduce((sum, w2) => sum + (w2.box1Wages || 0), 0)
  const totalFederalWithholding = w2s.reduce((sum, w2) => sum + (w2.box2FederalWithholding || 0), 0)

  // -------------------------------------------------------------------------
  // Real-time tax calculation via WebSocket (replaces HTTP polling)
  // -------------------------------------------------------------------------

  const effectiveSessionId = sessionId ?? 'income-screen-default'
  const useWs = Boolean(wsToken)

  const handleCalcResult = useCallback((result: TaxCalcResult) => {
    setTaxEstimate(result.tax_liability)
    setEstimateLoading(false)
  }, [])

  const handleCalcError = useCallback(() => {
    setEstimateLoading(false)
  }, [])

  const { sendCalcUpdate, connected: wsConnected } = useTaxCalcWebSocket({
    sessionId: effectiveSessionId,
    token: useWs ? wsToken : null,
    onResult: handleCalcResult,
    onError: handleCalcError,
    debounceMs: 500,
  })

  // Build the calc input whenever totals change
  const calcInput = useMemo(() => ({
    income: { wages: totalWages },
    withholdings: { federal: totalFederalWithholding },
  }), [totalWages, totalFederalWithholding])

  // Trigger calc on input change — WebSocket path or HTTP fallback
  useEffect(() => {
    if (totalWages === 0) {
      setTaxEstimate(0)
      return
    }
    setEstimateLoading(true)

    if (useWs && wsConnected) {
      // Server-push path: debounce handled inside the hook
      sendCalcUpdate(calcInput)
    } else {
      // HTTP polling fallback (no token or WS not yet connected)
      const timer = setTimeout(async () => {
        try {
          const response = await fetch('/api/estimate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              tax_year: 2025,
              income: { wages: totalWages },
              withholdings: { federal: totalFederalWithholding },
            }),
          })
          if (response.ok) {
            const data = await response.json()
            setTaxEstimate(data.tax_liability || 0)
          }
        } catch (error) {
          console.error('Tax estimate error:', error)
        } finally {
          setEstimateLoading(false)
        }
      }, 500)
      return () => clearTimeout(timer)
    }
  }, [calcInput, totalWages, totalFederalWithholding, useWs, wsConnected, sendCalcUpdate])

  // Auto-save to localStorage
  useEffect(() => {
    const timer = setTimeout(async () => {
      setAutoSaveStatus('saving')
      const data = { w2s, totalIncome: totalWages }
      localStorage.setItem('incomeScreen', JSON.stringify(data))

      // Try to sync with API
      try {
        await fetch('/api/auto-save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
        }).catch(() => {
          // API save optional; localStorage is primary
        })
      } finally {
        setAutoSaveStatus('saved')
        setTimeout(() => setAutoSaveStatus('idle'), 2000)
      }
    }, 30000)

    return () => clearTimeout(timer)
  }, [w2s, totalWages])

  const updateW2 = (index: number, field: keyof W2, value: any) => {
    const updated = [...w2s]
    updated[index] = {
      ...updated[index],
      [field]: value,
    }
    setW2s(updated)

    // Clear error for this field
    const key = `w2_${index}_${field}`
    if (errors[key]) {
      const newErrors = { ...errors }
      delete newErrors[key]
      setErrors(newErrors)
    }
  }

  const addW2 = () => {
    const newW2: W2 = {
      id: Date.now().toString(),
      ...defaultW2,
    }
    setW2s([...w2s, newW2])
    setActiveW2Index(w2s.length)
  }

  const removeW2 = (index: number) => {
    if (w2s.length === 1) {
      setErrors({ ...errors, general: 'At least one W-2 is required' })
      return
    }
    setW2s(w2s.filter((_, i) => i !== index))
    if (activeW2Index >= w2s.length - 1) {
      setActiveW2Index(w2s.length - 2)
    }
  }

  const handleNext = () => {
    // Validate
    const newErrors: Record<string, string> = {}

    if (w2s.some(w2 => !w2.employer?.trim())) {
      newErrors.employers = 'All W-2s must have an employer name'
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    if (onSave) {
      onSave({ w2s, totalIncome: totalWages })
    }

    if (onNext) {
      onNext()
    }
  }

  return (
    <div className="income-screen">
      <div className="screen-header">
        <h1>W-2 Income</h1>
        <p>Enter your W-2 forms from all employers</p>
      </div>

      {/* Tax Estimate Summary */}
      <div className="tax-summary">
        <div className="summary-card">
          <label>Total W-2 Wages</label>
          <div className="summary-value">${totalWages.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
        </div>
        <div className="summary-card">
          <label>Federal Withholding</label>
          <div className="summary-value">${totalFederalWithholding.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
        </div>
        <div className="summary-card">
          <label>Estimated Tax Liability</label>
          <div className={`summary-value ${estimateLoading ? 'loading' : ''}`}>
            {estimateLoading ? 'Calculating...' : `$${taxEstimate.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          </div>
        </div>
      </div>

      {/* Auto-save Status */}
      {autoSaveStatus === 'saved' && (
        <div className="auto-save-status">✓ Saved</div>
      )}

      {/* W-2 Forms Tabs */}
      <div className="w2-container">
        <div className="w2-tabs">
          {w2s.map((w2, index) => (
            <button
              key={w2.id}
              className={`w2-tab ${activeW2Index === index ? 'active' : ''}`}
              onClick={() => setActiveW2Index(index)}
            >
              <span className="tab-label">{w2.employer || `W-2 ${index + 1}`}</span>
              {w2s.length > 1 && (
                <button
                  className="tab-close"
                  onClick={(e) => {
                    e.stopPropagation()
                    removeW2(index)
                  }}
                  aria-label={`Remove W-2 ${index + 1}`}
                >
                  ×
                </button>
              )}
            </button>
          ))}
          <button className="w2-tab-add" onClick={addW2} title="Add another W-2">
            +
          </button>
        </div>

        {/* W-2 Form */}
        <div className="w2-form">
          {errors.general && <div className="error-message">{errors.general}</div>}

          <div className="form-section">
            <h3>Employer Information</h3>
            <div className="form-group">
              <label htmlFor={`employer-${activeW2Index}`}>Employer Name *</label>
              <input
                id={`employer-${activeW2Index}`}
                type="text"
                value={w2s[activeW2Index].employer}
                onChange={(e) => updateW2(activeW2Index, 'employer', e.target.value)}
                placeholder="Enter employer name"
              />
              {errors[`w2_${activeW2Index}_employer`] && (
                <span className="field-error">{errors[`w2_${activeW2Index}_employer`]}</span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor={`ein-${activeW2Index}`}>Employer EIN</label>
              <input
                id={`ein-${activeW2Index}`}
                type="text"
                value={w2s[activeW2Index].employerEin}
                onChange={(e) => updateW2(activeW2Index, 'employerEin', e.target.value)}
                placeholder="XX-XXXXXXX"
              />
            </div>
          </div>

          <div className="form-section">
            <h3>Income (Boxes 1-6)</h3>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor={`box1-${activeW2Index}`}>Box 1: Wages, Tips, Other (w/ dollars)</label>
                <input
                  id={`box1-${activeW2Index}`}
                  type="number"
                  value={w2s[activeW2Index].box1Wages}
                  onChange={(e) => updateW2(activeW2Index, 'box1Wages', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
              <div className="form-group">
                <label htmlFor={`box2-${activeW2Index}`}>Box 2: Federal Income Tax Withholding</label>
                <input
                  id={`box2-${activeW2Index}`}
                  type="number"
                  value={w2s[activeW2Index].box2FederalWithholding}
                  onChange={(e) => updateW2(activeW2Index, 'box2FederalWithholding', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor={`box3-${activeW2Index}`}>Box 3: Social Security Wages</label>
                <input
                  id={`box3-${activeW2Index}`}
                  type="number"
                  value={w2s[activeW2Index].box3SocialSecurityWages}
                  onChange={(e) => updateW2(activeW2Index, 'box3SocialSecurityWages', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
              <div className="form-group">
                <label htmlFor={`box4-${activeW2Index}`}>Box 4: Social Security Tax</label>
                <input
                  id={`box4-${activeW2Index}`}
                  type="number"
                  value={w2s[activeW2Index].box4SocialSecurityTax}
                  onChange={(e) => updateW2(activeW2Index, 'box4SocialSecurityTax', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor={`box5-${activeW2Index}`}>Box 5: Medicare Wages</label>
                <input
                  id={`box5-${activeW2Index}`}
                  type="number"
                  value={w2s[activeW2Index].box5MedicareWages}
                  onChange={(e) => updateW2(activeW2Index, 'box5MedicareWages', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
              <div className="form-group">
                <label htmlFor={`box6-${activeW2Index}`}>Box 6: Medicare Tax</label>
                <input
                  id={`box6-${activeW2Index}`}
                  type="number"
                  value={w2s[activeW2Index].box6MedicareTax}
                  onChange={(e) => updateW2(activeW2Index, 'box6MedicareTax', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
            </div>
          </div>

          <div className="form-section">
            <h3>Withholdings by State</h3>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor={`state-withholding-${activeW2Index}`}>State Income Tax Withheld</label>
                <input
                  id={`state-withholding-${activeW2Index}`}
                  type="number"
                  value={w2s[activeW2Index].stateTaxWithheld}
                  onChange={(e) => updateW2(activeW2Index, 'stateTaxWithheld', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
              <div className="form-group">
                <label htmlFor={`local-withholding-${activeW2Index}`}>Local Income Tax Withheld</label>
                <input
                  id={`local-withholding-${activeW2Index}`}
                  type="number"
                  value={w2s[activeW2Index].localTaxWithheld}
                  onChange={(e) => updateW2(activeW2Index, 'localTaxWithheld', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
            </div>
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
