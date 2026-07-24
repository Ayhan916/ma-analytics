import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { AppShell } from '../components/AppShell'
import { datasourceApi } from '../services/api'
import { Plus, Trash2, RefreshCw, CheckCircle, XCircle, Clock, Upload, Search, ChevronRight, Smartphone } from 'lucide-react'

interface DataSource {
  id: string
  name: string
  type: string
  app_id: string | null
  job_id: string | null
  job_status: string | null
  job_progress: string | null
  job_error: string | null
  job_started_at: string | null
  review_count: number
  sentence_count: number
  signal_count: number
  last_synced: string | null
  review_date_from: string | null
  review_date_to: string | null
}

const PIPELINE_STEPS = [
  { id: 'scraping',    label: 'Reviews',    keys: ['queued', 'scraping'] },
  { id: 'ml',         label: 'Sentiment',  keys: ['sentiment', 'embeddings', 'embedding'] },
  { id: 'clustering', label: 'Clustering', keys: ['clustering'] },
  { id: 'absa',       label: 'ABSA',       keys: ['intelligence_absa_', 'intelligence_signals_'] },
  { id: 'narratives', label: 'Narratives', keys: ['intelligence_synthesizing', 'intelligence_cleanup'] },
  { id: 'done',       label: 'Fertig',     keys: ['done'] },
]

function getStepIndex(progress: string | null): number {
  if (!progress) return 0
  for (let i = 0; i < PIPELINE_STEPS.length; i++) {
    if (PIPELINE_STEPS[i].keys.some(k => progress.startsWith(k))) return i
  }
  return 0
}

function extractPct(progress: string | null): number | null {
  if (!progress) return null
  const m = progress.match(/intelligence_(?:absa|signals)_(\d+)pct/)
  return m ? parseInt(m[1]) : null
}

function useElapsed(startedAt: string | null): string {
  const [, setTick] = useState(0)
  useEffect(() => {
    if (!startedAt) return
    const id = setInterval(() => setTick(t => t + 1), 1000)
    return () => clearInterval(id)
  }, [startedAt])
  if (!startedAt) return ''
  const sec = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000)
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

