import { api } from './api'
import { WhatsAppIntegrationStatus } from '../types'

export const getWhatsAppStatus = async (): Promise<WhatsAppIntegrationStatus> => {
  const response = await api.get('/integrations/whatsapp/status')
  return response.data
}
