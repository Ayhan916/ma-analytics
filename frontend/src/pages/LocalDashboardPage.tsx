import { useEffect, useState } from 'react'
import { LayoutDashboard, Star, MessageSquare, TrendingUp, TrendingDown, Loader2, AlertCircle, ExternalLink, RefreshCw } from 'lucide-react'
import { AppShell } from '../components/AppShell'
import { localMarketsApi, LocalDashboardResponse, BusinessDashboardItem, SignalSummary } from '../services/api'

// ── Helpers ───────────────────────────────────────────────────────────────────

function Stars({ value }: { value: number }) {
  return (
    <span className="flex items-center gap-1 text-amber-400 text-xs font-medium">
      <Star size={11} fill="currentColor" />
      {value.toFixed(1)}
    </span>
  )
}

function SentimentBar({ pos, neg, neu }: { pos: number; neg: number; neu: number }) {
  const total = pos + neg + neu
  if (total === 0) return <div className="h-1.5 rounded-full bg-slate-700/50 w-full" />
  const pPct = Math.round((pos / total) * 100)
  const nPct = Math.round((neg / total) * 100)
  const uPct = 100 - pPct - nPct
  return (
    <div className="flex h-1.5 rounded-full overflow-hidden gap-px w-full">
      <div className="bg-emerald-500" style={{ width: `${pPct}%` }} />
      <div className="bg-slate-600"  style={{ width: `${uPct}%` }} />
      <div className="bg-red-500"    style={{ width: `${nPct}%` }} />
    </div>
  )
}

function JobBadge({ status }: { status: string | null }) {
  if (!status) return null
  const map: Record<string, { label: string; cls: string }> = {
    completed: { label: 'Fertig',     cls: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20' },
    running:   { label: 'Läuft…',    cls: 'bg-indigo-500/15  text-indigo-400  border-indigo-500/20'  },
    pending:   { label: 'Wartend',    cls: 'bg-slate-700/50   text-slate-400   border-slate-600'       },
    failed:    { label: 'Fehler',     cls: 'bg-red-500/15     text-red-400     border-red-500/20'      },
  }
  const cfg = map[status] ?? { label: status, cls: 'bg-slate-700/50 text-slate-400 border-slate-600' }
  return (
    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${cfg.cls}`}>
      {cfg.label}
    </span>
  )
}

function SignalChip({ signal }: { signal: SignalSummary }) {
  const colorMap: Record<string, string> = {
    feature_request: 'bg-violet-500/15 text-violet-300 border-violet-500/20',
    bug:             'bg-red-500/15    text-red-300    border-red-500/20',
    positive:        'bg-emerald-500/15 text-emerald-300 border-emerald-500/20',
  }
  const cls = colorMap[signal.signal_type] ?? 'bg-indigo-500/15 text-indigo-300 border-indigo-500/20'
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full border ${cls}`}>
      {signal.feature}
      <span className="opacity-60">{signal.count}×</span>
    </span>
  )
}

// ── Business card ─────────────────────────────────────────────────────────────

