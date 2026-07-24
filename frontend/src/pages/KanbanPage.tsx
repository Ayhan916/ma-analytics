import { useState, useEffect } from 'react'
import { AppShell } from '../components/AppShell'
import { ticketsApi } from '../services/api'
import { Plus, X, Trash2, RefreshCw } from 'lucide-react'

interface Ticket {
  id: string
  title: string
  description: string | null
  priority: string
  status: string
  customer_name: string | null
  labels: string[]
  subtasks: { text: string; done: boolean }[]
  comments: string[]
  created_at: string
  updated_at: string
}

const COLUMNS = ['Backlog', 'Todo', 'In Progress', 'Done'] as const
type Status = typeof COLUMNS[number]

const PRIORITY_COLOR: Record<string, string> = {
  High:   'text-red-400 bg-red-400/10 border-red-400/20',
  Medium: 'text-amber-400 bg-amber-400/10 border-amber-400/20',
  Low:    'text-slate-400 bg-slate-400/10 border-slate-400/20',
}

function PriorityBadge({ p }: { p: string }) {
  return <span className={`inline-flex px-1.5 py-0.5 rounded border text-[10px] font-medium ${PRIORITY_COLOR[p] ?? PRIORITY_COLOR['Low']}`}>{p}</span>
}

function TicketCard({ ticket, onClick }: { ticket: Ticket; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className="w-full text-left bg-slate-800 hover:bg-slate-750 border border-white/10 hover:border-white/20 rounded-xl p-3 transition-all group">
      <p className="text-white text-sm font-medium leading-snug mb-2 line-clamp-2">{ticket.title}</p>
      <div className="flex items-center gap-2 flex-wrap">
        <PriorityBadge p={ticket.priority} />
        {ticket.labels?.slice(0, 2).map(l => (
          <span key={l} className="text-[10px] text-slate-400 bg-slate-700 px-1.5 py-0.5 rounded">{l}</span>
        ))}
      </div>
      {ticket.customer_name && (
        <p className="text-slate-500 text-xs mt-2">👤 {ticket.customer_name}</p>
      )}
    </button>
  )
}

