import { useState, useEffect, useRef } from 'react'
import { AppShell } from '../components/AppShell'
import { datasourceApi } from '../services/api'
import { Plus, Trash2, RefreshCw, CheckCircle, XCircle, Clock, Upload, Search } from 'lucide-react'

interface DataSource {
  id: string
  name: string
  type: string
  app_id: string | null
  job_id: string | null
  job_status: string | null
  job_error: string | null
  review_count: number
  last_synced: string | null
}

function StatusBadge({ status }: { status: string | null }) {
  if (!status) return null
  const map: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
    done:    { label: 'Done',    color: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20', icon: <CheckCircle size={12} /> },
    failed:  { label: 'Failed',  color: 'text-red-400 bg-red-400/10 border-red-400/20',           icon: <XCircle size={12} /> },
    running: { label: 'Running', color: 'text-blue-400 bg-blue-400/10 border-blue-400/20',        icon: <RefreshCw size={12} className="animate-spin" /> },
    pending: { label: 'Pending', color: 'text-amber-400 bg-amber-400/10 border-amber-400/20',     icon: <Clock size={12} /> },
    queued:  { label: 'Queued',  color: 'text-amber-400 bg-amber-400/10 border-amber-400/20',     icon: <Clock size={12} /> },
  }
  const s = map[status] ?? { label: status, color: 'text-slate-400 bg-slate-400/10 border-slate-400/20', icon: null }
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-medium ${s.color}`}>
      {s.icon}{s.label}
    </span>
  )
}

export function DataSourcesPage() {
  const [sources, setSources] = useState<DataSource[]>([])
  const [tab, setTab] = useState<'gplay' | 'csv'>('gplay')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // Google Play form
  const [gpName, setGpName] = useState('')
  const [gpAppId, setGpAppId] = useState('')
  const [gpCount, setGpCount] = useState(200)
  const [gpLang, setGpLang] = useState('de')
  const [gpCountry, setGpCountry] = useState('de')

  // CSV form
  const [csvName, setCsvName] = useState('')
  const [csvFile, setCsvFile] = useState<File | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = async () => {
    try { setSources(await datasourceApi.list()) } catch {}
  }

  useEffect(() => {
    load()
    pollingRef.current = setInterval(async () => {
      const list: DataSource[] = await datasourceApi.list().catch(() => [])
      setSources(list)
    }, 4000)
    return () => { if (pollingRef.current) clearInterval(pollingRef.current) }
  }, [])

  const parseAppId = (raw: string) => {
    try {
      const url = new URL(raw)
      return url.searchParams.get('id') || raw
    } catch { return raw.trim() }
  }

  const submitGPlay = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(''); setSuccess(''); setLoading(true)
    try {
      await datasourceApi.createGPlay({
        name: gpName, app_id: parseAppId(gpAppId),
        count: gpCount, lang: gpLang, country: gpCountry,
      })
      setSuccess('DataSource created — pipeline is running in background.')
      setGpName(''); setGpAppId('')
      await load()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create data source')
    } finally { setLoading(false) }
  }

  const submitCsv = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!csvFile) { setError('Please select a CSV file'); return }
    setError(''); setSuccess(''); setLoading(true)
    const fd = new FormData()
    fd.append('name', csvName)
    fd.append('file', csvFile)
    fd.append('text_col', 'content')
    fd.append('score_col', 'score')
    fd.append('date_col', 'at')
    fd.append('version_col', 'reviewCreatedVersion')
    try {
      await datasourceApi.uploadCsv(fd)
      setSuccess('CSV uploaded — pipeline is running in background.')
      setCsvName(''); setCsvFile(null)
      if (fileRef.current) fileRef.current.value = ''
      await load()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to upload CSV')
    } finally { setLoading(false) }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this data source and all its data?')) return
    try { await datasourceApi.delete(id); await load() } catch {}
  }

  const handleRetry = async (id: string) => {
    setError('')
    try {
      await datasourceApi.retry(id)
      await load()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Retry failed. Please try again.')
    }
  }

  return (
    <AppShell>
      <div className="p-6 max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-white text-2xl font-bold">Data Sources</h1>
          <p className="text-slate-400 text-sm mt-1">Connect your app reviews via Google Play or CSV upload</p>
        </div>

        {/* Existing sources */}
        {sources.length > 0 && (
          <div className="mb-8">
            <h2 className="text-slate-300 text-sm font-semibold uppercase tracking-wider mb-3">Connected Sources</h2>
            <div className="space-y-2">
              {sources.map(ds => (
                <div key={ds.id} className={`bg-slate-900 border rounded-xl px-4 py-3 ${ds.job_status === 'failed' ? 'border-red-500/30' : 'border-white/10'}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center shrink-0">
                        <Search size={14} className="text-indigo-400" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-white text-sm font-medium truncate">{ds.name}</p>
                        <p className="text-slate-500 text-xs">{ds.app_id || 'CSV'} · {ds.review_count} reviews</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <StatusBadge status={ds.job_status} />
                      {ds.last_synced && (
                        <span className="text-slate-500 text-xs hidden sm:block">
                          {new Date(ds.last_synced).toLocaleDateString()}
                        </span>
                      )}
                      {ds.job_status === 'failed' && (
                        <button
                          onClick={() => handleRetry(ds.id)}
                          className="flex items-center gap-1 text-xs text-amber-400 hover:text-amber-300 bg-amber-400/10 hover:bg-amber-400/20 border border-amber-400/20 px-2 py-1 rounded-lg transition-colors"
                        >
                          <RefreshCw size={11} />
                          Retry
                        </button>
                      )}
                      <button onClick={() => handleDelete(ds.id)} className="text-slate-600 hover:text-red-400 transition-colors">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                  {ds.job_status === 'failed' && ds.job_error && (
                    <div className="mt-2 ml-11 text-red-400 text-xs bg-red-500/5 border border-red-500/10 rounded-lg px-3 py-1.5">
                      {ds.job_error}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Add new source */}
        <div className="bg-slate-900 border border-white/10 rounded-xl overflow-hidden">
          <div className="flex border-b border-white/10">
            {(['gplay', 'csv'] as const).map(t => (
              <button key={t} onClick={() => setTab(t)}
                className={`flex-1 py-3 text-sm font-medium transition-colors ${tab === t ? 'text-white border-b-2 border-indigo-500 bg-white/5' : 'text-slate-400 hover:text-white'}`}>
                {t === 'gplay' ? '🎮 Google Play' : '📄 CSV Upload'}
              </button>
            ))}
          </div>

          <div className="p-6">
            {error && <div className="mb-4 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 text-red-400 text-sm">{error}</div>}
            {success && <div className="mb-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2 text-emerald-400 text-sm">{success}</div>}

            {tab === 'gplay' ? (
              <form onSubmit={submitGPlay} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-slate-400 text-xs mb-1">Source Name</label>
                    <input value={gpName} onChange={e => setGpName(e.target.value)} required placeholder="BMW Connected"
                      className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500" />
                  </div>
                  <div>
                    <label className="block text-slate-400 text-xs mb-1">App ID or Play Store URL</label>
                    <input value={gpAppId} onChange={e => setGpAppId(e.target.value)} required placeholder="de.bmw.connected"
                      className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500" />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-slate-400 text-xs mb-1">Review Count</label>
                    <select value={gpCount} onChange={e => setGpCount(Number(e.target.value))}
                      className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500">
                      {[50, 100, 200, 500].map(n => <option key={n} value={n}>{n}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-slate-400 text-xs mb-1">Language</label>
                    <select value={gpLang} onChange={e => setGpLang(e.target.value)}
                      className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500">
                      <option value="de">Deutsch</option>
                      <option value="en">English</option>
                      <option value="fr">Français</option>
                      <option value="es">Español</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-slate-400 text-xs mb-1">Country</label>
                    <select value={gpCountry} onChange={e => setGpCountry(e.target.value)}
                      className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500">
                      <option value="de">Germany</option>
                      <option value="us">United States</option>
                      <option value="gb">United Kingdom</option>
                      <option value="at">Austria</option>
                      <option value="ch">Switzerland</option>
                    </select>
                  </div>
                </div>
                <button type="submit" disabled={loading}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                  {loading ? <RefreshCw size={14} className="animate-spin" /> : <Plus size={14} />}
                  {loading ? 'Starting pipeline...' : 'Connect & Analyze'}
                </button>
              </form>
            ) : (
              <form onSubmit={submitCsv} className="space-y-4">
                <div>
                  <label className="block text-slate-400 text-xs mb-1">Source Name</label>
                  <input value={csvName} onChange={e => setCsvName(e.target.value)} required placeholder="My Review Export"
                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500" />
                </div>
                <div>
                  <label className="block text-slate-400 text-xs mb-1">CSV File</label>
                  <div
                    onClick={() => fileRef.current?.click()}
                    className="border-2 border-dashed border-white/10 hover:border-indigo-500/50 rounded-xl p-8 text-center cursor-pointer transition-colors">
                    <Upload size={24} className="mx-auto text-slate-500 mb-2" />
                    {csvFile ? (
                      <p className="text-white text-sm">{csvFile.name}</p>
                    ) : (
                      <>
                        <p className="text-slate-300 text-sm">Click to upload CSV</p>
                        <p className="text-slate-500 text-xs mt-1">Expected columns: content, score, at, reviewCreatedVersion</p>
                      </>
                    )}
                    <input ref={fileRef} type="file" accept=".csv" className="hidden"
                      onChange={e => setCsvFile(e.target.files?.[0] || null)} />
                  </div>
                </div>
                <button type="submit" disabled={loading || !csvFile}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                  {loading ? <RefreshCw size={14} className="animate-spin" /> : <Upload size={14} />}
                  {loading ? 'Uploading...' : 'Upload & Analyze'}
                </button>
              </form>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  )
}
