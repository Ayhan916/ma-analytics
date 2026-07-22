import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token, loading } = useAuth()
  if (loading) return <div className="flex h-screen items-center justify-center text-slate-400">Loading...</div>
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}
