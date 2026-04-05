import { useFilingWizard, WIZARD_STEPS } from '../context/FilingWizardContext'
import DeductionsScreen from './DeductionsScreen'
import CreditsScreen from './CreditsScreen'
import FilingStatusScreen from './FilingStatusScreen'
import ReviewScreen from './ReviewScreen'
import SubmitScreen from './SubmitScreen'
import '../styles/FilingWizard.css'

const SCREENS = [DeductionsScreen, CreditsScreen, FilingStatusScreen, ReviewScreen, SubmitScreen]

export default function FilingWizard() {
  const { state } = useFilingWizard()
  const currentStep = state.currentStep
  const CurrentScreen = SCREENS[currentStep]

  return (
    <div className="filing-wizard-container">
      {/* Progress Bar */}
      <div className="wizard-progress-section">
        <div className="wizard-progress-bar">
          <div
            className="wizard-progress-fill"
            style={{
              width: `${((currentStep + 1) / state.totalSteps) * 100}%`,
            }}
          ></div>
        </div>
        <div className="wizard-progress-text">
          <span className="step-indicator">
            Step {currentStep + 1} of {state.totalSteps}
          </span>
          <span className="step-label">{WIZARD_STEPS[currentStep]?.label}</span>
        </div>
      </div>

      {/* Breadcrumbs */}
      <nav className="wizard-breadcrumbs">
        <ol>
          {WIZARD_STEPS.map((step, index) => (
            <li key={index} className={`breadcrumb-item ${index === currentStep ? 'active' : ''} ${index < currentStep ? 'completed' : ''}`}>
              <span className="breadcrumb-number">{index + 1}</span>
              <span className="breadcrumb-label">{step.label}</span>
              {index < currentStep && <span className="breadcrumb-checkmark">✓</span>}
            </li>
          ))}
        </ol>
      </nav>

      {/* Current Screen */}
      <div className="wizard-screen-container">
        {CurrentScreen && <CurrentScreen />}
      </div>
    </div>
  )
}
