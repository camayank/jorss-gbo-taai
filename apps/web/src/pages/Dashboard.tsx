import { useAuth } from '../context/AuthContext'

export default function Dashboard() {
  const { user, logout } = useAuth()
  return (
    <div style={{ padding: 24 }}>
      <h1>Dashboard</h1>
      <p>Welcome, {user?.name} ({user?.role})</p>
      <button onClick={logout}>Sign out</button>
    </div>
  )
}
