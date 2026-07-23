import { useState, useEffect, useRef } from 'react'
import { AppShell } from '../components/AppShell'
import { datasourceApi, searchApi } from '../services/api'
import { Search, Sparkles, ChevronDown, X } from 'lucide-react'

interface DataSource { id: string; name: string; job_status: string | null }
interface SearchResult {
  review_id: string
  content: string
  score: number | null
  sentiment: string | null
  reviewed_at: string | null
  similarity: number
}

const SEARCH_TYPES = [
  { value: 'hybrid',   label: 'Hybrid' },
  { value: 'vector',   label: 'Semantic' },
  { value: 'fulltext', label: 'Keyword' },
]

function SentimentBadge({ s }: { s: string | null }) {
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

function ResultCard({ r, index }: { r: SearchResult; index?: number }) {
  const stars = r.score ? Math.round(r.score) : 0
  return (
    <div className="bg-slate-900 border border-white/10 rounded-xl p-4 space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        {index !== undefined && (
          <span className="text-[10px] font-mono text-slate-600 bg-slate-800 px-1.5 py-0.5 rounded">
            [{index + 1}]
          </span>
        )}
        <SentimentBadge s={r.sentiment} />
        {stars > 0 && (
          <span className="text-xs text-amber-400">{'★'.repeat(stars)}{'☆'.repeat(5 - stars)}</span>
        )}
        <span className="ml-auto text-xs font-mono text-slate-600">
          {(r.similarity * 100).toFixed(0)}% match
        </span>
      </div>
      <p className="text-slate-300 text-sm leading-relaxed line-clamp-3">{r.content}</p>
      {r.reviewed_at && (
        <p className="text-slate-600 text-xs">
          {new Date(r.reviewed_at).toLocaleDateString('de-DE', { day: '2-digit', month: 'short', year: 'numeric' })}
        </p>
      )}
    </div>
  )
}

