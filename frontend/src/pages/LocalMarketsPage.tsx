import { useState, useEffect } from 'react'
import { MapPin, Search, Star, MessageSquare, Loader2, CheckSquare, Square, BarChart2, AlertCircle } from 'lucide-react'
import { AppShell } from '../components/AppShell'
import { localMarketsApi, BusinessItem } from '../services/api'

const RADIUS_OPTIONS = [1, 2, 5, 10, 20]

function StarRating({ value }: { value: number }) {
  return (
    <span className="flex items-center gap-1 text-amber-400 text-xs">
      <Star size={12} fill="currentColor" />
      {value.toFixed(1)}
    </span>
  )
}

export function LocalMarketsPage() {
  const [categories, setCategories] = useState<string[]>([])
  const [postalCode, setPostalCode] = useState('')
  const [radius, setRadius] = useState(5)
  const [category, setCategory] = useState('')
  const [maxResults, setMaxResults] = useState(20)
  const [maxReviews, setMaxReviews] = useState(200)

  const [searching, setSearching] = useState(false)
  const [results, setResults] = useState<BusinessItem[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [searchError, setSearchError] = useState('')

  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeResult, setAnalyzeResult] = useState<{ datasource_ids: string[]; job_ids: string[] } | null>(null)
  const [analyzeError, setAnalyzeError] = useState('')

  useEffect(() => {
    localMarketsApi.categories().then(d => {
      setCategories(d.categories)
      setCategory(d.categories[0] ?? '')
    })
  }, [])

  const handleSearch = async () => {
    if (!postalCode.trim() || !category) return
    setSearching(true)
    setResults([])
    setSelected(new Set())
    setSearchError('')
    setAnalyzeResult(null)
    try {
      const data = await localMarketsApi.search({ postal_code: postalCode.trim(), radius_km: radius, category, max_results: maxResults })
      setResults(data)
      if (data.length === 0) setSearchError('Keine Ergebnisse gefunden. Prüfe die PLZ und Kategorie.')
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Suche fehlgeschlagen.'
      setSearchError(msg)
    } finally {
      setSearching(false)
    }
  }

  const toggleSelect = (placeId: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(placeId)) next.delete(placeId)
      else next.add(placeId)
      return next
    })
  }

  const toggleAll = () => {
    if (selected.size === results.length) setSelected(new Set())
    else setSelected(new Set(results.map(r => r.place_id)))
  }

  const handleAnalyze = async () => {
    const toAnalyze = results.filter(r => selected.has(r.place_id))
    if (!toAnalyze.length) return
    setAnalyzing(true)
    setAnalyzeError('')
    setAnalyzeResult(null)
    try {
      const data = await localMarketsApi.analyze(toAnalyze, maxReviews)
      setAnalyzeResult(data)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Analyse fehlgeschlagen.'
      setAnalyzeError(msg)
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <AppShell>
      <div className="flex flex-col gap-6 p-6 max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
            <MapPin size={18} className="text-emerald-400" />
          </div>
          <div>
            <h1 className="text-white font-semibold text-lg">Lokale Märkte</h1>
            <p className="text-slate-400 text-sm">Google Maps Reviews analysieren — PLZ, Radius, Kategorie</p>
          </div>
        </div>

        {/* Search form */}
        <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="col-span-1">
              <label className="block text-xs text-slate-400 mb-1.5">PLZ</label>
              <input
                type="text"
                value={postalCode}
                onChange={e => setPostalCode(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                placeholder="80331"
                maxLength={10}
                className="w-full bg-slate-900/60 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Radius</label>
              <select
                value={radius}
                onChange={e => setRadius(Number(e.target.value))}
                className="w-full bg-slate-900/60 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500"
              >
                {RADIUS_OPTIONS.map(r => (
                  <option key={r} value={r}>{r} km</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Kategorie</label>
              <select
                value={category}
                onChange={e => setCategory(e.target.value)}
                className="w-full bg-slate-900/60 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500"
              >
                {categories.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Max. Ergebnisse</label>
              <select
                value={maxResults}
                onChange={e => setMaxResults(Number(e.target.value))}
                className="w-full bg-slate-900/60 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500"
              >
                {[10, 20, 30, 50].map(n => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="mt-4">
            <button
              onClick={handleSearch}
              disabled={searching || !postalCode.trim() || !category}
              className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors"
            >
              {searching ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
              {searching ? 'Suche läuft…' : 'Suchen'}
            </button>
          </div>
        </div>

        {/* Error */}
        {searchError && (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/5 border border-red-400/20 rounded-lg px-4 py-3">
            <AlertCircle size={15} className="shrink-0" />
            {searchError}
          </div>
        )}

        {/* Results */}
        {results.length > 0 && (
          <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-700/50">
              <span className="text-slate-300 text-sm font-medium">{results.length} Betriebe gefunden</span>
              <button
                onClick={toggleAll}
                className="flex items-center gap-1.5 text-slate-400 hover:text-white text-xs transition-colors"
              >
                {selected.size === results.length ? <CheckSquare size={13} /> : <Square size={13} />}
                {selected.size === results.length ? 'Alle abwählen' : 'Alle auswählen'}
              </button>
            </div>

            <div className="divide-y divide-slate-700/30">
              {results.map(biz => {
                const isSelected = selected.has(biz.place_id)
                return (
                  <div
                    key={biz.place_id}
                    onClick={() => toggleSelect(biz.place_id)}
                    className={`flex items-center gap-4 px-5 py-3.5 cursor-pointer transition-colors
                      ${isSelected ? 'bg-emerald-500/5' : 'hover:bg-slate-700/20'}`}
                  >
                    <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors
                      ${isSelected ? 'border-emerald-500 bg-emerald-500' : 'border-slate-600'}`}>
                      {isSelected && (
                        <svg viewBox="0 0 12 12" className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth="2">
                          <polyline points="1,6 4,9 11,2" />
                        </svg>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-white text-sm font-medium truncate">{biz.name}</p>
                      {biz.address && (
                        <p className="text-slate-500 text-xs truncate mt-0.5">{biz.address}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-4 shrink-0">
                      {biz.rating > 0 && <StarRating value={biz.rating} />}
                      <span className="flex items-center gap-1 text-slate-400 text-xs">
                        <MessageSquare size={11} />
                        {biz.review_count}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Analyze panel */}
        {selected.size > 0 && !analyzeResult && (
          <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div>
                <p className="text-white text-sm font-medium">{selected.size} Betrieb{selected.size !== 1 ? 'e' : ''} ausgewählt</p>
                <p className="text-slate-400 text-xs mt-0.5">Reviews werden gescrapt und durch die ML-Pipeline geführt.</p>
              </div>
              <div className="flex items-center gap-3">
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Max. Reviews / Betrieb</label>
                  <select
                    value={maxReviews}
                    onChange={e => setMaxReviews(Number(e.target.value))}
                    className="bg-slate-900/60 border border-slate-700 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  >
                    {[50, 100, 200, 300, 500].map(n => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={handleAnalyze}
                  disabled={analyzing}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors mt-4"
                >
                  {analyzing ? <Loader2 size={15} className="animate-spin" /> : <BarChart2 size={15} />}
                  {analyzing ? 'Starte Jobs…' : 'Ausgewählte analysieren'}
                </button>
              </div>
            </div>
            {analyzeError && (
              <div className="mt-3 flex items-center gap-2 text-red-400 text-sm bg-red-400/5 border border-red-400/20 rounded-lg px-4 py-3">
                <AlertCircle size={15} className="shrink-0" />
                {analyzeError}
              </div>
            )}
          </div>
        )}

        {/* Success state */}
        {analyzeResult && (
          <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-5">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center shrink-0">
                <BarChart2 size={16} className="text-emerald-400" />
              </div>
              <div>
                <p className="text-white font-medium text-sm">
                  {analyzeResult.job_ids.length} Job{analyzeResult.job_ids.length !== 1 ? 's' : ''} gestartet
                </p>
                <p className="text-slate-400 text-sm mt-1">
                  Die Betriebe werden jetzt gescrapt und verarbeitet. Du kannst den Fortschritt unter{' '}
                  <a href="/datasources" className="text-indigo-400 hover:underline">Data Sources</a>{' '}
                  verfolgen.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
