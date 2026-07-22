import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { authApi } from '../services/api'

interface User { id: string; email: string; full_name?: string }
interface AuthContextType { user: User | null; token: string | null; login: (email: string, password: string) => Promise<void>; register: (email: string, password: string, fullName?: string) => Promise<void>; logout: () => void; loading: boolean }

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'))
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (token) {
      authApi.me(token).then(u => { setUser(u); setLoading(false) }).catch(() => { localStorage.removeItem('token'); setToken(null); setLoading(false) })
    } else {
      setLoading(false)
    }
  }, [token])

  const login = async (email: string, password: string) => {
    const { access_token } = await authApi.login(email, password)
    localStorage.setItem('token', access_token)
    setToken(access_token)
  }

  const register = async (email: string, password: string, fullName?: string) => {
    const { access_token } = await authApi.register(email, password, fullName)
    localStorage.setItem('token', access_token)
    setToken(access_token)
  }

  const logout = () => { localStorage.removeItem('token'); setToken(null); setUser(null) }

  return <AuthContext.Provider value={{ user, token, login, register, logout, loading }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
