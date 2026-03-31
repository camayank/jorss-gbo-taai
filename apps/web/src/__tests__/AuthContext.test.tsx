import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AuthProvider, useAuth } from '../context/AuthContext'

function TestConsumer() {
  const { isAuthenticated, user, logout } = useAuth()
  return (
    <div>
      <span data-testid="auth">{isAuthenticated ? 'yes' : 'no'}</span>
      {user && <span data-testid="name">{user.name}</span>}
      <button onClick={logout}>logout</button>
    </div>
  )
}

describe('AuthContext', () => {
  beforeEach(() => localStorage.clear())

  it('starts unauthenticated when localStorage is empty', () => {
    render(<AuthProvider><TestConsumer /></AuthProvider>)
    expect(screen.getByTestId('auth')).toHaveTextContent('no')
  })

  it('restores session from localStorage', () => {
    const user = { id: '1', email: 'a@b.com', name: 'Alice', role: 'taxpayer' as const }
    localStorage.setItem('token', 'tok')
    localStorage.setItem('user', JSON.stringify(user))
    render(<AuthProvider><TestConsumer /></AuthProvider>)
    expect(screen.getByTestId('auth')).toHaveTextContent('yes')
    expect(screen.getByTestId('name')).toHaveTextContent('Alice')
  })

  it('clears auth state on logout', async () => {
    const user = { id: '1', email: 'a@b.com', name: 'Alice', role: 'taxpayer' as const }
    localStorage.setItem('token', 'tok')
    localStorage.setItem('user', JSON.stringify(user))
    render(<AuthProvider><TestConsumer /></AuthProvider>)
    await act(async () => { await userEvent.click(screen.getByText('logout')) })
    expect(screen.getByTestId('auth')).toHaveTextContent('no')
    expect(localStorage.getItem('token')).toBeNull()
  })
})
