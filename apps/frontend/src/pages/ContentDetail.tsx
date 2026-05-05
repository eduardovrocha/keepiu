import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Trash2, ExternalLink, FileText, Link, Image,
  Instagram, RefreshCw, MessageCircle, Send, Mic, CheckCircle2, Clock, Loader2, Copy,
} from 'lucide-react'
import { useContent, useDeleteContent, useReprocessContent } from '../hooks/useContents'
import { Card } from '../components/Card'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { formatDateTime } from '../utils/date'
import { cn } from '../utils/cn'
import { Content } from '../types'

const typeIcons = {
  text: FileText,
  link: Link,
  image: Image,
  forward: FileText,
  audio: Mic,
  video: Image,
}

const typeLabels = {
  text: 'Text',
  link: 'Link',
  image: 'Image',
  forward: 'Forwarded',
  audio: 'Audio',
  video: 'Video',
}

const typeColors = {
  text: 'bg-blue-100 text-blue-700',
  link: 'bg-green-100 text-green-700',
  image: 'bg-purple-100 text-purple-700',
  forward: 'bg-gray-100 text-gray-700',
  audio: 'bg-amber-100 text-amber-700',
  video: 'bg-rose-100 text-rose-700',
}

// ── Processing progress ───────────────────────────────────────────────────────

const PIPELINE_STAGES = [
  { key: 'queued',       label: 'Na fila' },
  { key: 'capturing',   label: 'Capturando' },
  { key: 'audio_extract', label: 'Extraindo áudio' },
  { key: 'transcribing', label: 'Transcrevendo' },
  { key: 'ocr',         label: 'OCR' },
  { key: 'ai_processing', label: 'Analisando IA' },
  { key: 'finalizing',  label: 'Finalizando' },
]

