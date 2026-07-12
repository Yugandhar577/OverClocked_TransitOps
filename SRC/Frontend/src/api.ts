import axios from 'axios'

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

export const api = axios.create({ baseURL: API_BASE_URL })

api.interceptors.request.use((config) => {
  const session = localStorage.getItem('transitops-session')
  if (session) config.headers.Authorization = `Bearer ${JSON.parse(session).access_token}`
  return config
})

export const currentToken = () => {
  const saved = localStorage.getItem('transitops-session')
  return saved ? JSON.parse(saved).access_token as string : null
}

export const messageFrom = (error: unknown) => axios.isAxiosError(error)
  ? error.response?.data?.detail || 'Unable to save this change.'
  : error instanceof Error ? error.message : 'Unable to save this change.'
