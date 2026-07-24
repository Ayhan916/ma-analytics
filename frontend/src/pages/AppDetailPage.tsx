import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { AppShell } from '../components/AppShell'
import { dashboardApi, searchApi, datasourceApi, intelligenceApi, apiClient } from '../services/api'
import {
  ArrowLeft, Search, Sparkles, LayoutGrid, Star,
  TrendingDown, TrendingUp, ChevronDown, X, RefreshCw, Download, Cpu,
} from 'lucide-react'

// ─── Types ───────────────────────────────────────────────────────────────────

interface ClusterExample { id: string; content: string; score: number | null; sentiment: string | null }
interface Cluster { id: string; label: string; mentions: number; summary: string; examples: ClusterExample[] }
interface Summary {
  datasource_name: string
  review_count: number
  avg_rating: number
  sentiment: { positive: number; negative: number; neutral: number; total: number }
  top_issues: Cluster[]
  top_strengths: Cluster[]
}
interface SearchResult {
  review_id: string; content: string; score: number | null
  sentiment: string | null; reviewed_at: string | null; similarity: number
}
interface TrendPoint { month: string; positive: number; negative: number; neutral: number; total: number; avg_rating: number | null }
interface VersionMarker { month: string; version: string }
interface TrendData  { datasource_id: string; points: TrendPoint[]; version_markers: VersionMarker[] }
interface DataSource { id: string; name: string; type: string; app_id: string | null; job_status: string | null; review_count: number; last_synced: string | null }
interface ReviewAspect { aspect_term: string | null; feature: string; sentiment: string; confidence: number | null }

// ─── Small reusables ─────────────────────────────────────────────────────────

