import { Link } from 'react-router-dom'
import { FileText, Link as LinkIcon, Image, ArrowUpRight, Instagram, RefreshCw, MessageCircle, Send, File, Youtube, Linkedin } from 'lucide-react'
import { Content } from '../types'
import { formatDate } from '../utils/date'
import { cn } from '../utils/cn'
import { useReprocessContent } from '../hooks/useContents'

interface ContentCardProps {
  content: Content
}

const typeIcons: Record<string, React.ElementType> = {
  text: FileText,
  link: LinkIcon,
  image: Image,
  forward: FileText,
  file: File,
}

const typeColors: Record<string, string> = {
  text: 'bg-blue-100 text-blue-700',
  link: 'bg-green-100 text-green-700',
  image: 'bg-purple-100 text-purple-700',
  forward: 'bg-gray-100 text-gray-700',
  file: 'bg-orange-100 text-orange-700',
}

function StatusBadge({ status }: { status: Content['status'] }) {
  if (status === 'queued') {
    return (
      <div className="mt-3 flex items-center gap-2">
        <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40" />
        <span className="text-xs text-muted-foreground">Na fila</span>
      </div>
    )
  }
  if (status === 'processing') {
    return (
      <div className="mt-3 flex items-center gap-2">
        <div className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500" />
        <span className="text-xs text-amber-600">Processando…</span>
      </div>
    )
  }
  if (status === 'failed') {
    return (
      <div className="mt-3 flex items-center gap-2">
        <div className="h-1.5 w-1.5 rounded-full bg-red-500" />
        <span className="text-xs text-red-600">Falhou</span>
      </div>
    )
  }
  return null
}

function ChannelBadge({ channel }: { channel: string | null }) {
  if (channel === 'whatsapp') {
    return (
      <span className="flex-shrink-0 inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
        <MessageCircle className="h-3 w-3" />
        WhatsApp
      </span>
    )
  }
  if (channel === 'telegram') {
    return (
      <span className="flex-shrink-0 inline-flex items-center gap-1 rounded-full bg-sky-100 px-2 py-0.5 text-xs font-medium text-sky-700">
        <Send className="h-3 w-3" />
        Telegram
      </span>
    )
  }
  return null
}

export function ContentCard({ content }: ContentCardProps) {
  const Icon = typeIcons[content.type] || FileText
  const colorClass = typeColors[content.type] || typeColors.text
  const platform = content.source_platform
  const canReprocess = content.status === 'failed'

  const reprocessMutation = useReprocessContent()

  const handleReprocess = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    reprocessMutation.mutate(content.id)
  }

  return (
    <Link
      to={`/content/${content.id}`}
      className="group block rounded-xl border border-border bg-card p-5 shadow-sm transition-all hover:shadow-md hover:border-primary/20 overflow-hidden"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0 flex-1">
          <div className={cn('rounded-lg p-2 flex-shrink-0', colorClass)}>
            <Icon className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 min-w-0">
              <h4 className="font-medium text-foreground truncate">
                {content.title || content.raw_text?.slice(0, 60) || 'Untitled'}
              </h4>
              {platform === 'instagram' && (
                <span className="flex-shrink-0 inline-flex items-center gap-1 rounded-full bg-gradient-to-r from-pink-100 to-purple-100 px-2 py-0.5 text-xs font-medium text-pink-700">
                  <Instagram className="h-3 w-3" />
                  Instagram
                </span>
              )}
              {platform === 'youtube' && (
                <span className="flex-shrink-0 inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                  <Youtube className="h-3 w-3" />
                  YouTube
                </span>
              )}
              {platform === 'linkedin' && (
                <span className="flex-shrink-0 inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                  <Linkedin className="h-3 w-3" />
                  LinkedIn
                </span>
              )}
              <ChannelBadge channel={content.ingestion_channel} />
            </div>
            <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
              {content.summary || content.caption || content.raw_text || 'No content'}
            </p>
          </div>
        </div>
        <ArrowUpRight className="h-4 w-4 flex-shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
      </div>

      <div className="mt-4 flex items-center gap-2 flex-wrap">
        {content.category && (
          <span className="inline-flex items-center rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground">
            {content.category}
          </span>
        )}
        {content.tags?.slice(0, 3).map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
          >
            #{tag}
          </span>
        ))}
        <span className="ml-auto text-xs text-muted-foreground">
          {formatDate(content.created_at)}
        </span>
      </div>

      <StatusBadge status={content.status} />

      {canReprocess && (
        <div className="mt-3">
          <button
            onClick={handleReprocess}
            disabled={reprocessMutation.isPending}
            className={cn(
              'flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md transition-colors',
              'bg-muted text-muted-foreground hover:bg-primary/10 hover:text-primary',
              reprocessMutation.isPending && 'opacity-50 cursor-not-allowed'
            )}
          >
            <RefreshCw className={cn('h-3 w-3', reprocessMutation.isPending && 'animate-spin')} />
            {reprocessMutation.isPending ? 'Reprocessing…' : 'Reprocess'}
          </button>
        </div>
      )}
    </Link>
  )
}
