import { createContext, useContext, useState, useCallback, ReactNode } from 'react'

// Deductions data
export interface ScheduleADeductions {
  mortgageInterest: number
  propertyTaxes: number
  charitableDonations: number
  studentLoanInterest: number
  otherDeductions: number
}

export interface DeductionsData {
  deductionType: 'standard' | 'itemized'
  itemizedDeductions?: ScheduleADeductions
  delta?: number
}

// Credits data
export interface CreditsData {
  childTaxCredit: number
  earnedIncomeCreditEligible: boolean
  childAndDependentCareCredit: number
  studentEducationCredit: number
  electricVehicleCredit: number
  dependents: Array<{
    name: string
    relationship: string
    ssn: string
    age: number
  }>
}

// Filing status data
export interface FilingStatusData {
  status: 'single' | 'married_joint' | 'married_separate' | 'head_of_household'
  jointFilerName?: string
  jointFilerSSN?: string
  mfsComparison?: {
    mjAmount: number
    mfsAmount: number
    savings: number
  }
}

// Review data (summary of everything)
export interface ReviewData {
  totalIncome: number
  totalDeductions: number
  adjustedGrossIncome: number
  totalCredits: number
  totalTaxLiability: number
  estimatedRefund: number
}

// Submit data
export interface SubmitData {
  eFileConsent: boolean
  ipPin?: string
  refundMethod: 'direct_deposit' | 'check'
  bankAccount?: {
    routingNumber: string
    accountNumber: string
    accountType: 'checking' | 'savings'
  }
  submittedAt?: string
  confirmationNumber?: string
}

// Complete wizard state
export interface FilingWizardState {
  currentStep: number
  totalSteps: number
  deductions?: DeductionsData
  credits?: CreditsData
  filingStatus?: FilingStatusData
  review?: ReviewData
  submit?: SubmitData
}

interface FilingWizardContextType {
  state: FilingWizardState
  nextStep: () => void
  previousStep: () => void
  goToStep: (step: number) => void
  updateDeductions: (data: DeductionsData) => void
  updateCredits: (data: CreditsData) => void
  updateFilingStatus: (data: FilingStatusData) => void
  updateReview: (data: ReviewData) => void
  updateSubmit: (data: SubmitData) => void
  reset: () => void
}

const FilingWizardContext = createContext<FilingWizardContextType | undefined>(undefined)

const STEPS = [
  { label: 'Deductions', path: 'deductions' },
  { label: 'Credits', path: 'credits' },
  { label: 'Filing Status', path: 'filing-status' },
  { label: 'Review', path: 'review' },
  { label: 'Submit', path: 'submit' },
  { label: 'Complete', path: 'complete' },
]

export function FilingWizardProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<FilingWizardState>({
    currentStep: 0,
    totalSteps: STEPS.length,
  })

  const nextStep = useCallback(() => {
    setState((prev) => ({
      ...prev,
      currentStep: Math.min(prev.currentStep + 1, prev.totalSteps - 1),
    }))
  }, [])

  const previousStep = useCallback(() => {
    setState((prev) => ({
      ...prev,
      currentStep: Math.max(prev.currentStep - 1, 0),
    }))
  }, [])

  const goToStep = useCallback((step: number) => {
    setState((prev) => ({
      ...prev,
      currentStep: Math.max(0, Math.min(step, prev.totalSteps - 1)),
    }))
  }, [])

  const updateDeductions = useCallback((data: DeductionsData) => {
    setState((prev) => ({ ...prev, deductions: data }))
    // Save to localStorage
    localStorage.setItem('filingWizard_deductions', JSON.stringify(data))
  }, [])

  const updateCredits = useCallback((data: CreditsData) => {
    setState((prev) => ({ ...prev, credits: data }))
    localStorage.setItem('filingWizard_credits', JSON.stringify(data))
  }, [])

  const updateFilingStatus = useCallback((data: FilingStatusData) => {
    setState((prev) => ({ ...prev, filingStatus: data }))
    localStorage.setItem('filingWizard_filingStatus', JSON.stringify(data))
  }, [])

  const updateReview = useCallback((data: ReviewData) => {
    setState((prev) => ({ ...prev, review: data }))
    localStorage.setItem('filingWizard_review', JSON.stringify(data))
  }, [])

  const updateSubmit = useCallback((data: SubmitData) => {
    setState((prev) => ({ ...prev, submit: data }))
    localStorage.setItem('filingWizard_submit', JSON.stringify(data))
  }, [])

  const reset = useCallback(() => {
    setState({
      currentStep: 0,
      totalSteps: STEPS.length,
    })
    localStorage.removeItem('filingWizard_deductions')
    localStorage.removeItem('filingWizard_credits')
    localStorage.removeItem('filingWizard_filingStatus')
    localStorage.removeItem('filingWizard_review')
    localStorage.removeItem('filingWizard_submit')
  }, [])

  return (
    <FilingWizardContext.Provider
      value={{
        state,
        nextStep,
        previousStep,
        goToStep,
        updateDeductions,
        updateCredits,
        updateFilingStatus,
        updateReview,
        updateSubmit,
        reset,
      }}
    >
      {children}
    </FilingWizardContext.Provider>
  )
}

export function useFilingWizard() {
  const context = useContext(FilingWizardContext)
  if (!context) {
    throw new Error('useFilingWizard must be used within FilingWizardProvider')
  }
  return context
}

export const WIZARD_STEPS = STEPS
