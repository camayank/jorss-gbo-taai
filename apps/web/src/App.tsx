import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { FilingWizardProvider } from './context/FilingWizardContext'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'

function ProtectedRoute({ children }: { children: JSX.Element }) {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <AuthProvider>
      <FilingWizardProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<Navigate to="/login" replace />} />
          </Routes>
        </BrowserRouter>
      </FilingWizardProvider>
    </AuthProvider>
  )
}
