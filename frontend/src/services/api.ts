import axios from 'axios'

const BASE = '/api'

// Auth — plain axios (no interceptors)
export const authApi = {
  login: async (email: string, password: string) => {
    const { data } = await axios.post(`${BASE}/auth/login`, { email, password })
    return data
  },
  register: async (email: string, password: string, full_name?: string) => {
    const { data } = await axios.post(`${BASE}/auth/register`, { email, password, full_name })
    return data
  },
  me: async (token: string) => {
    const { data } = await axios.get(`${BASE}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
    return data
  },
  forgotPassword: async (email: string) => {
    const { data } = await axios.post(`${BASE}/auth/forgot-password`, { email })
    return data
  },
  resetPassword: async (token: string, new_password: string) => {
    const { data } = await axios.post(`${BASE}/auth/reset-password`, { token, new_password })
    return data
  },
}

// Authenticated client
export const apiClient = axios.create({ baseURL: BASE })

apiClient.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

apiClient.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) { localStorage.removeItem('token'); window.location.href = '/login' }
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
  list: async () => {
    const { data } = await apiClient.get('/messages')
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
