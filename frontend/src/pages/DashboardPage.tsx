import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { AppShell } from '../components/AppShell'
import { dashboardApi } from '../services/api'
import { RefreshCw, Target, ChevronRight, AlertTriangle, TrendingDown, TrendingUp, Minus } from 'lucide-react'

// ─── Types ───────────────────────────────────────────────────────────────────

interface Sentiment { positive: number; negative: number; neutral: number; total: number }

interface AppData {
  id: string
  name: string
  country: string
  review_count: number
  avg_rating: number | null
  sentiment: Sentiment
  negative_pct: number
  opportunity_score: number
  top_issue: string | null
  top_issue_mentions: number
}

interface PainPoint {
  label: string
  affected_apps: string[]
  app_count: number
  total_mentions: number
  opportunity_score: number
  is_market_issue: boolean
}

interface IndustryGroup {
  industry: string
  industry_label: string
  apps: AppData[]
  market_pain_points: PainPoint[]
}

interface Report { groups: IndustryGroup[] }

// ─── Helpers ─────────────────────────────────────────────────────────────────

function countryFlag(code: string): string {
  if (!code || code.length !== 2) return '🌐'
  return [...code.toUpperCase()].map(c => String.fromCodePoint(c.charCodeAt(0) + 127397)).join('')
}

function healthColor(app: AppData): 'green' | 'yellow' | 'red' {
  if (app.negative_pct >= 35 || (app.avg_rating !== null && app.avg_rating < 3.5)) return 'red'
  if (app.negative_pct >= 20 || (app.avg_rating !== null && app.avg_rating < 4.0)) return 'yellow'
  return 'green'
}

const HEALTH_DOT: Record<string, string> = {
  green:  'bg-emerald-400',
  yellow: 'bg-amber-400',
  red:    'bg-red-400',
}

const HEALTH_RING: Record<string, string> = {
  green:  'ring-emerald-400/20',
  yellow: 'ring-amber-400/20',
  red:    'ring-red-400/20',
}

// ─── KPI Tile ────────────────────────────────────────────────────────────────

function KpiTile({ label, value, sub, trend }: {
  label: string
  value: string | number
  sub?: string
  trend?: 'up' | 'down' | 'neutral'
}) {
  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus
  const trendColor = trend === 'up' ? 'text-emerald-400' : trend === 'down' ? 'text-red-400' : 'text-slate-500'
  return (
    <div className="bg-slate-900 border border-white/10 rounded-xl p-4">
      <p className="text-slate-500 text-xs font-medium uppercase tracking-wider mb-2">{label}</p>
      <p className="text-white text-2xl font-bold tracking-tight">{value}</p>
      {sub && (
        <div className={`flex items-center gap-1 mt-1.5 ${trendColor}`}>
          {trend && <TrendIcon size={11} />}
          <span className="text-xs">{sub}</span>
        </div>
      )}
    </div>
  )
}

// ─── App Health Row ───────────────────────────────────────────────────────────

