import { useEffect } from 'react'
import { useFilingWizard, ReviewData } from '../context/FilingWizardContext'
import '../styles/FilingWizard.css'

export default function ReviewScreen() {
  const { state, updateReview, nextStep } = useFilingWizard()

  const deductions = state.deductions
  const credits = state.credits
  const filingStatus = state.filingStatus

  // Simplified calculation (in real app, would call API)
  const totalIncome = 85000 // From earlier screens
  const totalDeductions = deductions?.deductionType === 'itemized'
    ? (deductions.itemizedDeductions?.mortgageInterest || 0) +
      (deductions.itemizedDeductions?.propertyTaxes || 0) +
      (deductions.itemizedDeductions?.charitableDonations || 0) +
      (deductions.itemizedDeductions?.studentLoanInterest || 0) +
      (deductions.itemizedDeductions?.otherDeductions || 0)
    : 15000

  const adjustedGrossIncome = Math.max(0, totalIncome - totalDeductions)
  const totalCredits = (credits?.childTaxCredit || 0) +
    (credits?.childAndDependentCareCredit || 0) +
    (credits?.studentEducationCredit || 0) +
    (credits?.electricVehicleCredit || 0)

  const estimatedTaxLiability = Math.max(0, adjustedGrossIncome * 0.12 - totalCredits) // Simplified
  const estimatedRefund = totalCredits - (estimatedTaxLiability > 0 ? 0 : Math.abs(estimatedTaxLiability))

  useEffect(() => {
    const timeout = setTimeout(() => {
      const data: ReviewData = {
        totalIncome,
        totalDeductions,
        adjustedGrossIncome,
        totalCredits,
        totalTaxLiability: Math.max(0, estimatedTaxLiability),
        estimatedRefund: Math.max(0, estimatedRefund),
      }
      updateReview(data)
    }, 500)

    return () => clearTimeout(timeout)
  }, [totalIncome, totalDeductions, adjustedGrossIncome, totalCredits, estimatedTaxLiability, estimatedRefund, updateReview])

  const handleNext = () => {
    const data: ReviewData = {
      totalIncome,
      totalDeductions,
      adjustedGrossIncome,
      totalCredits,
      totalTaxLiability: Math.max(0, estimatedTaxLiability),
      estimatedRefund: Math.max(0, estimatedRefund),
    }
    updateReview(data)
    nextStep()
  }

  return (
    <div className="wizard-screen">
      <div className="screen-header">
        <h1>Review Your Tax Return</h1>
        <p>Summary of income, deductions, credits, and estimated tax liability</p>
      </div>

      {/* Income Section */}
      <div className="review-section">
        <h2>Income Summary</h2>
        <div className="review-table">
          <div className="review-row">
            <span className="row-label">Total Income</span>
            <span className="row-value">${totalIncome.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
          </div>
        </div>
      </div>

      {/* Deductions Section */}
      <div className="review-section">
        <h2>Deductions</h2>
        <div className="review-table">
          <div className="review-row">
            <span className="row-label">
              {deductions?.deductionType === 'itemized' ? 'Itemized Deductions' : 'Standard Deduction'}
            </span>
            <span className="row-value">${totalDeductions.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
          </div>
          {deductions?.deductionType === 'itemized' && deductions.delta !== undefined && (
            <div className="review-row">
              <span className="row-label">Savings vs. Standard</span>
              <span className={`row-value ${deductions.delta > 0 ? 'positive' : ''}`}>
                ${Math.abs(deductions.delta).toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </span>
            </div>
          )}
          <div className="review-row divider">
            <span className="row-label">Adjusted Gross Income</span>
            <span className="row-value strong">${adjustedGrossIncome.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
          </div>
        </div>
      </div>

      {/* Credits Section */}
      <div className="review-section">
        <h2>Tax Credits</h2>
        <div className="review-table">
          {credits?.childTaxCredit ? (
            <div className="review-row">
              <span className="row-label">Child Tax Credit</span>
              <span className="row-value">${credits.childTaxCredit.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
            </div>
          ) : null}
          {credits?.childAndDependentCareCredit ? (
            <div className="review-row">
              <span className="row-label">Child & Dependent Care Credit</span>
              <span className="row-value">${credits.childAndDependentCareCredit.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
            </div>
          ) : null}
          {credits?.studentEducationCredit ? (
            <div className="review-row">
              <span className="row-label">Education Credits</span>
              <span className="row-value">${credits.studentEducationCredit.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
            </div>
          ) : null}
          {credits?.electricVehicleCredit ? (
            <div className="review-row">
              <span className="row-label">EV Credit</span>
              <span className="row-value">${credits.electricVehicleCredit.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
            </div>
          ) : null}
          {totalCredits > 0 && (
            <div className="review-row divider">
              <span className="row-label">Total Credits</span>
              <span className="row-value strong">${totalCredits.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
            </div>
          )}
        </div>
      </div>

      {/* Filing Status */}
      <div className="review-section">
        <h2>Filing Status & Taxpayer Info</h2>
        <div className="review-table">
          <div className="review-row">
            <span className="row-label">Filing Status</span>
            <span className="row-value">{filingStatus?.status?.replace(/_/g, ' ').toUpperCase()}</span>
          </div>
          {filingStatus?.jointFilerName && (
            <div className="review-row">
              <span className="row-label">Spouse Name</span>
              <span className="row-value">{filingStatus.jointFilerName}</span>
            </div>
          )}
        </div>
      </div>

      {/* Tax Calculation Summary */}
      <div className="tax-calculation">
        <div className="calc-row">
          <span>Adjusted Gross Income</span>
          <span>${adjustedGrossIncome.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
        </div>
        <div className="calc-row">
          <span>Federal Income Tax (est.)</span>
          <span>${(adjustedGrossIncome * 0.12).toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
        </div>
        <div className="calc-row">
          <span>Less: Tax Credits</span>
          <span>−${totalCredits.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
        </div>
        <div className="calc-row divider">
          <span>Estimated Tax Liability</span>
          <span className={estimatedTaxLiability > 0 ? 'tax-owed' : 'refund'}>
            {estimatedTaxLiability > 0 ? (
              `$${estimatedTaxLiability.toLocaleString('en-US', { minimumFractionDigits: 2 })} owed`
            ) : (
              `$${Math.abs(estimatedTaxLiability).toLocaleString('en-US', { minimumFractionDigits: 2 })} refund`
            )}
          </span>
        </div>

        {estimatedRefund > 0 && (
          <div className="refund-banner">
            <h3>💰 Estimated Refund: ${estimatedRefund.toLocaleString('en-US', { minimumFractionDigits: 2 })}</h3>
            <p>You may receive this refund via direct deposit</p>
          </div>
        )}
      </div>

      {/* Warning Flags */}
      <div className="wizard-section">
        <h4>⚠️ Important Notes</h4>
        <ul className="warning-list">
          <li>This is an estimate. Actual tax liability may vary based on final calculations</li>
          <li>Income limits apply to certain credits. Your eligibility may be reduced</li>
          <li>Additional tax may be due if you have other income sources not listed</li>
          <li>Some deductions and credits have specific documentation requirements</li>
        </ul>
      </div>

      {/* Navigation */}
      <div className="screen-footer">
        <button className="btn-secondary">Back</button>
        <button className="btn-primary" onClick={handleNext}>
          Continue to Submit
        </button>
      </div>
    </div>
  )
}
