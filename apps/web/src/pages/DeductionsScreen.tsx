import { useState, useEffect } from 'react'
import { useFilingWizard, DeductionsData } from '../context/FilingWizardContext'
import '../styles/FilingWizard.css'

const STANDARD_DEDUCTION_2025 = {
  single: 15000,
  married_joint: 30000,
  married_separate: 15000,
  head_of_household: 22500,
}

interface DeductionsScreenProps {
  filingStatus?: 'single' | 'married_joint' | 'married_separate' | 'head_of_household'
}

export default function DeductionsScreen({ filingStatus = 'single' }: DeductionsScreenProps) {
  const { state, updateDeductions, nextStep } = useFilingWizard()
  const [deductionType, setDeductionType] = useState<'standard' | 'itemized'>(
    state.deductions?.deductionType || 'standard'
  )
  const [mortgageInterest, setMortgageInterest] = useState(
    state.deductions?.itemizedDeductions?.mortgageInterest || 0
  )
  const [propertyTaxes, setPropertyTaxes] = useState(
    state.deductions?.itemizedDeductions?.propertyTaxes || 0
  )
  const [charitableDonations, setCharitableDonations] = useState(
    state.deductions?.itemizedDeductions?.charitableDonations || 0
  )
  const [studentLoanInterest, setStudentLoanInterest] = useState(
    state.deductions?.itemizedDeductions?.studentLoanInterest || 0
  )
  const [otherDeductions, setOtherDeductions] = useState(
    state.deductions?.itemizedDeductions?.otherDeductions || 0
  )

  const standardDeduction = STANDARD_DEDUCTION_2025[filingStatus]
  const totalItemized =
    mortgageInterest +
    propertyTaxes +
    charitableDonations +
    studentLoanInterest +
    otherDeductions
  const delta = totalItemized - standardDeduction
  const recommendedType = delta > 0 ? 'itemized' : 'standard'

  useEffect(() => {
    // Auto-save to localStorage
    const timeout = setTimeout(() => {
      const data: DeductionsData = {
        deductionType,
        itemizedDeductions: {
          mortgageInterest,
          propertyTaxes,
          charitableDonations,
          studentLoanInterest,
          otherDeductions,
        },
        delta,
      }
      updateDeductions(data)
    }, 500)

    return () => clearTimeout(timeout)
  }, [
    deductionType,
    mortgageInterest,
    propertyTaxes,
    charitableDonations,
    studentLoanInterest,
    otherDeductions,
    delta,
    updateDeductions,
  ])

  const handleNext = () => {
    const data: DeductionsData = {
      deductionType,
      itemizedDeductions: {
        mortgageInterest,
        propertyTaxes,
        charitableDonations,
        studentLoanInterest,
        otherDeductions,
      },
      delta,
    }
    updateDeductions(data)
    nextStep()
  }

  return (
    <div className="wizard-screen">
      <div className="screen-header">
        <h1>Deductions & Schedule A</h1>
        <p>Choose standard or itemized deductions to maximize your tax savings</p>
      </div>

      {/* Deduction Type Selection */}
      <div className="wizard-section">
        <h2>Which deduction method saves you more?</h2>

        <div className="deduction-comparison">
          {/* Standard Deduction Card */}
          <div className={`deduction-card ${deductionType === 'standard' ? 'selected' : ''}`}>
            <input
              type="radio"
              id="standard"
              name="deductionType"
              value="standard"
              checked={deductionType === 'standard'}
              onChange={(e) => setDeductionType(e.target.value as 'standard' | 'itemized')}
            />
            <label htmlFor="standard" className="card-label">
              <div className="card-header">
                <span className="card-title">Standard Deduction</span>
                {recommendedType === 'standard' && (
                  <span className="badge-recommended">Recommended</span>
                )}
              </div>
              <div className="card-amount">${standardDeduction.toLocaleString()}</div>
              <p className="card-description">Simple, no documentation required</p>
            </label>
          </div>

          {/* Itemized Deductions Card */}
          <div className={`deduction-card ${deductionType === 'itemized' ? 'selected' : ''}`}>
            <input
              type="radio"
              id="itemized"
              name="deductionType"
              value="itemized"
              checked={deductionType === 'itemized'}
              onChange={(e) => setDeductionType(e.target.value as 'standard' | 'itemized')}
            />
            <label htmlFor="itemized" className="card-label">
              <div className="card-header">
                <span className="card-title">Itemized Deductions</span>
                {recommendedType === 'itemized' && (
                  <span className="badge-recommended">Recommended</span>
                )}
              </div>
              <div className="card-amount">${totalItemized.toLocaleString()}</div>
              <p className="card-description">Requires tracking expenses</p>
            </label>
          </div>
        </div>

        {/* Delta Savings */}
        {delta !== 0 && (
          <div className={`delta-banner ${delta > 0 ? 'positive' : 'neutral'}`}>
            {delta > 0 ? (
              <>
                <strong>Save ${Math.abs(delta).toLocaleString()}</strong> by itemizing deductions
              </>
            ) : (
              <>
                Standard deduction is better for your situation
              </>
            )}
          </div>
        )}
      </div>

      {/* Itemized Deductions Form */}
      {deductionType === 'itemized' && (
        <div className="wizard-section">
          <h2>Schedule A: Itemized Deductions</h2>

          <div className="form-group">
            <label htmlFor="mortgage">Mortgage Interest (Box 1)</label>
            <div className="input-wrapper">
              <span className="currency-symbol">$</span>
              <input
                id="mortgage"
                type="number"
                value={mortgageInterest}
                onChange={(e) => setMortgageInterest(parseFloat(e.target.value) || 0)}
                placeholder="0.00"
                min="0"
                step="0.01"
              />
            </div>
            <small>From your mortgage statement or Form 1098</small>
          </div>

          <div className="form-group">
            <label htmlFor="property-taxes">State & Local Property Taxes (Box 5a)</label>
            <div className="input-wrapper">
              <span className="currency-symbol">$</span>
              <input
                id="property-taxes"
                type="number"
                value={propertyTaxes}
                onChange={(e) => setPropertyTaxes(parseFloat(e.target.value) || 0)}
                placeholder="0.00"
                min="0"
                step="0.01"
              />
            </div>
            <small>Limited to $10,000 combined with income taxes (SALT cap)</small>
          </div>

          <div className="form-group">
            <label htmlFor="charitable">Charitable Donations (Box 11)</label>
            <div className="input-wrapper">
              <span className="currency-symbol">$</span>
              <input
                id="charitable"
                type="number"
                value={charitableDonations}
                onChange={(e) => setCharitableDonations(parseFloat(e.target.value) || 0)}
                placeholder="0.00"
                min="0"
                step="0.01"
              />
            </div>
            <small>Cash and non-cash charitable donations</small>
          </div>

          <div className="form-group">
            <label htmlFor="student-loan">Student Loan Interest (Box 10)</label>
            <div className="input-wrapper">
              <span className="currency-symbol">$</span>
              <input
                id="student-loan"
                type="number"
                value={studentLoanInterest}
                onChange={(e) => setStudentLoanInterest(parseFloat(e.target.value) || 0)}
                placeholder="0.00"
                min="0"
                step="0.01"
              />
            </div>
            <small>Limited to $2,500 per return</small>
          </div>

          <div className="form-group">
            <label htmlFor="other">Other Deductions</label>
            <div className="input-wrapper">
              <span className="currency-symbol">$</span>
              <input
                id="other"
                type="number"
                value={otherDeductions}
                onChange={(e) => setOtherDeductions(parseFloat(e.target.value) || 0)}
                placeholder="0.00"
                min="0"
                step="0.01"
              />
            </div>
            <small>Medical, casualty loss, or other deductible expenses</small>
          </div>

          {/* Itemized Total */}
          <div className="form-summary">
            <div className="summary-row">
              <span>Total Itemized Deductions</span>
              <strong>${totalItemized.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
            </div>
            <div className="summary-row">
              <span>Standard Deduction</span>
              <span>${standardDeduction.toLocaleString()}</span>
            </div>
            <div className="summary-row divider">
              <span>Additional Savings</span>
              <strong className={delta > 0 ? 'positive' : 'neutral'}>
                {delta > 0 ? '+' : ''} ${Math.abs(delta).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </strong>
            </div>
          </div>
        </div>
      )}

      {/* Navigation */}
      <div className="screen-footer">
        <button className="btn-secondary">Back</button>
        <button className="btn-primary" onClick={handleNext}>
          Continue to Credits
        </button>
      </div>
    </div>
  )
}