function PipelineStatusBar({ progress, status, startedAt, reviews }: {
  progress: string | null
  status: string | null
  startedAt: string | null
  reviews: number
}) {
  const elapsed = useElapsed(status === 'running' ? startedAt : null)
  if (!status || status === 'done' || status === 'failed') return null

  const currentIdx = getStepIndex(progress)
  const pct = extractPct(progress)

  const STEP_LABELS: Record<string, string> = {
    queued: 'Warten…',
    scraping: 'Reviews laden…',
    sentiment: 'Sentiment…',
    embeddings: 'Embeddings…',
    clustering: 'Clustering…',
    intelligence_absa_: 'ABSA läuft…',
    intelligence_signals_: 'Signale schreiben…',
    intelligence_synthesizing_narratives: 'Narratives…',
    intelligence_cleanup_old_data: 'Aufräumen…',
  }
  const currentLabel = progress
    ? Object.entries(STEP_LABELS).find(([k]) => progress.startsWith(k))?.[1] ?? progress
    : 'Vorbereitung…'

  return (
    <div className="mt-3 space-y-2">
      {/* Step pills */}
      <div className="flex items-center gap-1">
        {PIPELINE_STEPS.map((step, i) => {
          const done   = i < currentIdx
          const active = i === currentIdx
          return (
            <div key={step.id} className="flex items-center gap-1 flex-1 min-w-0">
              <div className={`h-1 rounded-full w-full transition-all duration-500 ${
                done   ? 'bg-emerald-500' :
                active ? 'bg-blue-400' :
                         'bg-slate-700'
              }`} />
            </div>
          )
        })}
      </div>

      {/* Percentage bar (shown when pct is available) */}
      {pct !== null && (
        <div className="space-y-1">
          <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-700"
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-blue-400 font-medium">{pct}%</span>
            <span className="text-[10px] text-slate-500">{currentLabel}</span>
          </div>
        </div>
      )}

      {/* Status row */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-slate-400 flex items-center gap-1.5">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
          {pct === null ? currentLabel : PIPELINE_STEPS[currentIdx]?.label}
        </span>
        <div className="flex items-center gap-3 text-[10px] text-slate-500">
          <span><span className="text-slate-300 font-medium">{reviews.toLocaleString()}</span> Reviews</span>
          {elapsed && <span className="text-slate-600">{elapsed}</span>}
        </div>
      </div>
    </div>
  )
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
    try { setSources(await datasourceApi.list()) } catch { setError('Datenquellen konnten nicht geladen werden.') }
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
    try { await datasourceApi.delete(id); await load() } catch { setError('Löschen fehlgeschlagen. Bitte erneut versuchen.') }
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
              {sources.map(ds => {
                const isDone = ds.job_status === 'done'
                const card = (
                  <div className={`bg-slate-900 border rounded-xl px-4 py-3 transition-colors
                    ${ds.job_status === 'failed' ? 'border-red-500/30' : 'border-white/10'}
                    ${isDone ? 'hover:border-indigo-500/40 hover:bg-slate-800/60 cursor-pointer' : ''}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center shrink-0">
                          <Search size={14} className="text-indigo-400" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="text-white text-sm font-medium truncate">{ds.name}</p>
                            {ds.review_date_to && (() => {
                              const lastReview = new Date(ds.review_date_to + ' 01')
                              const monthsAgo = (new Date().getFullYear() - lastReview.getFullYear()) * 12
                                + (new Date().getMonth() - lastReview.getMonth())
                              return monthsAgo > 6
                                ? <span className="shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-slate-700/60 text-slate-400 border border-slate-600/40">Legacy</span>
                                : <span className="shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Aktiv</span>
                            })()}
                          </div>
                          <p className="text-slate-500 text-xs">
                            {ds.app_id || 'CSV'} · {ds.review_count.toLocaleString()} Reviews
                            {ds.review_date_from && ds.review_date_to && (
                              <span className="text-slate-600"> · {ds.review_date_from} – {ds.review_date_to}</span>
                            )}
                          </p>
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
                            onClick={e => { e.preventDefault(); handleRetry(ds.id) }}
                            className="flex items-center gap-1 text-xs text-amber-400 hover:text-amber-300 bg-amber-400/10 hover:bg-amber-400/20 border border-amber-400/20 px-2 py-1 rounded-lg transition-colors"
                          >
                            <RefreshCw size={11} /> Retry
                          </button>
                        )}
                        <button onClick={e => { e.preventDefault(); handleDelete(ds.id) }}
                          className="text-slate-600 hover:text-red-400 transition-colors">
                          <Trash2 size={14} />
                        </button>
                        {isDone && <ChevronRight size={14} className="text-slate-600" />}
                      </div>
                    </div>
                    <PipelineStatusBar progress={ds.job_progress} status={ds.job_status} startedAt={ds.job_started_at} reviews={ds.review_count} />
                    {ds.job_status === 'failed' && ds.job_error && (
                      <div className="mt-2 ml-11 text-red-400 text-xs bg-red-500/5 border border-red-500/10 rounded-lg px-3 py-1.5">
                        {ds.job_error}
                      </div>
                    )}
                  </div>
                )
                return isDone
                  ? <Link key={ds.id} to={`/datasources/${ds.id}`}>{card}</Link>
                  : <div key={ds.id}>{card}</div>
              })}
            </div>
          </div>
        )}

        {/* Add new source */}
        <div className="bg-slate-900 border border-white/10 rounded-xl overflow-hidden">
          <div className="flex border-b border-white/10">
            {(['gplay', 'csv'] as const).map(t => (
              <button key={t} onClick={() => setTab(t)}
                className={`flex-1 py-3 text-sm font-medium transition-colors flex items-center justify-center gap-2 ${tab === t ? 'text-white border-b-2 border-indigo-500 bg-white/5' : 'text-slate-400 hover:text-white'}`}>
                {t === 'gplay' ? <><Smartphone size={13} /> Google Play</> : <><Upload size={13} /> CSV Upload</>}
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
                    <div className="flex gap-1 mb-1.5">
                      {[1000, 5000, 10000, 250000].map(n => (
                        <button key={n} type="button" onClick={() => setGpCount(n)}
                          className={`flex-1 py-1 text-xs rounded-md border transition-colors ${gpCount === n ? 'bg-indigo-600 border-indigo-500 text-white' : 'bg-slate-800 border-white/10 text-slate-400 hover:text-white hover:border-white/20'}`}>
                          {n >= 250000 ? 'Alle' : n.toLocaleString()}
                        </button>
                      ))}
                    </div>
                    <input
                      type="number" min={1} max={250000}
                      value={gpCount}
                      onChange={e => setGpCount(Math.max(1, parseInt(e.target.value) || 1))}
                      className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
                      placeholder="Eigener Wert..."
                    />
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
