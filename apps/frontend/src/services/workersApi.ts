import { api } from './api'

export interface TaskMetrics {
  name: string
  task_name: string
  avg_duration_ms: number | null
  error_rate: number
  processed_last_1h: number
}

export interface WorkerTotals {
  active: number
  queued: number
  processed_last_1h: number
  error_rate: number
}

export interface WorkersStatus {
  tasks: TaskMetrics[]
  totals: WorkerTotals
}

export const getWorkersStatus = async (): Promise<WorkersStatus> => {
  const response = await api.get('/workers/status')
  return response.data
}