function BusinessCard({ biz, rank }: { biz: BusinessDashboardItem; rank: number }) {
  const total = biz.sentiment_positive + biz.sentiment_negative + biz.sentiment_neutral
  const posPct = total > 0 ? Math.round((biz.sentiment_positive / total) * 100) : 0
  const negPct = total > 0 ? Math.round((biz.sentiment_negative / total) * 100) : 0

  return (
    <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-slate-600 text-sm font-mono w-5 shrink-0">#{rank}</span>
          <div className="min-w-0">
            <p className="text-white font-medium text-sm truncate">{biz.name}</p>
            <div className="flex items-center gap-3 mt-1">
              {biz.avg_rating !== null && <Stars value={biz.avg_rating} />}
              <span className="flex items-center gap-1 text-slate-500 text-xs">
                <MessageSquare size={11} />
                {biz.review_count.toLocaleString('de-DE')} Reviews
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <JobBadge status={biz.job_status} />
          {biz.maps_url && (
            <a
              href={biz.maps_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-500 hover:text-white transition-colors"
            >
              <ExternalLink size={13} />
            </a>
          )}
        </div>
      </div>

      {/* Sentiment bar */}
      {total > 0 && (
        <div className="space-y-1.5">
          <SentimentBar pos={biz.sentiment_positive} neg={biz.sentiment_negative} neu={biz.sentiment_neutral} />
          <div className="flex items-center gap-4 text-[11px]">
            <span className="text-emerald-400 flex items-center gap-1"><TrendingUp size={10} /> {posPct}% positiv</span>
            <span className="text-red-400    flex items-center gap-1"><TrendingDown size={10} /> {negPct}% negativ</span>
          </div>
        </div>
      )}

      {/* Top signals */}
      {biz.top_signals.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {biz.top_signals.map(s => (
            <SignalChip key={`${s.feature}-${s.signal_type}`} signal={s} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {biz.review_count === 0 && (
        <p className="text-slate-600 text-xs">
          {biz.job_status === 'running' || biz.job_status === 'pending'
            ? 'Pipeline läuft — Daten erscheinen hier nach Abschluss.'
            : 'Noch keine Reviews analysiert.'
          }
        </p>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function LocalDashboardPage() {
  const [data, setData]       = useState<LocalDashboardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      setData(await localMarketsApi.dashboard())
    } catch {
      setError('Dashboard konnte nicht geladen werden.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  // Sort: completed + most reviews first
  const sorted = [...(data?.businesses ?? [])].sort((a, b) => {
    if (a.job_status === 'completed' && b.job_status !== 'completed') return -1
    if (b.job_status === 'completed' && a.job_status !== 'completed') return 1
    return b.review_count - a.review_count
  })

  return (
    <AppShell>
      <div className="flex flex-col gap-6 p-6 max-w-5xl mx-auto">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
              <LayoutDashboard size={18} className="text-emerald-400" />
            </div>
            <div>
              <h1 className="text-white font-semibold text-lg">Dashboard</h1>
              <p className="text-slate-400 text-sm">Alle analysierten Betriebe im Überblick</p>
            </div>
          </div>
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 text-slate-400 hover:text-white text-xs transition-colors disabled:opacity-50"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            Aktualisieren
          </button>
        </div>

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 size={24} className="animate-spin text-slate-500" />
          </div>
        )}

        {/* Error */}
        {error && !loading && (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/5 border border-red-400/20 rounded-lg px-4 py-3">
            <AlertCircle size={15} className="shrink-0" />
            {error}
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && data?.total_businesses === 0 && (
          <div className="text-center py-20 text-slate-500">
            <p className="text-sm">Noch keine Betriebe analysiert.</p>
            <p className="text-xs mt-1">Gehe zu <a href="/local" className="text-indigo-400 hover:underline">Betriebe</a>, suche und starte eine Analyse.</p>
          </div>
        )}

        {/* KPI strip */}
        {!loading && data && data.total_businesses > 0 && (
          <>
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl px-5 py-4">
                <p className="text-slate-400 text-xs mb-1">Betriebe</p>
                <p className="text-white text-2xl font-bold">{data.total_businesses}</p>
              </div>
              <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl px-5 py-4">
                <p className="text-slate-400 text-xs mb-1">Reviews gesamt</p>
                <p className="text-white text-2xl font-bold">{data.total_reviews.toLocaleString('de-DE')}</p>
              </div>
              <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl px-5 py-4">
                <p className="text-slate-400 text-xs mb-1">Ø Reviews / Betrieb</p>
                <p className="text-white text-2xl font-bold">
                  {data.total_businesses > 0 ? Math.round(data.total_reviews / data.total_businesses).toLocaleString('de-DE') : '–'}
                </p>
              </div>
            </div>

            {/* Cross-business signals */}
            {data.cross_signals.length > 0 && (
              <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                <p className="text-slate-300 text-sm font-medium mb-3">Dominante Signale (betriebsübergreifend)</p>
                <div className="flex flex-wrap gap-2">
                  {data.cross_signals.map(s => (
                    <SignalChip key={`${s.feature}-${s.signal_type}`} signal={s} />
                  ))}
                </div>
              </div>
            )}

            {/* Per-business cards */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {sorted.map((biz, i) => (
                <BusinessCard key={biz.id} biz={biz} rank={i + 1} />
              ))}
            </div>
          </>
        )}
      </div>
    </AppShell>
  )
}
