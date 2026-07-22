import { useState, useEffect } from 'react'
import { AppShell } from '../components/AppShell'
import { datasourceApi, dashboardApi } from '../services/api'
import { Link } from 'react-router-dom'
import { TrendingUp, TrendingDown, Star, MessageSquare, Lightbulb, ChevronDown, AlertCircle } from 'lucide-react'

interface Cluster { id: string; label: string; mentions: number; summary: string; examples: string[] }
interface Sentiment { positive: number; negative: number; neutral: number; total: number }
interface Summary {
  datasource_name: string
  review_count: number
  avg_rating: number | null
  sentiment: Sentiment
  top_issues: Cluster[]
  top_strengths: Cluster[]
}

function KpiCard({ label, value, sub, icon, color }: { label: string; value: string; sub?: string; icon: React.ReactNode; color: string }) {
  return (
    <div className="bg-slate-900 border border-white/10 rounded-xl p-4">
      <div className="flex items-start justify-between mb-3">
        <p className="text-slate-400 text-xs font-medium uppercase tracking-wider">{label}</p>
        <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${color}`}>{icon}</div>
      </div>
      <p className="text-white text-2xl font-bold">{value}</p>
      {sub && <p className="text-slate-500 text-xs mt-1">{sub}</p>}
    </div>
  )
}

function ClusterCard({ cluster, type }: { cluster: Cluster; type: 'issue' | 'strength' }) {
  const [open, setOpen] = useState(false)
  const isIssue = type === 'issue'
  return (
    <div className="bg-slate-900 border border-white/10 rounded-xl overflow-hidden">
      <button onClick={() => setOpen(o => !o)} className="w-full flex items-center justify-between p-4 text-left hover:bg-white/5 transition-colors">
        <div className="flex items-center gap-3 min-w-0">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${isIssue ? 'bg-red-500/10 text-red-400' : 'bg-emerald-500/10 text-emerald-400'}`}>
            {isIssue ? <TrendingDown size={14} /> : <TrendingUp size={14} />}
          </div>
          <div className="min-w-0">
            <p className="text-white text-sm font-medium truncate">{cluster.label}</p>
            <p className="text-slate-500 text-xs">{cluster.summary}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0 ml-3">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${isIssue ? 'bg-red-500/10 text-red-400' : 'bg-emerald-500/10 text-emerald-400'}`}>
            {cluster.mentions}
          </span>
          <ChevronDown size={14} className={`text-slate-500 transition-transform ${open ? 'rotate-180' : ''}`} />
        </div>
      </button>
      {open && cluster.examples?.length > 0 && (
        <div className="border-t border-white/5 px-4 py-3 space-y-2">
          {cluster.examples.slice(0, 3).map((ex, i) => (
            <p key={i} className="text-slate-400 text-xs leading-relaxed border-l-2 border-white/10 pl-3">"{ex}"</p>
          ))}
        </div>
      )}
    </div>
  )
}

