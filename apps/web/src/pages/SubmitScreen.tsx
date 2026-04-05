import { useState, useEffect } from 'react'
import { useFilingWizard, SubmitData } from '../context/FilingWizardContext'
import '../styles/FilingWizard.css'

export default function SubmitScreen() {
  const { state, updateSubmit, nextStep } = useFilingWizard()
  const [eFileConsent, setEFileConsent] = useState(state.submit?.eFileConsent || false)
  const [ipPin, setIpPin] = useState(state.submit?.ipPin || '')
  const [refundMethod, setRefundMethod] = useState(state.submit?.refundMethod || 'direct_deposit')
  const [routingNumber, setRoutingNumber] = useState(
    state.submit?.bankAccount?.routingNumber || ''
  )
  const [accountNumber, setAccountNumber] = useState(
    state.submit?.bankAccount?.accountNumber || ''
  )
  const [accountType, setAccountType] = useState<'checking' | 'savings'>(
    state.submit?.bankAccount?.accountType || 'checking'
  )
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    const timeout = setTimeout(() => {
      const data: SubmitData = {
        eFileConsent,
        ipPin,
        refundMethod: refundMethod as 'direct_deposit' | 'check',
        bankAccount:
          refundMethod === 'direct_deposit'
            ? { routingNumber, accountNumber, accountType }
            : undefined,
      }
      updateSubmit(data)
    }, 500)

    return () => clearTimeout(timeout)
  }, [eFileConsent, ipPin, refundMethod, routingNumber, accountNumber, accountType, updateSubmit])

  const handleSubmit = async () => {
    const newErrors: Record<string, string> = {}

    if (!eFileConsent) {
      newErrors.eFileConsent = 'You must consent to e-filing to submit your return'
    }

    if (refundMethod === 'direct_deposit') {
      if (!routingNumber.trim()) {
        newErrors.routingNumber = 'Routing number is required'
      } else if (!/^\d{9}$/.test(routingNumber)) {
        newErrors.routingNumber = 'Routing number must be 9 digits'
      }

      if (!accountNumber.trim()) {
        newErrors.accountNumber = 'Account number is required'
      } else if (!/^\d{8,17}$/.test(accountNumber)) {
        newErrors.accountNumber = 'Account number must be 8-17 digits'
      }
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    setIsSubmitting(true)

    try {
      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 2000))

      const data: SubmitData = {
        eFileConsent,
        ipPin,
        refundMethod,
        bankAccount:
          refundMethod === 'direct_deposit'
            ? { routingNumber, accountNumber, accountType: accountType as 'checking' | 'savings' }
            : undefined,
        submittedAt: new Date().toISOString(),
        confirmationNumber: `2025-${Math.random().toString(36).substr(2, 9).toUpperCase()}`,
      }

      updateSubmit(data)
      nextStep()
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="wizard-screen">
      <div className="screen-header">
        <h1>Submit Your Return</h1>
        <p>Electronically file your 2025 tax return</p>
      </div>

      {/* E-File Consent */}
      <div className="wizard-section">
        <h2>Electronic Filing Consent</h2>

        <div className="consent-box">
          <div className="form-group">
            <label htmlFor="efile-consent" className="checkbox-label">
              <input
                id="efile-consent"
                type="checkbox"
                checked={eFileConsent}
                onChange={(e) => setEFileConsent(e.target.checked)}
              />
              <span className="checkbox-text">
                I consent to electronic filing of my 2025 tax return and authorize e-filing
              </span>
            </label>
          </div>

          {errors.eFileConsent && (
            <div className="error-message">{errors.eFileConsent}</div>
          )}

          <div className="consent-details">
            <h4>What happens when you e-file:</h4>
            <ul>
              <li>Your return is transmitted to the IRS electronically</li>
              <li>You receive an electronic acknowledgment within 24 hours</li>
              <li>Processing is typically faster than paper filing</li>
              <li>Direct deposit refunds arrive within 21 days (typically sooner)</li>
            </ul>
          </div>
        </div>
      </div>

      {/* IP PIN (Optional) */}
      <div className="wizard-section">
        <h2>Identity Protection PIN (Optional)</h2>
        <p>If you have an IRS Identity Protection PIN, enter it below</p>

        <div className="form-group">
          <label htmlFor="ip-pin">IP PIN (if you have one)</label>
          <input
            id="ip-pin"
            type="text"
            value={ipPin}
            onChange={(e) => setIpPin(e.target.value.slice(0, 6))}
            placeholder="6-digit PIN"
            maxLength={6}
          />
          <small>Helps protect your return from identity theft</small>
        </div>
      </div>

      {/* Refund Method */}
      <div className="wizard-section">
        <h2>How Would You Like Your Refund?</h2>

        <div className="refund-options">
          <label className="refund-option">
            <input
              type="radio"
              name="refundMethod"
              value="direct_deposit"
              checked={refundMethod === 'direct_deposit'}
              onChange={(e) => setRefundMethod(e.target.value as 'direct_deposit' | 'check')}
            />
            <div className="refund-option-content">
              <h3>Direct Deposit (Fastest)</h3>
              <p>Refund deposited to your bank account in 3-21 days</p>
            </div>
          </label>

          <label className="refund-option">
            <input
              type="radio"
              name="refundMethod"
              value="check"
              checked={refundMethod === 'check'}
              onChange={(e) => setRefundMethod(e.target.value as 'direct_deposit' | 'check')}
            />
            <div className="refund-option-content">
              <h3>Paper Check</h3>
              <p>Check mailed to your address in 3-4 weeks</p>
            </div>
          </label>
        </div>
      </div>

      {/* Direct Deposit Details */}
      {refundMethod === 'direct_deposit' && (
        <div className="wizard-section">
          <h2>Bank Account Information</h2>

          <div className="form-group">
            <label htmlFor="routing">Bank Routing Number (9 digits)</label>
            <input
              id="routing"
              type="text"
              value={routingNumber}
              onChange={(e) => setRoutingNumber(e.target.value.replace(/\D/g, '').slice(0, 9))}
              placeholder="123456789"
              maxLength={9}
            />
            {errors.routingNumber && (
              <span className="field-error">{errors.routingNumber}</span>
            )}
            <small>Find your routing number on a check or contact your bank</small>
          </div>

          <div className="form-group">
            <label htmlFor="account">Account Number</label>
            <input
              id="account"
              type="text"
              value={accountNumber}
              onChange={(e) => setAccountNumber(e.target.value.replace(/\D/g, '').slice(0, 17))}
              placeholder="123456789012345"
            />
            {errors.accountNumber && (
              <span className="field-error">{errors.accountNumber}</span>
            )}
            <small>Do not include dashes</small>
          </div>

          <div className="form-group">
            <label htmlFor="account-type">Account Type</label>
            <select
              id="account-type"
              value={accountType}
              onChange={(e) => setAccountType(e.target.value as 'checking' | 'savings')}
            >
              <option value="checking">Checking Account</option>
              <option value="savings">Savings Account</option>
            </select>
          </div>

          <div className="info-box">
            <h4>🔒 Your Account Information is Secure</h4>
            <p>
              We use industry-standard encryption and only transmit your banking information
              to the IRS for direct deposit purposes.
            </p>
          </div>
        </div>
      )}

      {/* Submission Summary */}
      <div className="submission-summary">
        <h3>Ready to Submit?</h3>
        <div className="summary-checklist">
          <div className="checklist-item">
            <span className={eFileConsent ? 'checked' : 'unchecked'}>✓</span>
            E-file consent provided
          </div>
          <div className="checklist-item">
            <span className={refundMethod ? 'checked' : 'unchecked'}>✓</span>
            Refund method selected
          </div>
          {refundMethod === 'direct_deposit' && (
            <div className="checklist-item">
              <span className={routingNumber && accountNumber ? 'checked' : 'unchecked'}>✓</span>
              Bank account information provided
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <div className="screen-footer">
        <button className="btn-secondary" disabled={isSubmitting}>
          Back
        </button>
        <button
          className="btn-primary btn-submit"
          onClick={handleSubmit}
          disabled={isSubmitting || !eFileConsent}
        >
          {isSubmitting ? 'Submitting...' : 'Submit Return to IRS'}
        </button>
      </div>

      {isSubmitting && (
        <div className="submission-progress">
          <div className="progress-spinner"></div>
          <p>Submitting your return to the IRS...</p>
        </div>
      )}
    </div>
  )
}