function AppHealthRow({ app, maxScore }: { app: AppData; maxScore: number }) {
  const health = healthColor(app)
  const posPct = app.sentiment.total > 0
    ? Math.round((app.sentiment.positive / app.sentiment.total) * 100)
    : 0
  const negPct = app.sentiment.total > 0
    ? Math.round((app.sentiment.negative / app.sentiment.total) * 100)
    : 0
  const barW = maxScore > 0 ? Math.round((app.opportunity_score / maxScore) * 100) : 0

  return (
    <Link to={`/datasources/${app.id}`}
      className="flex items-center gap-4 px-4 py-3 hover:bg-slate-800/50 transition-colors group">

      {/* Health dot */}
      <div className={`w-2 h-2 rounded-full shrink-0 ${HEALTH_DOT[health]} ring-2 ${HEALTH_RING[health]}`} />

      {/* Name + flag */}
      <div className="w-40 shrink-0 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-white text-sm font-medium truncate group-hover:text-indigo-300 transition-colors">
            {app.name}
          </span>
          <span className="text-base leading-none shrink-0">{countryFlag(app.country)}</span>
        </div>
        <p className="text-slate-600 text-xs">{app.review_count.toLocaleString()} Reviews</p>
      </div>

      {/* Sentiment bar */}
      <div className="flex-1 min-w-0 hidden sm:block">
        <div className="flex h-1.5 rounded-full overflow-hidden bg-slate-800 gap-px">
          <div className="bg-emerald-500 rounded-full transition-all" style={{ width: `${posPct}%` }} />
          <div className="bg-red-500 rounded-full transition-all"     style={{ width: `${negPct}%` }} />
        </div>
        <div className="flex gap-3 mt-1">
          <span className="text-[10px] text-emerald-400">{posPct}% pos</span>
          <span className="text-[10px] text-red-400">{negPct}% neg</span>
        </div>
      </div>

      {/* Stars */}
      <div className="w-16 shrink-0 text-right hidden md:block">
        {app.avg_rating ? (
          <>
            <span className="text-amber-400 text-sm font-semibold">{app.avg_rating.toFixed(1)}</span>
            <span className="text-amber-400/60 text-xs"> ★</span>
          </>
        ) : (
          <span className="text-slate-600 text-xs">—</span>
        )}
      </div>

      {/* Opportunity bar */}
      <div className="w-28 shrink-0 hidden lg:block">
        <div className="h-1 rounded-full bg-slate-800 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              health === 'red' ? 'bg-red-500' : health === 'yellow' ? 'bg-amber-500' : 'bg-emerald-500'
            }`}
            style={{ width: `${barW}%` }}
          />
        </div>
      </div>

      {/* Top issue */}
      <div className="flex-1 min-w-0 hidden md:block">
        {app.top_issue ? (
          <span className="text-slate-500 text-xs truncate flex items-center gap-1">
            <TrendingDown size={10} className="text-red-400 shrink-0" />
            {app.top_issue}
            <span className="text-slate-700 shrink-0">· {app.top_issue_mentions}×</span>
          </span>
        ) : (
          <span className="text-slate-700 text-xs">—</span>
        )}
      </div>

      <ChevronRight size={13} className="text-slate-700 group-hover:text-indigo-400 transition-colors shrink-0" />
    </Link>
  )
}

// ─── Empty State ─────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="bg-slate-900 border border-white/10 rounded-2xl p-12 text-center">
      <Target size={36} className="text-slate-700 mx-auto mb-4" />
      <p className="text-white text-sm font-medium mb-1">Noch keine Daten</p>
      <p className="text-slate-500 text-sm mb-4">
        Füge Apps unter Datenquellen hinzu, um die Analyse zu starten.
      </p>
      <Link to="/datasources"
        className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
        Erste App hinzufügen
      </Link>
    </div>
  )
}

// ─── Page ────────────────────────────────────────────────────────────────────

export function DashboardPage() {
  const [report, setReport]               = useState<Report | null>(null)
  const [loading, setLoading]             = useState(true)
  const [error, setError]                 = useState('')
  const [activeIndustry, setActiveIndustry] = useState<string>('')
  const [countryFilter, setCountryFilter] = useState<string>('')

  useEffect(() => {
    dashboardApi.competitive()
      .then((r: Report) => {
        setReport(r)
        if (r.groups.length > 0) setActiveIndustry(r.groups[0].industry)
      })
      .catch(() => setError('Dashboard konnte nicht geladen werden.'))
      .finally(() => setLoading(false))
  }, [])

  const group = report?.groups.find(g => g.industry === activeIndustry) ?? report?.groups[0]
  const hasMultiIndustry = (report?.groups.length ?? 0) > 1

  const filteredApps = countryFilter
    ? (group?.apps ?? []).filter(a => a.country === countryFilter)
    : (group?.apps ?? [])

  const availableCountries = [...new Set((group?.apps ?? []).map(a => a.country))].sort()

  // KPI aggregates
  const totalReviews   = filteredApps.reduce((s, a) => s + a.review_count, 0)
  const avgRating      = (() => {
    const rated = filteredApps.filter(a => a.avg_rating !== null)
    if (!rated.length) return null
    return (rated.reduce((s, a) => s + a.avg_rating!, 0) / rated.length)
  })()
  const avgNegPct      = filteredApps.length
    ? Math.round(filteredApps.reduce((s, a) => s + a.negative_pct, 0) / filteredApps.length)
    : 0
  const maxScore       = filteredApps.length ? Math.max(...filteredApps.map(a => a.opportunity_score), 1) : 1
  const maxPainScore   = group ? Math.max(...group.market_pain_points.map(p => p.opportunity_score), 1) : 1

  const sortedApps = [...filteredApps].sort((a, b) => b.opportunity_score - a.opportunity_score)
  const branchenProbleme = (group?.market_pain_points ?? []).filter(p => p.is_market_issue)
  const appSpezifisch    = (group?.market_pain_points ?? []).filter(p => !p.is_market_issue)

  return (
    <AppShell>
      <div className="min-h-full bg-slate-950 p-6 max-w-5xl mx-auto">

        {/* Header */}
        <div className="mb-6 flex items-end justify-between">
          <div>
            <h1 className="text-white text-2xl font-bold">Dashboard</h1>
            <p className="text-slate-500 text-sm mt-0.5">Review-Intelligenz auf einen Blick</p>
          </div>
          {hasMultiIndustry && (
            <div className="flex gap-1 bg-slate-900 border border-white/10 rounded-xl p-1">
              {report!.groups.map(g => (
                <button key={g.industry}
                  onClick={() => { setActiveIndustry(g.industry); setCountryFilter('') }}
                  className={`py-1.5 px-3 text-xs font-medium rounded-lg transition-colors ${
                    activeIndustry === g.industry
                      ? 'bg-indigo-600 text-white'
                      : 'text-slate-400 hover:text-white'
                  }`}>
                  {g.industry_label}
                  <span className="ml-1 opacity-50">{g.apps.length}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-24">
            <RefreshCw size={22} className="text-slate-600 animate-spin" />
          </div>
        ) : error ? (
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-6 text-center">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        ) : !report || report.groups.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="space-y-8">

            {/* ── KPI Tiles ── */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <KpiTile
                label="Reviews gesamt"
                value={totalReviews.toLocaleString()}
                sub={`${filteredApps.length} App${filteredApps.length !== 1 ? 's' : ''}`}
                trend="neutral"
              />
              <KpiTile
                label="Ø Bewertung"
                value={avgRating ? `${avgRating.toFixed(1)} ★` : '—'}
                trend={avgRating && avgRating >= 4.0 ? 'up' : 'down'}
              />
              <KpiTile
                label="Negativ-Quote"
                value={`${avgNegPct}%`}
                sub={avgNegPct >= 30 ? 'Kritisch' : avgNegPct >= 20 ? 'Erhöht' : 'Gut'}
                trend={avgNegPct >= 30 ? 'down' : avgNegPct >= 20 ? 'neutral' : 'up'}
              />
              <KpiTile
                label="Marktprobleme"
                value={branchenProbleme.length}
                sub={branchenProbleme.length > 0 ? 'Branchenübergreifend' : 'Keine'}
                trend={branchenProbleme.length > 3 ? 'down' : 'neutral'}
              />
            </div>

            {/* ── Country filter ── */}
            {availableCountries.length > 1 && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-slate-600 text-xs">Markt:</span>
                <button
                  onClick={() => setCountryFilter('')}
                  className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                    !countryFilter
                      ? 'bg-indigo-600 border-indigo-500 text-white'
                      : 'border-white/10 text-slate-400 hover:text-white'
                  }`}>
                  Alle
                </button>
                {availableCountries.map(c => (
                  <button key={c}
                    onClick={() => setCountryFilter(c === countryFilter ? '' : c)}
                    className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                      countryFilter === c
                        ? 'bg-indigo-600 border-indigo-500 text-white'
                        : 'border-white/10 text-slate-400 hover:text-white'
                    }`}>
                    {countryFlag(c)} {c.toUpperCase()}
                  </button>
                ))}
              </div>
            )}

            {/* ── App Health List ── */}
            {sortedApps.length > 0 && (
              <section>
                <div className="flex items-center gap-3 mb-1 px-4">
                  <p className="text-slate-600 text-xs font-semibold uppercase tracking-widest flex-1">Apps</p>
                  <p className="text-slate-700 text-[10px] hidden sm:block w-32 text-center">Sentiment</p>
                  <p className="text-slate-700 text-[10px] hidden md:block w-16 text-right">Rating</p>
                  <p className="text-slate-700 text-[10px] hidden lg:block w-28 text-center">Chance</p>
                  <p className="text-slate-700 text-[10px] hidden md:block flex-1">Top-Problem</p>
                  <div className="w-4" />
                </div>
                <div className="bg-slate-900 border border-white/10 rounded-xl overflow-hidden divide-y divide-white/[0.05]">
                  {sortedApps.map(app => (
                    <AppHealthRow key={app.id} app={app} maxScore={maxScore} />
                  ))}
                </div>
                {/* Legend */}
                <div className="flex items-center gap-4 mt-2 px-2">
                  {[
                    { dot: 'bg-emerald-400', label: 'Gut (neg < 20%, ★ ≥ 4.0)' },
                    { dot: 'bg-amber-400',   label: 'Mittel (neg 20–35%)' },
                    { dot: 'bg-red-400',     label: 'Kritisch (neg ≥ 35% oder ★ < 3.5)' },
                  ].map(({ dot, label }) => (
                    <div key={label} className="flex items-center gap-1.5">
                      <div className={`w-2 h-2 rounded-full ${dot}`} />
                      <span className="text-[10px] text-slate-600">{label}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* ── Market Patterns ── */}
            {(branchenProbleme.length > 0 || appSpezifisch.length > 0) && (
              <section>
                <div className="flex items-center gap-2 mb-3">
                  <AlertTriangle size={14} className="text-amber-400" />
                  <p className="text-slate-300 text-sm font-semibold">Branchenweite Muster</p>
                  <span className="text-slate-600 text-xs">
                    — {group!.industry_label} · {new Set(group!.market_pain_points.flatMap(p => p.affected_apps)).size} Apps
                  </span>
                </div>

                <div className="bg-slate-900 border border-white/10 rounded-xl overflow-hidden">

                  {/* Cross-app issues */}
                  {branchenProbleme.length > 0 && (
                    <div>
                      <div className="px-4 py-2 border-b border-white/[0.05] bg-amber-400/5">
                        <p className="text-amber-400/80 text-[10px] font-semibold uppercase tracking-widest">
                          Branchenprobleme · ≥ 2 Apps betroffen
                        </p>
                      </div>
                      <div className="divide-y divide-white/[0.04]">
                        {branchenProbleme.map((p, i) => (
                          <PainRow key={i} p={p} maxScore={maxPainScore} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* App-specific */}
                  {appSpezifisch.length > 0 && (
                    <div className={branchenProbleme.length > 0 ? 'border-t border-white/[0.06]' : ''}>
                      <div className="px-4 py-2 border-b border-white/[0.05]">
                        <p className="text-slate-500 text-[10px] font-semibold uppercase tracking-widest">
                          App-spezifisch · nur 1 App betroffen
                        </p>
                      </div>
                      <div className="divide-y divide-white/[0.04]">
                        {appSpezifisch.map((p, i) => (
                          <PainRow key={i} p={p} maxScore={maxPainScore} />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </section>
            )}

          </div>
        )}
      </div>
    </AppShell>
  )
}

function PainRow({ p, maxScore }: { p: PainPoint; maxScore: number }) {
  const pct = maxScore > 0 ? (p.opportunity_score / maxScore) * 100 : 0
  const urgency = pct > 70 ? 'text-red-400' : pct > 40 ? 'text-amber-400' : 'text-slate-500'

  return (
    <div className="px-4 py-3 flex items-center gap-4 hover:bg-white/[0.02] transition-colors">
      <div className="flex-1 min-w-0">
        <p className="text-white text-sm font-medium">{p.label}</p>
        <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
          {p.affected_apps.map(app => (
            <span key={app} className="text-[10px] text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded-full">{app}</span>
          ))}
        </div>
      </div>
      <div className="text-right shrink-0">
        <p className={`text-sm font-semibold ${urgency}`}>{p.total_mentions.toLocaleString()}×</p>
        <p className="text-slate-600 text-[10px]">{p.app_count} App{p.app_count !== 1 ? 's' : ''}</p>
      </div>
      <div className="w-16 shrink-0 hidden sm:block">
        <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${pct > 70 ? 'bg-red-500' : pct > 40 ? 'bg-amber-500' : 'bg-slate-600'}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  )
}
