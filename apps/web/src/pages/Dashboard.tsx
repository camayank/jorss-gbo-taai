import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import FilingWizard from './FilingWizard'

export default function Dashboard() {
  const { user, logout } = useAuth()
  const [showWizard, setShowWizard] = useState(false)

  if (showWizard) {
    return <FilingWizard />
  }

  return (
    <div style={{ padding: 24, maxWidth: '1200px', margin: '0 auto' }}>
      <h1>Tax Filing Dashboard</h1>
      <p>Welcome, {user?.name} ({user?.role})</p>

      <div style={{
        marginTop: 32,
        padding: 24,
        border: '1px solid #e0e0e0',
        borderRadius: 8,
        backgroundColor: '#f9f9f9'
      }}>
        <h2>2025 Tax Return</h2>
        <p>Start filing your taxes with our AI-powered filing wizard</p>
        <button
          onClick={() => setShowWizard(true)}
          style={{
            padding: '12px 24px',
            backgroundColor: '#14B8A6',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            cursor: 'pointer',
            fontSize: 16,
            fontWeight: 600,
            marginBottom: 16
          }}
        >
          Start Filing
        </button>
      </div>

      <button
        onClick={logout}
        style={{
          marginTop: 24,
          padding: '10px 16px',
          backgroundColor: 'transparent',
          color: '#666',
          border: '1px solid #ddd',
          borderRadius: 6,
          cursor: 'pointer',
          fontSize: 14
        }}
      >
        Sign out
      </button>
    </div>
  )
}
