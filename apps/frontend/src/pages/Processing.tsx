import React, { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Instagram, Youtube, Linkedin, Globe, Loader2 } from 'lucide-react'
import { useProcessingContents } from '../hooks/useContents'
import { ProcessingItem } from '../services/contentApi'
import { ProcessingDetailModal } from '../components/ProcessingDetailModal'
import { timeAgo } from '../utils/date'
import { cn } from '../utils/cn'

const platformConfig: Record<
  string,
  { label: string; icon: React.ElementType; className: string }
> = {
  instagram: {
    label: 'Instagram',
    icon: Instagram,
    className: 'bg-gradient-to-r from-pink-100 to-purple-100 text-pink-700',
  },
  youtube: {
    label: 'YouTube',
    icon: Youtube,
    className: 'bg-red-100 text-red-700',
  },
  linkedin: {
    label: 'LinkedIn',
    icon: Linkedin,
    className: 'bg-blue-100 text-blue-700',
  },
}

const STAGE_ORDER = ['queued', 'capturing', 'ocr', 'ai_processing', 'finalizing'] as const

const STAGE_LABELS: Record<string, string> = {
  queued: 'Na fila',
  capturing: 'Capturando',
  ocr: 'OCR',
  ai_processing: 'Analisando',
  finalizing: 'Finalizando',
  completed: 'Concluído',
  failed: 'Falhou',
}

function PlatformBadge({ platform }: { platform: string | null }) {
  const cfg = platform ? platformConfig[platform] : null
  if (!cfg) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
        <Globe className="h-3 w-3" />
        Web
      </span>
    )
  }
  const Icon = cfg.icon
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
        cfg.className
      )}
    >
      <Icon className="h-3 w-3" />
      {cfg.label}
    </span>
  )
}

function StageIndicator({ stage }: { stage: string | null }) {
  const resolvedStage = stage ?? 'queued'

  if (resolvedStage === 'failed') {
    return (
      <div className="flex items-center gap-1.5 flex-shrink-0">
        <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
        <span className="text-xs font-medium text-red-600">Falhou</span>
      </div>
    )
  }

  const isQueued = resolvedStage === 'queued'
  const currentIdx = STAGE_ORDER.indexOf(resolvedStage as typeof STAGE_ORDER[number])

  return (
    <>
      {/* Mobile: current stage only */}
      <div className="flex items-center gap-1.5 flex-shrink-0 sm:hidden">
        <span
          className={cn(
            'h-1.5 w-1.5 rounded-full',
            isQueued ? 'bg-muted-foreground/50' : 'animate-pulse bg-amber-500'
          )}
        />
        <span
          className={cn(
            'text-xs font-medium',
            isQueued ? 'text-muted-foreground' : 'text-amber-600'
          )}
        >
          {STAGE_LABELS[resolvedStage] ?? resolvedStage}
        </span>
      </div>

      {/* Desktop: full pipeline */}
      <div className="hidden sm:flex items-center gap-1 flex-shrink-0">
        {STAGE_ORDER.map((s, i) => {
          const isPast = i < currentIdx
          const isCurrent = i === currentIdx
          return (
            <React.Fragment key={s}>
              {i > 0 && (
                <span
                  className={cn(
                    'text-xs mx-0.5',
                    isPast || isCurrent
                      ? 'text-muted-foreground/50'
                      : 'text-muted-foreground/25'
                  )}
                >
                  →
                </span>
              )}
              <div
                className={cn(
                  'flex items-center gap-1 text-xs',
                  isCurrent && !isQueued && 'font-medium text-amber-600',
                  isCurrent && isQueued && 'text-muted-foreground',
                  isPast && 'text-muted-foreground/50',
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
    </>
  )
}

function ProcessingRow({
  item,
  onClick,
}: {
  item: ProcessingItem
  onClick: () => void
}) {
  const displayUrl = item.url || '—'
  const truncated =
    displayUrl.length > 60 ? displayUrl.slice(0, 60) + '…' : displayUrl

  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full flex items-center gap-4 px-5 py-4 border-b border-border last:border-0 text-left hover:bg-muted/40 transition-colors cursor-pointer"
    >
      <PlatformBadge platform={item.source_platform} />

      <span
        className="flex-1 text-sm text-muted-foreground font-mono truncate"
        title={displayUrl}
      >
        {truncated}
      </span>

      <StageIndicator stage={item.processing_stage} />

      <span className="text-xs text-muted-foreground flex-shrink-0 hidden sm:block">
        {timeAgo(item.created_at)}
      </span>
    </button>
  )
}

function SkeletonRow() {
  return (
    <div className="flex items-center gap-4 px-5 py-4 border-b border-border last:border-0 animate-pulse">
      <div className="h-5 w-20 rounded-full bg-muted" />
      <div className="flex-1 h-4 rounded bg-muted" />
      <div className="h-4 w-40 rounded bg-muted" />
      <div className="h-4 w-16 rounded bg-muted hidden sm:block" />
    </div>
  )
}

export function Processing() {
  const queryClient = useQueryClient()

  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: ['contents-processing'] })
  }, [queryClient])

  const { data: items, isLoading } = useProcessingContents()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">
            Processamento
          </h1>
          <p className="text-muted-foreground mt-1">
            Conteúdos sendo processados agora
          </p>
        </div>
        {!isLoading && (
          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Atualizando…
          </div>
        )}
      </div>

      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        {isLoading ? (
          <>
            <SkeletonRow />
            <SkeletonRow />
            <SkeletonRow />
          </>
        ) : items && items.length > 0 ? (
          items.map((item) => (
            <ProcessingRow
              key={item.id}
              item={item}
              onClick={() => setSelectedId(item.id)}
            />
          ))
        ) : (
          <div className="py-16 text-center">
            <div className="mx-auto h-10 w-10 rounded-full bg-muted flex items-center justify-center mb-3">
              <Loader2 className="h-5 w-5 text-muted-foreground" />
            </div>
            <p className="text-sm font-medium text-foreground">
              Nenhum processamento em andamento
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Os itens aparecem aqui automaticamente quando são enviados para processamento.
            </p>
          </div>
        )}
      </div>

      {selectedId && (
        <ProcessingDetailModal
          contentId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  )
}
