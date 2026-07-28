import { useEffect, useState } from 'react'
import { Lightbulb, Loader2, AlertCircle, CheckSquare, Square, Sparkles, RefreshCw, Copy, Check } from 'lucide-react'
import { AppShell } from '../components/AppShell'
import { localMarketsApi, BusinessDashboardItem } from '../services/api'

function JobBadge({ status }: { status: string | null }) {
  if (!status || status === 'pending' || status === 'running') return (
    <span className="text-[10px] text-slate-500 border border-slate-700 px-1.5 py-0.5 rounded-full">
      {status === 'running' ? 'Pipeline läuft…' : 'Wartend'}
    </span>
  )
  if (status === 'failed') return (
    <span className="text-[10px] text-red-400 border border-red-500/20 bg-red-500/10 px-1.5 py-0.5 rounded-full">Fehler</span>
  )
  return null
}

// Simple markdown renderer for bold + headers
function MarkdownReport({ text }: { text: string }) {
  const lines = text.split('\n')
  return (
    <div className="space-y-1 text-sm text-slate-300 leading-relaxed">
      {lines.map((line, i) => {
        if (line.startsWith('## ')) return (
          <h3 key={i} className="text-white font-semibold text-base mt-5 mb-2 first:mt-0">{line.slice(3)}</h3>
        )
        if (line.startsWith('### ')) return (
          <h4 key={i} className="text-white font-medium mt-4 mb-1">{line.slice(4)}</h4>
        )
        if (line.startsWith('**') && line.endsWith('**')) return (
          <p key={i} className="text-white font-medium">{line.slice(2, -2)}</p>
        )
        if (line.match(/^\d+\./)) return (
          <p key={i} className="pl-2 text-slate-300">{line}</p>
        )
        if (line.startsWith('- ') || line.startsWith('* ')) return (
          <p key={i} className="pl-2 text-slate-300 before:content-['·'] before:mr-2 before:text-slate-500">{line.slice(2)}</p>
        )
        if (line.trim() === '') return <div key={i} className="h-1" />
        // inline bold
        const parts = line.split(/\*\*(.+?)\*\*/)
        return (
          <p key={i}>
            {parts.map((part, j) =>
              j % 2 === 1
                ? <strong key={j} className="text-white font-medium">{part}</strong>
                : <span key={j}>{part}</span>
            )}
          </p>
        )
      })}
    </div>
  )
}