export function DashboardPage() {
  const [sources, setSources] = useState<{ id: string; name: string }[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [summary, setSummary] = useState<Summary | null>(null)
  const [insight, setInsight] = useState<{ insight: string; generated_by: string } | null>(null)
  const [loadingData, setLoadingData] = useState(false)

  useEffect(() => {
    datasourceApi.list().then((list: any[]) => {
      const done = list.filter(d => d.job_status === 'done')
      setSources(done)
      if (done.length > 0) setSelectedId(done[0].id)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedId) return
    setLoadingData(true)
    Promise.all([
      dashboardApi.summary(selectedId),
      dashboardApi.insight(selectedId),
    ]).then(([s, i]) => {
      setSummary(s)
      setInsight(i)
    }).catch(() => {}).finally(() => setLoadingData(false))
  }, [selectedId])

  if (sources.length === 0) {
    return (
      <AppShell>
        <div className="p-6 flex flex-col items-center justify-center h-full text-center">
          <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-4">
            <MessageSquare size={28} className="text-indigo-400" />
          </div>
          <h2 className="text-white text-xl font-bold mb-2">No data yet</h2>
          <p className="text-slate-400 text-sm mb-6 max-w-xs">Connect a Google Play app or upload a CSV to get AI-powered insights from your customer reviews.</p>
          <Link to="/datasources" className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
            Connect Data Source
          </Link>
        </div>
      </AppShell>
    )
  }

  const pctPos = summary ? Math.round((summary.sentiment.positive / summary.sentiment.total) * 100) : 0
  const pctNeg = summary ? Math.round((summary.sentiment.negative / summary.sentiment.total) * 100) : 0

  return (
    <AppShell>
      <div className="p-6 max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-white text-2xl font-bold">Product Intelligence</h1>
            <p className="text-slate-400 text-sm mt-1">AI-powered insights from customer reviews</p>
          </div>
          <select
            value={selectedId}
            onChange={e => setSelectedId(e.target.value)}
            className="bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500">
            {sources.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>

        {loadingData ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : summary ? (
          <>
            {/* KPIs */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <KpiCard label="Reviews" value={summary.review_count.toLocaleString()} icon={<MessageSquare size={14} />} color="bg-indigo-500/10 text-indigo-400" />
              <KpiCard label="Avg Rating" value={summary.avg_rating ? `${summary.avg_rating} ★` : '—'} icon={<Star size={14} />} color="bg-amber-500/10 text-amber-400" />
              <KpiCard label="Positive" value={`${pctPos}%`} sub={`${summary.sentiment.positive} reviews`} icon={<TrendingUp size={14} />} color="bg-emerald-500/10 text-emerald-400" />
              <KpiCard label="Negative" value={`${pctNeg}%`} sub={`${summary.sentiment.negative} reviews`} icon={<TrendingDown size={14} />} color="bg-red-500/10 text-red-400" />
            </div>

            {/* Sentiment bar */}
            <div className="bg-slate-900 border border-white/10 rounded-xl p-4 mb-6">
              <div className="flex items-center justify-between mb-2">
                <p className="text-slate-400 text-xs font-medium uppercase tracking-wider">Sentiment Distribution</p>
                <p className="text-slate-500 text-xs">{summary.sentiment.total} total</p>
              </div>
              <div className="flex rounded-full overflow-hidden h-2.5 gap-0.5">
                <div className="bg-emerald-500 transition-all" style={{ width: `${pctPos}%` }} />
                <div className="bg-slate-600 transition-all" style={{ width: `${100 - pctPos - pctNeg}%` }} />
                <div className="bg-red-500 transition-all" style={{ width: `${pctNeg}%` }} />
              </div>
              <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />Positive {pctPos}%</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-slate-600 inline-block" />Neutral {100 - pctPos - pctNeg}%</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500 inline-block" />Negative {pctNeg}%</span>
              </div>
            </div>

            {/* Issues + Strengths */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <AlertCircle size={14} className="text-red-400" />
                  <h2 className="text-white text-sm font-semibold">Top Issues</h2>
                  <span className="text-slate-500 text-xs">({summary.top_issues.length})</span>
                </div>
                <div className="space-y-2">
                  {summary.top_issues.length > 0
                    ? summary.top_issues.map(c => <ClusterCard key={c.id} cluster={c} type="issue" />)
                    : <p className="text-slate-500 text-sm">No issues detected.</p>}
                </div>
              </div>
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <TrendingUp size={14} className="text-emerald-400" />
                  <h2 className="text-white text-sm font-semibold">Top Strengths</h2>
                  <span className="text-slate-500 text-xs">({summary.top_strengths.length})</span>
                </div>
                <div className="space-y-2">
                  {summary.top_strengths.length > 0
                    ? summary.top_strengths.map(c => <ClusterCard key={c.id} cluster={c} type="strength" />)
                    : <p className="text-slate-500 text-sm">No strengths detected.</p>}
                </div>
              </div>
            </div>

            {/* AI Insight */}
            {insight && (
              <div className="bg-indigo-500/5 border border-indigo-500/20 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Lightbulb size={14} className="text-indigo-400" />
                  <p className="text-indigo-300 text-xs font-semibold uppercase tracking-wider">AI Insight</p>
                  <span className="text-slate-600 text-xs ml-auto">{insight.generated_by}</span>
                </div>
                <p className="text-slate-300 text-sm leading-relaxed">{insight.insight}</p>
              </div>
            )}
          </>
        ) : null}
      </div>
    </AppShell>
  )
}
