import axios from 'axios'

const BASE = '/api'

// Auth axios — no response interceptor to avoid redirect loops during refresh
const authAxios = axios.create({ baseURL: BASE, withCredentials: true })

export const authApi = {
  login: async (email: string, password: string) => {
    const { data } = await authAxios.post('/auth/login', { email, password })
    return data
  },
  register: async (email: string, password: string, full_name?: string) => {
    const { data } = await authAxios.post('/auth/register', { email, password, full_name })
    return data
  },
  me: async () => {
    const { data } = await authAxios.get('/auth/me')
    return data
  },
  refresh: async () => {
    const { data } = await authAxios.post('/auth/refresh')
    return data
  },
  logout: async () => {
    await authAxios.post('/auth/logout')
  },
  forgotPassword: async (email: string) => {
    const { data } = await authAxios.post('/auth/forgot-password', { email })
    return data
  },
  resetPassword: async (token: string, new_password: string) => {
    const { data } = await authAxios.post('/auth/reset-password', { token, new_password })
    return data
  },
  deleteAccount: async () => {
    await apiClient.delete('/auth/me')
  },
}

// Authenticated client — sends cookies automatically, handles silent refresh
export const apiClient = axios.create({ baseURL: BASE, withCredentials: true })

let isRefreshing = false
let failedQueue: Array<{ resolve: () => void; reject: (err: unknown) => void }> = []

const processQueue = (error: unknown) => {
  failedQueue.forEach(p => (error ? p.reject(error) : p.resolve()))
  failedQueue = []
}

apiClient.interceptors.response.use(
  r => r,
  async err => {
    const original = err.config
    if (err.response?.status === 401 && !original._retry) {
      if (isRefreshing) {
        return new Promise<void>((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then(() => apiClient(original))
      }
      original._retry = true
      isRefreshing = true
      try {
        await authAxios.post('/auth/refresh')
        processQueue(null)
        return apiClient(original)
      } catch (refreshErr) {
        processQueue(refreshErr)
        window.location.href = '/login'
        return Promise.reject(refreshErr)
      } finally {
        isRefreshing = false
      }
    }
    return Promise.reject(err)
  }
)

// DataSources
export const datasourceApi = {
  list: async () => {
    const { data } = await apiClient.get('/datasources')
    return data
  },
  createGPlay: async (payload: { name: string; app_id: string; count: number; lang: string; country: string }) => {
    const { data } = await apiClient.post('/datasources/google-play', payload)
    return data
  },
  uploadCsv: async (formData: FormData) => {
    const { data } = await apiClient.post('/datasources/upload-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },
  delete: async (id: string) => {
    await apiClient.delete(`/datasources/${id}`)
  },
  retry: async (id: string) => {
    const { data } = await apiClient.post(`/datasources/${id}/retry`)
    return data
  },
}

// Jobs
export const jobsApi = {
  get: async (jobId: string) => {
    const { data } = await apiClient.get(`/jobs/${jobId}`)
    return data
  },
}

// Dashboard
export const dashboardApi = {
  summary: async (datasourceId: string) => {
    const { data } = await apiClient.get(`/dashboard/summary?datasource_id=${datasourceId}`)
    return data
  },
  insight: async (datasourceId: string) => {
    const { data } = await apiClient.get(`/dashboard/insight?datasource_id=${datasourceId}`)
    return data
  },
}

// Tickets
export const ticketsApi = {
  list: async (params?: { status?: string; priority?: string }) => {
    const q = new URLSearchParams(params as Record<string, string>).toString()
    const { data } = await apiClient.get(`/tickets${q ? '?' + q : ''}`)
    return data
  },
  create: async (payload: object) => {
    const { data } = await apiClient.post('/tickets', payload)
    return data
  },
  update: async (id: string, payload: object) => {
    const { data } = await apiClient.patch(`/tickets/${id}`, payload)
    return data
  },
  delete: async (id: string) => {
    await apiClient.delete(`/tickets/${id}`)
  },
}

// Messages
export const messagesApi = {
  list: async (sentiment?: string) => {
    const q = sentiment ? `?sentiment=${sentiment}` : ''
    const { data } = await apiClient.get(`/messages${q}`)
    return data
  },
  create: async (payload: { name?: string; email?: string; text: string }) => {
    const { data } = await apiClient.post('/messages', payload)
    return data
  },
  generateReply: async (id: string) => {
    const { data } = await apiClient.post(`/messages/${id}/generate-reply`)
    return data
  },
  generateTickets: async (id: string) => {
    const { data } = await apiClient.post(`/messages/${id}/generate-tickets`)
    return data
  },
  sendReply: async (id: string, reply: string) => {
    const { data } = await apiClient.post(`/messages/${id}/send-reply`, { reply })
    return data
  },
}