export function BestPracticeLabPage() {
  const [businesses, setBusinesses]   = useState<BusinessDashboardItem[]>([])
  const [loading, setLoading]         = useState(true)
  const [selected, setSelected]       = useState<Set<string>>(new Set())
  const [focus, setFocus]             = useState('')
  const [generating, setGenerating]   = useState(false)
  const [report, setReport]           = useState('')
  const [reportDate, setReportDate]   = useState('')
  const [genError, setGenError]       = useState('')
  const [copied, setCopied]           = useState(false)

  useEffect(() => {
    localMarketsApi.dashboard()
      .then(d => {
        const ready = d.businesses.filter(b => b.review_count > 0)
        setBusinesses(ready)
        // Pre-select all ready businesses
        setSelected(new Set(ready.map(b => b.id)))
      })
      .catch(() => null)
      .finally(() => setLoading(false))
  }, [])

  const toggle = (id: string) =>
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const toggleAll = () =>
    setSelected(selected.size === businesses.length ? new Set() : new Set(businesses.map(b => b.id)))

  const handleGenerate = async () => {
    if (selected.size === 0) return
    setGenerating(true)
    setGenError('')
    setReport('')
    try {
      const result = await localMarketsApi.generateBestPractice([...selected], focus)
      setReport(result.report)
      setReportDate(new Date(result.generated_at).toLocaleString('de-DE'))
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Generierung fehlgeschlagen.'
      setGenError(msg)
    } finally {
      setGenerating(false)
    }
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(report)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const readyCount = businesses.filter(b => b.review_count > 0).length

  return (
    <AppShell>
      <div className="flex flex-col gap-6 p-6 max-w-4xl mx-auto">

        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
            <Lightbulb size={18} className="text-amber-400" />
          </div>
          <div>
            <h1 className="text-white font-semibold text-lg">Best Practice Lab</h1>
            <p className="text-slate-400 text-sm">Claude analysiert deine Betriebe und zeigt was die Besten besser machen</p>
          </div>
        </div>

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={22} className="animate-spin text-slate-500" />
          </div>
        )}

        {/* No data */}
        {!loading && businesses.length === 0 && (
          <div className="text-center py-16 text-slate-500">
            <Lightbulb size={32} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm">Noch keine analysierten Betriebe mit Reviews.</p>
            <p className="text-xs mt-1">
              Zuerst unter{' '}
              <a href="/local" className="text-indigo-400 hover:underline">Betriebe</a>{' '}
              suchen und analysieren.
            </p>
          </div>
        )}

        {!loading && businesses.length > 0 && (
          <>
            {/* Business selection */}
            <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl overflow-hidden">
              <div className="flex items-center justify-between px-5 py-3 border-b border-slate-700/50">
                <span className="text-slate-300 text-sm font-medium">
                  Betriebe auswählen
                  <span className="text-slate-500 ml-2 text-xs">({readyCount} mit Reviews)</span>
                </span>
                <button
                  onClick={toggleAll}
                  className="flex items-center gap-1.5 text-slate-400 hover:text-white text-xs transition-colors"
                >
                  {selected.size === businesses.length
                    ? <CheckSquare size={13} className="text-amber-400" />
                    : <Square size={13} />
                  }
                  {selected.size === businesses.length ? 'Alle abwählen' : 'Alle auswählen'}
                </button>
              </div>

              <div className="divide-y divide-slate-700/30">
                {businesses.map(biz => {
                  const isSelected = selected.has(biz.id)
                  const total = biz.sentiment_positive + biz.sentiment_negative + biz.sentiment_neutral
                  const posPct = total > 0 ? Math.round((biz.sentiment_positive / total) * 100) : 0
                  return (
                    <div
                      key={biz.id}
                      onClick={() => toggle(biz.id)}
                      className={`flex items-center gap-4 px-5 py-3.5 cursor-pointer transition-colors
                        ${isSelected ? 'bg-amber-500/5' : 'hover:bg-slate-700/20'}`}
                    >
                      <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors
                        ${isSelected ? 'border-amber-500 bg-amber-500' : 'border-slate-600'}`}>
                        {isSelected && (
                          <svg viewBox="0 0 12 12" className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth="2">
                            <polyline points="1,6 4,9 11,2" />
                          </svg>
                        )}
                      </div>

                      <div className="flex-1 min-w-0">
                        <p className="text-white text-sm font-medium truncate">{biz.name}</p>
                        <div className="flex items-center gap-3 mt-0.5">
                          {biz.avg_rating !== null && (
                            <span className="flex items-center gap-1 text-amber-400 text-xs">
                              <span>⭐</span>{biz.avg_rating.toFixed(1)}
                            </span>
                          )}
                          <span className="text-slate-500 text-xs">
                            {biz.review_count.toLocaleString('de-DE')} Reviews
                          </span>
                          {total > 0 && (
                            <span className="text-emerald-400 text-xs">{posPct}% positiv</span>
                          )}
                        </div>
                      </div>

                      <div className="shrink-0">
                        {biz.top_signals.slice(0, 2).map(s => (
                          <span key={`${s.feature}-${s.signal_type}`} className="text-[10px] text-slate-500 mr-1">
                            {s.feature}
                          </span>
                        ))}
                        <JobBadge status={biz.job_status} />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Focus input + generate */}
            <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5 space-y-4">
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">
                  Fokus-Thema <span className="text-slate-600">(optional — z.B. "Wartezeit", "Freundlichkeit", "Preis-Leistung")</span>
                </label>
                <input
                  type="text"
                  value={focus}
                  onChange={e => setFocus(e.target.value)}
                  placeholder="Auf welchen Aspekt soll Claude besonders eingehen?"
                  className="w-full bg-slate-900/60 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
                />
              </div>

              <div className="flex items-center justify-between">
                <p className="text-slate-500 text-xs">
                  {selected.size} Betrieb{selected.size !== 1 ? 'e' : ''} ausgewählt
                  {selected.size < 2 && (
                    <span className="text-amber-500/80 ml-2">— mindestens 2 empfohlen für Vergleich</span>
                  )}
                </p>
                <button
                  onClick={handleGenerate}
                  disabled={generating || selected.size === 0}
                  className="flex items-center gap-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors"
                >
                  {generating
                    ? <><Loader2 size={15} className="animate-spin" /> Analysiere…</>
                    : <><Sparkles size={15} /> Best Practice generieren</>
                  }
                </button>
              </div>

              {genError && (
                <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/5 border border-red-400/20 rounded-lg px-4 py-3">
                  <AlertCircle size={15} className="shrink-0" />
                  {genError}
                </div>
              )}
            </div>

            {/* Report output */}
            {report && (
              <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl overflow-hidden">
                <div className="flex items-center justify-between px-5 py-3 border-b border-slate-700/50">
                  <div className="flex items-center gap-2">
                    <Sparkles size={14} className="text-amber-400" />
                    <span className="text-white text-sm font-medium">Best Practice Analyse</span>
                    <span className="text-slate-500 text-xs">{reportDate}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleGenerate}
                      disabled={generating}
                      className="flex items-center gap-1.5 text-slate-400 hover:text-white text-xs transition-colors"
                    >
                      <RefreshCw size={12} className={generating ? 'animate-spin' : ''} />
                      Neu generieren
                    </button>
                    <button
                      onClick={handleCopy}
                      className="flex items-center gap-1.5 text-slate-400 hover:text-white text-xs transition-colors"
                    >
                      {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                      {copied ? 'Kopiert' : 'Kopieren'}
                    </button>
                  </div>
                </div>
                <div className="p-6">
                  <MarkdownReport text={report} />
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  )
}
