import { useState } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '../services/api'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await authApi.forgotPassword(email)
      setSubmitted(true)
    } catch {
      setError('Something went wrong. Please try again.')
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
          <p className="text-slate-400 text-sm mt-1">Passwort zurücksetzen</p>
        </div>

        <div className="bg-slate-900 rounded-xl border border-white/10 p-6">
          {submitted ? (
            <div className="text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-green-500/10 border border-green-500/20 flex items-center justify-center mx-auto">
                <svg className="w-6 h-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div>
                <p className="text-white font-medium">E-Mail gesendet</p>
                <p className="text-slate-400 text-sm mt-1">
                  Falls ein Konto mit dieser E-Mail existiert, erhältst du in Kürze einen Reset-Link.
                </p>
              </div>
              <Link to="/login" className="block text-indigo-400 hover:text-indigo-300 text-sm">
                Zurück zum Login
              </Link>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <p className="text-slate-400 text-sm">
                Gib deine E-Mail-Adresse ein und wir schicken dir einen Link zum Zurücksetzen deines Passworts.
              </p>
              {error && (
                <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 text-red-400 text-sm">
                  {error}
                </div>
              )}
              <div>
                <label className="block text-slate-400 text-sm mb-1">E-Mail</label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  placeholder="deine@email.de"
                  className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg py-2 text-sm font-medium transition-colors"
              >
                {loading ? 'Sende...' : 'Reset-Link senden'}
              </button>
              <p className="text-center text-slate-500 text-sm">
                <Link to="/login" className="text-indigo-400 hover:text-indigo-300">
                  Zurück zum Login
                </Link>
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
