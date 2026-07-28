import { useState, useEffect, useMemo } from 'react'
import {
  MapPin, Search, Star, MessageSquare, Loader2, BarChart2,
  AlertCircle, SlidersHorizontal, ArrowUpDown, Store,
  CheckSquare, Square, ChevronDown, X,
} from 'lucide-react'
import { AppShell } from '../components/AppShell'
import { localMarketsApi, BusinessItem } from '../services/api'

// ── Constants ────────────────────────────────────────────────────────────────

const CATEGORIES = [
  'Restaurant', 'Supermarkt', 'Friseur', 'Autowerkstatt',
  'Apotheke', 'Café', 'Bäckerei', 'Arzt', 'Zahnarzt',
  'Fitnessstudio', 'Hotel', 'Bar', 'Pizzeria', 'Tankstelle',
]

const RADIUS_OPTIONS = [1, 2, 5, 10, 20, 50]
const MAX_RESULTS_OPTIONS = [10, 20, 30, 50]
const MAX_REVIEWS_OPTIONS = [50, 100, 200, 300, 500]

type SortKey = 'rating_desc' | 'reviews_desc' | 'name_asc' | 'rating_asc'

const SORT_LABELS: Record<SortKey, string> = {
  rating_desc:   'Bewertung ↓',
  rating_asc:    'Bewertung ↑',
  reviews_desc:  'Reviews ↓',
  name_asc:      'Name A–Z',
}

// ── Small helpers ─────────────────────────────────────────────────────────────

function Stars({ value, size = 12 }: { value: number; size?: number }) {
  return (
    <span className="flex items-center gap-1 text-amber-400 text-xs">
      <Star size={size} fill="currentColor" />
      <span>{value.toFixed(1)}</span>
    </span>
  )
}

