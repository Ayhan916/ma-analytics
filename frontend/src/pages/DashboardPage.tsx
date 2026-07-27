import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { AppShell } from '../components/AppShell'
import { dashboardApi } from '../services/api'
import { TrendingDown, Target, RefreshCw, ChevronRight, AlertTriangle, Globe } from 'lucide-react'

// ─── Types ───────────────────────────────────────────────────────────────────

interface Sentiment { positive: number; negative: number; neutral: number; total: number }

interface AppData {
  id: string
  name: string
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

interface Report { apps: AppData[]; market_pain_points: PainPoint[] }

// ─── Helpers ─────────────────────────────────────────────────────────────────

function RatingStars({ rating }: { rating: number | null }) {
  if (!rating) return <span className="text-slate-600 text-xs">—</span>
  const full = Math.round(rating)
  return (
    <span className="text-amber-400 text-sm tracking-tight">
      {'★'.repeat(full)}{'☆'.repeat(5 - full)}
      <span className="text-slate-400 text-xs ml-1">{rating.toFixed(1)}</span>
    </span>
  )
}

function SentimentBar({ s }: { s: Sentiment }) {
  const total = s.total || 1
  const pos = Math.round((s.positive / total) * 100)
  const neu = Math.round((s.neutral  / total) * 100)
  const neg = Math.round((s.negative / total) * 100)
  return (
    <div className="space-y-1">
      <div className="flex h-1.5 rounded-full overflow-hidden gap-px">
        <div className="bg-emerald-500 rounded-full" style={{ width: `${pos}%` }} />
        <div className="bg-slate-600 rounded-full"   style={{ width: `${neu}%` }} />
        <div className="bg-red-500 rounded-full"     style={{ width: `${neg}%` }} />
      </div>
      <div className="flex gap-3 text-[10px] text-slate-500">
        <span><span className="text-emerald-400">●</span> {pos}%</span>
        <span><span className="text-red-400">●</span> {neg}%</span>
      </div>
    </div>
  )
}

function OpportunityBadge({ score, max }: { score: number; max: number }) {
  const pct = max > 0 ? score / max : 0
  const color = pct > 0.7 ? 'text-red-400 bg-red-400/10 border-red-400/20'
              : pct > 0.4 ? 'text-amber-400 bg-amber-400/10 border-amber-400/20'
              :              'text-slate-400 bg-slate-400/10 border-slate-400/20'
  const label = pct > 0.7 ? 'Hoch' : pct > 0.4 ? 'Mittel' : 'Niedrig'
  return (
    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${color}`}>
      {label}
    </span>
  )
}

function EmptyState() {
  return (
    <div className="bg-slate-900 border border-white/10 rounded-2xl p-12 text-center">
      <Target size={36} className="text-slate-700 mx-auto mb-4" />
      <p className="text-white text-sm font-medium mb-1">Noch keine Wettbewerbsdaten</p>
      <p className="text-slate-500 text-sm mb-4">
        Füge Wettbewerber-Apps unter Datenquellen hinzu, um die Analyse zu starten.
      </p>
      <Link to="/datasources"
        className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
        Ersten Wettbewerber hinzufügen
      </Link>
    </div>
  )
}

// ─── Section 1: Competitive Ranking ──────────────────────────────────────────

function CompetitiveRanking({ apps, maxScore }: { apps: AppData[]; maxScore: number }) {
  return (
    <section>
      <div className="flex items-center gap-2 mb-4">
        <TrendingDown size={15} className="text-red-400" />
        <h2 className="text-white text-sm font-semibold">Wettbewerbsranking</h2>
        <span className="text-slate-500 text-xs">— sortiert nach Marktchance</span>
      </div>

      <div className="space-y-2">
        {apps.map((app, i) => (
          <Link key={app.id} to={`/datasources/${app.id}`}
            className="flex items-center gap-4 bg-slate-900 border border-white/10 hover:border-indigo-500/40 hover:bg-slate-800/60 rounded-xl px-4 py-3.5 transition-all group">

            <span className="text-slate-600 text-sm font-mono w-5 shrink-0">#{i + 1}</span>

            <div className="flex-1 min-w-0">
              <p className="text-white text-sm font-medium group-hover:text-indigo-300 transition-colors">
                {app.name}
              </p>
              {app.top_issue && (
                <p className="text-slate-500 text-xs mt-0.5 truncate">
                  Häufigstes Problem: {app.top_issue}
                </p>
              )}
            </div>

            <div className="shrink-0 hidden sm:block">
              <RatingStars rating={app.avg_rating} />
            </div>

            <div className="w-24 shrink-0 hidden md:block">
              <SentimentBar s={app.sentiment} />
            </div>

            <div className="text-right shrink-0 hidden sm:block">
              <p className="text-white text-sm font-medium">{app.review_count.toLocaleString()}</p>
              <p className="text-slate-500 text-xs">Bewertungen</p>
            </div>

            <OpportunityBadge score={app.opportunity_score} max={maxScore} />

            <ChevronRight size={14} className="text-slate-600 group-hover:text-indigo-400 transition-colors shrink-0" />
          </Link>
        ))}
      </div>
    </section>
  )
}

// ─── Section 2: Market Pain Points ───────────────────────────────────────────

function PainPointTable({
  points,
  maxScore,
  borderClass,
}: {
  points: PainPoint[]
  maxScore: number
  borderClass: string
}) {
  return (
    <div className={`bg-slate-900 border ${borderClass} rounded-xl overflow-hidden`}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/[0.06]">
            <th className="text-left text-slate-500 text-xs font-medium uppercase tracking-wider px-4 py-3">Problem</th>
            <th className="text-left text-slate-500 text-xs font-medium uppercase tracking-wider px-4 py-3 hidden sm:table-cell">Betroffene Apps</th>
            <th className="text-right text-slate-500 text-xs font-medium uppercase tracking-wider px-4 py-3">Erwähnungen</th>
            <th className="text-right text-slate-500 text-xs font-medium uppercase tracking-wider px-4 py-3 hidden md:table-cell">Chance</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.04]">
          {points.map((p, i) => (
            <tr key={i} className="hover:bg-white/[0.02] transition-colors">
              <td className="px-4 py-3">
                <span className="text-white font-medium">{p.label}</span>
              </td>
              <td className="px-4 py-3 hidden sm:table-cell">
                <div className="flex flex-wrap gap-1">
                  {p.affected_apps.map(app => (
                    <span key={app} className="text-slate-400 text-xs bg-slate-800 px-2 py-0.5 rounded-full">{app}</span>
                  ))}
                </div>
              </td>
              <td className="px-4 py-3 text-right">
                <span className="text-red-400 font-semibold">{p.total_mentions.toLocaleString()}</span>
                <div className="text-slate-500 text-[10px]">{p.app_count} App{p.app_count !== 1 ? 's' : ''}</div>
              </td>
              <td className="px-4 py-3 text-right hidden md:table-cell">
                <OpportunityBadge score={p.opportunity_score} max={maxScore} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function MarketPainPoints({ points, maxScore }: { points: PainPoint[]; maxScore: number }) {
  const branchenProbleme = points.filter(p => p.is_market_issue)
  const appSpezifisch    = points.filter(p => !p.is_market_issue)

  return (
    <section>
      <div className="flex items-center gap-2 mb-1">
        <AlertTriangle size={15} className="text-amber-400" />
        <h2 className="text-white text-sm font-semibold">Markt-Schmerzpunkte</h2>
        <span className="text-slate-500 text-xs">— branchenweite Probleme der Automobilbranche</span>
      </div>

      <div className="mb-3 flex items-center gap-2">
        <Globe size={12} className="text-slate-600" />
        <span className="text-slate-600 text-xs">
          Aggregiert über alle {new Set(points.flatMap(p => p.affected_apps)).size} Apps ·&nbsp;
          <span className="text-amber-400/80">{branchenProbleme.length} Branchenprobleme</span>
          &nbsp;·&nbsp;
          <span className="text-slate-500">{appSpezifisch.length} App-spezifisch</span>
        </span>
      </div>

      {branchenProbleme.length > 0 && (
        <div className="mb-4">
          <p className="text-slate-500 text-[10px] font-medium uppercase tracking-widest mb-2">
            Branchenprobleme · in ≥ 2 Apps
          </p>
          <PainPointTable points={branchenProbleme} maxScore={maxScore} borderClass="border-amber-500/20" />
        </div>
      )}

      {appSpezifisch.length > 0 && (
        <div>
          <p className="text-slate-500 text-[10px] font-medium uppercase tracking-widest mb-2">
            App-spezifische Schwächen · nur in 1 App
          </p>
          <PainPointTable points={appSpezifisch} maxScore={maxScore} borderClass="border-white/10" />
        </div>
      )}
    </section>
  )
}

// ─── Section 3: Opportunity Score ────────────────────────────────────────────

function OpportunityScores({ apps, maxScore }: { apps: AppData[]; maxScore: number }) {
  return (
    <section>
      <div className="flex items-center gap-2 mb-4">
        <Target size={15} className="text-indigo-400" />
        <h2 className="text-white text-sm font-semibold">Chancen-Score</h2>
        <span className="text-slate-500 text-xs">— wo zuerst angreifen</span>
      </div>

      <div className="space-y-3">
        {apps.map(app => {
          const pct = maxScore > 0 ? (app.opportunity_score / maxScore) * 100 : 0
          const barColor = pct > 70 ? 'bg-red-500' : pct > 40 ? 'bg-amber-500' : 'bg-slate-600'
          return (
            <Link key={app.id} to={`/datasources/${app.id}`}
              className="block bg-slate-900 border border-white/10 hover:border-white/20 rounded-xl p-4 transition-all group">
              <div className="flex items-center justify-between mb-2">
                <span className="text-white text-sm font-medium group-hover:text-indigo-300 transition-colors">
                  {app.name}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-slate-400 text-xs">{app.negative_pct}% negativ</span>
                  <span className="text-white text-sm font-bold">{app.opportunity_score.toLocaleString()}</span>
                </div>
              </div>
              <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${pct}%` }} />
              </div>
              {app.top_issue && (
                <p className="text-slate-500 text-xs mt-2">
                  <TrendingDown size={10} className="inline mr-1 text-red-400" />
                  {app.top_issue} ({app.top_issue_mentions} Erwähnungen)
                </p>
              )}
            </Link>
          )
        })}
      </div>

      <div className="mt-4 bg-slate-900/50 border border-white/[0.06] rounded-xl p-4">
        <p className="text-slate-500 text-xs leading-relaxed">
          <span className="text-slate-300 font-medium">Berechnung: </span>
          Der Chancen-Score kombiniert Negativbewertungsrate × Anzahl der Beschwerden × Bewertungslücke zum Maximum.
          Höherer Score = mehr unzufriedene Nutzer + mehr Erwähnungen + schlechtere Bewertung = größere Marktlücke.
        </p>
      </div>
    </section>
  )
}

