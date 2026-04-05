import { useState, useEffect, useCallback } from 'react'
import '../styles/SelfEmploymentScreen.css'

interface SelfEmploymentBusiness {
  id: string
  businessName: string
  businessEin: string
  businessAddress: string
  grossIncome: number
  costOfGoodsSold: number
  grossProfit: number
  // Expenses
  supplies: number
  utilities: number
  rent: number
  insurance: number
  marketing: number
  wages: number
  depreciation: number
  otherExpenses: number
  totalExpenses: number
  netProfit: number
  // Mileage
  businessMiles: number
  mileageRate: number
  mileageDeduction: number
  // QB Sync
  qbSyncEnabled: boolean
  qbSyncStatus: 'not_connected' | 'syncing' | 'synced' | 'error'
  qbSyncLastDate?: string
  qbSyncError?: string
}

interface SelfEmploymentScreenProps {
  onNext?: () => void
  onSave?: (data: { businesses: SelfEmploymentBusiness[]; totalNetIncome: number }) => void
  initialData?: { businesses: SelfEmploymentBusiness[] }
}

const defaultBusiness: Omit<SelfEmploymentBusiness, 'id'> = {
  businessName: '',
  businessEin: '',
  businessAddress: '',
  grossIncome: 0,
  costOfGoodsSold: 0,
  grossProfit: 0,
  supplies: 0,
  utilities: 0,
  rent: 0,
  insurance: 0,
  marketing: 0,
  wages: 0,
  depreciation: 0,
  otherExpenses: 0,
  totalExpenses: 0,
  netProfit: 0,
  businessMiles: 0,
  mileageRate: 2025 === 2025 ? 0.67 : 0.655, // 2025 standard mileage rate
  mileageDeduction: 0,
  qbSyncEnabled: false,
  qbSyncStatus: 'not_connected',
}

