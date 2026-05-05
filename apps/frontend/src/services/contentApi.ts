import { api } from './api'
import { Content, ContentListResponse, DashboardStats, SearchResult } from '../types'

export const login = async (username: string, password: string) => {
  const response = await api.post('/auth/login', { username, password })
  return response.data
}

export const getDashboardStats = async (): Promise<DashboardStats> => {
  const response = await api.get('/dashboard/stats')
  return response.data
}

export const getContents = async (params?: {
  page?: number
  page_size?: number
  category?: string
  type?: string
  processed?: boolean
  ingestion_channel?: string
  source_platform?: string
  status?: string
}): Promise<ContentListResponse> => {
  const response = await api.get('/contents', { params })
  return response.data
}

export const getContent = async (id: string): Promise<Content> => {
  const response = await api.get(`/contents/${id}`)
  return response.data
}

export const updateContent = async (id: string, data: Partial<Content>): Promise<Content> => {
  const response = await api.put(`/contents/${id}`, data)
  return response.data
}

export const deleteContent = async (id: string) => {
  const response = await api.delete(`/contents/${id}`)
  return response.data
}

export const searchContents = async (query: string, limit = 10): Promise<SearchResult[]> => {
  const response = await api.post('/search/semantic', { query, limit })
  return response.data
}

export const getCategories = async (): Promise<{ category: string; count: number }[]> => {
  const response = await api.get('/search/categories')
  return response.data
}

export const reprocessContent = async (id: string): Promise<{ requeued: boolean; content_id: string }> => {
  const response = await api.post(`/contents/${id}/reprocess`)
  return response.data
}

export const createContent = async (data: {
  source_url: string
  source_platform: string
}): Promise<Content> => {
  const response = await api.post('/contents', data)
  return response.data
}

export const processContentBatch = async (): Promise<{ queued: number }> => {
  const response = await api.post('/content/process-batch')
  return response.data
}

export interface ProcessingItem {
  id: string
  url: string | null
  source_platform: string | null
  ingestion_channel: string | null
  status: string
  processing_stage: string | null
  created_at: string
}

export const getProcessingContents = async (): Promise<ProcessingItem[]> => {
  const response = await api.get('/contents/processing')
  return response.data
}
