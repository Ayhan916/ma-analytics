import React, { useState, useEffect, useCallback } from 'react'
import { AppShell } from '../components/AppShell'
import { datasourceApi, innovationApi } from '../services/api'
import {
  Lightbulb, Zap, Target, Users, ShieldAlert, TrendingUp,
  ChevronDown, ChevronUp, Loader2, AlertCircle, Sparkles,
  BarChart3, Globe, MessageSquare, CheckCircle2, AlertTriangle,
  XCircle, Clock, Trash2, History, Send, Bot
} from 'lucide-react'

interface ProductFeature { name: string; mentions: number; priority: string }
interface FeatureSignal {
  feature: string; total_mentions: number; fr_mentions: number
  app_count: number; affected_apps: string[]; top_narrative: string | null
}
interface SavedBriefFull {
  id: string; created_at: string; mode: string; scope: string
  industry: string | null; user_hypothesis: string | null
  product_name: string; tagline: string; core_problem: string
  market_gap: string; features: ProductFeature[]; target_audience: string
  differentiation: string; risk: string; risk_level: string
  hypothesis_check: string | null; hypothesis_alignment: string | null
  total_demand: number; apps_analyzed: number; sources: FeatureSignal[]
}
interface SavedBriefMeta {
  id: string; created_at: string; mode: string; scope: string
  product_name: string; tagline: string | null; risk_level: string | null
  total_demand: number | null; apps_analyzed: number | null
  user_hypothesis: string | null; industry: string | null
}
interface DataSource { id: string; name: string; industry: string; job_status?: string }