export default function SelfEmploymentScreen({ onNext, onSave, initialData }: SelfEmploymentScreenProps) {
  const [businesses, setBusinesses] = useState<SelfEmploymentBusiness[]>(
    initialData?.businesses || [
      {
        id: '1',
        ...defaultBusiness,
      },
    ]
  )
  const [taxEstimate, setTaxEstimate] = useState<number>(0)
  const [estimateLoading, setEstimateLoading] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [activeBusinessIndex, setActiveBusinessIndex] = useState(0)
  const [autoSaveStatus, setAutoSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle')

  // Calculate total self-employment income
  const totalNetIncome = businesses.reduce((sum, b) => sum + (b.netProfit || 0), 0)

  // Calculate a business's net profit
  const calculateNetProfit = (business: SelfEmploymentBusiness) => {
    const grossProfit = business.grossIncome - (business.costOfGoodsSold || 0)
    const totalExpenses = (business.supplies || 0) + (business.utilities || 0) +
      (business.rent || 0) + (business.insurance || 0) + (business.marketing || 0) +
      (business.wages || 0) + (business.depreciation || 0) + (business.otherExpenses || 0) +
      (business.mileageDeduction || 0)
    return Math.max(0, grossProfit - totalExpenses)
  }

  // Fetch real-time tax estimate
  const fetchTaxEstimate = useCallback(async () => {
    if (totalNetIncome === 0) {
      setTaxEstimate(0)
      return
    }

    setEstimateLoading(true)
    try {
      const response = await fetch('/api/estimate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tax_year: 2025,
          income: {
            wages: 0,
            business_income: totalNetIncome,
            interest_income: 0,
            dividend_income: 0,
            capital_gains: 0,
            rental_income: 0,
            other_income: 0,
          },
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
  }, [totalNetIncome])

  // Auto-save to localStorage
  useEffect(() => {
    const timer = setTimeout(async () => {
      setAutoSaveStatus('saving')
      const data = { businesses, totalNetIncome }
      localStorage.setItem('selfEmploymentScreen', JSON.stringify(data))

      try {
        await fetch('/api/auto-save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
        }).catch(() => {})
      } finally {
        setAutoSaveStatus('saved')
        setTimeout(() => setAutoSaveStatus('idle'), 2000)
      }
    }, 30000)

    return () => clearTimeout(timer)
  }, [businesses, totalNetIncome])

  // Real-time tax estimate
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchTaxEstimate()
    }, 500)

    return () => clearTimeout(timer)
  }, [totalNetIncome, fetchTaxEstimate])

  const updateBusiness = (index: number, field: keyof SelfEmploymentBusiness, value: any) => {
    const updated = [...businesses]
    const business = { ...updated[index], [field]: value }

    // Recalculate derived fields
    if (field === 'grossIncome' || field === 'costOfGoodsSold') {
      business.grossProfit = (business.grossIncome || 0) - (business.costOfGoodsSold || 0)
    }

    if (field === 'businessMiles' || field === 'mileageRate') {
      business.mileageDeduction = ((business.businessMiles || 0) * (business.mileageRate || 0))
    }

    if (['grossIncome', 'costOfGoodsSold', 'supplies', 'utilities', 'rent', 'insurance',
      'marketing', 'wages', 'depreciation', 'otherExpenses', 'mileageDeduction'].includes(field)) {
      business.netProfit = calculateNetProfit(business)
    }

    updated[index] = business
    setBusinesses(updated)

    // Clear error
    const key = `business_${index}_${field}`
    if (errors[key]) {
      const newErrors = { ...errors }
      delete newErrors[key]
      setErrors(newErrors)
    }
  }

  const handleQBSync = async (index: number) => {
    const updated = [...businesses]
    updated[index].qbSyncStatus = 'syncing'
    setBusinesses(updated)

    try {
      // Mock QB sync - replace with actual API call
      await new Promise(resolve => setTimeout(resolve, 2000))
      updated[index].qbSyncStatus = 'synced'
      updated[index].qbSyncLastDate = new Date().toISOString()
      setBusinesses([...updated])
    } catch (error) {
      updated[index].qbSyncStatus = 'error'
      updated[index].qbSyncError = 'Failed to sync with QuickBooks'
      setBusinesses([...updated])
    }
  }

  const addBusiness = () => {
    const newBusiness: SelfEmploymentBusiness = {
      id: Date.now().toString(),
      ...defaultBusiness,
    }
    setBusinesses([...businesses, newBusiness])
    setActiveBusinessIndex(businesses.length)
  }

  const removeBusiness = (index: number) => {
    if (businesses.length === 1) {
      setErrors({ ...errors, general: 'At least one business is required' })
      return
    }
    setBusinesses(businesses.filter((_, i) => i !== index))
    if (activeBusinessIndex >= businesses.length - 1) {
      setActiveBusinessIndex(businesses.length - 2)
    }
  }

  const handleNext = () => {
    const newErrors: Record<string, string> = {}

    if (businesses.some(b => !b.businessName?.trim())) {
      newErrors.businessNames = 'All businesses must have a name'
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    if (onSave) {
      onSave({ businesses, totalNetIncome })
    }

    if (onNext) {
      onNext()
    }
  }

  const activeBusiness = businesses[activeBusinessIndex]

  return (
    <div className="self-employment-screen">
      <div className="screen-header">
        <h1>Self-Employment Income</h1>
        <p>Enter your business income and expenses (Schedule C)</p>
      </div>

      {/* Tax Estimate Summary */}
      <div className="tax-summary">
        <div className="summary-card">
          <label>Total Net Business Income</label>
          <div className="summary-value">${totalNetIncome.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
        </div>
        <div className="summary-card">
          <label>Estimated Self-Employment Tax</label>
          <div className={`summary-value ${estimateLoading ? 'loading' : ''}`}>
            {estimateLoading ? 'Calculating...' : `$${(taxEstimate * 0.9235).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          </div>
        </div>
      </div>

      {/* Auto-save Status */}
      {autoSaveStatus === 'saved' && (
        <div className="auto-save-status">✓ Saved</div>
      )}

      {/* Business Tabs */}
      <div className="business-container">
        <div className="business-tabs">
          {businesses.map((business, index) => (
            <button
              key={business.id}
              className={`business-tab ${activeBusinessIndex === index ? 'active' : ''}`}
              onClick={() => setActiveBusinessIndex(index)}
            >
              <span className="tab-label">{business.businessName || `Business ${index + 1}`}</span>
              {businesses.length > 1 && (
                <button
                  className="tab-close"
                  onClick={(e) => {
                    e.stopPropagation()
                    removeBusiness(index)
                  }}
                >
                  ×
                </button>
              )}
            </button>
          ))}
          <button className="business-tab-add" onClick={addBusiness} title="Add another business">
            +
          </button>
        </div>

        {/* Business Form */}
        <div className="business-form">
          {errors.general && <div className="error-message">{errors.general}</div>}

          <div className="form-section">
            <h3>Business Information</h3>
            <div className="form-group">
              <label htmlFor={`name-${activeBusinessIndex}`}>Business Name *</label>
              <input
                id={`name-${activeBusinessIndex}`}
                type="text"
                value={activeBusiness.businessName}
                onChange={(e) => updateBusiness(activeBusinessIndex, 'businessName', e.target.value)}
                placeholder="e.g., Consulting LLC"
              />
            </div>

            <div className="form-group">
              <label htmlFor={`ein-${activeBusinessIndex}`}>EIN</label>
              <input
                id={`ein-${activeBusinessIndex}`}
                type="text"
                value={activeBusiness.businessEin}
                onChange={(e) => updateBusiness(activeBusinessIndex, 'businessEin', e.target.value)}
                placeholder="XX-XXXXXXX"
              />
            </div>

            <div className="form-group">
              <label htmlFor={`address-${activeBusinessIndex}`}>Business Address</label>
              <input
                id={`address-${activeBusinessIndex}`}
                type="text"
                value={activeBusiness.businessAddress}
                onChange={(e) => updateBusiness(activeBusinessIndex, 'businessAddress', e.target.value)}
                placeholder="123 Main St, City, State 12345"
              />
            </div>

            {/* QB Sync */}
            <div className="qb-sync-section">
              <h4>QuickBooks Integration</h4>
              <div className="qb-status">
                <span className={`status-badge ${activeBusiness.qbSyncStatus}`}>
                  {activeBusiness.qbSyncStatus === 'synced' && '✓ Synced'}
                  {activeBusiness.qbSyncStatus === 'syncing' && '⟳ Syncing...'}
                  {activeBusiness.qbSyncStatus === 'not_connected' && '○ Not Connected'}
                  {activeBusiness.qbSyncStatus === 'error' && '⚠ Error'}
                </span>
                {activeBusiness.qbSyncLastDate && (
                  <span className="sync-date">Last synced: {new Date(activeBusiness.qbSyncLastDate).toLocaleDateString()}</span>
                )}
              </div>
              <button
                className="btn-qb-sync"
                onClick={() => handleQBSync(activeBusinessIndex)}
                disabled={activeBusiness.qbSyncStatus === 'syncing'}
              >
                {activeBusiness.qbSyncStatus === 'syncing' ? 'Syncing...' : 'Sync with QuickBooks'}
              </button>
            </div>
          </div>

          <div className="form-section">
            <h3>Income</h3>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor={`gross-${activeBusinessIndex}`}>Gross Income</label>
                <input
                  id={`gross-${activeBusinessIndex}`}
                  type="number"
                  value={activeBusiness.grossIncome}
                  onChange={(e) => updateBusiness(activeBusinessIndex, 'grossIncome', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
              <div className="form-group">
                <label htmlFor={`cogs-${activeBusinessIndex}`}>Cost of Goods Sold</label>
                <input
                  id={`cogs-${activeBusinessIndex}`}
                  type="number"
                  value={activeBusiness.costOfGoodsSold}
                  onChange={(e) => updateBusiness(activeBusinessIndex, 'costOfGoodsSold', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
            </div>
            <div className="readonly-field">
              <label>Gross Profit</label>
              <div className="readonly-value">${activeBusiness.grossProfit.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
            </div>
          </div>

          <div className="form-section">
            <h3>Deductible Expenses</h3>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor={`supplies-${activeBusinessIndex}`}>Supplies</label>
                <input
                  id={`supplies-${activeBusinessIndex}`}
                  type="number"
                  value={activeBusiness.supplies}
                  onChange={(e) => updateBusiness(activeBusinessIndex, 'supplies', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
              <div className="form-group">
                <label htmlFor={`utilities-${activeBusinessIndex}`}>Utilities</label>
                <input
                  id={`utilities-${activeBusinessIndex}`}
                  type="number"
                  value={activeBusiness.utilities}
                  onChange={(e) => updateBusiness(activeBusinessIndex, 'utilities', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor={`rent-${activeBusinessIndex}`}>Rent/Lease</label>
                <input
                  id={`rent-${activeBusinessIndex}`}
                  type="number"
                  value={activeBusiness.rent}
                  onChange={(e) => updateBusiness(activeBusinessIndex, 'rent', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
              <div className="form-group">
                <label htmlFor={`insurance-${activeBusinessIndex}`}>Insurance</label>
                <input
                  id={`insurance-${activeBusinessIndex}`}
                  type="number"
                  value={activeBusiness.insurance}
                  onChange={(e) => updateBusiness(activeBusinessIndex, 'insurance', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor={`marketing-${activeBusinessIndex}`}>Marketing/Advertising</label>
                <input
                  id={`marketing-${activeBusinessIndex}`}
                  type="number"
                  value={activeBusiness.marketing}
                  onChange={(e) => updateBusiness(activeBusinessIndex, 'marketing', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
              <div className="form-group">
                <label htmlFor={`wages-${activeBusinessIndex}`}>Wages Paid</label>
                <input
                  id={`wages-${activeBusinessIndex}`}
                  type="number"
                  value={activeBusiness.wages}
                  onChange={(e) => updateBusiness(activeBusinessIndex, 'wages', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor={`depreciation-${activeBusinessIndex}`}>Depreciation</label>
                <input
                  id={`depreciation-${activeBusinessIndex}`}
                  type="number"
                  value={activeBusiness.depreciation}
                  onChange={(e) => updateBusiness(activeBusinessIndex, 'depreciation', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
              <div className="form-group">
                <label htmlFor={`other-${activeBusinessIndex}`}>Other Expenses</label>
                <input
                  id={`other-${activeBusinessIndex}`}
                  type="number"
                  value={activeBusiness.otherExpenses}
                  onChange={(e) => updateBusiness(activeBusinessIndex, 'otherExpenses', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
            </div>
          </div>

          <div className="form-section">
            <h3>Business Mileage Deduction</h3>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor={`miles-${activeBusinessIndex}`}>Total Business Miles</label>
                <input
                  id={`miles-${activeBusinessIndex}`}
                  type="number"
                  value={activeBusiness.businessMiles}
                  onChange={(e) => updateBusiness(activeBusinessIndex, 'businessMiles', parseFloat(e.target.value) || 0)}
                  step="1"
                />
              </div>
              <div className="form-group">
                <label htmlFor={`rate-${activeBusinessIndex}`}>Rate per Mile</label>
                <input
                  id={`rate-${activeBusinessIndex}`}
                  type="number"
                  value={activeBusiness.mileageRate}
                  onChange={(e) => updateBusiness(activeBusinessIndex, 'mileageRate', parseFloat(e.target.value) || 0)}
                  step="0.01"
                  disabled
                />
                <small>2025 standard rate: $0.67/mile</small>
              </div>
            </div>
            <div className="readonly-field">
              <label>Mileage Deduction</label>
              <div className="readonly-value">${activeBusiness.mileageDeduction.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
            </div>
          </div>

          <div className="form-section net-profit-summary">
            <h3>Net Profit (Loss)</h3>
            <div className="profit-calculation">
              <div className="calc-row">
                <span>Gross Profit:</span>
                <strong>${activeBusiness.grossProfit.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
              </div>
              <div className="calc-row">
                <span>Total Expenses + Mileage:</span>
                <strong>−${((activeBusiness.supplies || 0) + (activeBusiness.utilities || 0) + (activeBusiness.rent || 0) +
                  (activeBusiness.insurance || 0) + (activeBusiness.marketing || 0) + (activeBusiness.wages || 0) +
                  (activeBusiness.depreciation || 0) + (activeBusiness.otherExpenses || 0) + (activeBusiness.mileageDeduction || 0)
                ).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
              </div>
              <div className="calc-row total">
                <span>Schedule C Net Profit:</span>
                <strong className={activeBusiness.netProfit >= 0 ? 'positive' : 'negative'}>
                  ${activeBusiness.netProfit.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </strong>
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
