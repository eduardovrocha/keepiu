import axios, { AxiosError } from 'axios'
import { useAuthStore } from '../store/authStore'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

let _refreshing: Promise<boolean> | null = null

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (typeof error.config & { _retry?: boolean }) | undefined

    // Don't retry refresh/login/logout calls — avoids infinite loops
    const isAuthEndpoint = original?.url?.includes('/auth/refresh') ||
      original?.url?.includes('/auth/login') ||
      original?.url?.includes('/auth/logout')

    if (error.response?.status === 401 && original && !original._retry && !isAuthEndpoint) {
      original._retry = true

      // Deduplicate concurrent refresh attempts
      if (!_refreshing) {
        _refreshing = api.post('/auth/refresh')
          .then(() => true)
          .catch(() => false)
          .finally(() => { _refreshing = null })
      }

      const refreshed = await _refreshing

      if (refreshed) {
        return api(original)
      }

      // Refresh failed — session is over
      useAuthStore.getState().logout()
    } else if (error.response?.status === 401 && isAuthEndpoint) {
      useAuthStore.getState().logout()
    }

    return Promise.reject(error)
  }
)
