import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getSettings,
  updateSettings,
  revealAllSettings,
  testSettings,
} from '../services/settingsApi'

export const useSettings = (enabled = true) => {
  return useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
    enabled,
  })
}

// Fetches all plain values on mount — used to pre-populate form fields.
// staleTime=Infinity means it won't re-fetch silently; gcTime=0 means it's
// not retained after the component unmounts (reduces in-memory exposure).
export const useRevealAllSettings = (enabled = true) => {
  return useQuery({
    queryKey: ['settings-revealed'],
    queryFn: revealAllSettings,
    staleTime: Infinity,
    gcTime: 0,
    enabled,
  })
}

export const useUpdateSettings = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (updates: { key: string; value: string }[]) =>
      updateSettings(updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      queryClient.invalidateQueries({ queryKey: ['settings-revealed'] })
    },
  })
}

export const useTestSettings = () => {
  return useMutation({
    mutationFn: testSettings,
  })
}
