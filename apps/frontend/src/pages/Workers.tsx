import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { getWorkersStatus, TaskMetrics } from '../services/workersApi'
import { cn } from '../utils/cn'

function formatDuration(ms: number | null): string {
  if (ms === null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatErrorRate(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`
}

function durationColor(ms: number | null): string {
  if (ms === null) return 'text-muted-foreground'
  if (ms < 1000) return 'text-green-600'
  if (ms <= 3000) return 'text-amber-600'
  return 'text-red-600'
}

function errorColor(rate: number): string {
  if (rate < 0.05) return 'text-green-600'
  if (rate <= 0.15) return 'text-amber-600'
  return 'text-red-600'
}

function errorBadge(rate: number): string {
  if (rate < 0.05) return 'bg-green-50 text-green-700 ring-green-200'
  if (rate <= 0.15) return 'bg-amber-50 text-amber-700 ring-amber-200'
  return 'bg-red-50 text-red-700 ring-red-200'
}

function SummaryCard({
  label,
  value,
  valueClass,
}: {
  label: string
  value: string | number
  valueClass?: string
}) {
  return (
    <div className="rounded-xl border border-border bg-card px-5 py-4 shadow-sm">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn('text-2xl font-semibold mt-1', valueClass ?? 'text-foreground')}>
        {value}
      </p>
    </div>
  )
}

function TaskCard({ task }: { task: TaskMetrics }) {
  const hasData = task.processed_last_1h > 0

  return (
    <div className="rounded-xl border border-border bg-card shadow-sm p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-foreground">{task.name}</p>
        {hasData ? (
          <span
            className={cn(
              'text-xs font-medium rounded-full px-2 py-0.5 ring-1',
              errorBadge(task.error_rate)
            )}
          >
            {formatErrorRate(task.error_rate)} erro
          </span>
        ) : (
          <span className="text-xs text-muted-foreground/50">Sem dados</span>
        )}
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-xs text-muted-foreground mb-0.5">Tempo médio</p>
          <p className={cn('text-lg font-semibold tabular-nums', durationColor(task.avg_duration_ms))}>
            {formatDuration(task.avg_duration_ms)}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground mb-0.5">Última hora</p>
          <p className="text-lg font-semibold text-foreground tabular-nums">
            {task.processed_last_1h}
            <span className="text-xs font-normal text-muted-foreground ml-1">exec</span>
          </p>
        </div>
      </div>

      {/* Duration bar (visual hint) */}
      {task.avg_duration_ms !== null && (
        <div className="h-1 rounded-full bg-muted overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all',
              task.avg_duration_ms < 1000
                ? 'bg-green-500'
                : task.avg_duration_ms <= 3000
                ? 'bg-amber-500'
                : 'bg-red-500'
            )}
            style={{
              width: `${Math.min(100, (task.avg_duration_ms / 5000) * 100)}%`,
            }}
          />
        </div>
      )}
    </div>
  )
}

function SkeletonCard() {
  return (
    <div className="rounded-xl border border-border bg-card shadow-sm p-5 space-y-4 animate-pulse">
      <div className="flex items-center justify-between">
        <div className="h-4 w-24 rounded bg-muted" />
        <div className="h-5 w-16 rounded-full bg-muted" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <div className="h-3 w-20 rounded bg-muted" />
          <div className="h-6 w-14 rounded bg-muted" />
        </div>
        <div className="space-y-1">
          <div className="h-3 w-20 rounded bg-muted" />
          <div className="h-6 w-14 rounded bg-muted" />
        </div>
      </div>
      <div className="h-1 rounded-full bg-muted" />
    </div>
  )
}

export function Workers() {
  const queryClient = useQueryClient()

  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: ['workers-status'] })
  }, [queryClient])

  const { data, isLoading } = useQuery({
    queryKey: ['workers-status'],
    queryFn: getWorkersStatus,
    refetchInterval: 5_000,
    refetchIntervalInBackground: false,
  })

  const totals = data?.totals
  const tasks = data?.tasks ?? []

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Workers</h1>
          <p className="text-muted-foreground mt-1">
            Observabilidade do pipeline de processamento
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Atualizando…
        </div>
      </div>

      {/* Summary row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {isLoading ? (
          <>
            {[...Array(4)].map((_, i) => (
              <div
                key={i}
                className="rounded-xl border border-border bg-card px-5 py-4 shadow-sm animate-pulse space-y-2"
              >
                <div className="h-3 w-20 rounded bg-muted" />
                <div className="h-7 w-12 rounded bg-muted" />
              </div>
            ))}
          </>
        ) : (
          <>
            <SummaryCard label="Ativos agora" value={totals?.active ?? 0} />
            <SummaryCard label="Na fila" value={totals?.queued ?? 0} />
            <SummaryCard
              label="Última hora"
              value={`${totals?.processed_last_1h ?? 0} exec`}
            />
            <SummaryCard
              label="Taxa de erro"
              value={formatErrorRate(totals?.error_rate ?? 0)}
              valueClass={errorColor(totals?.error_rate ?? 0)}
            />
          </>
        )}
      </div>

      {/* Divider + legend */}
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
          Rápido (&lt;1s)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-amber-500" />
          Médio (1–3s)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-red-500" />
          Lento (&gt;3s)
        </span>
      </div>

      {/* Task cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {isLoading
          ? [...Array(4)].map((_, i) => <SkeletonCard key={i} />)
          : tasks.map((task) => <TaskCard key={task.task_name} task={task} />)}
      </div>

      <p className="text-xs text-muted-foreground">
        Métricas da última hora · atualiza a cada 5s
      </p>
    </div>
  )
}