function TicketDetail({ ticket, onClose, onUpdate, onDelete }: {
  ticket: Ticket
  onClose: () => void
  onUpdate: (t: Ticket) => void
  onDelete: (id: string) => void
}) {
  const [status, setStatus] = useState(ticket.status)
  const [priority, setPriority] = useState(ticket.priority)
  const [title, setTitle] = useState(ticket.title)
  const [desc, setDesc] = useState(ticket.description || '')
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      const updated = await ticketsApi.update(ticket.id, { title, description: desc, status, priority })
      onUpdate(updated)
    } finally { setSaving(false) }
  }

  const del = async () => {
    if (!confirm('Delete this ticket?')) return
    setDeleting(true)
    try {
      await ticketsApi.delete(ticket.id)
      onDelete(ticket.id)
      onClose()
    } finally { setDeleting(false) }
  }

  const dirty = title !== ticket.title || desc !== (ticket.description || '') || status !== ticket.status || priority !== ticket.priority

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-start justify-end">
      <div className="w-full max-w-md h-full bg-slate-900 border-l border-white/10 flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10 shrink-0">
          <p className="text-slate-400 text-xs font-mono">#{ticket.id.slice(0, 8)}</p>
          <div className="flex items-center gap-2">
            <button onClick={del} disabled={deleting} className="text-slate-500 hover:text-red-400 transition-colors">
              {deleting ? <RefreshCw size={15} className="animate-spin" /> : <Trash2 size={15} />}
            </button>
            <button onClick={onClose} className="text-slate-400 hover:text-white"><X size={18} /></button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          <div>
            <label className="block text-slate-400 text-xs mb-1">Title</label>
            <input value={title} onChange={e => setTitle(e.target.value)}
              className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500" />
          </div>
          <div>
            <label className="block text-slate-400 text-xs mb-1">Description</label>
            <textarea value={desc} onChange={e => setDesc(e.target.value)} rows={5}
              className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500 resize-none" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-400 text-xs mb-1">Status</label>
              <select value={status} onChange={e => setStatus(e.target.value)}
                className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500">
                {COLUMNS.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-slate-400 text-xs mb-1">Priority</label>
              <select value={priority} onChange={e => setPriority(e.target.value)}
                className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500">
                {['High', 'Medium', 'Low'].map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
          </div>
          {ticket.customer_name && (
            <div>
              <label className="block text-slate-400 text-xs mb-1">Customer</label>
              <p className="text-slate-300 text-sm">{ticket.customer_name}</p>
            </div>
          )}
          {ticket.labels?.length > 0 && (
            <div>
              <label className="block text-slate-400 text-xs mb-1">Labels</label>
              <div className="flex flex-wrap gap-1">
                {ticket.labels.map(l => <span key={l} className="text-xs text-slate-400 bg-slate-700 px-2 py-0.5 rounded">{l}</span>)}
              </div>
            </div>
          )}
          <p className="text-slate-600 text-xs">Created {new Date(ticket.created_at).toLocaleString()}</p>
        </div>

        {/* Footer */}
        {dirty && (
          <div className="shrink-0 p-4 border-t border-white/10">
            <button onClick={save} disabled={saving}
              className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white py-2 rounded-lg text-sm font-medium transition-colors">
              {saving ? <RefreshCw size={14} className="animate-spin" /> : null}
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function NewTicketForm({ onCreated }: { onCreated: (t: Ticket) => void }) {
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [priority, setPriority] = useState('Medium')
  const [loading, setLoading] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const t = await ticketsApi.create({ title, priority, status: 'Backlog' })
      onCreated(t)
      setTitle(''); setOpen(false)
    } finally { setLoading(false) }
  }

  if (!open) return (
    <button onClick={() => setOpen(true)}
      className="flex items-center gap-1.5 text-slate-500 hover:text-white text-xs px-2 py-1.5 rounded-lg hover:bg-white/5 transition-colors w-full">
      <Plus size={13} />Add ticket
    </button>
  )

  return (
    <form onSubmit={submit} className="bg-slate-800 border border-white/10 rounded-xl p-3 space-y-2">
      <input autoFocus value={title} onChange={e => setTitle(e.target.value)} required placeholder="Ticket title..."
        className="w-full bg-slate-700 border border-white/10 rounded-lg px-2 py-1.5 text-white text-sm focus:outline-none focus:border-indigo-500" />
      <div className="flex items-center gap-2">
        <select value={priority} onChange={e => setPriority(e.target.value)}
          className="flex-1 bg-slate-700 border border-white/10 rounded-lg px-2 py-1.5 text-white text-xs focus:outline-none">
          {['High', 'Medium', 'Low'].map(p => <option key={p}>{p}</option>)}
        </select>
        <button type="button" onClick={() => setOpen(false)} className="text-slate-400 hover:text-white"><X size={14} /></button>
        <button type="submit" disabled={loading}
          className="bg-indigo-600 hover:bg-indigo-500 text-white px-2 py-1.5 rounded-lg text-xs font-medium transition-colors">
          Add
        </button>
      </div>
    </form>
  )
}

export function KanbanPage() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [selected, setSelected] = useState<Ticket | null>(null)
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    ticketsApi.list().then(setTickets).catch(() => setLoadError(true))
  }, [])

  const byStatus = (status: Status) => tickets.filter(t => t.status === status)

  const handleUpdate = (updated: Ticket) => {
    setTickets(prev => prev.map(t => t.id === updated.id ? updated : t))
    setSelected(updated)
  }

  const handleDelete = (id: string) => {
    setTickets(prev => prev.filter(t => t.id !== id))
  }

  const handleCreated = (t: Ticket) => {
    setTickets(prev => [t, ...prev])
  }

  return (
    <AppShell>
      <div className="p-6 h-full flex flex-col">
        <div className="mb-5 shrink-0">
          <h1 className="text-white text-2xl font-bold">Kanban Board</h1>
          <p className="text-slate-400 text-sm mt-1">{tickets.length} tickets total</p>
        </div>

        {loadError && (
          <div className="mb-4 bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-center">
            <p className="text-red-400 text-sm">Tickets konnten nicht geladen werden. Bitte Seite neu laden.</p>
          </div>
        )}

        <div className="flex-1 overflow-x-auto">
          <div className="flex gap-4 h-full min-w-max">
            {COLUMNS.map(col => (
              <div key={col} className="w-72 flex flex-col bg-slate-900/50 rounded-xl border border-white/5">
                {/* Column header */}
                <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 shrink-0">
                  <div className="flex items-center gap-2">
                    <span className="text-white text-sm font-medium">{col}</span>
                    <span className="text-slate-500 text-xs bg-slate-800 px-1.5 py-0.5 rounded-full">
                      {byStatus(col).length}
                    </span>
                  </div>
                </div>

                {/* Cards */}
                <div className="flex-1 overflow-y-auto p-3 space-y-2">
                  {byStatus(col).map(t => (
                    <TicketCard key={t.id} ticket={t} onClick={() => setSelected(t)} />
                  ))}
                  {col === 'Backlog' && <NewTicketForm onCreated={handleCreated} />}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {selected && (
        <TicketDetail
          ticket={selected}
          onClose={() => setSelected(null)}
          onUpdate={handleUpdate}
          onDelete={handleDelete}
        />
      )}
    </AppShell>
  )
}
