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
  createGPlay: async (payload: { name: string; app_id: string; count: number; lang: string; country: string; industry: string }) => {
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
  fetchAll: async (id: string) => {
    const { data } = await apiClient.post(`/datasources/${id}/fetch-all`)
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
  competitive: async () => {
    const { data } = await apiClient.get('/dashboard/competitive')
    return data
  },
  sentimentTrend: async (datasourceId: string) => {
    const { data } = await apiClient.get(`/dashboard/sentiment-trend?datasource_id=${datasourceId}`)
    return data
  },
  versionAnalysis: async (datasourceId: string) => {
    const { data } = await apiClient.get(`/dashboard/version-analysis?datasource_id=${datasourceId}`)
    return data
  },
  versionCompare: async (datasourceId: string, clusterId: string, v1: string, v2: string) => {
    const { data } = await apiClient.get(`/dashboard/version-compare?datasource_id=${datasourceId}&cluster_id=${clusterId}&v1=${encodeURIComponent(v1)}&v2=${encodeURIComponent(v2)}`)
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

// Search
export const searchApi = {
  search: async (params: {
    datasource_id: string
    q: string
    search_type?: string
    rerank?: boolean
    limit?: number
    sentiment?: string
  }) => {
    const p: Record<string, string> = { datasource_id: params.datasource_id, q: params.q }
    if (params.search_type) p.search_type = params.search_type
    if (params.rerank !== undefined) p.rerank = String(params.rerank)
    if (params.limit !== undefined) p.limit = String(params.limit)
    if (params.sentiment) p.sentiment = params.sentiment
    const { data } = await apiClient.get(`/search?${new URLSearchParams(p)}`)
    return data
  },
}

// Intelligence
export const intelligenceApi = {
  matrix: async (datasourceId: string) => {
    const { data } = await apiClient.get(`/intelligence/matrix?datasource_id=${datasourceId}`)
    return data
  },
  feature: async (datasourceId: string, feature: string, signalTypeFilter?: string, versionFilter?: string, sortBy?: string, dateFrom?: string, dateTo?: string, versionFrom?: string, versionTo?: string) => {
    const p = new URLSearchParams({ datasource_id: datasourceId, feature })
    if (signalTypeFilter) p.set('signal_type_filter', signalTypeFilter)
    if (versionFilter) p.set('version_filter', versionFilter)
    if (sortBy) p.set('sort_by', sortBy)
    if (dateFrom) p.set('date_from', dateFrom)
    if (dateTo) p.set('date_to', dateTo)
    if (versionFrom) p.set('version_from', versionFrom)
    if (versionTo) p.set('version_to', versionTo)
    const { data } = await apiClient.get(`/intelligence/feature?${p}`)
    return data
  },
  reviewAspects: async (reviewId: string) => {
    const { data } = await apiClient.get(`/intelligence/review/${reviewId}/aspects`)
    return data
  },
  versionBreakdown: async (datasourceId: string, version: string) => {
    const { data } = await apiClient.get(`/intelligence/version-breakdown?datasource_id=${datasourceId}&version=${encodeURIComponent(version)}`)
    return data
  },
  backfillReplies: async (datasourceId: string) => {
    const { data } = await apiClient.post(`/intelligence/backfill-replies?datasource_id=${datasourceId}`)
    return data
  },
  reclassifyGeneral: async (datasourceId: string) => {
    const { data } = await apiClient.post(`/intelligence/reclassify-general?datasource_id=${datasourceId}`)
    return data
  },
  reclassifySignals: async (datasourceId: string) => {
    const { data } = await apiClient.post(`/intelligence/reclassify-signals?datasource_id=${datasourceId}`)
    return data
  },
  clusterGeneral: async (datasourceId: string) => {
    const { data } = await apiClient.post(`/intelligence/cluster-general?datasource_id=${datasourceId}`)
    return data
  },
  resolutionCheck: async (reviewId: string) => {
    const { data } = await apiClient.get(`/intelligence/review/${reviewId}/resolution-check`)
    return data
  },
  similarHistory: async (reviewId: string) => {
    const { data } = await apiClient.get(`/intelligence/review/${reviewId}/similar-history`)
    return data
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