const PRIORITY_STYLE: Record<string, string> = {
  hoch: 'bg-red-500/15 text-red-400 border border-red-500/20',
  mittel: 'bg-amber-500/15 text-amber-400 border border-amber-500/20',
  niedrig: 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20',
}
const RISK_STYLE: Record<string, string> = {
  hoch: 'text-red-400', mittel: 'text-amber-400', niedrig: 'text-emerald-400',
}
const ALIGNMENT_CONFIG: Record<string, { icon: React.ElementType; color: string; bg: string; border: string; label: string }> = {
  stark:   { icon: CheckCircle2,  color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', label: 'Stark validiert' },
  mittel:  { icon: AlertTriangle, color: 'text-amber-400',   bg: 'bg-amber-500/10',   border: 'border-amber-500/20',   label: 'Teilweise validiert' },
  schwach: { icon: XCircle,       color: 'text-red-400',     bg: 'bg-red-500/10',     border: 'border-red-500/20',     label: 'Schwach validiert' },
}

function PriorityBadge({ priority }: { priority: string }) {
  return (
    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide ${PRIORITY_STYLE[priority] ?? PRIORITY_STYLE.mittel}`}>
      {priority}
    </span>
  )
}
function InfoCard({ icon: Icon, label, children }: { icon: React.ElementType; label: string; children: React.ReactNode }) {
  return (
    <div className="bg-slate-800/40 border border-white/[0.06] rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={14} className="text-indigo-400 shrink-0" />
        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">{label}</span>
      </div>
      <p className="text-sm text-slate-200 leading-relaxed">{children}</p>
    </div>
  )
}

function formatDate(iso: string) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit' })
    + ' ' + d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
}

function BriefCard({ brief, onDelete, onClick, active }: {
  brief: SavedBriefMeta; onDelete: (id: string) => void
  onClick: (id: string) => void; active: boolean
}) {
  return (
    <div
      onClick={() => onClick(brief.id)}
      className={`group relative rounded-xl border p-3 cursor-pointer transition-colors ${
        active
          ? 'bg-indigo-500/10 border-indigo-500/30'
          : 'bg-slate-800/40 border-white/[0.06] hover:border-white/10'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 mb-1">
            <span className={`text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded ${
              brief.mode === 'competitor' ? 'bg-red-500/20 text-red-400' : 'bg-violet-500/20 text-violet-400'
            }`}>
              {brief.mode === 'competitor' ? 'Konkurrenz' : 'Innovation'}
            </span>
            {brief.user_hypothesis && (
              <MessageSquare size={10} className="text-indigo-400 shrink-0" />
            )}
          </div>
          <p className="text-sm font-semibold text-slate-200 truncate">{brief.product_name}</p>
          {brief.tagline && (
            <p className="text-[11px] text-slate-500 truncate mt-0.5">{brief.tagline}</p>
          )}
          <div className="flex items-center gap-2 mt-1.5">
            <Clock size={10} className="text-slate-600 shrink-0" />
            <span className="text-[10px] text-slate-600">{formatDate(brief.created_at)}</span>
          </div>
        </div>
        <button
          onClick={e => { e.stopPropagation(); onDelete(brief.id) }}
          className="opacity-0 group-hover:opacity-100 shrink-0 p-1 rounded text-slate-600 hover:text-red-400 transition-all"
        >
          <Trash2 size={12} />
        </button>
      </div>
    </div>
  )
}

interface ChatMsg { role: 'user' | 'assistant'; content: string }

function BriefDetail({ brief, mode }: { brief: SavedBriefFull; mode: string }) {
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const [chatHistory, setChatHistory] = useState<ChatMsg[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const chatEndRef = React.useRef<HTMLDivElement>(null)

  // Scroll to bottom on new message
  React.useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory, chatLoading])

  const handleChat = async () => {
    const msg = chatInput.trim()
    if (!msg || chatLoading) return
    setChatInput('')
    const userMsg: ChatMsg = { role: 'user', content: msg }
    setChatHistory(h => [...h, userMsg])
    setChatLoading(true)
    try {
      const res = await innovationApi.chat(brief.id, {
        message: msg,
        history: chatHistory,
      })
      setChatHistory(h => [...h, { role: 'assistant', content: res.reply }])
    } catch {
      setChatHistory(h => [...h, { role: 'assistant', content: 'Fehler beim Laden der Antwort. Bitte erneut versuchen.' }])
    } finally {
      setChatLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Hero */}
      <div className={`rounded-xl p-6 border ${
        mode === 'competitor'
          ? 'bg-gradient-to-br from-red-950/40 to-slate-900 border-red-500/20'
          : 'bg-gradient-to-br from-violet-950/40 to-slate-900 border-violet-500/20'
      }`}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className={`text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded ${
                mode === 'competitor' ? 'bg-red-500/20 text-red-400' : 'bg-violet-500/20 text-violet-400'
              }`}>
                {mode === 'competitor' ? 'Konkurrenzprodukt' : 'Innovationsprodukt'}
              </span>
              {brief.hypothesis_check && (
                <span className="text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-400">
                  Geführte Analyse
                </span>
              )}
              {brief.created_at && (
                <span className="text-[10px] text-slate-500 flex items-center gap-1">
                  <Clock size={9} /> {formatDate(brief.created_at)}
                </span>
              )}
            </div>
            <h2 className="text-2xl font-bold text-white mt-2">{brief.product_name}</h2>
            <p className={`text-sm mt-1 ${mode === 'competitor' ? 'text-red-300/80' : 'text-violet-300/80'}`}>
              {brief.tagline}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <p className="text-2xl font-bold text-white">{brief.total_demand.toLocaleString()}</p>
            <p className="text-[11px] text-slate-400">Feature-Wünsche</p>
            <p className="text-lg font-semibold text-slate-300 mt-1">{brief.apps_analyzed}</p>
            <p className="text-[11px] text-slate-400">Apps analysiert</p>
          </div>
        </div>
      </div>

      {/* Hypothesis check */}
      {brief.hypothesis_check && brief.hypothesis_alignment && (() => {
        const cfg = ALIGNMENT_CONFIG[brief.hypothesis_alignment] ?? ALIGNMENT_CONFIG['mittel']
        const Icon = cfg.icon
        return (
          <div className={`rounded-xl p-4 border ${cfg.bg} ${cfg.border}`}>
            <div className="flex items-center gap-2 mb-2">
              <Icon size={15} className={cfg.color} />
              <span className={`text-[11px] font-semibold uppercase tracking-wider ${cfg.color}`}>
                Hypothesen-Check — {cfg.label}
              </span>
            </div>
            <p className="text-sm text-slate-200 leading-relaxed">{brief.hypothesis_check}</p>
          </div>
        )
      })()}

      <div className="grid grid-cols-2 gap-3">
        <InfoCard icon={Target} label="Kernproblem">{brief.core_problem}</InfoCard>
        <InfoCard icon={TrendingUp} label="Marktlücke">{brief.market_gap}</InfoCard>
        <InfoCard icon={Users} label="Zielgruppe">{brief.target_audience}</InfoCard>
        <InfoCard icon={Zap} label="Alleinstellungsmerkmal">{brief.differentiation}</InfoCard>
      </div>

      <div className="bg-slate-800/40 border border-white/[0.06] rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <BarChart3 size={14} className="text-indigo-400" />
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Kern-Features</span>
        </div>
        <div className="space-y-2">
          {brief.features.map((f, i) => (
            <div key={i} className="flex items-center gap-3 py-2 border-b border-white/[0.04] last:border-0">
              <span className="text-[11px] text-slate-500 w-4 shrink-0">{i + 1}</span>
              <span className="text-sm text-slate-200 flex-1">{f.name}</span>
              <span className="text-xs text-slate-500 shrink-0">{f.mentions.toLocaleString()} Erwähnungen</span>
              <PriorityBadge priority={f.priority} />
            </div>
          ))}
        </div>
      </div>

      <div className="bg-slate-800/40 border border-white/[0.06] rounded-xl p-4 flex items-start gap-3">
        <ShieldAlert size={15} className={`shrink-0 mt-0.5 ${RISK_STYLE[brief.risk_level] ?? 'text-amber-400'}`} />
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Hauptrisiko</span>
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase ${PRIORITY_STYLE[brief.risk_level] ?? PRIORITY_STYLE['mittel']}`}>
              {brief.risk_level}
            </span>
          </div>
          <p className="text-sm text-slate-200">{brief.risk}</p>
        </div>
      </div>

      {brief.sources.length > 0 && (
        <div className="bg-slate-800/40 border border-white/[0.06] rounded-xl overflow-hidden">
          <button
            onClick={() => setSourcesOpen(o => !o)}
            className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-white/[0.02] transition-colors"
          >
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Datengrundlage — {brief.sources.length} Signal-Cluster
            </span>
            {sourcesOpen ? <ChevronUp size={14} className="text-slate-500" /> : <ChevronDown size={14} className="text-slate-500" />}
          </button>
          {sourcesOpen && (
            <div className="border-t border-white/[0.06]">
              {brief.sources.map((s, i) => (
                <div key={i} className="px-4 py-2.5 border-b border-white/[0.04] last:border-0">
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-slate-200 flex-1 font-medium">{s.feature}</span>
                    <span className="text-[11px] text-violet-400 shrink-0">{s.fr_mentions} FR</span>
                    <span className="text-[11px] text-slate-500 shrink-0">{s.total_mentions} gesamt</span>
                    <span className="text-[11px] text-indigo-400 shrink-0">{s.app_count} App{s.app_count !== 1 ? 's' : ''}</span>
                  </div>
                  {s.top_narrative && (
                    <p className="text-xs text-slate-500 mt-1 line-clamp-2">"{s.top_narrative}"</p>
                  )}
                  <div className="flex gap-1 mt-1 flex-wrap">
                    {s.affected_apps.slice(0, 4).map(a => (
                      <span key={a} className="text-[10px] bg-slate-700/60 text-slate-400 px-1.5 py-0.5 rounded">{a}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Copilot Chat */}
      <div className="bg-slate-900 border border-indigo-500/20 rounded-xl overflow-hidden">
        <div className="flex items-center gap-2.5 px-4 py-3 border-b border-white/[0.06] bg-indigo-500/5">
          <Bot size={15} className="text-indigo-400 shrink-0" />
          <span className="text-[11px] font-semibold text-indigo-300 uppercase tracking-wider">Strategie-Copilot</span>
          <span className="text-[10px] text-slate-500 ml-1">— stelle Fragen zum Konzept oder diskutiere Anpassungen</span>
        </div>

        {/* Messages */}
        <div className="px-4 py-3 space-y-3 max-h-80 overflow-y-auto">
          {chatHistory.length === 0 && !chatLoading && (
            <div className="py-4 text-center">
              <p className="text-xs text-slate-600">Noch keine Fragen gestellt.</p>
              <div className="flex flex-wrap gap-2 justify-center mt-3">
                {[
                  `Was verstehst du unter "${brief.features[0]?.name}"?`,
                  'Welches Feature hat den größten Marktbedarf?',
                  'Wie würde das Monetarisierungsmodell aussehen?',
                ].map(q => (
                  <button
                    key={q}
                    onClick={() => { setChatInput(q); }}
                    className="text-[11px] px-3 py-1.5 rounded-lg bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700 transition-colors text-left"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {chatHistory.map((msg, i) => (
            <div key={i} className={`flex gap-2.5 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${
                msg.role === 'user' ? 'bg-indigo-500/20' : 'bg-slate-700'
              }`}>
                {msg.role === 'user'
                  ? <span className="text-[9px] font-bold text-indigo-400">Du</span>
                  : <Bot size={11} className="text-slate-400" />
                }
              </div>
              <div className={`max-w-[80%] rounded-xl px-3 py-2 text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-indigo-500/10 text-slate-200 rounded-tr-sm'
                  : 'bg-slate-800 text-slate-200 rounded-tl-sm'
              }`}>
                {msg.content}
              </div>
            </div>
          ))}

          {chatLoading && (
            <div className="flex gap-2.5">
              <div className="w-6 h-6 rounded-full bg-slate-700 flex items-center justify-center shrink-0">
                <Bot size={11} className="text-slate-400" />
              </div>
              <div className="bg-slate-800 rounded-xl rounded-tl-sm px-3 py-2.5 flex gap-1 items-center">
                <span className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input */}
        <div className="px-3 py-3 border-t border-white/[0.06] flex gap-2">
          <input
            value={chatInput}
            onChange={e => setChatInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleChat()}
            placeholder="Frage zum Konzept stellen..."
            className="flex-1 bg-slate-800/60 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500/40"
          />
          <button
            onClick={handleChat}
            disabled={!chatInput.trim() || chatLoading}
            className={`px-3 py-2 rounded-lg transition-colors flex items-center gap-1.5 text-sm font-medium ${
              chatInput.trim() && !chatLoading
                ? 'bg-indigo-500 hover:bg-indigo-400 text-white'
                : 'bg-slate-800 text-slate-600 cursor-not-allowed'
            }`}
          >
            <Send size={13} />
          </button>
        </div>
      </div>
    </div>
  )
}

export function InnovationLabPage() {
  const [sources, setSources] = useState<DataSource[]>([])
  const [mode, setMode] = useState<'competitor' | 'innovation'>('competitor')
  const [scope, setScope] = useState<'all' | 'industry' | 'datasource'>('all')
  const [industry, setIndustry] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [market, setMarket] = useState('')
  const [hypothesis, setHypothesis] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [brief, setBrief] = useState<SavedBriefFull | null>(null)
  const [history, setHistory] = useState<SavedBriefMeta[]>([])
  const [historyOpen, setHistoryOpen] = useState(true)
  const [activeId, setActiveId] = useState<string | null>(null)

  const loadHistory = useCallback(() => {
    innovationApi.listBriefs().then((list: SavedBriefMeta[]) => setHistory(list)).catch(() => {})
  }, [])

  useEffect(() => {
    datasourceApi.list().then((list: DataSource[]) => {
      setSources(list.filter((d: DataSource) => d.job_status === 'done'))
    }).catch(() => {})
    loadHistory()
  }, [loadHistory])

  const industries = [...new Set(sources.map(s => s.industry).filter(Boolean))].sort()
  const isGuided = hypothesis.trim().length > 0

  const toggleId = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const handleGenerate = async () => {
    setLoading(true)
    setError(null)
    setBrief(null)
    setActiveId(null)
    try {
      const body: Record<string, unknown> = { mode, scope }
      if (scope === 'industry' && industry) body.industry = industry
      if (scope === 'datasource' && selectedIds.size > 0) body.datasource_ids = [...selectedIds]
      if (market.trim()) body.market = market.trim().toLowerCase()
      if (hypothesis.trim()) body.user_hypothesis = hypothesis.trim()
      const result: SavedBriefFull = await innovationApi.generate(body)
      setBrief(result)
      setActiveId(result.id)
      loadHistory()
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setError(e?.response?.data?.detail ?? 'Fehler beim Generieren. Bitte erneut versuchen.')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectBrief = async (id: string) => {
    if (activeId === id) return
    setActiveId(id)
    setError(null)
    try {
      const result: SavedBriefFull = await innovationApi.getBrief(id)
      setBrief(result)
    } catch {
      setError('Brief konnte nicht geladen werden.')
    }
  }

  const handleDelete = async (id: string) => {
    await innovationApi.deleteBrief(id)
    setHistory(h => h.filter(b => b.id !== id))
    if (activeId === id) { setBrief(null); setActiveId(null) }
  }

  const canGenerate = !loading && (
    scope === 'all' ||
    (scope === 'industry' && !!industry) ||
    (scope === 'datasource' && selectedIds.size > 0)
  )

  return (
    <AppShell>
      <div className="min-h-screen bg-slate-950">
        {/* Header */}
        <div className="border-b border-white/[0.06] bg-gradient-to-r from-violet-950/30 via-indigo-950/20 to-slate-900/0">
          <div className="max-w-7xl mx-auto px-6 py-8">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-violet-500/20 border border-violet-400/20 flex items-center justify-center shrink-0">
                <Lightbulb size={20} className="text-violet-400" />
              </div>
              <div>
                <h1 className="text-xl font-semibold text-white">Innovation Lab</h1>
                <p className="text-sm text-slate-400 mt-0.5">
                  Generiere datengestützte Produktideen — frei oder mit deiner eigenen Hypothese
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="max-w-7xl mx-auto px-6 py-8 flex gap-6 items-start">
          {/* Config Panel */}
          <div className="w-72 shrink-0 space-y-5">

            <div>
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">Modus</p>
              <div className="grid grid-cols-1 gap-2">
                <button onClick={() => setMode('competitor')}
                  className={`flex items-start gap-3 p-3 rounded-xl border text-left transition-colors ${
                    mode === 'competitor' ? 'bg-red-500/10 border-red-500/30 text-red-300' : 'bg-slate-800/40 border-white/[0.06] text-slate-400 hover:border-white/10'
                  }`}>
                  <Zap size={15} className={`shrink-0 mt-0.5 ${mode === 'competitor' ? 'text-red-400' : ''}`} />
                  <div>
                    <p className="text-sm font-medium">Konkurrenzprodukt</p>
                    <p className="text-[11px] mt-0.5 opacity-70">Greife die größten Schwächen an</p>
                  </div>
                </button>
                <button onClick={() => setMode('innovation')}
                  className={`flex items-start gap-3 p-3 rounded-xl border text-left transition-colors ${
                    mode === 'innovation' ? 'bg-violet-500/10 border-violet-500/30 text-violet-300' : 'bg-slate-800/40 border-white/[0.06] text-slate-400 hover:border-white/10'
                  }`}>
                  <Sparkles size={15} className={`shrink-0 mt-0.5 ${mode === 'innovation' ? 'text-violet-400' : ''}`} />
                  <div>
                    <p className="text-sm font-medium">Innovationsprodukt</p>
                    <p className="text-[11px] mt-0.5 opacity-70">Finde unbesetzte Marktlücken</p>
                  </div>
                </button>
              </div>
            </div>

            <div>
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">Datenbasis</p>
              <div className="flex rounded-lg overflow-hidden border border-white/[0.06] bg-slate-800/40">
                {(['all', 'industry', 'datasource'] as const).map(s => (
                  <button key={s} onClick={() => setScope(s)}
                    className={`flex-1 py-2 text-[11px] font-medium transition-colors ${
                      scope === s ? 'bg-indigo-500/20 text-indigo-300' : 'text-slate-400 hover:text-slate-200'
                    }`}>
                    {s === 'all' ? 'Alle' : s === 'industry' ? 'Branche' : 'Apps'}
                  </button>
                ))}
              </div>
            </div>

            {scope === 'industry' && (
              <div>
                <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">Branche</p>
                <select value={industry} onChange={e => setIndustry(e.target.value)}
                  className="w-full bg-slate-800/60 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500/50">
                  <option value="">Branche wählen...</option>
                  {industries.map(ind => <option key={ind} value={ind}>{ind}</option>)}
                </select>
              </div>
            )}

            {scope === 'datasource' && (
              <div>
                <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Apps auswählen {selectedIds.size > 0 && <span className="text-indigo-400">({selectedIds.size})</span>}
                </p>
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {sources.map(src => (
                    <label key={src.id} className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-white/[0.03] cursor-pointer">
                      <input type="checkbox" checked={selectedIds.has(src.id)} onChange={() => toggleId(src.id)} className="accent-indigo-500 shrink-0" />
                      <span className="text-xs text-slate-300 truncate">{src.name}</span>
                      {src.industry && <span className="text-[10px] text-slate-500 shrink-0">{src.industry}</span>}
                    </label>
                  ))}
                </div>
              </div>
            )}

            <div>
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Markt <span className="text-slate-600 normal-case font-normal">(optional)</span>
              </p>
              <div className="relative">
                <Globe size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input type="text" value={market} onChange={e => setMarket(e.target.value)}
                  placeholder="z.B. de, us, gb"
                  className="w-full bg-slate-800/60 border border-white/[0.08] rounded-lg pl-8 pr-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500/50" />
              </div>
            </div>

            <div className="border-t border-white/[0.06]" />

            <div>
              <div className="flex items-center gap-2 mb-2">
                <MessageSquare size={13} className={isGuided ? 'text-indigo-400' : 'text-slate-500'} />
                <p className={`text-[11px] font-semibold uppercase tracking-wider ${isGuided ? 'text-indigo-400' : 'text-slate-400'}`}>
                  Deine Hypothese <span className={`normal-case font-normal ${isGuided ? 'text-indigo-500' : 'text-slate-600'}`}>(optional)</span>
                </p>
              </div>
              {isGuided && (
                <div className="flex items-center gap-1.5 mb-2 px-2 py-1 rounded-md bg-indigo-500/10 border border-indigo-500/20">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />
                  <span className="text-[10px] text-indigo-300 font-medium">Geführte Analyse aktiv</span>
                </div>
              )}
              <textarea value={hypothesis} onChange={e => setHypothesis(e.target.value)} rows={4}
                placeholder={"z.B. Ich möchte eine App bauen, die das Bezahlen im Auto vereinfacht..."}
                className={`w-full bg-slate-800/60 border rounded-xl px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none resize-none leading-relaxed transition-colors ${
                  isGuided ? 'border-indigo-500/30 focus:border-indigo-400/50' : 'border-white/[0.08] focus:border-white/20'
                }`} />
              <p className="text-[10px] text-slate-600 mt-1.5">
                {isGuided ? 'KI validiert deine Idee gegen echte Nutzerdaten.' : 'Leer = freie Analyse. Mit Text = Hypothesenvalidierung.'}
              </p>
            </div>

            <button onClick={handleGenerate} disabled={!canGenerate}
              className={`w-full flex items-center justify-center gap-2 py-3 rounded-xl font-semibold text-sm transition-all ${
                canGenerate ? 'bg-indigo-500 hover:bg-indigo-400 text-white shadow-lg shadow-indigo-500/20' : 'bg-slate-800 text-slate-500 cursor-not-allowed'
              }`}>
              {loading ? <><Loader2 size={15} className="animate-spin" /> Analysiere...</>
                : isGuided ? <><MessageSquare size={15} /> Hypothese validieren</>
                : <><Sparkles size={15} /> Idee generieren</>}
            </button>

            {/* History */}
            {history.length > 0 && (
              <div>
                <button onClick={() => setHistoryOpen(o => !o)}
                  className="w-full flex items-center justify-between py-1">
                  <div className="flex items-center gap-2">
                    <History size={13} className="text-slate-500" />
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                      Verlauf <span className="text-slate-600 font-normal">({history.length})</span>
                    </span>
                  </div>
                  {historyOpen ? <ChevronUp size={12} className="text-slate-600" /> : <ChevronDown size={12} className="text-slate-600" />}
                </button>
                {historyOpen && (
                  <div className="space-y-2 mt-2 max-h-72 overflow-y-auto pr-0.5">
                    {history.map(b => (
                      <BriefCard key={b.id} brief={b} active={activeId === b.id}
                        onClick={handleSelectBrief} onDelete={handleDelete} />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Result */}
          <div className="flex-1 min-w-0">
            {error && (
              <div className="flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300">
                <AlertCircle size={16} className="shrink-0 mt-0.5" />
                <p className="text-sm">{error}</p>
              </div>
            )}

            {!brief && !loading && !error && (
              <div className="flex flex-col items-center justify-center py-24 text-center">
                <div className="w-16 h-16 rounded-2xl bg-slate-800/60 border border-white/[0.06] flex items-center justify-center mb-4">
                  <Lightbulb size={28} className="text-slate-600" />
                </div>
                <p className="text-slate-400 font-medium">Noch keine Idee generiert</p>
                <p className="text-sm text-slate-600 mt-1 max-w-sm">
                  {history.length > 0
                    ? 'Klicke auf einen Eintrag im Verlauf oder generiere eine neue Idee.'
                    : 'Wähle links Modus und Datenbasis und klicke auf "Idee generieren".'}
                </p>
              </div>
            )}

            {loading && (
              <div className="space-y-4 animate-pulse">
                <div className="h-32 rounded-xl bg-slate-800/60" />
                <div className="grid grid-cols-2 gap-4">
                  <div className="h-24 rounded-xl bg-slate-800/40" />
                  <div className="h-24 rounded-xl bg-slate-800/40" />
                </div>
                <div className="h-40 rounded-xl bg-slate-800/40" />
              </div>
            )}

            {brief && !loading && <BriefDetail brief={brief} mode={brief.mode} />}
          </div>
        </div>
      </div>
    </AppShell>
  )
}
