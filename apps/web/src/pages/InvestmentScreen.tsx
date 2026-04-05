import { useState, useEffect, useCallback } from 'react'
import '../styles/InvestmentScreen.css'

interface CapitalGain {
  id: string
  description: string
  dateAcquired: string
  dateSold: string
  costBasis: number
  salePrice: number
  gain: number
  holdingPeriod: 'short' | 'long'
  washSaleFlag: boolean
  form8949Line?: string
}

interface Investment {
  id: string
  symbol: string
  investmentType: 'stock' | 'mutual_fund' | 'bond' | 'crypto' | 'other'
  gains: CapitalGain[]
}

interface InvestmentScreenProps {
  onNext?: () => void
  onSave?: (data: { investments: Investment[]; totalGain: number; shortTermGain: number; longTermGain: number }) => void
  initialData?: { investments: Investment[] }
}

const defaultCapitalGain: Omit<CapitalGain, 'id'> = {
  description: '',
  dateAcquired: '',
  dateSold: '',
  costBasis: 0,
  salePrice: 0,
  gain: 0,
  holdingPeriod: 'long',
  washSaleFlag: false,
}

export default function InvestmentScreen({ onNext, onSave, initialData }: InvestmentScreenProps) {
  const [investments, setInvestments] = useState<Investment[]>(initialData?.investments || [])
  const [expandedInvestments, setExpandedInvestments] = useState<Set<string>>(new Set())
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [autoSaveStatus, setAutoSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle')
  const [importStatus, setImportStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle')
  const [importError, setImportError] = useState<string>('')

  // Calculate totals
  const shortTermGain = investments.reduce((sum, inv) =>
    sum + inv.gains.reduce((invSum, g) => invSum + (g.holdingPeriod === 'short' ? g.gain : 0), 0), 0
  )
  const longTermGain = investments.reduce((sum, inv) =>
    sum + inv.gains.reduce((invSum, g) => invSum + (g.holdingPeriod === 'long' ? g.gain : 0), 0), 0
  )
  const totalGain = shortTermGain + longTermGain

  // Auto-save
  useEffect(() => {
    const timer = setTimeout(async () => {
      setAutoSaveStatus('saving')
      const data = { investments, totalGain, shortTermGain, longTermGain }
      localStorage.setItem('investmentScreen', JSON.stringify(data))

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
  }, [investments, totalGain, shortTermGain, longTermGain])

  // Detect wash sales
  const checkWashSale = (investment: Investment, gainIndex: number) => {
    const gain = investment.gains[gainIndex]
    const soldDate = new Date(gain.dateSold)

    // Check if similar security was bought within 30 days before or after
    const washSaleWindow = 30 * 24 * 60 * 60 * 1000 // 30 days in ms

    return investment.gains.some((other, idx) => {
      if (idx === gainIndex) return false
      const otherDate = new Date(other.dateAcquired)
      const timeDiff = Math.abs(otherDate.getTime() - soldDate.getTime())
      return timeDiff <= washSaleWindow
    })
  }

  const calculateGain = (gain: CapitalGain) => {
    const result = gain.salePrice - gain.costBasis
    // Determine holding period
    const acquired = new Date(gain.dateAcquired)
    const sold = new Date(gain.dateSold)
    const diffTime = sold.getTime() - acquired.getTime()
    const diffDays = diffTime / (1000 * 60 * 60 * 24)
    const period = diffDays > 365 ? 'long' : 'short'

    return { result, period: period as 'short' | 'long' }
  }

  const updateGain = (investmentId: string, gainIndex: number, field: keyof CapitalGain, value: any) => {
    const updated = investments.map(inv => {
      if (inv.id !== investmentId) return inv
      const gains = [...inv.gains]
      const gain = { ...gains[gainIndex], [field]: value }

      // Recalculate gain and holding period
      if (['costBasis', 'salePrice', 'dateAcquired', 'dateSold'].includes(field)) {
        const { result, period } = calculateGain(gain)
        gain.gain = result
        gain.holdingPeriod = period
      }

      // Check wash sale
      if (['dateSold', 'dateAcquired'].includes(field)) {
        gain.washSaleFlag = checkWashSale({ ...inv, gains: [...gains.slice(0, gainIndex), gain, ...gains.slice(gainIndex + 1)] }, gainIndex)
      }

      gains[gainIndex] = gain
      return { ...inv, gains }
    })
    setInvestments(updated)
  }

  const addGain = (investmentId: string) => {
    const updated = investments.map(inv => {
      if (inv.id !== investmentId) return inv
      return {
        ...inv,
        gains: [
          ...inv.gains,
          {
            id: Date.now().toString(),
            ...defaultCapitalGain,
          },
        ],
      }
    })
    setInvestments(updated)
  }

  const removeGain = (investmentId: string, gainIndex: number) => {
    const updated = investments.map(inv => {
      if (inv.id !== investmentId) return inv
      return {
        ...inv,
        gains: inv.gains.filter((_, idx) => idx !== gainIndex),
      }
    })
    setInvestments(updated)
  }

  const addInvestment = () => {
    const newInv: Investment = {
      id: Date.now().toString(),
      symbol: '',
      investmentType: 'stock',
      gains: [],
    }
    setInvestments([...investments, newInv])
  }

  const removeInvestment = (id: string) => {
    setInvestments(investments.filter(inv => inv.id !== id))
  }

  const toggleExpanded = (id: string) => {
    const newExpanded = new Set(expandedInvestments)
    if (newExpanded.has(id)) {
      newExpanded.delete(id)
    } else {
      newExpanded.add(id)
    }
    setExpandedInvestments(newExpanded)
  }

  const handle1099BImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setImportStatus('uploading')
    setImportError('')

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('/api/import/1099b', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        throw new Error('Failed to import 1099-B')
      }

      const data = await response.json()
      // Merge imported gains with existing investments
      const imported: Investment[] = data.investments
      setInvestments([...investments, ...imported])
      setImportStatus('success')
      setTimeout(() => setImportStatus('idle'), 2000)
    } catch (error) {
      setImportError(error instanceof Error ? error.message : 'Import failed')
      setImportStatus('error')
    }

    // Reset file input
    e.target.value = ''
  }

  const handleNext = () => {
    const newErrors: Record<string, string> = {}

    if (investments.length === 0) {
      newErrors.general = 'Add at least one investment or gain'
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    if (onSave) {
      onSave({ investments, totalGain, shortTermGain, longTermGain })
    }

    if (onNext) {
      onNext()
    }
  }

  return (
    <div className="investment-screen">
      <div className="screen-header">
        <h1>Investment Income</h1>
        <p>Enter capital gains and losses from investments (Schedule D/8949)</p>
      </div>

      {/* Summary Cards */}
      <div className="tax-summary">
        <div className="summary-card">
          <label>Long-Term Capital Gains</label>
          <div className={`summary-value ${longTermGain >= 0 ? 'positive' : 'negative'}`}>
            ${longTermGain.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div className="summary-card">
          <label>Short-Term Capital Gains</label>
          <div className={`summary-value ${shortTermGain >= 0 ? 'positive' : 'negative'}`}>
            ${shortTermGain.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div className="summary-card">
          <label>Total Capital Gains/Losses</label>
          <div className={`summary-value ${totalGain >= 0 ? 'positive' : 'negative'}`}>
            ${totalGain.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
      </div>

      {/* Auto-save Status */}
      {autoSaveStatus === 'saved' && (
        <div className="auto-save-status">✓ Saved</div>
      )}

      {/* Import 1099-B */}
      <div className="import-section">
        <h3>Import from 1099-B</h3>
        <label htmlFor="file-upload" className="import-label">
          <input
            id="file-upload"
            type="file"
            accept=".csv,.xlsx,.xls,.pdf"
            onChange={handle1099BImport}
            disabled={importStatus === 'uploading'}
          />
          <span className="import-button">
            {importStatus === 'uploading' ? 'Uploading...' : 'Choose file'}
          </span>
        </label>
        {importStatus === 'success' && <span className="import-success">✓ Import successful</span>}
        {importStatus === 'error' && <span className="import-error">✗ {importError}</span>}
      </div>

      {/* Investments List */}
      <div className="investments-container">
        {errors.general && <div className="error-message">{errors.general}</div>}

        <div className="investments-list">
          {investments.map((investment, invIndex) => (
            <div key={investment.id} className="investment-card">
              <div
                className="investment-header"
                onClick={() => toggleExpanded(investment.id)}
              >
                <div className="investment-info">
                  <div className="investment-symbol">{investment.symbol || `Investment ${invIndex + 1}`}</div>
                  <div className="investment-gains-count">{investment.gains.length} gain(s)</div>
                </div>
                <div className="investment-total">
                  ${investment.gains.reduce((sum, g) => sum + g.gain, 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
                <button className={`expand-btn ${expandedInvestments.has(investment.id) ? 'expanded' : ''}`}>
                  ▼
                </button>
              </div>

              {expandedInvestments.has(investment.id) && (
                <div className="investment-details">
                  <div className="investment-config">
                    <div className="form-group">
                      <label>Symbol/Description</label>
                      <input
                        type="text"
                        value={investment.symbol}
                        onChange={(e) => {
                          const updated = investments.map((inv, idx) =>
                            idx === invIndex ? { ...inv, symbol: e.target.value } : inv
                          )
                          setInvestments(updated)
                        }}
                        placeholder="AAPL, Apple Inc., etc."
                      />
                    </div>
                    <div className="form-group">
                      <label>Type</label>
                      <select
                        value={investment.investmentType}
                        onChange={(e) => {
                          const updated = investments.map((inv, idx) =>
                            idx === invIndex ? { ...inv, investmentType: e.target.value as any } : inv
                          )
                          setInvestments(updated)
                        }}
                      >
                        <option value="stock">Stock</option>
                        <option value="mutual_fund">Mutual Fund</option>
                        <option value="bond">Bond</option>
                        <option value="crypto">Cryptocurrency</option>
                        <option value="other">Other</option>
                      </select>
                    </div>
                  </div>

                  {/* Gains Table */}
                  <div className="gains-table-container">
                    <table className="gains-table">
                      <thead>
                        <tr>
                          <th>Description</th>
                          <th>Date Acquired</th>
                          <th>Date Sold</th>
                          <th>Cost Basis</th>
                          <th>Sale Price</th>
                          <th>Gain/Loss</th>
                          <th>Type</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {investment.gains.map((gain, gainIndex) => (
                          <tr key={gain.id} className={gain.washSaleFlag ? 'wash-sale-warning' : ''}>
                            <td>
                              <input
                                type="text"
                                value={gain.description}
                                onChange={(e) => updateGain(investment.id, gainIndex, 'description', e.target.value)}
                                placeholder="Lot description"
                              />
                            </td>
                            <td>
                              <input
                                type="date"
                                value={gain.dateAcquired}
                                onChange={(e) => updateGain(investment.id, gainIndex, 'dateAcquired', e.target.value)}
                              />
                            </td>
                            <td>
                              <input
                                type="date"
                                value={gain.dateSold}
                                onChange={(e) => updateGain(investment.id, gainIndex, 'dateSold', e.target.value)}
                              />
                            </td>
                            <td>
                              <input
                                type="number"
                                value={gain.costBasis}
                                onChange={(e) => updateGain(investment.id, gainIndex, 'costBasis', parseFloat(e.target.value) || 0)}
                                step="0.01"
                                className="amount-input"
                              />
                            </td>
                            <td>
                              <input
                                type="number"
                                value={gain.salePrice}
                                onChange={(e) => updateGain(investment.id, gainIndex, 'salePrice', parseFloat(e.target.value) || 0)}
                                step="0.01"
                                className="amount-input"
                              />
                            </td>
                            <td className={gain.gain >= 0 ? 'positive' : 'negative'}>
                              ${gain.gain.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </td>
                            <td>
                              <span className={`badge ${gain.holdingPeriod}`}>
                                {gain.holdingPeriod === 'long' ? 'Long' : 'Short'}
                              </span>
                            </td>
                            <td>
                              <button
                                className="btn-remove"
                                onClick={() => removeGain(investment.id, gainIndex)}
                                title="Remove this gain"
                              >
                                ✕
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>

                    {investment.gains.some(g => g.washSaleFlag) && (
                      <div className="wash-sale-notice">
                        ⚠ Wash Sale Detected: Some gains involve wash sales within 30 days. Losses may be disallowed.
                      </div>
                    )}
                  </div>

                  <div className="gains-actions">
                    <button className="btn-secondary" onClick={() => addGain(investment.id)}>
                      + Add Lot
                    </button>
                    <button className="btn-danger" onClick={() => removeInvestment(investment.id)}>
                      Remove Investment
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        <button className="btn-secondary btn-add-investment" onClick={addInvestment}>
          + Add Investment
        </button>
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