// ─── Page ────────────────────────────────────────────────────────────────────

export function DashboardPage() {
  const [report, setReport]   = useState<Report | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')

  useEffect(() => {
    dashboardApi.competitive()
      .then(setReport)
      .catch(() => setError('Dashboard konnte nicht geladen werden. Bitte Seite neu laden.'))
      .finally(() => setLoading(false))
  }, [])

  const maxAppScore   = report ? Math.max(...report.apps.map(a => a.opportunity_score), 1)                   : 1
  const maxPointScore = report ? Math.max(...report.market_pain_points.map(p => p.opportunity_score), 1) : 1

  return (
    <AppShell>
      <div className="min-h-full bg-slate-950 p-6 max-w-5xl mx-auto">

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-white text-2xl font-bold">Wettbewerbsanalyse</h1>
          <p className="text-slate-400 text-sm mt-1">
            Wo Wettbewerber scheitern — und wo du gewinnen kannst.
          </p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-24">
            <RefreshCw size={22} className="text-slate-600 animate-spin" />
          </div>
        ) : error ? (
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-6 text-center">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        ) : !report || report.apps.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="space-y-10">
            <CompetitiveRanking apps={report.apps} maxScore={maxAppScore} />
            {report.market_pain_points.length > 0 && (
              <MarketPainPoints points={report.market_pain_points} maxScore={maxPointScore} />
            )}
            <OpportunityScores apps={report.apps} maxScore={maxAppScore} />
          </div>
        )}
      </div>
    </AppShell>
  )
}