function ProcessingProgress({ stage }: { stage: string | null }) {
  const currentIdx = PIPELINE_STAGES.findIndex((s) => s.key === stage)

  return (
    <div className="rounded-lg bg-amber-50 border border-amber-200 p-4">
      <p className="text-sm font-medium text-amber-800 flex items-center gap-2 mb-3">
        <Loader2 className="w-4 h-4 animate-spin shrink-0" />
        Processando conteúdo…
      </p>
      <ol className="space-y-1.5">
        {PIPELINE_STAGES.map((s, i) => {
          const done = currentIdx > i
          const active = currentIdx === i
          const pending = currentIdx < i
          return (
            <li key={s.key} className="flex items-center gap-2 text-xs">
              {done ? (
                <CheckCircle2 className="w-3.5 h-3.5 shrink-0 text-green-600" />
              ) : active ? (
                <Loader2 className="w-3.5 h-3.5 shrink-0 text-amber-600 animate-spin" />
              ) : (
                <Clock className="w-3.5 h-3.5 shrink-0 text-muted-foreground/40" />
              )}
              <span className={cn(
                done ? 'text-green-700 line-through' : active ? 'text-amber-800 font-medium' : 'text-muted-foreground/60',
              )}>
                {s.label}
              </span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

// ── Transcript section ────────────────────────────────────────────────────────

function TranscriptCard({ content }: { content: Content }) {
  const [copied, setCopied] = useState(false)

  if (content.type !== 'audio' && content.type !== 'video' && !content.transcript) return null

  const isTranscribing =
    content.processing_stage === 'transcribing' || content.processing_stage === 'audio_extract'

  const handleCopy = () => {
    if (!content.transcript) return
    navigator.clipboard.writeText(content.transcript)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Card className="p-6 border-amber-100">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-8 h-8 rounded-lg bg-amber-50 border border-amber-100 flex items-center justify-center">
          <Mic className="w-4 h-4 text-amber-600" />
        </div>
        <h3 className="font-semibold text-foreground">Transcrição de Áudio</h3>
        {content.transcript_language && (
          <span className="ml-auto px-2 py-0.5 rounded-full bg-muted text-xs text-muted-foreground">
            {content.transcript_language}
          </span>
        )}
      </div>

      {content.transcript ? (
        <div className="relative">
          <div className="max-h-64 overflow-y-auto rounded-lg bg-muted/50 p-3 pr-8">
            <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
              {content.transcript}
            </p>
          </div>
          <button
            onClick={handleCopy}
            title="Copiar transcrição"
            className="absolute top-2 right-2 p-1.5 rounded-md hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
          >
            {copied
              ? <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />
              : <Copy className="w-3.5 h-3.5" />}
          </button>
        </div>
      ) : isTranscribing ? (
        <p className="text-sm text-amber-700 flex items-center gap-2 italic">
          <Loader2 className="w-4 h-4 animate-spin shrink-0" />
          Transcrevendo áudio…
        </p>
      ) : (
        <p className="text-sm text-muted-foreground italic">Transcrição não disponível</p>
      )}
    </Card>
  )
}

// ── Instagram Intelligence section ────────────────────────────────────────────

function SentimentBar({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = score >= 0.7 ? 'bg-green-500' : score >= 0.4 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm font-medium text-foreground w-10 text-right">{pct}%</span>
    </div>
  )
}

function IgField({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null
  return (
    <div>
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">{label}</p>
      <p className="text-sm text-foreground leading-relaxed">{value}</p>
    </div>
  )
}

function InstagramIntelligenceCard({ content }: { content: Content }) {
  const hasIntelligence = content.summary || content.tone || content.niche || content.cta

  if (!hasIntelligence) return null

  return (
    <Card className="p-6 border-pink-100">
      <div className="flex items-center gap-3 mb-5">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-pink-500 to-purple-600 flex items-center justify-center">
          <Instagram className="w-4 h-4 text-white" />
        </div>
        <h3 className="font-semibold text-foreground">Instagram Intelligence</h3>
        {content.language_detected && (
          <span className="ml-auto px-2 py-0.5 rounded-full bg-muted text-xs text-muted-foreground">
            {content.language_detected}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Resumo */}
        {content.summary && (
          <div className="md:col-span-2">
            <IgField label="Resumo" value={content.summary} />
          </div>
        )}

        <IgField label="Tom" value={content.tone} />
        <IgField label="Nicho" value={content.niche} />

        {content.cta && (
          <div className="md:col-span-2">
            <IgField label="Call to Action" value={content.cta} />
          </div>
        )}

        {/* Sentimento */}
        {typeof content.sentiment_score === 'number' && (
          <div className="md:col-span-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
              Sentimento
            </p>
            <SentimentBar score={content.sentiment_score} />
          </div>
        )}

        {/* Carousel OCR — show per-slide if available, else aggregated */}
        {content.ocr_blocks && content.ocr_blocks.length > 0 ? (
          <div className="md:col-span-2 space-y-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              OCR por slide ({content.ocr_blocks.length} slide{content.ocr_blocks.length !== 1 ? 's' : ''})
            </p>
            {content.ocr_blocks
              .slice()
              .sort((a, b) => a.index - b.index)
              .map((block) => (
                <div key={block.index} className="rounded-lg border border-border overflow-hidden">
                  <div className="flex items-center justify-between px-3 py-1.5 bg-muted/40 border-b border-border">
                    <span className="text-xs font-medium text-muted-foreground">
                      Slide {block.index + 1}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {Math.round(block.confidence * 100)}% confiança
                    </span>
                  </div>
                  <p className="text-sm text-foreground p-3 leading-relaxed whitespace-pre-wrap">
                    {block.text}
                  </p>
                </div>
              ))}
          </div>
        ) : content.extracted_text ? (
          <div className="md:col-span-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
              OCR detectado
            </p>
            <p className="text-sm text-foreground bg-muted/50 rounded-lg p-3 leading-relaxed">
              {content.extracted_text}
            </p>
            {typeof content.confidence_score_ocr === 'number' && (
              <p className="text-xs text-muted-foreground mt-1">
                Confiança OCR: {Math.round(content.confidence_score_ocr * 100)}%
              </p>
            )}
          </div>
        ) : null}

        {/* Caption */}
        {content.caption && content.caption !== content.raw_text && (
          <div className="md:col-span-2">
            <IgField label="Legenda original" value={content.caption} />
          </div>
        )}
      </div>

      {/* Tags */}
      {content.tags && content.tags.length > 0 && (
        <div className="mt-5 pt-5 border-t border-border">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Tags</p>
          <div className="flex flex-wrap gap-1.5">
            {content.tags.map((tag) => (
              <span
                key={tag}
                className="px-2 py-0.5 rounded-md bg-pink-50 text-pink-700 text-xs font-medium"
              >
                #{tag}
              </span>
            ))}
          </div>
        </div>
      )}
    </Card>
  )
}

// ── Main page ──────────────────────────────���────────────────────────────────��──

export function ContentDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: content, isLoading } = useContent(id || '')
  const deleteMutation = useDeleteContent()
  const reprocessMutation = useReprocessContent()

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this content?')) return
    await deleteMutation.mutateAsync(id || '')
    navigate('/library')
  }

  const handleReprocess = () => {
    const confirmed = confirm(
      'Deseja reprocessar este conteúdo?\n\nIsso irá recalcular resumo, tags, IA e embeddings.'
    )
    if (!confirmed) return
    reprocessMutation.mutate(id || '')
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner />
      </div>
    )
  }

  if (!content) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Content not found</p>
        <button
          onClick={() => navigate('/library')}
          className="mt-4 text-primary hover:underline"
        >
          Back to Library
        </button>
      </div>
    )
  }

  const Icon = typeIcons[content.type] || FileText
  const colorClass = typeColors[content.type] || typeColors.text
  const isInstagram = content.source_platform === 'instagram'
  const canReprocess = content.status !== 'processing'
  const channel = content.ingestion_channel

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate(-1)}
          className="p-2 rounded-lg hover:bg-muted transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl font-semibold text-foreground truncate">
              {content.title || 'Untitled'}
            </h1>
            {isInstagram && (
              <span className="flex-shrink-0 inline-flex items-center gap-1 rounded-full bg-gradient-to-r from-pink-100 to-purple-100 px-3 py-1 text-sm font-medium text-pink-700">
                <Instagram className="w-4 h-4" />
                Instagram
              </span>
            )}
            {channel === 'whatsapp' && (
              <span className="flex-shrink-0 inline-flex items-center gap-1 rounded-full bg-green-100 px-3 py-1 text-sm font-medium text-green-700">
                <MessageCircle className="w-4 h-4" />
                WhatsApp
              </span>
            )}
            {channel === 'telegram' && (
              <span className="flex-shrink-0 inline-flex items-center gap-1 rounded-full bg-sky-100 px-3 py-1 text-sm font-medium text-sky-700">
                <Send className="w-4 h-4" />
                Telegram
              </span>
            )}
          </div>
          <p className="text-sm text-muted-foreground">
            Added {formatDateTime(content.created_at)}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {canReprocess && (
            <button
              onClick={handleReprocess}
              disabled={reprocessMutation.isPending}
              className={cn(
                'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                'bg-muted text-muted-foreground hover:bg-primary/10 hover:text-primary',
                reprocessMutation.isPending && 'opacity-50 cursor-not-allowed'
              )}
            >
              <RefreshCw className={cn('w-4 h-4', reprocessMutation.isPending && 'animate-spin')} />
              Reprocess
            </button>
          )}
          <button
            onClick={handleDelete}
            className="p-2 rounded-lg text-red-600 hover:bg-red-50 transition-colors"
          >
            <Trash2 className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Metadata badges */}
      <div className="flex flex-wrap items-center gap-3">
        <span className={cn('flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium', colorClass)}>
          <Icon className="w-4 h-4" />
          {typeLabels[content.type] || content.type}
        </span>

        {content.category && (
          <span className="px-3 py-1 rounded-full bg-secondary text-sm font-medium text-secondary-foreground">
            {content.category}
          </span>
        )}

        {content.actionable && (
          <span className="px-3 py-1 rounded-full bg-amber-100 text-amber-700 text-sm font-medium">
            Actionable
          </span>
        )}

        <span className="px-3 py-1 rounded-full bg-muted text-sm text-muted-foreground">
          Score: {content.importance_score}/10
        </span>
      </div>

      {/* Audio/video transcript */}
      <TranscriptCard content={content} />

      {/* Instagram Intelligence (shown for Instagram content) */}
      {isInstagram && <InstagramIntelligenceCard content={content} />}

      {/* Standard summary (non-Instagram or when Instagram section doesn't cover it) */}
      {content.summary && !isInstagram && (
        <Card className="p-6">
          <h3 className="font-medium text-foreground mb-2">Summary</h3>
          <p className="text-muted-foreground leading-relaxed">{content.summary}</p>
        </Card>
      )}

      {/* Tags (non-Instagram) */}
      {!isInstagram && content.tags && content.tags.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground">Tags:</span>
          {content.tags.map((tag) => (
            <span key={tag} className="px-2.5 py-1 rounded-md bg-muted text-sm text-muted-foreground">
              #{tag}
            </span>
          ))}
        </div>
      )}

      {/* URL */}
      {content.url && (
        <Card className="p-6">
          <h3 className="font-medium text-foreground mb-2">Link</h3>
          <a
            href={content.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-primary hover:underline break-all"
          >
            {content.url}
            <ExternalLink className="w-4 h-4 flex-shrink-0" />
          </a>
        </Card>
      )}

      {/* Extracted Text (non-Instagram; for Instagram it's in the Intelligence card) */}
      {!isInstagram && content.extracted_text && (
        <Card className="p-6">
          <h3 className="font-medium text-foreground mb-2">Extracted Text</h3>
          <p className="text-muted-foreground whitespace-pre-wrap leading-relaxed">
            {content.extracted_text}
          </p>
        </Card>
      )}

      {/* Raw Text */}
      {content.raw_text && (
        <Card className="p-6">
          <h3 className="font-medium text-foreground mb-2">Original Content</h3>
          <p className="text-muted-foreground whitespace-pre-wrap leading-relaxed">
            {content.raw_text}
          </p>
        </Card>
      )}

      {/* Processing stage progress */}
      {(content.status === 'processing' || content.status === 'queued') && (
        <ProcessingProgress stage={content.processing_stage} />
      )}

      {content.processing_error && content.status === 'failed' && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4">
          <p className="text-sm font-medium text-red-700 mb-1">Erro no processamento</p>
          <p className="text-xs text-red-600 font-mono">{content.processing_error}</p>
        </div>
      )}
    </div>
  )
}
