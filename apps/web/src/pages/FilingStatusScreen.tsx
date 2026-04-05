import { useState, useEffect } from 'react'
import { useFilingWizard, FilingStatusData } from '../context/FilingWizardContext'
import '../styles/FilingWizard.css'

const FILING_STATUS_OPTIONS = [
  {
    value: 'single',
    label: 'Single',
    description: 'Unmarried at year-end',
    icon: '👤',
  },
  {
    value: 'married_joint',
    label: 'Married Filing Jointly',
    description: 'Combined return (recommended for most)',
    icon: '👫',
  },
  {
    value: 'married_separate',
    label: 'Married Filing Separately',
    description: 'Individual returns (limited benefits)',
    icon: '👥',
  },
  {
    value: 'head_of_household',
    label: 'Head of Household',
    description: 'Unmarried with dependent',
    icon: '👨‍👧',
  },
]

export default function FilingStatusScreen() {
  const { state, updateFilingStatus, nextStep } = useFilingWizard()
  const totalIncome = 0
  const [filingStatus, setFilingStatus] = useState<'single' | 'married_joint' | 'married_separate' | 'head_of_household'>(
    state.filingStatus?.status || 'single'
  )
  const [jointFilerName, setJointFilerName] = useState(
    state.filingStatus?.jointFilerName || ''
  )
  const [jointFilerSSN, setJointFilerSSN] = useState(
    state.filingStatus?.jointFilerSSN || ''
  )
  const [showComparison, setShowComparison] = useState(false)

  // Calculate MFJ vs MFS comparison
  const mfjTaxEstimate = totalIncome * 0.12 // Simplified
  const mfsTaxEstimate = (totalIncome * 0.12) * 1.05 // MFS typically less favorable

  useEffect(() => {
    const timeout = setTimeout(() => {
      const data: FilingStatusData = {
        status: filingStatus as any,
        jointFilerName,
        jointFilerSSN,
        mfsComparison:
          filingStatus === 'married_joint'
            ? {
                mjAmount: mfjTaxEstimate,
                mfsAmount: mfsTaxEstimate,
                savings: mfsTaxEstimate - mfjTaxEstimate,
              }
            : undefined,
      }
      updateFilingStatus(data)
    }, 500)

    return () => clearTimeout(timeout)
  }, [filingStatus, jointFilerName, jointFilerSSN, mfjTaxEstimate, mfsTaxEstimate, updateFilingStatus])

  const handleNext = () => {
    const data: FilingStatusData = {
      status: filingStatus as any,
      jointFilerName,
      jointFilerSSN,
      mfsComparison:
        filingStatus === 'married_joint'
          ? {
              mjAmount: mfjTaxEstimate,
              mfsAmount: mfsTaxEstimate,
              savings: mfsTaxEstimate - mfjTaxEstimate,
            }
          : undefined,
    }
    updateFilingStatus(data)
    nextStep()
  }

  return (
    <div className="wizard-screen">
      <div className="screen-header">
        <h1>Filing Status Optimization</h1>
        <p>Choose the filing status that maximizes your tax savings</p>
      </div>

      {/* Filing Status Selection */}
      <div className="wizard-section">
        <h2>What is your filing status?</h2>

        <div className="status-grid">
          {FILING_STATUS_OPTIONS.map((option) => (
            <label key={option.value} className="status-card">
              <input
                type="radio"
                name="filingStatus"
                value={option.value}
                checked={filingStatus === option.value}
                onChange={(e) => setFilingStatus(e.target.value as 'single' | 'married_joint' | 'married_separate' | 'head_of_household')}
              />
              <div className="status-card-content">
                <div className="status-icon">{option.icon}</div>
                <h3>{option.label}</h3>
                <p>{option.description}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Spouse Information */}
      {filingStatus === 'married_joint' && (
        <div className="wizard-section">
          <h2>Spouse Information</h2>

          <div className="form-group">
            <label htmlFor="spouse-name">Spouse's Full Name</label>
            <input
              id="spouse-name"
              type="text"
              value={jointFilerName}
              onChange={(e) => setJointFilerName(e.target.value)}
              placeholder="Enter spouse's full name"
            />
          </div>

          <div className="form-group">
            <label htmlFor="spouse-ssn">Spouse's Social Security Number</label>
            <input
              id="spouse-ssn"
              type="text"
              value={jointFilerSSN}
              onChange={(e) => setJointFilerSSN(e.target.value)}
              placeholder="XXX-XX-XXXX"
            />
          </div>

          {/* MFJ vs MFS Comparison */}
          <button
            type="button"
            className="btn-text"
            onClick={() => setShowComparison(!showComparison)}
          >
            {showComparison ? '✓' : 'ℹ︎'} Compare MFJ vs MFS
          </button>

          {showComparison && (
            <div className="comparison-box">
              <h3>Married Filing Jointly vs. Separately</h3>
              <div className="comparison-row">
                <div className="comparison-column">
                  <h4>Married Filing Jointly (MFJ)</h4>
                  <div className="comparison-value">${mfjTaxEstimate.toLocaleString('en-US', { maximumFractionDigits: 0 })}</div>
                  <p className="comparison-label">Estimated tax</p>
                  <ul className="comparison-benefits">
                    <li>✓ Lower tax rates</li>
                    <li>✓ Higher standard deduction</li>
                    <li>✓ More credits available</li>
                    <li>✓ Better for most couples</li>
                  </ul>
                </div>
                <div className="comparison-column">
                  <h4>Married Filing Separately (MFS)</h4>
                  <div className="comparison-value">${mfsTaxEstimate.toLocaleString('en-US', { maximumFractionDigits: 0 })}</div>
                  <p className="comparison-label">Estimated tax</p>
                  <ul className="comparison-benefits">
                    <li>✗ Higher tax rates</li>
                    <li>✗ Lower standard deduction</li>
                    <li>✗ Fewer credits available</li>
                    <li>✗ Limited situations only</li>
                  </ul>
                </div>
              </div>

              {mfsTaxEstimate - mfjTaxEstimate > 0 && (
                <div className="savings-banner">
                  <strong>MFJ saves ${(mfsTaxEstimate - mfjTaxEstimate).toLocaleString('en-US', { maximumFractionDigits: 0 })}</strong>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Info Boxes */}
      <div className="wizard-section">
        <div className="info-box">
          <h4>📋 How to Determine Your Filing Status</h4>
          <p>Your filing status on December 31st of the tax year determines your status for the entire year.</p>
        </div>

        <div className="info-box">
          <h4>💡 Tips for Married Filers</h4>
          <p>In most cases, Married Filing Jointly offers the lowest tax rate and qualifies you for more credits and deductions.</p>
        </div>
      </div>

      {/* Navigation */}
      <div className="screen-footer">
        <button className="btn-secondary">Back</button>
        <button className="btn-primary" onClick={handleNext}>
          Continue to Review
        </button>
      </div>
    </div>
  )
}