function SentimentPill({ s }: { s: string | null }) {
  if (!s) return null
  const map: Record<string, string> = {
    positive: 'text-emerald-400 bg-emerald-400/10',
    negative: 'text-red-400 bg-red-400/10',
    neutral:  'text-slate-400 bg-slate-400/10',
  }
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${map[s] ?? map.neutral}`}>
      {s}
    </span>
  )
}

function Stars({ score }: { score: number | null }) {
  if (!score) return null
  const n = Math.round(score)
  return <span className="text-xs text-amber-400">{'★'.repeat(n)}{'☆'.repeat(5 - n)}</span>
}

function ClusterModal({ cluster, type, onClose }: { cluster: Cluster; type: 'issue' | 'strength'; onClose: () => void }) {
  const isIssue = type === 'issue'
  const accentText  = isIssue ? 'text-red-400'     : 'text-emerald-400'
  const accentBg    = isIssue ? 'bg-red-400/10'    : 'bg-emerald-400/10'
  const accentBorder= isIssue ? 'border-red-400/20': 'border-emerald-400/20'
  const Icon = isIssue ? TrendingDown : TrendingUp

  // Close on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-slate-900 border border-white/10 rounded-2xl w-full max-w-lg max-h-[80vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 p-5 border-b border-white/[0.06]">
          <div className="flex items-center gap-3 min-w-0">
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${accentBg} border ${accentBorder}`}>
              <Icon size={14} className={accentText} />
            </div>
            <div className="min-w-0">
              <p className="text-white text-sm font-semibold leading-snug">{cluster.label}</p>
              <p className={`text-xs font-medium mt-0.5 ${accentText}`}>{cluster.mentions} mentions</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors shrink-0 mt-0.5">
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto p-5 space-y-5">
          {/* Summary */}
          <div>
            <p className="text-slate-500 text-xs font-medium uppercase tracking-wider mb-2">Summary</p>
            <p className="text-slate-200 text-sm leading-relaxed">{cluster.summary}</p>
          </div>

          {/* Examples */}
          {cluster.examples.length > 0 && (
            <div>
              <p className="text-slate-500 text-xs font-medium uppercase tracking-wider mb-3">
                Example reviews
              </p>
              <div className="space-y-2">
                {cluster.examples.slice(0, 5).map(ex => (
                  <div key={ex.id} className="bg-slate-800/60 border border-white/5 rounded-xl p-3">
                    <div className="flex items-center gap-2 mb-1.5">
                      <SentimentPill s={ex.sentiment} />
                      <Stars score={ex.score} />
                    </div>
                    <p className="text-slate-300 text-xs leading-relaxed">{ex.content}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ClusterCard({ cluster, type }: { cluster: Cluster; type: 'issue' | 'strength' }) {
  const [modalOpen, setModalOpen] = useState(false)
  const isIssue = type === 'issue'
  const accentText   = isIssue ? 'text-red-400'          : 'text-emerald-400'
  const accentBorder = isIssue ? 'border-red-500/20'     : 'border-emerald-500/20'
  const accentBg     = isIssue ? 'hover:bg-red-500/5'    : 'hover:bg-emerald-500/5'

  return (
    <>
      <button
        onClick={() => setModalOpen(true)}
        className={`w-full text-left border ${accentBorder} ${accentBg} bg-slate-900/40 rounded-xl p-4 transition-colors group`}
      >
        <div className="flex items-center justify-between gap-3">
          <p className="text-white text-sm font-medium leading-snug group-hover:text-white/90">{cluster.label}</p>
          <div className="flex items-center gap-2 shrink-0">
            <span className={`text-xs font-semibold ${accentText}`}>{cluster.mentions} mentions</span>
            <ChevronDown size={12} className="text-slate-600 -rotate-90" />
          </div>
        </div>
      </button>

      {modalOpen && (
        <ClusterModal cluster={cluster} type={type} onClose={() => setModalOpen(false)} />
      )}
    </>
  )
}

function AbsaFeatureCard({ feat, type, onSelect }: { feat: FeatureRow; type: 'issue' | 'strength'; onSelect: (f: string) => void }) {
  const isIssue = type === 'issue'
  const accentText   = isIssue ? 'text-red-400'       : 'text-emerald-400'
  const accentBorder = isIssue ? 'border-red-500/20'  : 'border-emerald-500/20'
  const accentBg     = isIssue ? 'hover:bg-red-500/5' : 'hover:bg-emerald-500/5'

  const bugCount  = feat.signal_types.find(s => s.signal_type === 'bug')?.count ?? 0
  const perfCount = feat.signal_types.find(s => s.signal_type === 'performance')?.count ?? 0
  const uxCount   = feat.signal_types.find(s => s.signal_type === 'ux')?.count ?? 0
  const resCount  = feat.signal_types.find(s => s.signal_type === 'resolution')?.count ?? 0

  const metricValue = isIssue ? bugCount + perfCount + uxCount : resCount
  const metricLabel = isIssue
    ? `${bugCount > 0 ? `${bugCount} Bug${bugCount !== 1 ? 's' : ''}` : ''}${perfCount > 0 ? `${bugCount > 0 ? ' · ' : ''}${perfCount} Perf` : ''}${uxCount > 0 ? ` · ${uxCount} UX` : ''}`
    : `${resCount} behoben`

  return (
    <button
      onClick={() => onSelect(feat.feature)}
      className={`w-full text-left border ${accentBorder} ${accentBg} bg-slate-900/40 rounded-xl p-4 transition-colors group`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-white text-sm font-medium leading-snug group-hover:text-white/90">{feat.feature}</p>
          {feat.narrative && (
            <p className="text-slate-500 text-xs mt-0.5 line-clamp-1">{feat.narrative}</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`text-xs font-semibold ${accentText}`}>{metricValue} Signale</span>
          <ChevronDown size={12} className="text-slate-600 -rotate-90" />
        </div>
      </div>
      <div className="mt-2 flex items-center gap-3">
        <span className={`text-[10px] font-medium ${accentText}`}>{metricLabel}</span>
        {isIssue && feat.avg_severity && (
          <span className={`text-[10px] ${feat.avg_severity >= 4 ? 'text-red-400' : feat.avg_severity >= 3 ? 'text-amber-400' : 'text-slate-500'}`}>
            Ø Sev {feat.avg_severity.toFixed(1)}
          </span>
        )}
        <span className="text-slate-700 text-[10px] ml-auto">{feat.total_mentions} gesamt</span>
      </div>
    </button>
  )
}

// ─── Sentiment Trend Chart ───────────────────────────────────────────────────

type TimeRange = '3M' | '6M' | '1J' | 'Alles'

function SentimentTrendChart({ datasourceId }: { datasourceId: string }) {
  const [trend, setTrend]         = useState<TrendData | null>(null)
  const [loading, setLoading]     = useState(true)
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null)
  const [range, setRange]         = useState<TimeRange>('Alles')
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    dashboardApi.sentimentTrend(datasourceId)
      .then(setTrend)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [datasourceId])

  if (loading) return (
    <div className="h-40 flex items-center justify-center">
      <RefreshCw size={16} className="text-slate-700 animate-spin" />
    </div>
  )
  if (!trend || trend.points.length < 2) return (
    <div className="h-28 flex items-center justify-center">
      <p className="text-slate-600 text-xs">Not enough data for trend (needs reviews from multiple months)</p>
    </div>
  )

  // ── Time range filter ──
  const allPts = trend.points
  const rangeMap: Record<TimeRange, number> = { '3M': 3, '6M': 6, '1J': 12, 'Alles': Infinity }
  const pts = rangeMap[range] === Infinity ? allPts : allPts.slice(-rangeMap[range])
  const n   = pts.length

  const W = 600, H = 210
  const PAD = { top: 20, right: 60, bottom: 44, left: 44 }
  const pw = W - PAD.left - PAD.right
  const ph = H - PAD.top - PAD.bottom
  const MAX_BAR_H = 35  // max height of volume bars (px in viewBox)

  const xOf   = (i: number) => PAD.left + (n === 1 ? pw / 2 : (i / (n - 1)) * pw)
  const yOf   = (pct: number) => PAD.top + (1 - pct / 100) * ph
  const pctOf = (val: number, total: number) => total ? Math.round((val / total) * 100) : 0

  const posPoints = pts.map((p, i) => ({ x: xOf(i), y: yOf(pctOf(p.positive, p.total)) }))
  const negPoints = pts.map((p, i) => ({ x: xOf(i), y: yOf(pctOf(p.negative, p.total)) }))
  const neuPoints = pts.map((p, i) => ({ x: xOf(i), y: yOf(pctOf(p.neutral,  p.total)) }))

  const toPath = (points: { x: number; y: number }[]) =>
    points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
  const toArea = (points: { x: number; y: number }[]) => {
    const base = PAD.top + ph
    return `${toPath(points)} L ${points[points.length-1].x.toFixed(1)} ${base} L ${points[0].x.toFixed(1)} ${base} Z`
  }

  // Volume bars
  const maxTotal = Math.max(...pts.map(p => p.total), 1)
  const barW     = n > 1 ? Math.max(4, (pw / n) * 0.5) : 20

  // Rating line (normalized 0-5 → 0-100%)
  const hasRating = pts.some(p => p.avg_rating !== null)
  const ratingPoints = hasRating
    ? pts.map((p, i) => ({ x: xOf(i), y: yOf(p.avg_rating !== null ? (p.avg_rating / 5) * 100 : 0), r: p.avg_rating }))
    : []

  // Version markers — only within selected range and dedupe per month
  const monthsInView = new Set(pts.map(p => p.month))
  const markersInView = (trend.version_markers ?? []).filter(m => monthsInView.has(m.month))
  // dedupe: keep only first version per month to avoid overlap
  const markersByMonth = new Map<string, string>()
  markersInView.forEach(m => { if (!markersByMonth.has(m.month)) markersByMonth.set(m.month, m.version) })

  // Trend summary
  const trendSuffix = (() => {
    if (n < 4) return null
    const half = Math.min(3, Math.floor(n / 2))
    const recent = pts.slice(-half), early = pts.slice(0, half)
    const avg = (arr: TrendPoint[]) => arr.reduce((s, p) => s + pctOf(p.positive, p.total), 0) / arr.length
    const delta = Math.round(avg(recent) - avg(early))
    if (Math.abs(delta) < 2) return null
    return delta > 0
      ? { label: `▲ +${delta}% positiv`, color: 'text-emerald-400' }
      : { label: `▼ ${delta}% positiv`, color: 'text-red-400' }
  })()

  const gridPcts = [0, 25, 50, 75, 100]
  const step = n <= 6 ? 1 : n <= 12 ? 2 : Math.ceil(n / 6)
  const MONTH_NAMES = ['Jan','Feb','Mär','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Dez']

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current
    if (!svg) return
    const rect = svg.getBoundingClientRect()
    const mouseX = (e.clientX - rect.left) * (W / rect.width)
    let closest = 0, minDist = Infinity
    posPoints.forEach((p, i) => { const d = Math.abs(p.x - mouseX); if (d < minDist) { minDist = d; closest = i } })
    setHoveredIdx(closest)
  }

  const hp  = hoveredIdx !== null ? pts[hoveredIdx] : null
  const hx  = hoveredIdx !== null ? posPoints[hoveredIdx].x : null
  const tooltipRight = hoveredIdx !== null && hoveredIdx < n / 2

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <p className="text-slate-500 text-xs font-medium uppercase tracking-wider">Sentiment Trend</p>
          {trendSuffix && (
            <span className={`text-[10px] font-semibold ${trendSuffix.color}`}>{trendSuffix.label}</span>
          )}
        </div>
        {/* Time range filter */}
        <div className="flex gap-1">
          {(['3M','6M','1J','Alles'] as TimeRange[]).map(r => (
            <button key={r} onClick={() => { setRange(r); setHoveredIdx(null) }}
              className={`text-[10px] px-2 py-0.5 rounded-md font-medium transition-colors ${
                range === r
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800'
              }`}>
              {r}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-slate-900 border border-white/10 rounded-xl p-4 relative">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="w-full h-auto cursor-crosshair"
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoveredIdx(null)}
        >
          {/* Grid lines */}
          {gridPcts.map(pct => {
            const y = yOf(pct)
            return (
              <g key={pct}>
                <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y}
                  stroke="#1e293b" strokeWidth={pct === 0 ? 1.5 : 1} />
                <text x={PAD.left - 6} y={y + 3.5} textAnchor="end" fontSize="9" fill="#475569">{pct}%</text>
              </g>
            )
          })}

          {/* Volume bars (background) */}
          {pts.map((p, i) => {
            const bh = (p.total / maxTotal) * MAX_BAR_H
            return (
              <rect key={i}
                x={xOf(i) - barW / 2} y={PAD.top + ph - bh}
                width={barW} height={bh}
                fill={hoveredIdx === i ? '#64748b' : '#334155'}
                fillOpacity={hoveredIdx === i ? 0.5 : 0.3}
                rx="1"
              />
            )
          })}

          {/* Version markers */}
          {Array.from(markersByMonth.entries()).map(([month, version]) => {
            const idx = pts.findIndex(p => p.month === month)
            if (idx < 0) return null
            const x = xOf(idx)
            return (
              <g key={month}>
                <line x1={x} y1={PAD.top} x2={x} y2={PAD.top + ph}
                  stroke="#6366f1" strokeWidth="1" strokeDasharray="3 3" strokeOpacity="0.6" />
                <text x={x + 3} y={PAD.top + 9} fontSize="7.5" fill="#818cf8" fontWeight="500">
                  {version.length > 8 ? version.slice(0, 8) : version}
                </text>
              </g>
            )
          })}

          {/* Area fills */}
          <path d={toArea(posPoints)} fill="#10b981" fillOpacity="0.07" />
          <path d={toArea(negPoints)} fill="#ef4444" fillOpacity="0.07" />

          {/* Neutral line */}
          <path d={toPath(neuPoints)} fill="none" stroke="#64748b" strokeWidth="1.5"
            strokeDasharray="4 3" strokeLinecap="round" strokeLinejoin="round" />

          {/* Sentiment lines */}
          <path d={toPath(posPoints)} fill="none" stroke="#10b981" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round" />
          <path d={toPath(negPoints)} fill="none" stroke="#ef4444" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round" />

          {/* Rating line */}
          {hasRating && ratingPoints.length > 1 && (
            <>
              <path d={toPath(ratingPoints)} fill="none" stroke="#f59e0b" strokeWidth="1.5"
                strokeDasharray="5 2" strokeLinecap="round" strokeLinejoin="round" />
              {/* Right Y-axis rating labels */}
              {[1,2,3,4,5].map(r => (
                <text key={r} x={W - PAD.right + 6} y={yOf((r/5)*100) + 3.5}
                  fontSize="8" fill="#92400e">{r}★</text>
              ))}
            </>
          )}

          {/* Crosshair */}
          {hx !== null && (
            <line x1={hx} y1={PAD.top} x2={hx} y2={PAD.top + ph}
              stroke="#94a3b8" strokeWidth="1" strokeDasharray="3 3" />
          )}

          {/* Dots */}
          {posPoints.map((p, i) => (
            <circle key={i} cx={p.x} cy={p.y} r={hoveredIdx === i ? 5 : 3.5}
              fill="#10b981" stroke="#0f172a" strokeWidth="2" />
          ))}
          {negPoints.map((p, i) => (
            <circle key={i} cx={p.x} cy={p.y} r={hoveredIdx === i ? 5 : 3.5}
              fill="#ef4444" stroke="#0f172a" strokeWidth="2" />
          ))}
          {neuPoints.map((p, i) => (
            <circle key={i} cx={p.x} cy={p.y} r={hoveredIdx === i ? 4 : 2.5}
              fill="#64748b" stroke="#0f172a" strokeWidth="1.5" />
          ))}
          {hasRating && ratingPoints.map((p, i) => p.r !== null ? (
            <circle key={i} cx={p.x} cy={p.y} r={hoveredIdx === i ? 4 : 2.5}
              fill="#f59e0b" stroke="#0f172a" strokeWidth="1.5" />
          ) : null)}

          {/* Invisible hit areas */}
          {posPoints.map((p, i) => {
            const x0 = i === 0 ? PAD.left : (posPoints[i-1].x + p.x) / 2
            const x1 = i === n-1 ? PAD.left + pw : ((posPoints[i+1]?.x ?? p.x) + p.x) / 2
            return (
              <rect key={i} x={x0} y={PAD.top} width={x1 - x0} height={ph}
                fill="transparent" onMouseEnter={() => setHoveredIdx(i)} />
            )
          })}

          {/* X-axis labels */}
          {pts.map((p, i) => {
            if (i % step !== 0 && i !== n - 1) return null
            const [year, month] = p.month.split('-')
            return (
              <text key={i} x={xOf(i)} y={H - 6} textAnchor="middle" fontSize="9"
                fill={hoveredIdx === i ? '#94a3b8' : '#475569'}>
                {MONTH_NAMES[parseInt(month)-1]}/{year.slice(2)}
              </text>
            )
          })}
        </svg>

        {/* Floating tooltip */}
        {hp !== null && hoveredIdx !== null && (
          <div className={`absolute top-4 pointer-events-none z-10 bg-slate-800 border border-white/10 rounded-xl px-3 py-2.5 shadow-xl text-xs min-w-[152px] ${tooltipRight ? 'left-[38%]' : 'right-[12%]'}`}>
            <p className="text-slate-300 font-semibold mb-2">
              {MONTH_NAMES[parseInt(hp.month.split('-')[1])-1]} {hp.month.split('-')[0]}
            </p>
            <div className="space-y-1.5">
              <div className="flex justify-between gap-4">
                <span className="text-emerald-400 flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />Positiv</span>
                <span className="text-white font-medium">{pctOf(hp.positive, hp.total)}%</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-red-400 flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-red-400 shrink-0" />Negativ</span>
                <span className="text-white font-medium">{pctOf(hp.negative, hp.total)}%</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-slate-400 flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-slate-500 shrink-0" />Neutral</span>
                <span className="text-white font-medium">{pctOf(hp.neutral, hp.total)}%</span>
              </div>
              {hp.avg_rating !== null && (
                <div className="flex justify-between gap-4">
                  <span className="text-amber-400 flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />Ø Rating</span>
                  <span className="text-white font-medium">{hp.avg_rating?.toFixed(1)} ★</span>
                </div>
              )}
            </div>
            <div className="mt-2 pt-2 border-t border-white/10 flex justify-between text-slate-500">
              <span>{hp.total.toLocaleString()} Reviews</span>
              {markersByMonth.get(hp.month) && (
                <span className="text-indigo-400">{markersByMonth.get(hp.month)}</span>
              )}
            </div>
          </div>
        )}

        {/* Legend */}
        <div className="flex flex-wrap gap-4 mt-2 justify-end items-center">
          <span className="text-[10px] text-slate-500 flex items-center gap-1.5">
            <span className="w-3 h-0.5 bg-emerald-400 inline-block rounded" />Positiv
          </span>
          <span className="text-[10px] text-slate-500 flex items-center gap-1.5">
            <span className="w-3 h-0.5 bg-red-400 inline-block rounded" />Negativ
          </span>
          <span className="text-[10px] text-slate-500 flex items-center gap-1.5">
            <span className="w-3 h-0.5 bg-slate-500 inline-block rounded" />Neutral
          </span>
          {hasRating && (
            <span className="text-[10px] text-slate-500 flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-amber-400 inline-block rounded" />Ø Rating
            </span>
          )}
          {markersByMonth.size > 0 && (
            <span className="text-[10px] text-slate-500 flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-indigo-400 inline-block rounded border-dashed" />Version
            </span>
          )}
          <span className="text-[10px] text-slate-500 flex items-center gap-1.5">
            <span className="w-2 h-2 bg-slate-700 inline-block rounded-sm opacity-60" />Volumen
          </span>
        </div>
      </div>
    </div>
  )
}

// ─── ABSA Feature Overview (shared) ──────────────────────────────────────────

// ─── Tab: Overview ───────────────────────────────────────────────────────────

function OverviewTab({ datasourceId }: { datasourceId: string }) {
  const [summary, setSummary]       = useState<Summary | null>(null)
  const [matrix, setMatrix]         = useState<FeatureMatrix | null>(null)
  const [loading, setLoading]       = useState(true)
  const [loadError, setLoadError]   = useState(false)
  const [selectedFeature, setSelectedFeature] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      dashboardApi.summary(datasourceId),
      intelligenceApi.matrix(datasourceId).catch(() => null),
    ])
      .then(([s, m]) => { setSummary(s); setMatrix(m) })
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
  }, [datasourceId])

  if (loading) return <Spinner />
  if (loadError) return (
    <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-6 text-center m-6">
      <p className="text-red-400 text-sm">Daten konnten nicht geladen werden. Bitte Seite neu laden.</p>
    </div>
  )
  if (!summary) return <Empty text="No data available yet." />

  const { review_count, avg_rating, sentiment } = summary
  const total = sentiment.total || 1
  const posP = Math.round((sentiment.positive / total) * 100)
  const negP = Math.round((sentiment.negative / total) * 100)

  const absaFeatures = matrix?.features ?? []
  const useAbsa = absaFeatures.length > 0

  const absaIssues = [...absaFeatures]
    .filter(f => f.feature !== 'General')
    .map(f => ({
      ...f,
      bugLike: (f.signal_types.find(s => s.signal_type === 'bug')?.count ?? 0)
             + (f.signal_types.find(s => s.signal_type === 'performance')?.count ?? 0)
             + (f.signal_types.find(s => s.signal_type === 'ux')?.count ?? 0),
    }))
    .filter(f => f.bugLike > 0)
    .sort((a, b) => b.bugLike - a.bugLike)

  const absaStrengths = [...absaFeatures]
    .filter(f => f.feature !== 'General')
    .map(f => ({ ...f, resCount: f.signal_types.find(s => s.signal_type === 'resolution')?.count ?? 0 }))
    .filter(f => f.resCount > 0)
    .sort((a, b) => b.resCount - a.resCount)

  return (
    <div className="space-y-8">
      {/* KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KpiCard label="Total Reviews" value={review_count.toLocaleString()} />
        <KpiCard label="Avg Rating" value={`${avg_rating.toFixed(1)} ★`} valueColor="text-amber-400" />
        <KpiCard label="Positive" value={`${posP}%`} valueColor="text-emerald-400"
          sub={`${sentiment.positive.toLocaleString()} reviews`} />
        <KpiCard label="Negative" value={`${negP}%`} valueColor="text-red-400"
          sub={`${sentiment.negative.toLocaleString()} reviews`} />
      </div>

      {/* Sentiment bar */}
      <div>
        <p className="text-slate-500 text-xs font-medium uppercase tracking-wider mb-2">Sentiment distribution</p>
        <div className="flex h-2 rounded-full overflow-hidden gap-0.5">
          <div className="bg-emerald-500 rounded-full" style={{ width: `${posP}%` }} />
          <div className="bg-slate-600 rounded-full" style={{ width: `${Math.round((sentiment.neutral / total) * 100)}%` }} />
          <div className="bg-red-500 rounded-full" style={{ width: `${negP}%` }} />
        </div>
        <div className="flex gap-4 mt-2">
          <span className="text-xs text-slate-500"><span className="text-emerald-400">●</span> Positive {posP}%</span>
          <span className="text-xs text-slate-500"><span className="text-slate-400">●</span> Neutral {Math.round((sentiment.neutral / total) * 100)}%</span>
          <span className="text-xs text-slate-500"><span className="text-red-400">●</span> Negative {negP}%</span>
        </div>
      </div>

      {/* Trend chart */}
      <SentimentTrendChart datasourceId={datasourceId} />

      {/* Issues & Strengths — ABSA wenn verfügbar, sonst Cluster-Fallback */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <section>
          <div className="flex items-center gap-2 mb-3">
            <TrendingDown size={14} className="text-red-400" />
            <h3 className="text-white text-sm font-semibold">Top Issues</h3>
            {useAbsa && (
              <span className="text-[10px] text-indigo-400 bg-indigo-400/10 border border-indigo-400/20 px-1.5 py-0.5 rounded-full font-medium">ABSA</span>
            )}
          </div>
          <div className="space-y-3">
            {useAbsa
              ? absaIssues.length === 0
                ? <Empty text="Keine Bug/Perf/UX-Signale gefunden." />
                : absaIssues.map(f => <AbsaFeatureCard key={f.feature} feat={f} type="issue" onSelect={setSelectedFeature} />)
              : summary.top_issues.length === 0
                ? <Empty text="No issues detected." />
                : summary.top_issues.map(c => <ClusterCard key={c.id} cluster={c} type="issue" />)
            }
          </div>
        </section>
        <section>
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp size={14} className="text-emerald-400" />
            <h3 className="text-white text-sm font-semibold">Top Strengths</h3>
            {useAbsa && (
              <span className="text-[10px] text-indigo-400 bg-indigo-400/10 border border-indigo-400/20 px-1.5 py-0.5 rounded-full font-medium">ABSA</span>
            )}
          </div>
          <div className="space-y-3">
            {useAbsa
              ? absaStrengths.length === 0
                ? <Empty text="Keine Resolution-Signale gefunden." />
                : absaStrengths.map(f => <AbsaFeatureCard key={f.feature} feat={f} type="strength" onSelect={setSelectedFeature} />)
              : summary.top_strengths.length === 0
                ? <Empty text="No strengths detected." />
                : summary.top_strengths.map(c => <ClusterCard key={c.id} cluster={c} type="strength" />)
            }
          </div>
        </section>
      </div>

      {/* ABSA stats summary */}
      {useAbsa && matrix && (
        <p className="text-slate-600 text-xs text-center">
          {matrix.n_topics} Features analysiert · {matrix.total_signals.toLocaleString()} Signale
        </p>
      )}

      {/* Feature Detail Modal */}
      {selectedFeature && (
        <FeatureDetailModal
          feature={selectedFeature}
          datasourceId={datasourceId}
          onClose={() => setSelectedFeature(null)}
        />
      )}
    </div>
  )
}

// ─── Tab: Reviews ────────────────────────────────────────────────────────────

const SEARCH_TYPES = [
  { value: 'hybrid',   label: 'Hybrid' },
  { value: 'vector',   label: 'Semantic' },
  { value: 'fulltext', label: 'Keyword' },
]

function ReviewsTab({ datasourceId }: { datasourceId: string }) {
  const [query, setQuery]         = useState('')
  const [searchType, setType]     = useState('hybrid')
  const [rerank, setRerank]       = useState(false)
  const [results, setResults]     = useState<SearchResult[]>([])
  const [searched, setSearched]   = useState(false)
  const [searching, setSearching] = useState(false)
  const [error, setError]         = useState('')
  const [aspectsMap, setAspectsMap] = useState<Record<string, ReviewAspect[]>>({})

  const handleSearch = async () => {
    if (query.trim().length < 2) return
    setSearching(true); setError(''); setSearched(false); setAspectsMap({})
    try {
      const resp = await searchApi.search({
        datasource_id: datasourceId, q: query.trim(),
        search_type: searchType, rerank, limit: 20,
      })
      const hits: SearchResult[] = resp.results ?? []
      setResults(hits)
      setSearched(true)
      // Fetch ABSA aspects in parallel for top 15 results
      const entries = await Promise.allSettled(
        hits.slice(0, 15).map(r => intelligenceApi.reviewAspects(r.review_id).then(a => [r.review_id, a] as [string, ReviewAspect[]]))
      )
      const map: Record<string, ReviewAspect[]> = {}
      entries.forEach(e => { if (e.status === 'fulfilled') map[e.value[0]] = e.value[1] })
      setAspectsMap(map)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(detail || 'Search failed. Please try again.')
    } finally { setSearching(false) }
  }

  return (
    <div className="space-y-5">
      {/* Search bar */}
      <div className="bg-slate-900 border border-white/10 rounded-xl p-4">
        <div className="flex gap-2 flex-wrap">
          <div className="relative flex-1 min-w-48">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input
              type="text" value={query} onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              placeholder="Search reviews…"
              className="w-full bg-slate-800 border border-white/10 text-white text-sm rounded-lg pl-9 pr-3 py-2.5 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <select value={searchType} onChange={e => setType(e.target.value)}
            className="bg-slate-800 border border-white/10 text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500">
            {SEARCH_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
          <label className="flex items-center gap-2 bg-slate-800 border border-white/10 rounded-lg px-3 cursor-pointer select-none">
            <input type="checkbox" checked={rerank} onChange={e => setRerank(e.target.checked)}
              className="accent-indigo-500 w-3.5 h-3.5" />
            <span className="text-sm text-slate-300">Rerank</span>
          </label>
          <button onClick={handleSearch} disabled={searching || query.trim().length < 2}
            className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors">
            {searching ? 'Searching…' : 'Search'}
          </button>
        </div>
        {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
      </div>

      {/* Results */}
      {searched && (
        <div>
          <p className="text-slate-500 text-xs font-medium uppercase tracking-wider mb-3">
            {results.length === 0 ? 'No results' : `${results.length} results`}
          </p>
          <div className="space-y-2">
            {results.map((r, i) => {
              const aspects = aspectsMap[r.review_id] ?? []
              return (
                <div key={r.review_id} className="bg-slate-900 border border-white/10 rounded-xl p-4 space-y-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] font-mono text-slate-600 bg-slate-800 px-1.5 py-0.5 rounded">[{i + 1}]</span>
                    <SentimentPill s={r.sentiment} />
                    <Stars score={r.score} />
                    <span className="ml-auto text-xs font-mono text-slate-600">{(r.similarity * 100).toFixed(0)}% match</span>
                  </div>
                  <p className="text-slate-300 text-sm leading-relaxed line-clamp-3">{r.content}</p>
                  {r.reviewed_at && (
                    <p className="text-slate-600 text-xs">
                      {new Date(r.reviewed_at).toLocaleDateString('de-DE', { day: '2-digit', month: 'short', year: 'numeric' })}
                    </p>
                  )}
                  {aspects.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1.5 border-t border-white/[0.04]">
                      {aspects.slice(0, 6).map((asp, j) => {
                        const sent = asp.sentiment.toLowerCase()
                        const color = sent === 'positive' ? 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20'
                          : sent === 'negative' ? 'text-red-400 bg-red-400/10 border-red-400/20'
                          : 'text-slate-400 bg-slate-400/10 border-slate-400/20'
                        return (
                          <span key={j} className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full border font-medium ${color}`}>
                            {asp.feature}
                            {asp.aspect_term && asp.aspect_term.toLowerCase() !== asp.feature.toLowerCase() && (
                              <span className="opacity-50">· {asp.aspect_term}</span>
                            )}
                          </span>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Tab: Insights ───────────────────────────────────────────────────────────

const PRESETS = [
  { id: 'issues',   label: 'Top Issues',     icon: TrendingDown, color: 'text-red-400 bg-red-400/10 border-red-400/20 hover:bg-red-400/20',
    query: 'Was sind die häufigsten Probleme und Beschwerden der Nutzer dieser App?' },
  { id: 'loves',    label: 'What users love', icon: TrendingUp,  color: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20 hover:bg-emerald-400/20',
    query: 'Was schätzen und loben die Nutzer an dieser App am meisten?' },
  { id: 'verdict',  label: 'Overall verdict', icon: Star,        color: 'text-amber-400 bg-amber-400/10 border-amber-400/20 hover:bg-amber-400/20',
    query: 'Was ist das Gesamtfazit der Nutzer zu dieser App? Bitte gib eine ausgewogene Zusammenfassung.' },
]

function InsightsTab({ datasourceId }: { datasourceId: string }) {
  const [activePreset, setActivePreset] = useState<string | null>(null)
  const [freeQuery, setFreeQuery]       = useState('')
  const [answer, setAnswer]             = useState('')
  const [sources, setSources]           = useState<SearchResult[]>([])
  const [streaming, setStreaming]       = useState(false)
  const [done, setDone]                 = useState(false)
  const [streamError, setStreamError]   = useState('')
  const [showSources, setShowSources]   = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const answerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (streaming) answerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [answer, streaming])

  const runStream = async (query: string, presetId?: string) => {
    abortRef.current?.abort()
    abortRef.current = new AbortController()
    setActivePreset(presetId ?? null)
    setStreaming(true); setAnswer(''); setSources([]); setDone(false); setStreamError(''); setShowSources(false)
    try {
      const resp = await fetch('/api/search/ask/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        signal: abortRef.current.signal,
        body: JSON.stringify({ query, datasource_id: datasourceId, search_type: 'hybrid', limit: 10 }),
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error((body as { detail?: string }).detail || `HTTP ${resp.status}`)
      }
      const reader = resp.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done: rdone, value } = await reader.read()
        if (rdone) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const ev = JSON.parse(line.slice(6)) as { type: string; content?: string; sources?: SearchResult[]; message?: string }
            if (ev.type === 'sources') setSources(ev.sources ?? [])
            else if (ev.type === 'token') setAnswer(prev => prev + (ev.content ?? ''))
            else if (ev.type === 'done') setDone(true)
            else if (ev.type === 'error') setStreamError(ev.message ?? 'Unknown error')
          } catch { /* skip malformed */ }
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name !== 'AbortError') setStreamError((err as Error).message || 'Stream error.')
    } finally { setStreaming(false) }
  }

  return (
    <div className="space-y-8">

      {/* Quick Insights */}
      <section>
        <p className="text-slate-500 text-xs font-medium uppercase tracking-wider mb-4">Quick Insights</p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {PRESETS.map(p => {
            const Icon = p.icon
            const isActive = activePreset === p.id
            return (
              <button
                key={p.id}
                onClick={() => !streaming && runStream(p.query, p.id)}
                disabled={streaming}
                className={`flex items-center gap-3 border rounded-xl px-4 py-3.5 text-left transition-all disabled:opacity-50
                  ${isActive ? p.color + ' ring-1 ring-inset ring-current/30' : `border-white/10 bg-slate-900 hover:bg-slate-800 ${p.color.split(' ')[0]}`}`}
              >
                <Icon size={16} className={`shrink-0 ${p.color.split(' ')[0]}`} />
                <span className="text-sm font-medium text-white">{p.label}</span>
              </button>
            )
          })}
        </div>
      </section>

      {/* Streaming answer */}
      {(answer || streaming || streamError) && (
        <div className="bg-slate-900 border border-white/10 rounded-xl p-5 space-y-4" ref={answerRef}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles size={14} className="text-indigo-400" />
              <span className="text-white text-sm font-semibold">
                {activePreset ? PRESETS.find(p => p.id === activePreset)?.label : 'Answer'}
              </span>
            </div>
            {streaming && (
              <button onClick={() => abortRef.current?.abort()}
                className="flex items-center gap-1 text-xs text-slate-500 hover:text-red-400 transition-colors">
                <X size={12} /> Stop
              </button>
            )}
          </div>

          {streamError ? (
            <p className="text-red-400 text-sm">{streamError}</p>
          ) : (
            <p className="text-slate-200 text-sm leading-relaxed whitespace-pre-wrap">
              {answer}
              {streaming && <span className="inline-block w-0.5 h-[1.1em] bg-indigo-400 ml-0.5 animate-pulse align-middle" />}
            </p>
          )}

          {sources.length > 0 && done && (
            <div className="border-t border-white/5 pt-3">
              <button onClick={() => setShowSources(s => !s)}
                className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors">
                <ChevronDown size={11} className={`transition-transform ${showSources ? 'rotate-180' : ''}`} />
                {sources.length} source review{sources.length !== 1 ? 's' : ''}
              </button>
              {showSources && (
                <div className="mt-3 space-y-2">
                  {sources.map((r, i) => (
                    <div key={r.review_id} className="bg-slate-800/60 border border-white/5 rounded-lg p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] font-mono text-slate-600">[{i + 1}]</span>
                        <SentimentPill s={r.sentiment} />
                        <Stars score={r.score} />
                      </div>
                      <p className="text-slate-300 text-xs leading-relaxed line-clamp-2">{r.content}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Divider */}
      <div className="border-t border-white/[0.06]" />

      {/* ABSA Feature Narratives */}
      <FeatureNarratives datasourceId={datasourceId} />

      {/* Divider */}
      <div className="border-t border-white/[0.06]" />

      {/* Free question */}
      <section>
        <p className="text-slate-500 text-xs font-medium uppercase tracking-wider mb-4">Ask a question</p>
        <div className="bg-slate-900 border border-white/10 rounded-xl p-4 space-y-3">
          <p className="text-slate-400 text-xs">Ask anything about this app's reviews — Groq will search and answer based on real user feedback.</p>
          <div className="flex gap-2">
            <input
              type="text" value={freeQuery} onChange={e => setFreeQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !streaming && freeQuery.trim().length >= 4 && runStream(freeQuery.trim())}
              placeholder="e.g. Why do users uninstall the app?"
              className="flex-1 bg-slate-800 border border-white/10 text-white text-sm rounded-lg px-3 py-2.5 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            {streaming && activePreset === null ? (
              <button onClick={() => abortRef.current?.abort()}
                className="flex items-center gap-1.5 bg-red-600/20 hover:bg-red-600/30 border border-red-500/30 text-red-400 text-sm font-medium px-4 py-2 rounded-lg transition-colors shrink-0">
                <X size={14} /> Stop
              </button>
            ) : (
              <button onClick={() => freeQuery.trim().length >= 4 && runStream(freeQuery.trim())}
                disabled={streaming || freeQuery.trim().length < 4}
                className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white text-sm font-medium px-4 py-2.5 rounded-lg transition-colors shrink-0">
                <Sparkles size={14} /> Ask
              </button>
            )}
          </div>
        </div>
      </section>

      {/* Divider */}
      <div className="border-t border-white/[0.06]" />

      {/* Developer Replies Backfill */}
      <BackfillRepliesSection datasourceId={datasourceId} />

    </div>
  )
}

function BackfillRepliesSection({ datasourceId }: { datasourceId: string }) {
  const [status, setStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle')
  const [jobId, setJobId] = useState<string | null>(null)

  const start = async () => {
    setStatus('running')
    try {
      const res = await intelligenceApi.backfillReplies(datasourceId)
      setJobId(res.job_id)
      const poll = setInterval(async () => {
        try {
          const job = await apiClient.get(`/jobs/${res.job_id}`).then(r => r.data)
          if (job.status === 'done') { clearInterval(poll); setStatus('done') }
          else if (job.status === 'failed') { clearInterval(poll); setStatus('error') }
        } catch { clearInterval(poll); setStatus('error') }
      }, 4000)
    } catch {
      setStatus('error')
    }
  }

  return (
    <section>
      <p className="text-slate-500 text-xs font-medium uppercase tracking-wider mb-3">Developer-Antworten</p>
      <div className="bg-slate-900 border border-white/10 rounded-xl p-4 flex items-start gap-4">
        <div className="flex-1">
          <p className="text-white text-sm font-medium mb-1">Hersteller-Antworten laden</p>
          <p className="text-slate-400 text-xs leading-relaxed">
            Durchsucht alle bestehenden Reviews bei Google Play und speichert Antworten des App-Herstellers.
            Diese werden später für "Wurde das bereits behoben?" genutzt.
          </p>
          {status === 'running' && jobId && (
            <p className="text-indigo-400 text-xs mt-2">Läuft — Job {jobId.slice(0, 8)}… (kann einige Minuten dauern)</p>
          )}
          {status === 'done' && (
            <p className="text-emerald-400 text-xs mt-2">Fertig — Hersteller-Antworten wurden gespeichert.</p>
          )}
          {status === 'error' && (
            <p className="text-red-400 text-xs mt-2">Fehler beim Starten des Backfills.</p>
          )}
        </div>
        <button
          onClick={start}
          disabled={status === 'running'}
          className="shrink-0 flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 border border-white/10 text-white text-xs font-medium px-3 py-2 rounded-lg transition-colors"
        >
          <RefreshCw size={12} className={status === 'running' ? 'animate-spin' : ''} />
          {status === 'running' ? 'Läuft…' : 'Starten'}
        </button>
      </div>
    </section>
  )
}

// ─── Tab: Versions ───────────────────────────────────────────────────────────

interface VersionCluster { cluster_id: string; label: string; cluster_type: string; mentions_in_version: number; total_cluster_mentions: number; pct_of_version: number }
interface VersionStat    { version: string; version_source_mix: string; review_count: number; negative_pct: number; first_seen: string; last_seen: string; clusters: VersionCluster[] }
interface VersionAnalysis { datasource_id: string; versions: VersionStat[] }
interface CompareResult  { cluster_id: string; cluster_label: string; cluster_type: string; v1: string; v2: string; v1_mentions: number; v2_mentions: number; v1_review_count: number; v2_review_count: number; trend: string; verdict: string; analysis: string; v1_examples: string[]; v2_examples: string[] }
interface VersionFeatureRow { feature: string; total: number; bug_count: number; resolved_count: number; avg_severity: number | null; neg_pct: number }
interface VersionBreakdown { version: string; datasource_id: string; features: VersionFeatureRow[] }

const TREND_CONFIG: Record<string, { label: string; color: string }> = {
  new:        { label: 'Neu',          color: 'text-blue-400 bg-blue-400/10 border-blue-400/20' },
  resolved:   { label: 'Behoben',      color: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20' },
  declining:  { label: 'Rückläufig',   color: 'text-amber-400 bg-amber-400/10 border-amber-400/20' },
  persistent: { label: 'Persistent',   color: 'text-red-400 bg-red-400/10 border-red-400/20' },
  worsening:  { label: 'Verschlechtert', color: 'text-red-500 bg-red-500/10 border-red-500/20' },
  unknown:    { label: 'Unbekannt',    color: 'text-slate-400 bg-slate-400/10 border-slate-400/20' },
}

const VERDICT_CONFIG: Record<string, { label: string; color: string }> = {
  resolved:    { label: '✓ Behoben',              color: 'text-emerald-400' },
  persistent:  { label: '✗ Weiterhin vorhanden',  color: 'text-red-400' },
  no_evidence: { label: '— Keine Hinweise',        color: 'text-slate-400' },
}

function VersionsTab({ datasourceId }: { datasourceId: string }) {
  const [data, setData]           = useState<VersionAnalysis | null>(null)
  const [loading, setLoading]     = useState(true)
  const [selectedV, setSelectedV] = useState<string>('')
  const [compareV1, setCompareV1] = useState<string>('')
  const [compareV2, setCompareV2] = useState<string>('')
  const [comparing, setComparing] = useState(false)
  const [compareResults, setCompareResults] = useState<CompareResult[]>([])
  const [compareError, setCompareError] = useState('')
  const [versionBreakdown, setVersionBreakdown] = useState<VersionBreakdown | null>(null)
  const [loadingBreakdown, setLoadingBreakdown] = useState(false)

  useEffect(() => {
    dashboardApi.versionAnalysis(datasourceId)
      .then((d: VersionAnalysis) => {
        setData(d)
        if (d.versions.length > 0) {
          const last = d.versions[d.versions.length - 1].version
          setSelectedV(last)
          if (d.versions.length >= 2) {
            setCompareV1(d.versions[d.versions.length - 2].version)
            setCompareV2(last)
          }
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [datasourceId])

  useEffect(() => {
    if (!selectedV) return
    setLoadingBreakdown(true)
    setVersionBreakdown(null)
    intelligenceApi.versionBreakdown(datasourceId, selectedV)
      .then(setVersionBreakdown)
      .catch(() => {})
      .finally(() => setLoadingBreakdown(false))
  }, [datasourceId, selectedV])

  const handleCompare = async () => {
    if (!compareV1 || !compareV2 || compareV1 === compareV2 || !data) return
    setComparing(true); setCompareResults([]); setCompareError('')

    const vStat = data.versions.find(v => v.version === compareV1)
    const issueClusters = (vStat?.clusters ?? []).filter(c => c.cluster_type === 'issue').slice(0, 5)

    try {
      const results = await Promise.all(
        issueClusters.map(c =>
          dashboardApi.versionCompare(datasourceId, c.cluster_id, compareV1, compareV2)
        )
      )
      setCompareResults(results)
    } catch {
      setCompareError('Vergleich fehlgeschlagen. Bitte erneut versuchen.')
    } finally { setComparing(false) }
  }

  if (loading) return <Spinner />
  if (!data || data.versions.length === 0) return <Empty text="Keine Versionsdaten verfügbar." />

  const selectedStat = data.versions.find(v => v.version === selectedV)
  const issues    = selectedStat?.clusters.filter(c => c.cluster_type === 'issue')    ?? []
  const strengths = selectedStat?.clusters.filter(c => c.cluster_type === 'strength') ?? []

  return (
    <div className="space-y-10">

      {/* ── Versionsübersicht ── */}
      <section>
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          <div className="flex items-center gap-2">
            <Star size={14} className="text-indigo-400" />
            <h2 className="text-white text-sm font-semibold">Version auswählen</h2>
          </div>
          <select
            value={selectedV}
            onChange={e => setSelectedV(e.target.value)}
            className="bg-slate-800 border border-white/10 text-white text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {[...data.versions].reverse().map(v => (
              <option key={v.version} value={v.version}>
                {v.version} ({v.review_count} Reviews · {v.first_seen.slice(0, 7)})
              </option>
            ))}
          </select>
          {selectedStat && (
            <span className="text-slate-500 text-xs">
              {selectedStat.first_seen} – {selectedStat.last_seen} ·
              <span className="text-red-400 ml-1">{selectedStat.negative_pct}% negativ</span>
              {selectedStat.version_source_mix !== 'provided' && (
                <span className="text-slate-600 ml-1">(teilweise inferiert)</span>
              )}
            </span>
          )}
        </div>

        {selectedStat && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Issues */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <TrendingDown size={13} className="text-red-400" />
                <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Issues in dieser Version</p>
              </div>
              {issues.length === 0
                ? <p className="text-slate-600 text-xs py-4 text-center">Keine Issues gefunden</p>
                : <div className="space-y-2">
                    {issues.map(c => (
                      <div key={c.cluster_id} className="bg-slate-900 border border-red-500/15 rounded-xl px-4 py-3">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-white text-sm font-medium">{c.label}</p>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-red-400 text-xs font-semibold">{c.mentions_in_version}×</span>
                            <span className="text-slate-600 text-xs">{c.pct_of_version}%</span>
                          </div>
                        </div>
                        <div className="mt-2 h-1 bg-slate-800 rounded-full overflow-hidden">
                          <div className="h-full bg-red-500/60 rounded-full"
                            style={{ width: `${Math.min(c.pct_of_version * 3, 100)}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
              }
            </div>

            {/* Strengths */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <TrendingUp size={13} className="text-emerald-400" />
                <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Stärken in dieser Version</p>
              </div>
              {strengths.length === 0
                ? <p className="text-slate-600 text-xs py-4 text-center">Keine Stärken gefunden</p>
                : <div className="space-y-2">
                    {strengths.map(c => (
                      <div key={c.cluster_id} className="bg-slate-900 border border-emerald-500/15 rounded-xl px-4 py-3">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-white text-sm font-medium">{c.label}</p>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-emerald-400 text-xs font-semibold">{c.mentions_in_version}×</span>
                            <span className="text-slate-600 text-xs">{c.pct_of_version}%</span>
                          </div>
                        </div>
                        <div className="mt-2 h-1 bg-slate-800 rounded-full overflow-hidden">
                          <div className="h-full bg-emerald-500/60 rounded-full"
                            style={{ width: `${Math.min(c.pct_of_version * 3, 100)}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
              }
            </div>
          </div>
        )}
      </section>

      {/* ── ABSA Feature-Analyse ── */}
      {(loadingBreakdown || versionBreakdown) && (
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Cpu size={14} className="text-indigo-400" />
            <h2 className="text-white text-sm font-semibold">ABSA Feature-Analyse</h2>
            {selectedV && <span className="text-slate-600 text-xs font-mono">{selectedV}</span>}
          </div>

          {loadingBreakdown && (
            <div className="flex justify-center py-8">
              <RefreshCw size={16} className="animate-spin text-slate-600" />
            </div>
          )}

          {!loadingBreakdown && versionBreakdown && (
            <div className="bg-slate-900 border border-white/10 rounded-xl divide-y divide-white/[0.04]">
              {versionBreakdown.features.length === 0 ? (
                <p className="text-slate-600 text-xs py-6 text-center">Keine ABSA-Daten für diese Version</p>
              ) : (
                versionBreakdown.features.map(f => (
                  <div key={f.feature} className="px-4 py-3 flex items-center gap-3">
                    <p className="text-white text-xs font-medium w-24 shrink-0">{f.feature}</p>
                    <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${f.neg_pct > 60 ? 'bg-red-500/70' : f.neg_pct > 30 ? 'bg-amber-500/70' : 'bg-emerald-500/60'}`}
                        style={{ width: `${Math.max(f.neg_pct, 4)}%` }}
                      />
                    </div>
                    <span className="text-slate-500 text-xs w-14 text-right shrink-0">{f.neg_pct}% neg</span>
                    <span className="text-slate-600 text-xs w-8 text-right shrink-0">{f.total}×</span>
                    <div className="flex gap-3 shrink-0 w-32 justify-end">
                      {f.bug_count > 0 && <span className="text-red-400 text-[10px]">{f.bug_count} bugs</span>}
                      {f.resolved_count > 0 && <span className="text-emerald-400 text-[10px]">{f.resolved_count} ✓</span>}
                      {f.avg_severity != null && (
                        <span className={`text-[10px] ${f.avg_severity >= 4 ? 'text-red-400' : f.avg_severity >= 3 ? 'text-amber-400' : 'text-slate-500'}`}>
                          Sev {f.avg_severity.toFixed(1)}
                        </span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </section>
      )}

      {/* ── Versionsvergleich ── */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <RefreshCw size={14} className="text-indigo-400" />
          <h2 className="text-white text-sm font-semibold">Versionen vergleichen</h2>
        </div>

        <div className="bg-slate-900 border border-white/10 rounded-xl p-4 space-y-4">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <span className="text-slate-500 text-xs">Von</span>
              <select value={compareV1} onChange={e => setCompareV1(e.target.value)}
                className="bg-slate-800 border border-white/10 text-white text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                {data.versions.map(v => <option key={v.version} value={v.version}>{v.version}</option>)}
              </select>
            </div>
            <span className="text-slate-600 text-sm">→</span>
            <div className="flex items-center gap-2">
              <span className="text-slate-500 text-xs">Nach</span>
              <select value={compareV2} onChange={e => setCompareV2(e.target.value)}
                className="bg-slate-800 border border-white/10 text-white text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                {data.versions.map(v => <option key={v.version} value={v.version}>{v.version}</option>)}
              </select>
            </div>
            <button
              onClick={handleCompare}
              disabled={comparing || compareV1 === compareV2}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white text-sm font-medium px-4 py-1.5 rounded-lg transition-colors"
            >
              {comparing ? <><RefreshCw size={13} className="animate-spin" /> Analysiere…</> : 'Vergleichen'}
            </button>
          </div>

          {compareError && <p className="text-red-400 text-xs">{compareError}</p>}

          {compareResults.length > 0 && (
            <div className="space-y-3 pt-2 border-t border-white/[0.06]">
              {compareResults.map(r => {
                const tConf = TREND_CONFIG[r.trend] ?? TREND_CONFIG.unknown
                const vConf = VERDICT_CONFIG[r.verdict] ?? VERDICT_CONFIG.no_evidence
                return (
                  <div key={r.cluster_id} className="bg-slate-800/50 border border-white/5 rounded-xl p-4 space-y-3">
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <p className="text-white text-sm font-semibold">{r.cluster_label}</p>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${tConf.color}`}>
                          {tConf.label}
                        </span>
                        <span className={`text-xs font-semibold ${vConf.color}`}>{vConf.label}</span>
                      </div>
                    </div>

                    {/* Mentions comparison */}
                    <div className="flex items-center gap-4 text-xs text-slate-400">
                      <span><span className="text-white font-medium">{r.v1_mentions}</span> Erwähnungen in {r.v1}</span>
                      <span>→</span>
                      <span><span className={r.v2_mentions < r.v1_mentions ? 'text-emerald-400' : 'text-red-400'} style={{ fontWeight: 600 }}>{r.v2_mentions}</span> Erwähnungen in {r.v2}</span>
                    </div>

                    {/* LLM Analysis */}
                    <p className="text-slate-300 text-xs leading-relaxed">{r.analysis}</p>

                    {/* Examples */}
                    {(r.v1_examples.length > 0 || r.v2_examples.length > 0) && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-white/[0.04]">
                        {r.v1_examples.length > 0 && (
                          <div>
                            <p className="text-slate-600 text-[10px] font-medium mb-1.5">{r.v1}</p>
                            <p className="text-slate-400 text-xs leading-relaxed line-clamp-3 italic">"{r.v1_examples[0]}"</p>
                          </div>
                        )}
                        {r.v2_examples.length > 0 && (
                          <div>
                            <p className="text-slate-600 text-[10px] font-medium mb-1.5">{r.v2}</p>
                            <p className="text-slate-400 text-xs leading-relaxed line-clamp-3 italic">"{r.v2_examples[0]}"</p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

// ─── Tab: Intelligence ───────────────────────────────────────────────────────

interface FeatureSignalType  { signal_type: string; count: number }
interface FeatureVersionCell { version: string; mention_count: number; avg_severity: number | null; bug_count: number; resolved_count: number }
interface FeatureRow         { feature: string; total_mentions: number; avg_severity: number | null; narrative: string | null; signal_types: FeatureSignalType[]; top_versions: FeatureVersionCell[] }
interface FeatureMatrix      { datasource_id: string; features: FeatureRow[]; total_sentences: number; total_signals: number; n_topics: number }
interface SentenceSignal     { id: string; review_id: string; text: string; review_content: string | null; feature: string; signal_type: string; severity: number | null; is_resolved: boolean; version: string | null; reviewed_at: string | null; score: number | null }
interface FeatureDetail      { feature: string; datasource_id: string; narrative: string | null; mention_count: number; avg_severity: number | null; signal_types: FeatureSignalType[]; version_trend: FeatureVersionCell[]; top_signals: SentenceSignal[] }

const SIGNAL_COLORS: Record<string, string> = {
  bug:             'text-red-400 bg-red-400/10 border-red-400/20',
  performance:     'text-orange-400 bg-orange-400/10 border-orange-400/20',
  ux:              'text-amber-400 bg-amber-400/10 border-amber-400/20',
  feature_request: 'text-blue-400 bg-blue-400/10 border-blue-400/20',
  resolution:      'text-emerald-400 bg-emerald-400/10 border-emerald-400/20',
  competitive:     'text-purple-400 bg-purple-400/10 border-purple-400/20',
  brand:           'text-pink-400 bg-pink-400/10 border-pink-400/20',
  general:         'text-slate-400 bg-slate-400/10 border-slate-400/20',
}

const SIGNAL_LABELS: Record<string, string> = {
  bug: 'Bug', performance: 'Performance', ux: 'UX', feature_request: 'Feature Request',
  resolution: 'Behoben', competitive: 'Wettbewerb', brand: 'Marke', general: 'Allgemein',
}

function SeverityDot({ severity }: { severity: number | null }) {
  if (!severity) return null
  const colors = ['', 'bg-slate-500', 'bg-yellow-500', 'bg-amber-500', 'bg-orange-500', 'bg-red-500']
  return (
    <span title={`Severity ${severity}/5`} className={`w-2 h-2 rounded-full inline-block ${colors[severity] ?? 'bg-slate-500'}`} />
  )
}

function FeatureDetailModal({ feature, datasourceId, onClose }: { feature: string; datasourceId: string; onClose: () => void }) {
  const [detail, setDetail]               = useState<FeatureDetail | null>(null)
  const [loading, setLoading]             = useState(true)
  const [signalTypeFilter, setSignalTypeFilter] = useState<string | null>(null)
  const [versionFilter, setVersionFilter] = useState<string | null>(null)
  const [sortBy, setSortBy] = useState<string | null>(null)
  const [filteredSignals, setFilteredSignals] = useState<SentenceSignal[] | null>(null)
  const [loadingFilter, setLoadingFilter] = useState(false)
  const [filterError, setFilterError] = useState('')
  const [initialError, setInitialError] = useState('')
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  // Initial load — onClose excluded from deps to prevent re-fetch on parent re-render
  useEffect(() => {
    setLoading(true)
    setInitialError('')
    intelligenceApi.feature(datasourceId, feature)
      .then(setDetail)
      .catch((e: unknown) => {
        const msg = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? 'Fehler beim Laden'
        setInitialError(msg)
      })
      .finally(() => setLoading(false))

    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onCloseRef.current() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [feature, datasourceId])

  // Filtered/sorted load
  useEffect(() => {
    if (!signalTypeFilter && !versionFilter && !sortBy) { setFilteredSignals(null); setFilterError(''); return }
    setLoadingFilter(true)
    setFilterError('')
    intelligenceApi.feature(datasourceId, feature, signalTypeFilter ?? undefined, versionFilter ?? undefined, sortBy ?? undefined)
      .then((d: FeatureDetail) => setFilteredSignals(d.top_signals))
      .catch((e: unknown) => {
        const msg = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? 'Filter fehlgeschlagen'
        setFilterError(msg)
      })
      .finally(() => setLoadingFilter(false))
  }, [signalTypeFilter, versionFilter, sortBy, feature, datasourceId])

  const hasFilter = !!(signalTypeFilter || versionFilter || sortBy)
  const displaySignals = filteredSignals ?? detail?.top_signals ?? []

  const toggleSignalType = (st: string) => { setSignalTypeFilter(prev => prev === st ? null : st); setFilteredSignals(null) }
  const toggleVersion    = (v: string)  => { setVersionFilter(prev => prev === v ? null : v);      setFilteredSignals(null) }
  const toggleSort       = (s: string)  => { setSortBy(prev => prev === s ? null : s);             setFilteredSignals(null) }
  const clearFilters = () => { setSignalTypeFilter(null); setVersionFilter(null); setSortBy(null); setFilteredSignals(null) }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="bg-slate-900 border border-white/10 rounded-2xl w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl">

        {/* Header */}
        <div className="flex items-center justify-between gap-4 p-5 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center">
              <Cpu size={14} className="text-indigo-400" />
            </div>
            <div>
              <p className="text-white text-sm font-semibold">{feature}</p>
              {detail && <p className="text-slate-500 text-xs">{detail.mention_count} Signale{detail.avg_severity ? ` · Ø Severity ${detail.avg_severity.toFixed(1)}` : ''}</p>}
            </div>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors"><X size={16} /></button>
        </div>

        <div className="overflow-y-auto p-5 space-y-5">
          {loading && <div className="flex justify-center py-8"><RefreshCw size={16} className="animate-spin text-slate-600" /></div>}
          {initialError && <p className="text-red-400 text-sm text-center py-8">{initialError}</p>}

          {detail && <>
            {/* KI-Synthese — Groq-generierte Zusammenfassung aller Signale */}
            {detail.narrative && (
              <div className="bg-indigo-500/5 border border-indigo-500/20 rounded-xl p-4">
                <p className="text-slate-500 text-[10px] font-semibold uppercase tracking-wider mb-2">KI-Synthese · Groq-Zusammenfassung aller Signale</p>
                <p className="text-slate-200 text-sm leading-relaxed">{detail.narrative}</p>
              </div>
            )}

            {/* Signal-Typen — klickbar zum Filtern */}
            <div>
              <p className="text-slate-500 text-[10px] font-semibold uppercase tracking-wider mb-2">
                Signal-Typen <span className="text-slate-700 font-normal normal-case">— klicken zum Filtern</span>
              </p>
              <div className="flex flex-wrap gap-2">
                {detail.signal_types.map(st => {
                  const isActive = signalTypeFilter === st.signal_type
                  return (
                    <button
                      key={st.signal_type}
                      onClick={() => toggleSignalType(st.signal_type)}
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium transition-all
                        ${isActive
                          ? (SIGNAL_COLORS[st.signal_type] ?? SIGNAL_COLORS.general) + ' ring-1 ring-inset ring-current/30 scale-105'
                          : 'text-slate-400 bg-slate-800/60 border-slate-700/60 hover:border-slate-600'
                        }`}
                    >
                      {SIGNAL_LABELS[st.signal_type] ?? st.signal_type}
                      <span className="opacity-70">({st.count})</span>
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Version-Trend — klickbar zum Filtern */}
            {detail.version_trend.length > 0 && (
              <div>
                <p className="text-slate-500 text-[10px] font-semibold uppercase tracking-wider mb-2">
                  Version-Trend <span className="text-slate-700 font-normal normal-case">— klicken zum Filtern</span>
                </p>
                <div className="space-y-1.5">
                  {detail.version_trend.slice(0, 10).map(v => {
                    const isActive = versionFilter === v.version
                    return (
                      <button
                        key={v.version}
                        onClick={() => toggleVersion(v.version)}
                        className={`w-full flex items-center gap-3 rounded-lg px-3 py-2 transition-all text-left
                          ${isActive
                            ? 'bg-indigo-500/15 border border-indigo-500/40'
                            : 'bg-slate-800/40 border border-white/5 hover:border-white/15'
                          }`}
                      >
                        <span className={`text-xs font-mono w-24 shrink-0 ${isActive ? 'text-indigo-300' : 'text-white'}`}>{v.version}</span>
                        <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${isActive ? 'bg-indigo-400/80' : 'bg-indigo-500/50'}`}
                            style={{ width: `${Math.min(100, (v.mention_count / detail.version_trend[0].mention_count) * 100)}%` }} />
                        </div>
                        <span className="text-slate-400 text-xs w-12 text-right shrink-0">{v.mention_count}×</span>
                        {v.bug_count > 0 && <span className="text-red-400 text-[10px] shrink-0">{v.bug_count} bugs</span>}
                        {v.resolved_count > 0 && <span className="text-emerald-400 text-[10px] shrink-0">{v.resolved_count} ✓</span>}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Filter-Status + Signale */}
            <div>
              {/* Sort chips */}
              <div className="flex items-center gap-1.5 flex-wrap mb-2">
                <span className="text-slate-600 text-[10px] mr-0.5">Sortierung:</span>
                {([
                  { key: 'datum_neu', label: 'Neueste' },
                  { key: 'datum_alt', label: 'Älteste' },
                  { key: 'version',   label: 'Version' },
                  { key: 'bewertung', label: 'Bewertung' },
                  { key: 'severity',  label: 'Schweregrad' },
                ] as { key: string; label: string }[]).map(opt => (
                  <button
                    key={opt.key}
                    onClick={() => toggleSort(opt.key)}
                    className={`text-[10px] px-2 py-0.5 rounded-full border transition-all
                      ${sortBy === opt.key
                        ? 'text-indigo-300 bg-indigo-500/15 border-indigo-500/40'
                        : 'text-slate-500 border-slate-700 hover:text-slate-300 hover:border-slate-500'}`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>

              <div className="flex items-center justify-between mb-2">
                <p className="text-slate-500 text-[10px] font-semibold uppercase tracking-wider">
                  {hasFilter ? `${loadingFilter ? '…' : displaySignals.length} Reviews` : 'Top Reviews'}
                  {signalTypeFilter && <span className="text-indigo-400 ml-1">· {SIGNAL_LABELS[signalTypeFilter] ?? signalTypeFilter}</span>}
                  {versionFilter && <span className="text-indigo-400 ml-1">· v{versionFilter}</span>}
                  {sortBy && <span className="text-slate-500 ml-1">· sortiert</span>}
                </p>
                {hasFilter && (
                  <button onClick={clearFilters} className="flex items-center gap-1 text-[10px] text-slate-500 hover:text-white transition-colors">
                    <X size={10} /> Alles zurücksetzen
                  </button>
                )}
              </div>

              {filterError ? (
                <p className="text-red-400 text-xs py-4 text-center">{filterError}</p>
              ) : loadingFilter ? (
                <div className="flex justify-center py-6"><RefreshCw size={14} className="animate-spin text-slate-600" /></div>
              ) : displaySignals.length === 0 ? (
                <p className="text-slate-600 text-xs py-4 text-center">Keine Reviews für diesen Filter</p>
              ) : (
                <div className="space-y-2">
                  {displaySignals.map(s => (
                    <ReviewSignalCard key={s.id} signal={s} feature={feature} versionFilter={versionFilter} />
                  ))}
                </div>
              )}
            </div>
          </>}
        </div>
      </div>
    </div>
  )
}

// ─── Similar History + Resolution Check Types ────────────────────────────────

interface SimilarOccurrence {
  version: string | null
  date: string | null
  count: number
  has_reply: boolean
  example_content: string
  reply_content: string | null
  reply_at: string | null
}

interface SimilarHistoryResult {
  review_id: string
  feature: string | null
  signal_type: string | null
  total_similar: number
  occurrences: SimilarOccurrence[]
  has_any_reply: boolean
  synthesis: string
}

interface ResolutionCheckResult {
  review_id: string
  feature: string | null
  verdict: string
  confidence: string
  developer_reply: string | null
  developer_reply_at: string | null
  resolution_signals_after: number
  bug_count_same_version: number
  bug_count_newer_versions: number
  last_bug_version: string | null
  synthesis: string
}

const VERDICT_STYLES: Record<string, { label: string; color: string; dot: string }> = {
  behoben:                { label: 'Behoben',                color: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30', dot: 'bg-emerald-400' },
  wahrscheinlich_behoben: { label: 'Wahrscheinlich behoben', color: 'text-amber-400 bg-amber-400/10 border-amber-400/30',   dot: 'bg-amber-400'   },
  offen:                  { label: 'Noch offen',             color: 'text-red-400 bg-red-400/10 border-red-400/30',          dot: 'bg-red-400'     },
  keine_daten:            { label: 'Keine Daten',            color: 'text-slate-400 bg-slate-800 border-slate-700',          dot: 'bg-slate-500'   },
}

function ReviewSignalCard({ signal: s, versionFilter }: { signal: SentenceSignal; feature: string; versionFilter: string | null }) {
  const [openPanel, setOpenPanel] = useState<'resolution' | 'history' | null>(null)

  // Resolution check state
  const [resolution, setResolution] = useState<ResolutionCheckResult | null>(null)
  const [loadingRes, setLoadingRes] = useState(false)
  const [errorRes, setErrorRes] = useState('')

  // Similar history state
  const [history, setHistory] = useState<SimilarHistoryResult | null>(null)
  const [loadingHist, setLoadingHist] = useState(false)
  const [errorHist, setErrorHist] = useState('')

  const openResolution = async () => {
    if (openPanel === 'resolution') { setOpenPanel(null); return }
    setOpenPanel('resolution')
    if (resolution) return
    setLoadingRes(true); setErrorRes('')
    try { setResolution(await intelligenceApi.resolutionCheck(s.review_id)) }
    catch { setErrorRes('Analyse fehlgeschlagen.') }
    finally { setLoadingRes(false) }
  }

  const openHistory = async () => {
    if (openPanel === 'history') { setOpenPanel(null); return }
    setOpenPanel('history')
    if (history) return
    setLoadingHist(true); setErrorHist('')
    try { setHistory(await intelligenceApi.similarHistory(s.review_id)) }
    catch { setErrorHist('Verlauf konnte nicht geladen werden.') }
    finally { setLoadingHist(false) }
  }

  const vs = resolution ? (VERDICT_STYLES[resolution.verdict] ?? VERDICT_STYLES.keine_daten) : null

  return (
    <div className="bg-slate-800/40 border border-white/5 rounded-lg overflow-hidden">
      <div className="px-3 py-2.5">
        <div className="flex items-center gap-2 mb-1.5 flex-wrap">
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full border font-medium ${SIGNAL_COLORS[s.signal_type] ?? SIGNAL_COLORS.general}`}>
            {SIGNAL_LABELS[s.signal_type] ?? s.signal_type}
          </span>
          <SeverityDot severity={s.severity} />
          {s.is_resolved && <span className="text-emerald-400 text-[10px]">✓ behoben</span>}
          {s.score && <Stars score={s.score} />}
          {!versionFilter && s.version && <span className="text-slate-600 text-[10px] font-mono">{s.version}</span>}
          {s.reviewed_at && <span className="text-slate-700 text-[10px] ml-auto">{s.reviewed_at}</span>}
          <button
            onClick={openResolution}
            title="Wurde dieses Problem behoben?"
            className={`ml-1 flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border transition-all
              ${openPanel === 'resolution' ? 'text-indigo-300 bg-indigo-500/15 border-indigo-500/40' : 'text-slate-500 border-slate-700 hover:text-slate-300 hover:border-slate-500'}`}
          >
            <Search size={9} />
            Behoben?
          </button>
          <button
            onClick={openHistory}
            title="Kam so etwas früher schon mal vor?"
            className={`flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border transition-all
              ${openPanel === 'history' ? 'text-violet-300 bg-violet-500/15 border-violet-500/40' : 'text-slate-500 border-slate-700 hover:text-slate-300 hover:border-slate-500'}`}
          >
            <RefreshCw size={9} />
            Verlauf?
          </button>
        </div>
        <p className="text-slate-300 text-xs leading-relaxed">{s.review_content ?? s.text}</p>
      </div>

      {/* Resolution panel */}
      {openPanel === 'resolution' && (
        <div className="border-t border-white/[0.06] px-3 py-3 bg-slate-900/60 space-y-2.5">
          {loadingRes && <div className="flex items-center gap-2 text-slate-500 text-xs"><RefreshCw size={11} className="animate-spin" /> Analysiere…</div>}
          {errorRes && <p className="text-red-400 text-xs">{errorRes}</p>}
          {resolution && vs && (() => {
            const verdictEvidence: { icon: string; text: string; source: string; color: string }[] = []
            const confidenceReason: string[] = []

            if (resolution.developer_reply) {
              verdictEvidence.push({
                icon: '💬',
                text: 'Hersteller hat direkt auf diesen Review geantwortet',
                source: resolution.developer_reply_at ? `Quelle: Hersteller-Antwort vom ${resolution.developer_reply_at}` : 'Quelle: Hersteller-Antwort (Datum unbekannt)',
                color: 'text-indigo-300',
              })
            }
            if (resolution.resolution_signals_after > 0) {
              verdictEvidence.push({
                icon: '✓',
                text: `${resolution.resolution_signals_after} weitere Nutzer meldeten nach diesem Review eine Lösung für „${resolution.feature}"`,
                source: `Quelle: ${resolution.resolution_signals_after} Resolution-Signale in review_signals (nach Review-Datum)`,
                color: 'text-emerald-400',
              })
            }
            if (resolution.bug_count_newer_versions === 0 && resolution.bug_count_same_version > 0) {
              verdictEvidence.push({
                icon: '📉',
                text: `Keine weiteren Bug-Meldungen für „${resolution.feature}" in neueren App-Versionen`,
                source: `Quelle: 0 Bug-Signale nach Review-Datum (vorher: ${resolution.bug_count_same_version})`,
                color: 'text-emerald-400',
              })
            }
            if (resolution.bug_count_newer_versions > 0) {
              verdictEvidence.push({
                icon: '⚠',
                text: `„${resolution.feature}" wurde ${resolution.bug_count_newer_versions}× in neueren Versionen noch als Bug gemeldet`,
                source: resolution.last_bug_version
                  ? `Quelle: ${resolution.bug_count_newer_versions} Bug-Signale nach Review-Datum — letzter bekannter Fehlerbericht: v${resolution.last_bug_version}`
                  : `Quelle: ${resolution.bug_count_newer_versions} Bug-Signale nach Review-Datum`,
                color: 'text-red-400',
              })
            }
            if (resolution.bug_count_newer_versions === 0 && resolution.resolution_signals_after === 0 && !resolution.developer_reply) {
              verdictEvidence.push({
                icon: '—',
                text: 'Keine direkten Hinweise auf Behebung oder weiteres Auftreten gefunden',
                source: 'Quelle: review_signals, reviews (kein passendes Signal nach Review-Datum)',
                color: 'text-slate-500',
              })
            }
            if (resolution.verdict === 'behoben') {
              confidenceReason.push('Hersteller-Antwort vorhanden UND keine neueren Bug-Meldungen → hohe Sicherheit')
            } else if (resolution.verdict === 'wahrscheinlich_behoben') {
              if (resolution.developer_reply && resolution.bug_count_newer_versions > 0)
                confidenceReason.push('Hersteller hat geantwortet, aber ähnliche Fehler wurden danach noch gemeldet — daher nur „mittel"')
              else if (!resolution.developer_reply)
                confidenceReason.push('Keine direkte Hersteller-Antwort — Schluss basiert nur auf indirekter Evidenz')
            } else if (resolution.verdict === 'offen') {
              confidenceReason.push(`Noch ${resolution.bug_count_newer_versions} Bug-Meldungen nach diesem Review — Problem scheint weiterhin zu bestehen`)
            } else {
              confidenceReason.push('Zu wenig Datenpunkte für eine verlässliche Aussage')
            }
            return (
              <>
                <div className="flex items-start gap-3">
                  <span className={`inline-flex items-center gap-1.5 text-[10px] font-semibold px-2.5 py-1 rounded-full border shrink-0 ${vs.color}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${vs.dot}`} />
                    {vs.label}
                  </span>
                  <p className="text-slate-500 text-[10px]">
                    Konfidenz: <span className="text-slate-300 font-medium">{resolution.confidence}</span>
                    <span className="text-slate-700"> · {confidenceReason[0]}</span>
                  </p>
                </div>
                <p className="text-slate-300 text-xs leading-relaxed">{resolution.synthesis}</p>
                <div className="space-y-1.5">
                  <p className="text-slate-600 text-[10px] font-semibold uppercase tracking-wider">Begründung & Quellen</p>
                  {verdictEvidence.map((e, i) => (
                    <div key={i} className="bg-slate-800/60 border border-white/[0.04] rounded-lg px-3 py-2">
                      <p className={`text-xs font-medium ${e.color}`}>{e.icon} {e.text}</p>
                      <p className="text-slate-600 text-[10px] mt-0.5">{e.source}</p>
                    </div>
                  ))}
                </div>
                {resolution.developer_reply && (
                  <div className="bg-indigo-500/5 border border-indigo-500/20 rounded-lg px-3 py-2.5">
                    <p className="text-[10px] text-indigo-400 font-semibold mb-1.5">
                      Hersteller-Antwort{resolution.developer_reply_at ? ` vom ${resolution.developer_reply_at}` : ''}
                    </p>
                    <p className="text-slate-300 text-xs leading-relaxed">{resolution.developer_reply}</p>
                  </div>
                )}
              </>
            )
          })()}
        </div>
      )}

      {/* Similar history panel */}
      {openPanel === 'history' && (
        <div className="border-t border-white/[0.06] px-3 py-3 bg-slate-900/60 space-y-2.5">
          {loadingHist && <div className="flex items-center gap-2 text-slate-500 text-xs"><RefreshCw size={11} className="animate-spin" /> Verlauf wird geladen…</div>}
          {errorHist && <p className="text-red-400 text-xs">{errorHist}</p>}
          {history && (
            <>
              {/* Header */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[10px] font-semibold text-violet-300 bg-violet-500/10 border border-violet-500/30 px-2.5 py-1 rounded-full">
                  {history.total_similar === 0 ? 'Erstmalig' : `${history.total_similar}× früher aufgetreten`}
                </span>
                {history.has_any_reply && (
                  <span className="text-[10px] text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 rounded-full">
                    Hersteller hat mind. 1× geantwortet
                  </span>
                )}
              </div>

              {/* KI-Synthese */}
              <p className="text-slate-300 text-xs leading-relaxed">{history.synthesis}</p>

              {/* Vorkommen nach Version */}
              {history.occurrences.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-slate-600 text-[10px] font-semibold uppercase tracking-wider">
                    Vorkommen nach Version
                  </p>
                  {history.occurrences.map((o, i) => (
                    <div key={i} className="bg-slate-800/60 border border-white/[0.04] rounded-lg px-3 py-2">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="text-white text-[10px] font-mono font-medium">v{o.version ?? '?'}</span>
                        {o.date && <span className="text-slate-500 text-[10px]">{o.date}</span>}
                        <span className="text-slate-400 text-[10px]">{o.count}× gemeldet</span>
                        {o.has_reply
                          ? <span className="text-indigo-400 text-[10px] ml-auto">💬 Hersteller hat geantwortet</span>
                          : <span className="text-slate-600 text-[10px] ml-auto">Keine Antwort</span>
                        }
                      </div>
                      <p className="text-slate-400 text-[10px] leading-relaxed line-clamp-2">{o.example_content}</p>
                      {o.reply_content && (
                        <div className="mt-1.5 border-t border-white/[0.04] pt-1.5">
                          <p className="text-[10px] text-indigo-400 font-medium mb-0.5">
                            Hersteller{o.reply_at ? ` (${o.reply_at})` : ''}:
                          </p>
                          <p className="text-slate-300 text-[10px] leading-relaxed line-clamp-3">{o.reply_content}</p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function FeatureNarratives({ datasourceId }: { datasourceId: string }) {
  const [matrix, setMatrix] = useState<FeatureMatrix | null>(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    intelligenceApi.matrix(datasourceId).then(setMatrix).catch(() => {}).finally(() => setLoading(false))
  }, [datasourceId])

  if (loading) return (
    <div className="h-16 flex items-center justify-center">
      <RefreshCw size={14} className="text-slate-700 animate-spin" />
    </div>
  )

  const featuresWithNarratives = matrix?.features.filter(f => f.narrative) ?? []
  if (featuresWithNarratives.length === 0) return null

  return (
    <section>
      <div className="flex items-center gap-2 mb-4">
        <Cpu size={14} className="text-indigo-400" />
        <p className="text-slate-500 text-xs font-medium uppercase tracking-wider">Feature Intelligence</p>
        <span className="text-slate-700 text-xs ml-1">({featuresWithNarratives.length} Analysen)</span>
      </div>
      <div className="space-y-2">
        {featuresWithNarratives.map(feat => {
          const isExpanded = expanded === feat.feature
          const bugCount = feat.signal_types.find(s => s.signal_type === 'bug')?.count ?? 0
          return (
            <div key={feat.feature} className="bg-slate-900 border border-white/10 rounded-xl overflow-hidden">
              <button
                onClick={() => setExpanded(isExpanded ? null : feat.feature)}
                className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-slate-800/40 transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-6 h-6 rounded-md bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center shrink-0">
                    <Cpu size={10} className="text-indigo-400" />
                  </div>
                  <span className="text-white text-sm font-medium">{feat.feature}</span>
                  {bugCount > 0 && <span className="text-[10px] text-red-400 font-medium">{bugCount} bugs</span>}
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-slate-500 text-xs">{feat.total_mentions}×</span>
                  <ChevronDown size={12} className={`text-slate-600 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                </div>
              </button>
              {isExpanded && feat.narrative && (
                <div className="px-4 pb-4 border-t border-white/[0.05]">
                  <p className="text-slate-200 text-sm leading-relaxed mt-3">{feat.narrative}</p>
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {feat.signal_types.map(st => (
                      <span key={st.signal_type} className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${SIGNAL_COLORS[st.signal_type] ?? SIGNAL_COLORS.general}`}>
                        {SIGNAL_LABELS[st.signal_type] ?? st.signal_type} ({st.count})
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}

function IntelligenceTab({ datasourceId }: { datasourceId: string }) {
  const [matrix, setMatrix]       = useState<FeatureMatrix | null>(null)
  const [loading, setLoading]     = useState(true)
  const [selected, setSelected]   = useState<string | null>(null)

  useEffect(() => {
    intelligenceApi.matrix(datasourceId).then(setMatrix).catch(() => {}).finally(() => setLoading(false))
  }, [datasourceId])

  if (loading) return <Spinner />

  if (!matrix || matrix.features.length === 0) return (
    <div className="py-16 text-center space-y-2">
      <Cpu size={32} className="mx-auto text-slate-700" />
      <p className="text-slate-400 text-sm font-medium">Keine Intelligence-Daten verfügbar</p>
      <p className="text-slate-600 text-xs max-w-sm mx-auto">
        Die Intelligence-Pipeline läuft automatisch nach dem nächsten Scraping-Job. Starte einen neuen Job oder warte bis der aktuelle abgeschlossen ist.
      </p>
    </div>
  )

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <KpiCard label="Analysierte Sätze" value={matrix.total_sentences.toLocaleString()} />
        <KpiCard label="Extrahierte Signale" value={matrix.total_signals.toLocaleString()} />
        <KpiCard label="BERTopic Cluster" value={matrix.n_topics.toLocaleString()} />
      </div>

      {/* Feature list */}
      <div>
        <p className="text-slate-500 text-xs font-semibold uppercase tracking-wider mb-3">
          Feature-Matrix — {matrix.features.length} Features erkannt
        </p>
        <div className="space-y-2">
          {matrix.features.map(feat => {
            const bugCount = feat.signal_types.find(s => s.signal_type === 'bug')?.count ?? 0
            const resCount = feat.signal_types.find(s => s.signal_type === 'resolution')?.count ?? 0
            const sevColor = !feat.avg_severity ? 'text-slate-500'
              : feat.avg_severity >= 4 ? 'text-red-400'
              : feat.avg_severity >= 3 ? 'text-amber-400'
              : 'text-emerald-400'

            return (
              <button
                key={feat.feature}
                onClick={() => setSelected(feat.feature)}
                className="w-full text-left bg-slate-900 border border-white/10 hover:border-indigo-500/30 hover:bg-slate-800/60 rounded-xl px-4 py-3 transition-colors group"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-7 h-7 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center shrink-0">
                      <Cpu size={12} className="text-indigo-400" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-white text-sm font-medium">{feat.feature}</p>
                      {feat.narrative && (
                        <p className="text-slate-500 text-xs truncate mt-0.5 max-w-md">{feat.narrative}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    {bugCount > 0 && <span className="text-[10px] text-red-400 font-medium">{bugCount} bugs</span>}
                    {resCount > 0 && <span className="text-[10px] text-emerald-400 font-medium">{resCount} ✓</span>}
                    {feat.avg_severity && <span className={`text-xs font-semibold ${sevColor}`}>Sev {feat.avg_severity.toFixed(1)}</span>}
                    <span className="text-slate-500 text-xs">{feat.total_mentions}×</span>

                    {/* Signal type chips */}
                    <div className="hidden sm:flex gap-1">
                      {feat.signal_types.slice(0, 3).map(st => (
                        <span key={st.signal_type} className={`text-[9px] px-1.5 py-0.5 rounded-full border font-medium ${SIGNAL_COLORS[st.signal_type] ?? SIGNAL_COLORS.general}`}>
                          {st.count}
                        </span>
                      ))}
                    </div>
                    <ChevronDown size={12} className="text-slate-600 -rotate-90" />
                  </div>
                </div>

                {/* Version bar preview */}
                {feat.top_versions.length > 0 && (
                  <div className="mt-2.5 flex gap-1 items-end h-4">
                    {feat.top_versions.slice(0, 5).map((v, i) => {
                      const maxMentions = feat.top_versions[0].mention_count
                      const heightPct = Math.max(20, Math.round((v.mention_count / maxMentions) * 100))
                      return (
                        <div key={i} className="flex flex-col items-center gap-0.5 flex-1">
                          <div className="w-full bg-indigo-500/40 rounded-sm" style={{ height: `${heightPct}%` }} />
                        </div>
                      )
                    })}
                    <span className="text-[9px] text-slate-700 ml-1 self-end">{feat.top_versions.slice(0, 1).map(v => v.version)}</span>
                  </div>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Feature detail modal */}
      {selected && (
        <FeatureDetailModal
          feature={selected}
          datasourceId={datasourceId}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  )
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function KpiCard({ label, value, valueColor = 'text-white', sub }: { label: string; value: string; valueColor?: string; sub?: string }) {
  return (
    <div className="bg-slate-900 border border-white/10 rounded-xl p-4">
      <p className="text-slate-500 text-xs mb-1">{label}</p>
      <p className={`text-2xl font-bold ${valueColor}`}>{value}</p>
      {sub && <p className="text-slate-600 text-xs mt-0.5">{sub}</p>}
    </div>
  )
}

function Spinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <RefreshCw size={20} className="text-slate-600 animate-spin" />
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return <p className="text-slate-500 text-sm py-4 text-center">{text}</p>
}

// ─── Page ────────────────────────────────────────────────────────────────────

type Tab = 'overview' | 'reviews' | 'insights' | 'versions' | 'intelligence'

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'overview',     label: 'Overview',     icon: LayoutGrid },
  { id: 'reviews',      label: 'Reviews',      icon: Search },
  { id: 'insights',     label: 'Insights',     icon: Sparkles },
  { id: 'versions',     label: 'Versions',     icon: TrendingDown },
  { id: 'intelligence', label: 'Intelligence', icon: Cpu },
]

export function AppDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [tab, setTab]         = useState<Tab>('overview')
  const [ds, setDs]           = useState<DataSource | null>(null)
  const [fetchingAll, setFetchingAll] = useState(false)
  const [fetchAllMsg, setFetchAllMsg] = useState('')

  const refreshDs = () => {
    if (!id) return
    datasourceApi.list().then((list: DataSource[]) => {
      setDs(list.find((d: DataSource) => d.id === id) ?? null)
    }).catch(() => {})
  }

  useEffect(() => { refreshDs() }, [id])

  const handleFetchAll = async () => {
    if (!id || fetchingAll) return
    setFetchingAll(true)
    setFetchAllMsg('')
    try {
      await datasourceApi.fetchAll(id)
      setFetchAllMsg('Job gestartet — alle Reviews werden geladen. Das kann einige Minuten dauern.')
      refreshDs()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setFetchAllMsg(detail || 'Fehler beim Starten des Jobs.')
    } finally {
      setFetchingAll(false)
    }
  }

  if (!id) return null

  return (
    <AppShell>
      <div className="min-h-full bg-slate-950">

        {/* Top bar */}
        <div className="border-b border-white/[0.06] bg-slate-900/50">
          <div className="max-w-5xl mx-auto px-6 py-4">
            <div className="flex items-center gap-3 mb-4">
              <Link to="/datasources"
                className="flex items-center gap-1.5 text-slate-400 hover:text-white text-sm transition-colors">
                <ArrowLeft size={14} /> Data Sources
              </Link>
            </div>
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div>
                <h1 className="text-white text-xl font-bold">{ds?.name ?? '…'}</h1>
                {ds && (
                  <p className="text-slate-500 text-sm mt-0.5">
                    {ds.review_count.toLocaleString()} reviews
                    {ds.last_synced && ` · Last synced ${new Date(ds.last_synced).toLocaleDateString('de-DE')}`}
                  </p>
                )}
              </div>

              {ds?.type === 'google_play' && (
                <div className="flex flex-col items-end gap-1">
                  <button
                    onClick={handleFetchAll}
                    disabled={fetchingAll || ds.job_status === 'running' || ds.job_status === 'pending'}
                    className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
                  >
                    {fetchingAll
                      ? <><RefreshCw size={14} className="animate-spin" /> Wird gestartet…</>
                      : <><Download size={14} /> Alle Reviews laden</>
                    }
                  </button>
                  {fetchAllMsg && (
                    <p className="text-xs text-slate-400 max-w-xs text-right">{fetchAllMsg}</p>
                  )}
                </div>
              )}
            </div>

            {/* Tabs */}
            <div className="flex gap-1 mt-5 -mb-px">
              {TABS.map(t => {
                const Icon = t.icon
                const active = tab === t.id
                return (
                  <button key={t.id} onClick={() => setTab(t.id)}
                    className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors
                      ${active
                        ? 'border-indigo-500 text-white'
                        : 'border-transparent text-slate-400 hover:text-white'}`}
                  >
                    <Icon size={14} />
                    {t.label}
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        {/* Tab content */}
        <div className="max-w-5xl mx-auto px-6 py-8">
          {tab === 'overview'     && <OverviewTab     datasourceId={id} />}
          {tab === 'reviews'      && <ReviewsTab      datasourceId={id} />}
          {tab === 'insights'     && <InsightsTab     datasourceId={id} />}
          {tab === 'versions'     && <VersionsTab     datasourceId={id} />}
          {tab === 'intelligence' && <IntelligenceTab datasourceId={id} />}
        </div>
      </div>
    </AppShell>
  )
}
