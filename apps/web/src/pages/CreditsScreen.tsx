import { useState, useEffect } from 'react'
import { useFilingWizard, CreditsData } from '../context/FilingWizardContext'
import '../styles/FilingWizard.css'

interface Dependent {
  name: string
  relationship: string
  ssn: string
  age: number
}

export default function CreditsScreen() {
  const { state, updateCredits, nextStep } = useFilingWizard()
  const [childTaxCredit, setChildTaxCredit] = useState(
    state.credits?.childTaxCredit || 0
  )
  const [earnedIncomeCreditEligible, setEarnedIncomeCreditEligible] = useState(
    state.credits?.earnedIncomeCreditEligible || false
  )
  const [childAndDependentCareCredit, setChildAndDependentCareCredit] = useState(
    state.credits?.childAndDependentCareCredit || 0
  )
  const [studentEducationCredit, setStudentEducationCredit] = useState(
    state.credits?.studentEducationCredit || 0
  )
  const [electricVehicleCredit, setElectricVehicleCredit] = useState(
    state.credits?.electricVehicleCredit || 0
  )
  const [dependents, setDependents] = useState<Dependent[]>(
    state.credits?.dependents || [{ name: '', relationship: '', ssn: '', age: 0 }]
  )
  const [errors, setErrors] = useState<Record<string, string>>({})

  const totalCredits =
    childTaxCredit +
    childAndDependentCareCredit +
    studentEducationCredit +
    electricVehicleCredit

  useEffect(() => {
    // Auto-save
    const timeout = setTimeout(() => {
      const data: CreditsData = {
        childTaxCredit,
        earnedIncomeCreditEligible,
        childAndDependentCareCredit,
        studentEducationCredit,
        electricVehicleCredit,
        dependents,
      }
      updateCredits(data)
    }, 500)

    return () => clearTimeout(timeout)
  }, [
    childTaxCredit,
    earnedIncomeCreditEligible,
    childAndDependentCareCredit,
    studentEducationCredit,
    electricVehicleCredit,
    dependents,
    updateCredits,
  ])

  const updateDependent = (index: number, field: keyof Dependent, value: any) => {
    const updated = [...dependents]
    updated[index] = { ...updated[index], [field]: value }
    setDependents(updated)
  }

  const addDependent = () => {
    setDependents([...dependents, { name: '', relationship: '', ssn: '', age: 0 }])
  }

  const removeDependent = (index: number) => {
    setDependents(dependents.filter((_, i) => i !== index))
  }

  const handleNext = () => {
    const newErrors: Record<string, string> = {}

    // Validate dependents with child tax credit
    if (childTaxCredit > 0 && dependents.some(d => !d.name.trim() || !d.ssn.trim())) {
      newErrors.dependents = 'All dependents claiming child tax credit must have name and SSN'
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    const data: CreditsData = {
      childTaxCredit,
      earnedIncomeCreditEligible,
      childAndDependentCareCredit,
      studentEducationCredit,
      electricVehicleCredit,
      dependents,
    }
    updateCredits(data)
    nextStep()
  }

  return (
    <div className="wizard-screen">
      <div className="screen-header">
        <h1>Tax Credits & Dependents</h1>
        <p>Claim credits to reduce your tax liability dollar-for-dollar</p>
      </div>

      {/* Credits Overview */}
      <div className="wizard-section">
        <h2>Available Tax Credits</h2>
        <p className="section-hint">Tax credits directly reduce the amount of tax you owe</p>

        {/* Child Tax Credit */}
        <div className="credit-card">
          <div className="credit-header">
            <h3>Child Tax Credit</h3>
            <span className="credit-amount">$2,000 per child under 17</span>
          </div>
          <div className="form-group">
            <label htmlFor="ctc">Number of Qualifying Children</label>
            <input
              id="ctc"
              type="number"
              min="0"
              value={childTaxCredit / 2000}
              onChange={(e) => setChildTaxCredit((parseInt(e.target.value) || 0) * 2000)}
            />
            <small>Partial credit available for modified AGI above limits</small>
          </div>
        </div>

        {/* Earned Income Credit */}
        <div className="credit-card">
          <div className="credit-header">
            <h3>Earned Income Tax Credit (EITC)</h3>
            <span className="credit-amount">Up to $3,995</span>
          </div>
          <div className="form-group">
            <label htmlFor="eitc">
              <input
                id="eitc"
                type="checkbox"
                checked={earnedIncomeCreditEligible}
                onChange={(e) => setEarnedIncomeCreditEligible(e.target.checked)}
              />
              <span>Eligible for EITC (low to moderate income)</span>
            </label>
            <small>Income limits apply based on filing status and dependents</small>
          </div>
        </div>

        {/* Child & Dependent Care */}
        <div className="credit-card">
          <div className="credit-header">
            <h3>Child & Dependent Care Credit</h3>
            <span className="credit-amount">20-35% of expenses</span>
          </div>
          <div className="form-group">
            <label htmlFor="childcare">Qualifying Childcare Expenses</label>
            <div className="input-wrapper">
              <span className="currency-symbol">$</span>
              <input
                id="childcare"
                type="number"
                value={childAndDependentCareCredit}
                onChange={(e) => setChildAndDependentCareCredit(parseFloat(e.target.value) || 0)}
                placeholder="0.00"
                min="0"
                step="0.01"
              />
            </div>
            <small>Daycare, preschool, or after-school care expenses (max $3,000)</small>
          </div>
        </div>

        {/* Education Credits */}
        <div className="credit-card">
          <div className="credit-header">
            <h3>Education Credits</h3>
            <span className="credit-amount">American Opportunity, Lifetime Learning</span>
          </div>
          <div className="form-group">
            <label htmlFor="education">Qualified Education Expenses</label>
            <div className="input-wrapper">
              <span className="currency-symbol">$</span>
              <input
                id="education"
                type="number"
                value={studentEducationCredit}
                onChange={(e) => setStudentEducationCredit(parseFloat(e.target.value) || 0)}
                placeholder="0.00"
                min="0"
                step="0.01"
              />
            </div>
            <small>Tuition, fees, books for self, spouse, or dependents</small>
          </div>
        </div>

        {/* EV Credit */}
        <div className="credit-card">
          <div className="credit-header">
            <h3>Electric Vehicle Credit</h3>
            <span className="credit-amount">Up to $7,500</span>
          </div>
          <div className="form-group">
            <label htmlFor="ev">EV Purchase Credit Amount</label>
            <div className="input-wrapper">
              <span className="currency-symbol">$</span>
              <input
                id="ev"
                type="number"
                value={electricVehicleCredit}
                onChange={(e) => setElectricVehicleCredit(parseFloat(e.target.value) || 0)}
                placeholder="0.00"
                min="0"
                step="0.01"
                max="7500"
              />
            </div>
            <small>New vehicle purchase credit (income limits apply)</small>
          </div>
        </div>
      </div>

      {/* Dependents Section */}
      {childTaxCredit > 0 && (
        <div className="wizard-section">
          <h2>Dependents for Child Tax Credit</h2>
          {errors.dependents && (
            <div className="error-message">{errors.dependents}</div>
          )}

          {dependents.map((dependent, index) => (
            <div key={index} className="dependent-form">
              <div className="form-row">
                <div className="form-group">
                  <label>Name</label>
                  <input
                    type="text"
                    value={dependent.name}
                    onChange={(e) => updateDependent(index, 'name', e.target.value)}
                    placeholder="Full name"
                  />
                </div>
                <div className="form-group">
                  <label>Relationship</label>
                  <select
                    value={dependent.relationship}
                    onChange={(e) => updateDependent(index, 'relationship', e.target.value)}
                  >
                    <option value="">Select</option>
                    <option value="son">Son</option>
                    <option value="daughter">Daughter</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>SSN</label>
                  <input
                    type="text"
                    value={dependent.ssn}
                    onChange={(e) => updateDependent(index, 'ssn', e.target.value)}
                    placeholder="XXX-XX-XXXX"
                  />
                </div>
                <div className="form-group">
                  <label>Age</label>
                  <input
                    type="number"
                    value={dependent.age}
                    onChange={(e) => updateDependent(index, 'age', parseInt(e.target.value) || 0)}
                    min="0"
                    max="120"
                  />
                </div>
              </div>

              {dependents.length > 1 && (
                <button
                  className="btn-text-small"
                  onClick={() => removeDependent(index)}
                >
                  Remove Dependent
                </button>
              )}
            </div>
          ))}

          <button className="btn-secondary-small" onClick={addDependent}>
            + Add Another Dependent
          </button>
        </div>
      )}

      {/* Credits Summary */}
      {totalCredits > 0 && (
        <div className="credits-summary">
          <div className="summary-row">
            <span>Total Tax Credits</span>
            <strong>${totalCredits.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
          </div>
          <p className="summary-note">Credits reduce your tax liability dollar-for-dollar</p>
        </div>
      )}

      {/* Navigation */}
      <div className="screen-footer">
        <button className="btn-secondary">Back</button>
        <button className="btn-primary" onClick={handleNext}>
          Continue to Filing Status
        </button>
      </div>
    </div>
  )
}
