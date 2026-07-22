import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AppShell } from '../components/AppShell'
import { useAuth } from '../contexts/AuthContext'
import { authApi } from '../services/api'
import { User, Trash2, AlertTriangle } from 'lucide-react'

export function SettingsPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [confirmText, setConfirmText] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState('')

  const handleDeleteAccount = async () => {
    if (confirmText !== 'DELETE') return
    setDeleting(true)
    setDeleteError('')
    try {
      await authApi.deleteAccount()
      logout()
      navigate('/login', { replace: true })
    } catch {
      setDeleteError('Konto konnte nicht gelöscht werden. Bitte versuche es erneut.')
      setDeleting(false)
    }
  }

  return (
    <AppShell>
      <div className="p-6 max-w-2xl mx-auto">
        <div className="mb-6">
          <h1 className="text-white text-2xl font-bold">Settings</h1>
          <p className="text-slate-400 text-sm mt-1">Konto und Präferenzen verwalten</p>
        </div>

        {/* Profile section */}
        <div className="bg-slate-900 border border-white/10 rounded-xl p-5 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <User size={16} className="text-indigo-400" />
            <h2 className="text-white text-sm font-semibold">Profil</h2>
          </div>
          <div className="space-y-3">
            <div>
              <p className="text-slate-500 text-xs mb-1">Name</p>
              <p className="text-white text-sm">{user?.full_name || '—'}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs mb-1">E-Mail</p>
              <p className="text-white text-sm">{user?.email}</p>
            </div>
          </div>
        </div>

        {/* Danger zone */}
        <div className="bg-slate-900 border border-red-500/20 rounded-xl p-5">
          <div className="flex items-center gap-3 mb-4">
            <AlertTriangle size={16} className="text-red-400" />
            <h2 className="text-red-400 text-sm font-semibold">Danger Zone</h2>
          </div>

          <div className="mb-4">
            <p className="text-slate-300 text-sm font-medium mb-1">Konto dauerhaft löschen</p>
            <p className="text-slate-500 text-xs leading-relaxed">
              Hiermit werden dein Konto und alle zugehörigen Daten unwiderruflich gelöscht —
              Data Sources, Reviews, Analyse-Ergebnisse, Nachrichten und Tickets.
              Diese Aktion kann nicht rückgängig gemacht werden.
            </p>
          </div>

          <div className="space-y-3">
            <div>
              <label className="block text-slate-400 text-xs mb-1.5">
                Zur Bestätigung <span className="text-white font-mono">DELETE</span> eingeben
              </label>
              <input
                value={confirmText}
                onChange={e => setConfirmText(e.target.value)}
                placeholder="DELETE"
                className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-red-500/50 placeholder:text-slate-600"
              />
            </div>

            {deleteError && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 text-red-400 text-sm">
                {deleteError}
              </div>
            )}

            <button
              onClick={handleDeleteAccount}
              disabled={confirmText !== 'DELETE' || deleting}
              className="flex items-center gap-2 bg-red-600 hover:bg-red-500 disabled:opacity-30 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              <Trash2 size={14} />
              {deleting ? 'Wird gelöscht…' : 'Konto endgültig löschen'}
            </button>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
