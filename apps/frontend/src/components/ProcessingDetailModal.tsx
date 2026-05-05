import React, { useEffect } from 'react'
import { X } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { getContent } from '../services/contentApi'
import { timeAgo } from '../utils/date'
import { cn } from '../utils/cn'

const STAGE_ORDER = ['queued', 'capturing', 'ocr', 'ai_processing', 'finalizing'] as const

const STAGE_LABELS: Record<string, string> = {
  queued: 'Na fila',
  capturing: 'Capturando',
  ocr: 'Extraindo texto',
  ai_processing: 'Analisando',
  finalizing: 'Finalizando',
  completed: 'Concluído',
  failed: 'Falhou',
}

const PLATFORM_LABELS: Record<string, string> = {
  instagram: 'Instagram',
  youtube: 'YouTube',
  linkedin: 'LinkedIn',
}

interface Props {
  contentId: string
  onClose: () => void
}

export function ProcessingDetailModal({ contentId, onClose }: Props) {
  const { data: content, isLoading } = useQuery({
    queryKey: ['content', contentId],
    queryFn: () => getContent(contentId),
    refetchInterval: 3_000,
    refetchIntervalInBackground: false,
  })

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const stage = content?.processing_stage ?? null
  const currentIdx = stage ? STAGE_ORDER.indexOf(stage as typeof STAGE_ORDER[number]) : -1
  const isFailed = stage === 'failed' || content?.status === 'failed'
  const isCompleted = stage === 'completed' || content?.status === 'completed'
  const isQueued = stage === 'queued'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md mx-4 bg-card rounded-2xl border border-border shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          className="absolute right-4 top-4 text-muted-foreground hover:text-foreground transition-colors"
          onClick={onClose}
          aria-label="Fechar"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="p-6 space-y-5">
          {isLoading ? (
            <div className="py-10 text-center text-sm text-muted-foreground">
              Carregando detalhes…
            </div>
          ) : !content ? (
            <div className="py-10 text-center text-sm text-muted-foreground">
              Item não encontrado
            </div>
          ) : (
            <>
              {/* Header */}
              <div className="space-y-1 pr-6">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {content.source_platform
                    ? (PLATFORM_LABELS[content.source_platform] ?? content.source_platform)
                    : 'Web'}
                </p>
                {content.url && (
                  <p className="text-sm font-mono text-foreground break-all line-clamp-2">
                    {content.url}
                  </p>
                )}
              </div>

              <hr className="border-border" />

              {/* Stage + time */}
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-0.5">
                  <p className="text-xs text-muted-foreground">Etapa atual</p>
                  {isFailed ? (
                    <p className="text-sm font-medium text-red-600">Falhou</p>
                  ) : isCompleted ? (
                    <p className="text-sm font-medium text-green-600">Concluído</p>
                  ) : (
                    <p className={cn(
                      'text-sm font-medium',
                      isQueued ? 'text-muted-foreground' : 'text-amber-600'
                    )}>
                      {STAGE_LABELS[stage ?? 'queued']}
                    </p>
                  )}
                </div>
                <p className="text-xs text-muted-foreground flex-shrink-0 pt-1">
                  Iniciado {timeAgo(content.created_at)}
                </p>
              </div>

              {/* Pipeline */}
              {!isFailed && !isCompleted && (
                <div className="flex flex-wrap items-center gap-1">
                  {STAGE_ORDER.map((s, i) => {
                    const isPast = currentIdx !== -1 && i < currentIdx
                    const isCurrent = i === currentIdx
                    return (
                      <React.Fragment key={s}>
                        {i > 0 && (
                          <span className="text-muted-foreground/40 text-xs">→</span>
                        )}
                        <div
                          className={cn(
                            'flex items-center gap-1 rounded-full px-2 py-0.5 text-xs',
                            isCurrent && !isQueued && 'bg-amber-50 dark:bg-amber-950 font-medium text-amber-700 dark:text-amber-400 ring-1 ring-amber-200 dark:ring-amber-800',
                            isCurrent && isQueued && 'bg-muted text-muted-foreground',
                            isPast && 'text-muted-foreground/40',
                            !isCurrent && !isPast && 'text-muted-foreground/30'
                          )}
                        >
                          {isCurrent && !isQueued && (
                            <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500" />
                          )}
                          {STAGE_LABELS[s]}
                        </div>
                      </React.Fragment>
                    )
                  })}
                </div>
              )}

              {/* Completed state */}
              {isCompleted && (
                <div className="rounded-lg border border-green-100 dark:border-green-800/30 bg-green-50 dark:bg-green-950/20 px-4 py-3 text-center">
                  <p className="text-sm font-medium text-green-700 dark:text-green-400">
                    Processamento concluído
                  </p>
                </div>
              )}

              {/* Error */}
              {isFailed && content.processing_error && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3">
                  <p className="mb-0.5 text-xs font-medium text-destructive">Erro</p>
                  <p className="text-xs text-destructive/80">{content.processing_error}</p>
                </div>
              )}

              {isFailed && !content.processing_error && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-center">
                  <p className="text-sm font-medium text-destructive">
                    Falha no processamento
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
