import { useState, useEffect } from 'react'
import { AppShell } from '../components/AppShell'
import { messagesApi } from '../services/api'
import { Plus, Send, Ticket, RefreshCw, Smile, Meh, Frown, X } from 'lucide-react'

interface Message {
  id: string
  name: string | null
  email: string | null
  text: string
  sentiment: string | null
  created_at: string
}

function SentimentBadge({ s }: { s: string | null }) {
  const map: Record<string, { icon: React.ReactNode; color: string }> = {
    positive: { icon: <Smile size={12} />, color: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20' },
    negative: { icon: <Frown size={12} />, color: 'text-red-400 bg-red-400/10 border-red-400/20' },
    neutral:  { icon: <Meh size={12} />, color: 'text-slate-400 bg-slate-400/10 border-slate-400/20' },
  }
  const style = map[s || 'neutral'] ?? map['neutral']
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-medium ${style.color}`}>
      {style.icon}{s || 'neutral'}
    </span>
  )
}

function NewMessageModal({ onClose, onCreated }: { onClose: () => void; onCreated: (m: Message) => void }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const msg = await messagesApi.create({ name: name || undefined, email: email || undefined, text })
      onCreated(msg)
      onClose()
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-white/10 rounded-2xl w-full max-w-md">
        <div className="flex items-center justify-between p-4 border-b border-white/10">
          <h3 className="text-white font-semibold">New Message</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white"><X size={18} /></button>
        </div>
        <form onSubmit={submit} className="p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-400 text-xs mb-1">Name</label>
              <input value={name} onChange={e => setName(e.target.value)} placeholder="Max Mustermann"
                className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500" />
            </div>
            <div>
              <label className="block text-slate-400 text-xs mb-1">Email</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="max@example.com"
                className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500" />
            </div>
          </div>
          <div>
            <label className="block text-slate-400 text-xs mb-1">Message</label>
            <textarea value={text} onChange={e => setText(e.target.value)} required rows={4} placeholder="Customer feedback..."
              className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500 resize-none" />
          </div>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-slate-400 hover:text-white text-sm">Cancel</button>
            <button type="submit" disabled={loading}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium">
              {loading ? <RefreshCw size={14} className="animate-spin" /> : <Send size={14} />}
              Send
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export function InboxPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [selected, setSelected] = useState<Message | null>(null)
  const [showNew, setShowNew] = useState(false)
  const [reply, setReply] = useState('')
  const [loadingReply, setLoadingReply] = useState(false)
  const [loadingTickets, setLoadingTickets] = useState(false)
  const [ticketsCreated, setTicketsCreated] = useState<number | null>(null)

  const load = async () => {
    const list = await messagesApi.list().catch(() => [])
    setMessages(list)
    if (selected) {
      const updated = list.find((m: Message) => m.id === selected.id)
      if (updated) setSelected(updated)
    }
  }

  useEffect(() => { load() }, [])

  const handleSelect = (m: Message) => {
    setSelected(m); setReply(''); setTicketsCreated(null)
  }

  const handleGenerateReply = async () => {
    if (!selected) return
    setLoadingReply(true)
    try {
      const res = await messagesApi.generateReply(selected.id)
      setReply(res.reply)
    } finally { setLoadingReply(false) }
  }

  const handleGenerateTickets = async () => {
    if (!selected) return
    setLoadingTickets(true)
    try {
      const res = await messagesApi.generateTickets(selected.id)
      setTicketsCreated(res.created)
    } finally { setLoadingTickets(false) }
  }

  return (
    <AppShell>
      <div className="flex h-full">
        {/* Message list */}
        <div className="w-80 border-r border-white/10 flex flex-col shrink-0">
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
            <h1 className="text-white text-sm font-semibold">Inbox <span className="text-slate-500 font-normal">({messages.length})</span></h1>
            <button onClick={() => setShowNew(true)}
              className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 bg-indigo-500/10 hover:bg-indigo-500/20 px-2 py-1 rounded-lg transition-colors">
              <Plus size={12} />New
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {messages.length === 0 ? (
              <div className="p-6 text-center text-slate-500 text-sm">No messages yet.<br />Click + New to add one.</div>
            ) : messages.map(m => (
              <button key={m.id} onClick={() => handleSelect(m)}
                className={`w-full text-left px-4 py-3 border-b border-white/5 hover:bg-white/5 transition-colors ${selected?.id === m.id ? 'bg-white/5' : ''}`}>
                <div className="flex items-start justify-between gap-2 mb-1">
                  <p className="text-white text-sm font-medium truncate">{m.name || 'Anonymous'}</p>
                  <SentimentBadge s={m.sentiment} />
                </div>
                <p className="text-slate-500 text-xs truncate">{m.text}</p>
                <p className="text-slate-600 text-xs mt-1">{new Date(m.created_at).toLocaleDateString()}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Detail panel */}
        <div className="flex-1 overflow-y-auto">
          {!selected ? (
            <div className="flex items-center justify-center h-full text-slate-500 text-sm">Select a message to view details</div>
          ) : (
            <div className="p-6 max-w-2xl">
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-white text-lg font-semibold">{selected.name || 'Anonymous'}</h2>
                  {selected.email && <p className="text-slate-400 text-sm">{selected.email}</p>}
                  <p className="text-slate-500 text-xs mt-1">{new Date(selected.created_at).toLocaleString()}</p>
                </div>
                <SentimentBadge s={selected.sentiment} />
              </div>

              {/* Message text */}
              <div className="bg-slate-900 border border-white/10 rounded-xl p-4 mb-4">
                <p className="text-slate-300 text-sm leading-relaxed">{selected.text}</p>
              </div>

              {/* Actions */}
              <div className="flex gap-3 mb-4">
                <button onClick={handleGenerateReply} disabled={loadingReply}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-3 py-2 rounded-lg text-sm font-medium transition-colors">
                  {loadingReply ? <RefreshCw size={13} className="animate-spin" /> : <Send size={13} />}
                  Generate Reply
                </button>
                <button onClick={handleGenerateTickets} disabled={loadingTickets}
                  className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white px-3 py-2 rounded-lg text-sm font-medium border border-white/10 transition-colors">
                  {loadingTickets ? <RefreshCw size={13} className="animate-spin" /> : <Ticket size={13} />}
                  Create Tickets
                </button>
              </div>

              {ticketsCreated !== null && (
                <div className="mb-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2 text-emerald-400 text-sm">
                  {ticketsCreated} ticket{ticketsCreated !== 1 ? 's' : ''} created in Kanban board.
                </div>
              )}

              {/* Reply box */}
              {reply && (
                <div>
                  <p className="text-slate-400 text-xs font-medium uppercase tracking-wider mb-2">Suggested Reply</p>
                  <div className="bg-slate-900 border border-indigo-500/20 rounded-xl p-4">
                    <p className="text-slate-300 text-sm leading-relaxed">{reply}</p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {showNew && (
        <NewMessageModal
          onClose={() => setShowNew(false)}
          onCreated={m => { setMessages(prev => [m, ...prev]); setSelected(m) }}
        />
      )}
    </AppShell>
  )
}
