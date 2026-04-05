import { useState, useEffect } from 'react'
import '../styles/RealEstateScreen.css'

interface RentalProperty {
  id: string
  address: string
  propertyType: 'residential' | 'commercial' | 'land' | 'other'
  rentalIncome: number
  expenses: {
    mortgage: number
    propertyTax: number
    insurance: number
    utilities: number
    maintenance: number
    other: number
  }
  depreciation: {
    baseCost: number
    landValue: number
    buildingCost: number
    annualDeduction: number
  }
  netIncome: number
}

interface RealEstateScreenProps {
  onNext?: () => void
  onSave?: (data: { properties: RentalProperty[]; totalNetIncome: number }) => void
  initialData?: { properties: RentalProperty[] }
}

const defaultProperty: Omit<RentalProperty, 'id'> = {
  address: '',
  propertyType: 'residential',
  rentalIncome: 0,
  expenses: {
    mortgage: 0,
    propertyTax: 0,
    insurance: 0,
    utilities: 0,
    maintenance: 0,
    other: 0,
  },
  depreciation: {
    baseCost: 0,
    landValue: 0,
    buildingCost: 0,
    annualDeduction: 0,
  },
  netIncome: 0,
}

export default function RealEstateScreen({ onNext, onSave, initialData }: RealEstateScreenProps) {
  const [properties, setProperties] = useState<RentalProperty[]>(
    initialData?.properties || [{ id: '1', ...defaultProperty }]
  )
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [activePropertyIndex, setActivePropertyIndex] = useState(0)
  const [autoSaveStatus, setAutoSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle')

  const totalNetIncome = properties.reduce((sum, p) => sum + (p.netIncome || 0), 0)

  const calculateNetIncome = (property: RentalProperty) => {
    const totalExpenses = Object.values(property.expenses).reduce((sum, val) => sum + (val || 0), 0)
    return (property.rentalIncome || 0) - totalExpenses - (property.depreciation.annualDeduction || 0)
  }

  // Auto-save
  useEffect(() => {
    const timer = setTimeout(async () => {
      setAutoSaveStatus('saving')
      const data = { properties, totalNetIncome }
      localStorage.setItem('realEstateScreen', JSON.stringify(data))

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
  }, [properties, totalNetIncome])

  const updateProperty = (index: number, field: string, value: any) => {
    const updated = [...properties]
    const keys = field.split('.')
    let current: any = updated[index]

    for (let i = 0; i < keys.length - 1; i++) {
      if (!current[keys[i]]) current[keys[i]] = {}
      current = current[keys[i]]
    }

    current[keys[keys.length - 1]] = value

    // Recalculate depreciation and net income
    if (field === 'depreciation.baseCost' || field === 'depreciation.landValue') {
      const prop = updated[index]
      prop.depreciation.buildingCost = (prop.depreciation.baseCost || 0) - (prop.depreciation.landValue || 0)
      // Simple straight-line depreciation: 27.5 years for residential
      prop.depreciation.annualDeduction = prop.depreciation.buildingCost / 27.5
    }

    if (keys[0] === 'rentalIncome' || keys[0] === 'expenses' || keys[0] === 'depreciation') {
      updated[index].netIncome = calculateNetIncome(updated[index])
    }

    setProperties(updated)
  }

  const addProperty = () => {
    const newProp: RentalProperty = {
      id: Date.now().toString(),
      ...defaultProperty,
    }
    setProperties([...properties, newProp])
    setActivePropertyIndex(properties.length)
  }

  const removeProperty = (index: number) => {
    if (properties.length === 1) {
      setErrors({ ...errors, general: 'At least one property is required' })
      return
    }
    setProperties(properties.filter((_, i) => i !== index))
    if (activePropertyIndex >= properties.length - 1) {
      setActivePropertyIndex(properties.length - 2)
    }
  }

  const handleNext = () => {
    const newErrors: Record<string, string> = {}

    if (properties.some(p => !p.address?.trim())) {
      newErrors.addresses = 'All properties must have an address'
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    if (onSave) {
      onSave({ properties, totalNetIncome })
    }

    if (onNext) {
      onNext()
    }
  }

  const activeProperty = properties[activePropertyIndex]

  return (
    <div className="real-estate-screen">
      <div className="screen-header">
        <h1>Rental Real Estate Income</h1>
        <p>Enter rental property information and depreciation (Schedule E)</p>
      </div>

      {/* Summary */}
      <div className="tax-summary">
        <div className="summary-card">
          <label>Total Rental Income</label>
          <div className="summary-value">
            ${properties.reduce((sum, p) => sum + (p.rentalIncome || 0), 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div className="summary-card">
          <label>Total Property Expenses</label>
          <div className="summary-value">
            ${properties.reduce((sum, p) => sum + Object.values(p.expenses).reduce((s, v) => s + (v || 0), 0), 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div className="summary-card">
          <label>Total Depreciation</label>
          <div className="summary-value">
            ${properties.reduce((sum, p) => sum + (p.depreciation.annualDeduction || 0), 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div className="summary-card">
          <label>Net Rental Income</label>
          <div className={`summary-value ${totalNetIncome >= 0 ? 'positive' : 'negative'}`}>
            ${totalNetIncome.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
      </div>

      {/* Auto-save */}
      {autoSaveStatus === 'saved' && (
        <div className="auto-save-status">✓ Saved</div>
      )}

      {/* Properties Tabs */}
      <div className="properties-container">
        <div className="properties-tabs">
          {properties.map((prop, index) => (
            <button
              key={prop.id}
              className={`property-tab ${activePropertyIndex === index ? 'active' : ''}`}
              onClick={() => setActivePropertyIndex(index)}
            >
              <span className="tab-label">{prop.address || `Property ${index + 1}`}</span>
              {properties.length > 1 && (
                <button
                  className="tab-close"
                  onClick={(e) => {
                    e.stopPropagation()
                    removeProperty(index)
                  }}
                >
                  ×
                </button>
              )}
            </button>
          ))}
          <button className="property-tab-add" onClick={addProperty} title="Add another property">
            +
          </button>
        </div>

        {/* Property Form */}
        <div className="property-form">
          {errors.general && <div className="error-message">{errors.general}</div>}

          <div className="form-section">
            <h3>Property Information</h3>
            <div className="form-group">
              <label htmlFor={`address-${activePropertyIndex}`}>Property Address *</label>
              <input
                id={`address-${activePropertyIndex}`}
                type="text"
                value={activeProperty.address}
                onChange={(e) => updateProperty(activePropertyIndex, 'address', e.target.value)}
                placeholder="123 Main St, City, State 12345"
              />
            </div>

            <div className="form-group">
              <label htmlFor={`type-${activePropertyIndex}`}>Property Type</label>
              <select
                id={`type-${activePropertyIndex}`}
                value={activeProperty.propertyType}
                onChange={(e) => updateProperty(activePropertyIndex, 'propertyType', e.target.value)}
              >
                <option value="residential">Residential</option>
                <option value="commercial">Commercial</option>
                <option value="land">Land</option>
                <option value="other">Other</option>
              </select>
            </div>
          </div>

          <div className="form-section">
            <h3>Rental Income</h3>
            <div className="form-group">
              <label htmlFor={`rental-income-${activePropertyIndex}`}>Annual Rental Income</label>
              <input
                id={`rental-income-${activePropertyIndex}`}
                type="number"
                value={activeProperty.rentalIncome}
                onChange={(e) => updateProperty(activePropertyIndex, 'rentalIncome', parseFloat(e.target.value) || 0)}
                step="0.01"
              />
            </div>
          </div>

          <div className="form-section">
            <h3>Deductible Expenses</h3>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor={`mortgage-${activePropertyIndex}`}>Mortgage Interest</label>
                <input
                  id={`mortgage-${activePropertyIndex}`}
                  type="number"
                  value={activeProperty.expenses.mortgage}
                  onChange={(e) => updateProperty(activePropertyIndex, 'expenses.mortgage', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
              <div className="form-group">
                <label htmlFor={`property-tax-${activePropertyIndex}`}>Property Tax</label>
                <input
                  id={`property-tax-${activePropertyIndex}`}
                  type="number"
                  value={activeProperty.expenses.propertyTax}
                  onChange={(e) => updateProperty(activePropertyIndex, 'expenses.propertyTax', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor={`insurance-${activePropertyIndex}`}>Insurance</label>
                <input
                  id={`insurance-${activePropertyIndex}`}
                  type="number"
                  value={activeProperty.expenses.insurance}
                  onChange={(e) => updateProperty(activePropertyIndex, 'expenses.insurance', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
              <div className="form-group">
                <label htmlFor={`utilities-${activePropertyIndex}`}>Utilities</label>
                <input
                  id={`utilities-${activePropertyIndex}`}
                  type="number"
                  value={activeProperty.expenses.utilities}
                  onChange={(e) => updateProperty(activePropertyIndex, 'expenses.utilities', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor={`maintenance-${activePropertyIndex}`}>Maintenance & Repairs</label>
                <input
                  id={`maintenance-${activePropertyIndex}`}
                  type="number"
                  value={activeProperty.expenses.maintenance}
                  onChange={(e) => updateProperty(activePropertyIndex, 'expenses.maintenance', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
              <div className="form-group">
                <label htmlFor={`other-expenses-${activePropertyIndex}`}>Other Expenses</label>
                <input
                  id={`other-expenses-${activePropertyIndex}`}
                  type="number"
                  value={activeProperty.expenses.other}
                  onChange={(e) => updateProperty(activePropertyIndex, 'expenses.other', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
            </div>
          </div>

          <div className="form-section">
            <h3>Depreciation Deduction</h3>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor={`base-cost-${activePropertyIndex}`}>Property Acquisition Cost</label>
                <input
                  id={`base-cost-${activePropertyIndex}`}
                  type="number"
                  value={activeProperty.depreciation.baseCost}
                  onChange={(e) => updateProperty(activePropertyIndex, 'depreciation.baseCost', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
              <div className="form-group">
                <label htmlFor={`land-value-${activePropertyIndex}`}>Land Value (non-depreciable)</label>
                <input
                  id={`land-value-${activePropertyIndex}`}
                  type="number"
                  value={activeProperty.depreciation.landValue}
                  onChange={(e) => updateProperty(activePropertyIndex, 'depreciation.landValue', parseFloat(e.target.value) || 0)}
                  step="0.01"
                />
              </div>
            </div>

            <div className="readonly-section">
              <div className="readonly-field">
                <label>Building Cost (Depreciable)</label>
                <div className="readonly-value">${activeProperty.depreciation.buildingCost.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
              </div>
              <div className="readonly-field">
                <label>Annual Depreciation (27.5 years)</label>
                <div className="readonly-value">${activeProperty.depreciation.annualDeduction.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
              </div>
            </div>
          </div>

          <div className="form-section net-income-summary">
            <h3>Net Rental Income (Loss)</h3>
            <div className="income-calculation">
              <div className="calc-row">
                <span>Rental Income:</span>
                <strong>${activeProperty.rentalIncome.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
              </div>
              <div className="calc-row">
                <span>Total Expenses:</span>
                <strong>−${Object.values(activeProperty.expenses).reduce((s, v) => s + (v || 0), 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
              </div>
              <div className="calc-row">
                <span>Depreciation:</span>
                <strong>−${activeProperty.depreciation.annualDeduction.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
              </div>
              <div className="calc-row total">
                <span>Net Income:</span>
                <strong className={activeProperty.netIncome >= 0 ? 'positive' : 'negative'}>
                  ${activeProperty.netIncome.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
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