export function SearchPage() {
  const [sources, setSources]               = useState<DataSource[]>([])
  const [datasourceId, setDatasourceId]     = useState('')
  const [query, setQuery]                   = useState('')
  const [searchType, setSearchType]         = useState('hybrid')
  const [rerank, setRerank]                 = useState(false)
  const [results, setResults]               = useState<SearchResult[]>([])
  const [searched, setSearched]             = useState(false)
  const [searching, setSearching]           = useState(false)
  const [searchError, setSearchError]       = useState('')
  const [askQuery, setAskQuery]             = useState('')
  const [askAnswer, setAskAnswer]           = useState('')
  const [askSources, setAskSources]         = useState<SearchResult[]>([])
  const [askStreaming, setAskStreaming]      = useState(false)
  const [askDone, setAskDone]               = useState(false)
  const [askError, setAskError]             = useState('')
  const [showSources, setShowSources]       = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const answerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    datasourceApi.list().then((list: DataSource[]) => {
      const done = list.filter(d => d.job_status === 'done')
      setSources(done)
      if (done.length > 0) setDatasourceId(done[0].id)
    }).catch(() => {})
  }, [])

  // Auto-scroll answer area while streaming
  useEffect(() => {
    if (askStreaming) answerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [askAnswer, askStreaming])

  const handleSearch = async () => {
    if (!datasourceId || query.trim().length < 2) return
    setSearching(true)
    setSearchError('')
    setSearched(false)
    try {
      const resp = await searchApi.search({
        datasource_id: datasourceId, q: query.trim(),
        search_type: searchType, rerank, limit: 20,
      })
      setResults(resp.results ?? [])
      setSearched(true)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setSearchError(detail || 'Search failed. Please try again.')
    } finally {
      setSearching(false)
    }
  }

  const handleAsk = async () => {
    if (!datasourceId || askQuery.trim().length < 2 || askStreaming) return
    abortRef.current?.abort()
    abortRef.current = new AbortController()
    setAskStreaming(true)
    setAskAnswer('')
    setAskSources([])
    setAskDone(false)
    setAskError('')
    setShowSources(false)
    try {
      const resp = await fetch('/api/search/ask/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        signal: abortRef.current.signal,
        body: JSON.stringify({
          query: askQuery.trim(),
          datasource_id: datasourceId,
          search_type: searchType,
          rerank,
          limit: 10,
        }),
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error((body as { detail?: string }).detail || `HTTP ${resp.status}`)
      }
      const reader = resp.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6)) as {
              type: string; content?: string; sources?: SearchResult[]; generated_by?: string; message?: string
            }
            if (event.type === 'sources') setAskSources(event.sources ?? [])
            else if (event.type === 'token') setAskAnswer(prev => prev + (event.content ?? ''))
            else if (event.type === 'done') setAskDone(true)
            else if (event.type === 'error') setAskError(event.message ?? 'Unknown error')
          } catch { /* skip malformed events */ }
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name !== 'AbortError') {
        setAskError((err as Error).message || 'Stream error. Please try again.')
      }
    } finally {
      setAskStreaming(false)
    }
  }

  const noDone = sources.length === 0

  return (
    <AppShell>
      <div className="min-h-full bg-slate-950 p-6 max-w-4xl mx-auto space-y-5">

        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-white text-xl font-semibold">Search</h1>
            <p className="text-slate-500 text-sm mt-0.5">Semantic and keyword search over user reviews</p>
          </div>
          <select
            value={datasourceId}
            onChange={e => setDatasourceId(e.target.value)}
            disabled={noDone}
            className="bg-slate-800 border border-white/10 text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
          >
            {noDone
              ? <option value="">No completed data sources</option>
              : sources.map(s => <option key={s.id} value={s.id}>{s.name}</option>)
            }
          </select>
        </div>

        {noDone ? (
          <div className="bg-slate-900 border border-white/10 rounded-xl p-10 text-center">
            <Search size={32} className="text-slate-700 mx-auto mb-3" />
            <p className="text-slate-400 text-sm">
              No completed data sources yet.{' '}
              <a href="/datasources" className="text-indigo-400 hover:underline">Add one</a> to start searching.
            </p>
          </div>
        ) : (
          <>
            {/* Search bar */}
            <div className="bg-slate-900 border border-white/10 rounded-xl p-4 space-y-3">
              <div className="flex gap-2 flex-wrap">
                <div className="relative flex-1 min-w-48">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
                  <input
                    type="text"
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleSearch()}
                    placeholder="Search reviews…"
                    className="w-full bg-slate-800 border border-white/10 text-white text-sm rounded-lg pl-9 pr-3 py-2.5 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <select
                  value={searchType}
                  onChange={e => setSearchType(e.target.value)}
                  className="bg-slate-800 border border-white/10 text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {SEARCH_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
                <label className="flex items-center gap-2 bg-slate-800 border border-white/10 rounded-lg px-3 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={rerank}
                    onChange={e => setRerank(e.target.checked)}
                    className="accent-indigo-500 w-3.5 h-3.5"
                  />
                  <span className="text-sm text-slate-300">Rerank</span>
                </label>
                <button
                  onClick={handleSearch}
                  disabled={searching || query.trim().length < 2}
                  className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors"
                >
                  {searching ? 'Searching…' : 'Search'}
                </button>
              </div>
              {searchError && <p className="text-red-400 text-xs">{searchError}</p>}
            </div>

            {/* Search results */}
            {searched && (
              <div>
                <p className="text-slate-500 text-xs font-medium uppercase tracking-wider mb-3">
                  {results.length === 0 ? 'No results' : `${results.length} results`}
                </p>
                <div className="space-y-2">
                  {results.map((r, i) => <ResultCard key={r.review_id} r={r} index={i} />)}
                </div>
              </div>
            )}

            {/* Ask AI */}
            <div className="bg-slate-900 border border-white/10 rounded-xl p-4 space-y-4">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-indigo-500/10 flex items-center justify-center shrink-0">
                  <Sparkles size={14} className="text-indigo-400" />
                </div>
                <h2 className="text-white text-sm font-semibold">Ask AI</h2>
                <span className="text-slate-500 text-xs">Get a grounded answer streamed from your reviews</span>
              </div>

              <div className="flex gap-2">
                <input
                  type="text"
                  value={askQuery}
                  onChange={e => setAskQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !askStreaming && handleAsk()}
                  placeholder="What are users complaining about most?"
                  className="flex-1 bg-slate-800 border border-white/10 text-white text-sm rounded-lg px-3 py-2.5 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                {askStreaming ? (
                  <button
                    onClick={() => abortRef.current?.abort()}
                    className="flex items-center gap-1.5 bg-red-600/20 hover:bg-red-600/30 border border-red-500/30 text-red-400 text-sm font-medium px-4 py-2 rounded-lg transition-colors shrink-0"
                  >
                    <X size={14} /> Stop
                  </button>
                ) : (
                  <button
                    onClick={handleAsk}
                    disabled={askQuery.trim().length < 2}
                    className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white text-sm font-medium px-4 py-2.5 rounded-lg transition-colors shrink-0"
                  >
                    <Sparkles size={14} /> Ask
                  </button>
                )}
              </div>

              {(askAnswer || askStreaming) && (
                <div ref={answerRef} className="bg-slate-800/50 border border-white/5 rounded-lg p-4">
                  <p className="text-slate-200 text-sm leading-relaxed whitespace-pre-wrap">
                    {askAnswer}
                    {askStreaming && (
                      <span className="inline-block w-0.5 h-[1.1em] bg-indigo-400 ml-0.5 animate-pulse align-middle" />
                    )}
                  </p>
                </div>
              )}

              {askError && (
                <p className="text-red-400 text-xs bg-red-400/5 border border-red-400/20 rounded-lg px-3 py-2">
                  {askError}
                </p>
              )}

              {askSources.length > 0 && askDone && (
                <div>
                  <button
                    onClick={() => setShowSources(s => !s)}
                    className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    <ChevronDown size={12} className={`transition-transform ${showSources ? 'rotate-180' : ''}`} />
                    {askSources.length} source{askSources.length !== 1 ? 's' : ''}
                  </button>
                  {showSources && (
                    <div className="mt-2 space-y-2">
                      {askSources.map((r, i) => <ResultCard key={r.review_id} r={r} index={i} />)}
                    </div>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </AppShell>
  )
}
