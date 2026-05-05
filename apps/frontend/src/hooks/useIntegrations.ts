import { useQuery } from '@tanstack/react-query'
import { getWhatsAppStatus } from '../services/integrationsApi'

export const useWhatsAppStatus = () => {
  return useQuery({
    queryKey: ['whatsapp-status'],
    queryFn: getWhatsAppStatus,
    staleTime: 60_000,
  })
}
