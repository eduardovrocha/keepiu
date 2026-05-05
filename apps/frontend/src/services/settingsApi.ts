import { api } from './api'
import {
  SystemSetting,
  SettingRevealResponse,
  SettingsRevealAllResponse,
  TestSettingsResponse,
} from '../types'

export const getSettings = async (): Promise<SystemSetting[]> => {
  const response = await api.get('/settings')
  return response.data
}

export const updateSettings = async (
  updates: { key: string; value: string }[]
): Promise<SystemSetting[]> => {
  const response = await api.put('/settings', { settings: updates })
  return response.data
}

export const revealAllSettings = async (): Promise<SettingsRevealAllResponse> => {
  const response = await api.post('/settings/reveal')
  return response.data
}

export const revealSetting = async (key: string): Promise<SettingRevealResponse> => {
  const response = await api.post(`/settings/${key}/reveal`)
  return response.data
}

export const testSettings = async (): Promise<TestSettingsResponse> => {
  const response = await api.post('/settings/test')
  return response.data
}