function Select({
  value, onChange, options, className = '',
}: {
  value: string | number
  onChange: (v: string) => void
  options: { value: string | number; label: string }[]
  className?: string
}) {
  return (
    <div className={`relative ${className}`}>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full appearance-none bg-slate-900/60 border border-slate-700 rounded-lg px-3 py-2 pr-8 text-white text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
      >
        {options.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <ChevronDown size={13} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
    </div>
  )
}

function FilterChip({
  label, active, onClick,
}: {
  label: string; active: boolean; onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 rounded-full text-xs font-medium transition-colors border
        ${active
          ? 'bg-indigo-600 border-indigo-500 text-white'
          : 'bg-slate-800/60 border-slate-700 text-slate-400 hover:text-white hover:border-slate-500'
        }`}
    >
      {label}
    </button>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function LocalMarketsPage() {
  // Search form
  const [postalCode, setPostalCode] = useState('')
  const [radius, setRadius]         = useState(5)
  const [category, setCategory]     = useState(CATEGORIES[0])
  const [keyword, setKeyword]       = useState('')
  const [maxResults, setMaxResults] = useState(20)

  // Result filters (client-side)
  const [minRating, setMinRating]     = useState(0)
  const [minReviews, setMinReviews]   = useState(0)
  const [sortBy, setSortBy]           = useState<SortKey>('rating_desc')
  const [showFilters, setShowFilters] = useState(false)

  // Quick filter chips
  type QuickFilter = 'all' | 'top_rated' | 'popular' | 'newcomer'
  const [quickFilter, setQuickFilter] = useState<QuickFilter>('all')

  // Results
  const [searching, setSearching]   = useState(false)
  const [results, setResults]       = useState<BusinessItem[]>([])
  const [selected, setSelected]     = useState<Set<string>>(new Set())
  const [searchError, setSearchError] = useState('')

  // Analysis
  const [maxReviews, setMaxReviews]     = useState(200)
  const [analyzing, setAnalyzing]       = useState(false)
  const [analyzeResult, setAnalyzeResult] = useState<{ datasource_ids: string[]; job_ids: string[] } | null>(null)
  const [analyzeError, setAnalyzeError] = useState('')

  // Load categories from backend (for future extensibility)
  useEffect(() => {
    localMarketsApi.categories().catch(() => null)
  }, [])

  // ── Search ──────────────────────────────────────────────────────────────────

  const handleSearch = async () => {
    if (!postalCode.trim()) return
    setSearching(true)
    setResults([])
    setSelected(new Set())
    setSearchError('')
    setAnalyzeResult(null)
    setQuickFilter('all')
    setMinRating(0)
    setMinReviews(0)
    try {
      const data = await localMarketsApi.search({
        postal_code: postalCode.trim(),
        radius_km: radius,
        category,
        keyword: keyword.trim(),
        max_results: maxResults,
      })
      setResults(data)
      if (data.length === 0) setSearchError('Keine Ergebnisse gefunden. Prüfe PLZ und Kategorie.')
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Suche fehlgeschlagen. Stelle sicher, dass Playwright installiert ist.'
      setSearchError(msg)
    } finally {
      setSearching(false)
    }
  }

  // ── Client-side filter + sort ───────────────────────────────────────────────

  const filtered = useMemo(() => {
    let list = [...results]

    // Quick filters
    if (quickFilter === 'top_rated')  list = list.filter(r => r.rating >= 4.5)
    if (quickFilter === 'popular')    list = list.filter(r => r.review_count >= 100)
    if (quickFilter === 'newcomer')   list = list.filter(r => r.review_count < 30)

    // Advanced filters
    if (minRating > 0)   list = list.filter(r => r.rating >= minRating)
    if (minReviews > 0)  list = list.filter(r => r.review_count >= minReviews)

    // Sort
    list.sort((a, b) => {
      if (sortBy === 'rating_desc')  return b.rating - a.rating
      if (sortBy === 'rating_asc')   return a.rating - b.rating
      if (sortBy === 'reviews_desc') return b.review_count - a.review_count
      if (sortBy === 'name_asc')     return a.name.localeCompare(b.name, 'de')
      return 0
    })

    return list
  }, [results, quickFilter, minRating, minReviews, sortBy])

  // ── Selection ───────────────────────────────────────────────────────────────

  const toggleSelect = (placeId: string) =>
    setSelected(prev => {
      const next = new Set(prev)
      next.has(placeId) ? next.delete(placeId) : next.add(placeId)
      return next
    })

  const toggleAll = () =>
    setSelected(
      selected.size === filtered.length
        ? new Set()
        : new Set(filtered.map(r => r.place_id))
    )

  const selectedBusinesses = results.filter(r => selected.has(r.place_id))

  // ── Analysis ────────────────────────────────────────────────────────────────

  const handleAnalyze = async () => {
    if (!selectedBusinesses.length) return
    setAnalyzing(true)
    setAnalyzeError('')
    setAnalyzeResult(null)
    try {
      const data = await localMarketsApi.analyze(selectedBusinesses, maxReviews)
      setAnalyzeResult(data)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Analyse fehlgeschlagen.'
      setAnalyzeError(msg)
    } finally {
      setAnalyzing(false)
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <AppShell>
      <div className="flex flex-col gap-5 p-6 max-w-4xl mx-auto">

        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
            <Store size={18} className="text-emerald-400" />
          </div>
          <div>
            <h1 className="text-white font-semibold text-lg">Betriebe</h1>
            <p className="text-slate-400 text-sm">Google Maps Reviews analysieren</p>
          </div>
        </div>

        {/* ── Search form ────────────────────────────────────────────────────── */}
        <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5 space-y-4">

          {/* Row 1: PLZ + Radius + Kategorie */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">PLZ oder Stadt</label>
              <input
                type="text"
                value={postalCode}
                onChange={e => setPostalCode(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                placeholder="80331 oder München"
                className="w-full bg-slate-900/60 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Radius</label>
              <Select
                value={radius}
                onChange={v => setRadius(Number(v))}
                options={RADIUS_OPTIONS.map(r => ({ value: r, label: `${r} km` }))}
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Kategorie</label>
              <Select
                value={category}
                onChange={setCategory}
                options={CATEGORIES.map(c => ({ value: c, label: c }))}
              />
            </div>
          </div>

          {/* Row 2: Keyword */}
          <div>
            <label className="block text-xs text-slate-400 mb-1.5">
              Suchbegriff <span className="text-slate-600">(optional — z.B. "vegan", "bio", "24h", "Sushi")</span>
            </label>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                value={keyword}
                onChange={e => setKeyword(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                placeholder="Zusätzliches Keyword verfeinert die Suche auf Google Maps"
                className="w-full bg-slate-900/60 border border-slate-700 rounded-lg pl-9 pr-3 py-2 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
              {keyword && (
                <button onClick={() => setKeyword('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white">
                  <X size={13} />
                </button>
              )}
            </div>
          </div>

          {/* Row 3: Advanced filters toggle + Max Ergebnisse */}
          <div className="flex items-center justify-between gap-3">
            <button
              onClick={() => setShowFilters(f => !f)}
              className="flex items-center gap-1.5 text-slate-400 hover:text-white text-xs transition-colors"
            >
              <SlidersHorizontal size={13} />
              Erweiterte Filter
              <ChevronDown size={12} className={`transition-transform ${showFilters ? 'rotate-180' : ''}`} />
            </button>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Max. Ergebnisse</span>
              <Select
                value={maxResults}
                onChange={v => setMaxResults(Number(v))}
                options={MAX_RESULTS_OPTIONS.map(n => ({ value: n, label: String(n) }))}
                className="w-20"
              />
            </div>
          </div>

          {/* Advanced filters (collapsible) */}
          {showFilters && (
            <div className="grid grid-cols-2 gap-3 pt-1 border-t border-slate-700/50">
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">Min. Bewertung</label>
                <div className="flex gap-1.5">
                  {[0, 3, 3.5, 4, 4.5].map(v => (
                    <button
                      key={v}
                      onClick={() => setMinRating(v)}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-medium border transition-colors
                        ${minRating === v
                          ? 'bg-amber-500/20 border-amber-500/40 text-amber-300'
                          : 'bg-slate-900/40 border-slate-700 text-slate-400 hover:text-white'
                        }`}
                    >
                      {v === 0 ? 'Alle' : `${v}★`}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">Min. Anzahl Reviews</label>
                <div className="flex gap-1.5">
                  {[0, 10, 50, 100, 200].map(v => (
                    <button
                      key={v}
                      onClick={() => setMinReviews(v)}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-medium border transition-colors
                        ${minReviews === v
                          ? 'bg-indigo-500/20 border-indigo-500/40 text-indigo-300'
                          : 'bg-slate-900/40 border-slate-700 text-slate-400 hover:text-white'
                        }`}
                    >
                      {v === 0 ? 'Alle' : `${v}+`}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Search button */}
          <button
            onClick={handleSearch}
            disabled={searching || !postalCode.trim()}
            className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors"
          >
            {searching ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
            {searching ? 'Suche läuft…' : 'Suchen'}
          </button>
        </div>

        {/* Error */}
        {searchError && (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/5 border border-red-400/20 rounded-lg px-4 py-3">
            <AlertCircle size={15} className="shrink-0" />
            {searchError}
          </div>
        )}

        {/* ── Results ──────────────────────────────────────────────────────────── */}
        {results.length > 0 && (
          <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl overflow-hidden">

            {/* Results toolbar */}
            <div className="px-5 py-3 border-b border-slate-700/50 space-y-2.5">
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-300 text-sm font-medium">
                  {filtered.length} von {results.length} Betrieben
                  {(minRating > 0 || minReviews > 0 || quickFilter !== 'all') && (
                    <button
                      onClick={() => { setMinRating(0); setMinReviews(0); setQuickFilter('all') }}
                      className="ml-2 text-xs text-slate-500 hover:text-red-400 transition-colors"
                    >
                      Filter zurücksetzen
                    </button>
                  )}
                </span>
                <div className="flex items-center gap-2">
                  <ArrowUpDown size={13} className="text-slate-500" />
                  <Select
                    value={sortBy}
                    onChange={v => setSortBy(v as SortKey)}
                    options={Object.entries(SORT_LABELS).map(([k, v]) => ({ value: k, label: v }))}
                    className="w-36"
                  />
                </div>
              </div>

              {/* Quick filter chips */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-slate-500">Schnellfilter:</span>
                <FilterChip label="Alle"         active={quickFilter === 'all'}      onClick={() => setQuickFilter('all')} />
                <FilterChip label="Top bewertet (4.5★+)" active={quickFilter === 'top_rated'} onClick={() => setQuickFilter('top_rated')} />
                <FilterChip label="Beliebt (100+ Reviews)" active={quickFilter === 'popular'}  onClick={() => setQuickFilter('popular')} />
                <FilterChip label="Wenig bewertet (<30)"   active={quickFilter === 'newcomer'} onClick={() => setQuickFilter('newcomer')} />
              </div>

              {/* Select all */}
              <button
                onClick={toggleAll}
                className="flex items-center gap-1.5 text-slate-400 hover:text-white text-xs transition-colors"
              >
                {selected.size === filtered.length && filtered.length > 0
                  ? <CheckSquare size={13} className="text-indigo-400" />
                  : <Square size={13} />
                }
                {selected.size === filtered.length && filtered.length > 0
                  ? 'Alle abwählen'
                  : `Alle ${filtered.length} auswählen`
                }
                {selected.size > 0 && selected.size < filtered.length && (
                  <span className="text-slate-500">({selected.size} ausgewählt)</span>
                )}
              </button>
            </div>

            {/* Business list */}
            {filtered.length === 0 ? (
              <div className="px-5 py-8 text-center text-slate-500 text-sm">
                Kein Betrieb entspricht den Filterkriterien.
              </div>
            ) : (
              <div className="divide-y divide-slate-700/30 max-h-[480px] overflow-y-auto">
                {filtered.map((biz, i) => {
                  const isSelected = selected.has(biz.place_id)
                  return (
                    <div
                      key={biz.place_id}
                      onClick={() => toggleSelect(biz.place_id)}
                      className={`flex items-center gap-4 px-5 py-3.5 cursor-pointer transition-colors
                        ${isSelected ? 'bg-emerald-500/5' : 'hover:bg-slate-700/20'}`}
                    >
                      {/* Rank */}
                      <span className="text-slate-600 text-xs w-5 shrink-0 text-right">{i + 1}</span>

                      {/* Checkbox */}
                      <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors
                        ${isSelected ? 'border-emerald-500 bg-emerald-500' : 'border-slate-600'}`}>
                        {isSelected && (
                          <svg viewBox="0 0 12 12" className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth="2">
                            <polyline points="1,6 4,9 11,2" />
                          </svg>
                        )}
                      </div>

                      {/* Name + address */}
                      <div className="flex-1 min-w-0">
                        <p className="text-white text-sm font-medium truncate">{biz.name}</p>
                        {biz.address && (
                          <p className="text-slate-500 text-xs truncate mt-0.5">{biz.address}</p>
                        )}
                      </div>

                      {/* Stats */}
                      <div className="flex items-center gap-4 shrink-0">
                        {biz.rating > 0 ? (
                          <Stars value={biz.rating} />
                        ) : (
                          <span className="text-slate-600 text-xs">–</span>
                        )}
                        <span className="flex items-center gap-1 text-slate-400 text-xs w-16 justify-end">
                          <MessageSquare size={11} />
                          {biz.review_count.toLocaleString('de-DE')}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* ── Analysis panel ────────────────────────────────────────────────── */}
        {selected.size > 0 && !analyzeResult && (
          <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
            <div className="flex items-start justify-between gap-6 flex-wrap">
              <div>
                <p className="text-white text-sm font-medium">
                  {selected.size} Betrieb{selected.size !== 1 ? 'e' : ''} ausgewählt
                </p>
                <p className="text-slate-400 text-xs mt-1 leading-relaxed">
                  Reviews werden via Playwright gescrapt und durch die ML-Pipeline geführt.<br />
                  Danach unter Data Sources → Dashboard → Innovation Lab verfügbar.
                </p>
                {/* Selected names preview */}
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {selectedBusinesses.slice(0, 5).map(b => (
                    <span key={b.place_id} className="text-xs bg-slate-700/50 text-slate-300 px-2 py-0.5 rounded-full">
                      {b.name}
                    </span>
                  ))}
                  {selectedBusinesses.length > 5 && (
                    <span className="text-xs text-slate-500">+{selectedBusinesses.length - 5} weitere</span>
                  )}
                </div>
              </div>

              <div className="flex items-end gap-3 shrink-0">
                <div>
                  <label className="block text-xs text-slate-400 mb-1.5">Max. Reviews / Betrieb</label>
                  <Select
                    value={maxReviews}
                    onChange={v => setMaxReviews(Number(v))}
                    options={MAX_REVIEWS_OPTIONS.map(n => ({ value: n, label: `${n} Reviews` }))}
                    className="w-36"
                  />
                </div>
                <button
                  onClick={handleAnalyze}
                  disabled={analyzing}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors whitespace-nowrap"
                >
                  {analyzing ? <Loader2 size={15} className="animate-spin" /> : <BarChart2 size={15} />}
                  {analyzing ? 'Starte Jobs…' : 'Analysieren'}
                </button>
              </div>
            </div>

            {analyzeError && (
              <div className="mt-4 flex items-center gap-2 text-red-400 text-sm bg-red-400/5 border border-red-400/20 rounded-lg px-4 py-3">
                <AlertCircle size={15} className="shrink-0" />
                {analyzeError}
              </div>
            )}
          </div>
        )}

        {/* ── Success ───────────────────────────────────────────────────────── */}
        {analyzeResult && (
          <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-5 flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center shrink-0">
              <MapPin size={16} className="text-emerald-400" />
            </div>
            <div>
              <p className="text-white font-medium text-sm">
                {analyzeResult.job_ids.length} Pipeline-Job{analyzeResult.job_ids.length !== 1 ? 's' : ''} gestartet
              </p>
              <p className="text-slate-400 text-sm mt-1">
                Fortschritt unter{' '}
                <a href="/datasources" className="text-indigo-400 hover:underline">Data Sources</a> verfolgen.
                Nach Abschluss im{' '}
                <a href="/" className="text-indigo-400 hover:underline">Dashboard</a> auswählbar.
              </p>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
