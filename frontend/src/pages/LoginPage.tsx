import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try { await login(email, password); navigate('/') }
    catch { setError('Invalid email or password') }
    finally { setLoading(false) }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-10 h-10 rounded-xl bg-indigo-500 flex items-center justify-center mx-auto mb-4">
            <span className="text-white font-bold text-sm">MA</span>
          </div>
          <h1 className="text-white text-2xl font-bold">MA Analytics</h1>
          <p className="text-slate-400 text-sm mt-1">Sign in to your account</p>
        </div>
        <form onSubmit={submit} className="bg-slate-900 rounded-xl border border-white/10 p-6 space-y-4">
          {error && <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 text-red-400 text-sm">{error}</div>}
          <div>
            <label className="block text-slate-400 text-sm mb-1">Email</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} required className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500" />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} required className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500" />
          </div>
          <button type="submit" disabled={loading} className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg py-2 text-sm font-medium transition-colors">
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
          <p className="text-center text-slate-500 text-sm">
            No account? <Link to="/register" className="text-indigo-400 hover:text-indigo-300">Register</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
