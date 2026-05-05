import { useState } from 'react'
import { Layers, Loader2, CheckCircle } from 'lucide-react'
import { useProcessInstagramBatch } from '../hooks/useContents'
import { cn } from '../utils/cn'

export function InstagramBatchButton() {
  const [feedback, setFeedback] = useState<string | null>(null)
  const mutation = useProcessInstagramBatch()

  const handleClick = () => {
    mutation.mutate(undefined, {
      onSuccess: ({ queued }) => {
        setFeedback(
          queued === 0
            ? 'Nenhum item pendente'
            : `${queued} ${queued === 1 ? 'item enviado' : 'itens enviados'} para processamento`
        )
        setTimeout(() => setFeedback(null), 4000)
      },
    })
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={handleClick}
        disabled={mutation.isPending}
        className={cn(
          'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
          'border border-border bg-background text-muted-foreground',
          'hover:bg-muted hover:text-foreground',
          'disabled:opacity-50 disabled:cursor-not-allowed'
        )}
      >
        {mutation.isPending ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Layers className="w-4 h-4" />
        )}
        Processar Instagram
      </button>
      {feedback && (
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          <CheckCircle className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />
          {feedback}
        </span>
      )}
    </div>
  )
}
