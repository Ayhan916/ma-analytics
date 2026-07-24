import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { LayoutDashboard, Database, Inbox, Kanban, Settings, LogOut, ChevronLeft, ChevronRight } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'

interface NavItem { icon: React.ElementType; label: string; to: string }

const NAV: NavItem[] = [
  { icon: LayoutDashboard, label: 'Dashboard',    to: '/' },
  { icon: Database,        label: 'Data Sources', to: '/datasources' },
  { icon: Inbox,           label: 'Inbox',        to: '/inbox' },
  { icon: Kanban,          label: 'Kanban',       to: '/kanban' },
]

function NavLink({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const { pathname } = useLocation()
  const active = pathname === item.to
  const Icon = item.icon
  return (
    <Link
      to={item.to}
      title={collapsed ? item.label : undefined}
      className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors
        ${active ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-white hover:bg-white/5'}
        ${collapsed ? 'justify-center px-0 py-2.5' : ''}`}
    >
      <Icon size={15} className={`shrink-0 ${active ? 'text-indigo-400' : ''}`} />
      {!collapsed && <span className="truncate flex-1">{item.label}</span>}
      {!collapsed && active && <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />}
    </Link>
  )
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const { user, logout } = useAuth()
  const initials = (user?.email ?? 'U').slice(0, 2).toUpperCase()

  return (
    <div className="flex h-screen overflow-hidden bg-slate-950">
      {/* Sidebar */}
      <aside className={`flex flex-col bg-slate-900 border-r border-white/[0.06] transition-all duration-200 shrink-0
        ${collapsed ? 'w-14' : 'w-52'}`}>

        {/* Logo */}
        <div className={`flex items-center gap-3 h-14 px-4 border-b border-white/[0.06] shrink-0 ${collapsed ? 'justify-center px-0' : ''}`}>
          <div className="w-7 h-7 rounded-lg bg-indigo-500 flex items-center justify-center shrink-0">
            <span className="text-white text-[11px] font-bold">MA</span>
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <p className="text-white text-sm font-semibold leading-none">MA Analytics</p>
              <p className="text-slate-500 text-[10px] mt-0.5 leading-none">Voice of Customer AI</p>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
          {NAV.map(item => <NavLink key={item.to} item={item} collapsed={collapsed} />)}
        </nav>

        {/* Footer */}
        <div className={`shrink-0 border-t border-white/[0.06] p-2 space-y-1`}>
          <Link to="/settings" className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-400 hover:text-white hover:bg-white/5 ${collapsed ? 'justify-center px-0' : ''}`}>
            <Settings size={15} className="shrink-0" />
            {!collapsed && <span>Settings</span>}
          </Link>
          <button onClick={logout} className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-400 hover:text-red-400 hover:bg-white/5 ${collapsed ? 'justify-center px-0' : ''}`}>
            <LogOut size={15} className="shrink-0" />
            {!collapsed && <span>Logout</span>}
          </button>
          {!collapsed && (
            <div className="flex items-center gap-2 px-3 pt-2 pb-1">
              <div className="w-6 h-6 rounded-full bg-indigo-500 flex items-center justify-center text-[10px] font-bold text-white shrink-0">{initials}</div>
              <span className="text-slate-400 text-xs truncate">{user?.email}</span>
            </div>
          )}
        </div>

        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(c => !c)}
          className="absolute left-full top-1/2 -translate-y-1/2 w-4 h-8 bg-slate-800 border border-white/10 rounded-r flex items-center justify-center text-slate-400 hover:text-white"
        >
          {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
        </button>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  )
}
