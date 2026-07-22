import { useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { authApi } from '../services/api'

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token') ?? ''

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950">
        <div className="w-full max-w-sm bg-slate-900 rounded-xl border border-white/10 p-6 text-center space-y-3">
          <p className="text-red-400 font-medium">Ungültiger Reset-Link</p>
          <p className="text-slate-400 text-sm">Bitte fordere einen neuen Reset-Link an.</p>
          <Link to="/forgot-password" className="text-indigo-400 hover:text-indigo-300 text-sm">
            Neuen Link anfordern
          </Link>
        </div>
      </div>
    )
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (password.length < 8) {
      setError('Das Passwort muss mindestens 8 Zeichen lang sein.')
      return
    }
    if (password !== confirm) {
      setError('Die Passwörter stimmen nicht überein.')
      return
    }

    setLoading(true)
    try {
      await authApi.resetPassword(token, password)
      navigate('/login?reset=success')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Der Link ist ungültig oder abgelaufen. Bitte fordere einen neuen an.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-10 h-10 rounded-xl bg-indigo-500 flex items-center justify-center mx-auto mb-4">
            <span className="text-white font-bold text-sm">MA</span>
          </div>
          <h1 className="text-white text-2xl font-bold">MA Analytics</h1>
          <p className="text-slate-400 text-sm mt-1">Neues Passwort setzen</p>
        </div>

        <form onSubmit={submit} className="bg-slate-900 rounded-xl border border-white/10 p-6 space-y-4">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 text-red-400 text-sm">
              {error}
            </div>
          )}
          <div>
            <label className="block text-slate-400 text-sm mb-1">Neues Passwort</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              placeholder="Mindestens 8 Zeichen"
              className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">Passwort bestätigen</label>
            <input
              type="password"
              value={confirm}
              onChange={e => setConfirm(e.target.value)}
              required
              placeholder="Passwort wiederholen"
              className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg py-2 text-sm font-medium transition-colors"
          >
            {loading ? 'Speichern...' : 'Passwort ändern'}
          </button>
        </form>
      </div>
    </div>
  )
}
