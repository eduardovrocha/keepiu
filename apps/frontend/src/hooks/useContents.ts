import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getContents,
  getContent,
  updateContent,
  deleteContent,
  searchContents,
  getCategories,
  getDashboardStats,
  reprocessContent,
  createContent,
  processContentBatch,
  getProcessingContents,
} from '../services/contentApi'
import { Content } from '../types'

export const useDashboardStats = () => {
  return useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  })
}

export const useContents = (params?: {
  page?: number
  page_size?: number
  category?: string
  type?: string
  processed?: boolean
  ingestion_channel?: string
  source_platform?: string
  status?: string
}) => {
  return useQuery({
    queryKey: ['contents', params],
    queryFn: () => getContents(params),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  })
}

export const useContent = (id: string) => {
  return useQuery({
    queryKey: ['content', id],
    queryFn: () => getContent(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'processing' || status === 'queued' ? 5_000 : false
    },
  })
}

export const useUpdateContent = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Content> }) =>
      updateContent(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['content', variables.id] })
      queryClient.invalidateQueries({ queryKey: ['contents'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })
}

export const useDeleteContent = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteContent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contents'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })
}

export const useReprocessContent = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => reprocessContent(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['content', id] })
      queryClient.invalidateQueries({ queryKey: ['contents'] })
    },
  })
}

export const useCreateContent = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { source_url: string; source_platform: string }) =>
      createContent(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contents'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })
}

export const useProcessContentBatch = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: processContentBatch,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contents'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })
}

export const useSearch = (query: string, enabled = false) => {
  return useQuery({
    queryKey: ['search', query],
    queryFn: () => searchContents(query),
    enabled: enabled && query.length > 0,
  })
}

export const useProcessingContents = () => {
  return useQuery({
    queryKey: ['contents-processing'],
    queryFn: getProcessingContents,
    refetchInterval: 3_000,
    refetchIntervalInBackground: false,
  })
}

export const useCategories = () => {
  return useQuery({
    queryKey: ['categories'],
    queryFn: getCategories,
  })
}
