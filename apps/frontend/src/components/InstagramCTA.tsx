import { useState, useRef } from 'react'
import { Instagram, ArrowRight, Loader2 } from 'lucide-react'
import { useCreateContent } from '../hooks/useContents'
import { cn } from '../utils/cn'

const IG_URL_RE = /instagram\.com\/(p|reel|reels|tv)\/[A-Za-z0-9_\-]+/

export function InstagramCTA() {
  const [url, setUrl] = useState('')
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const mutation = useCreateContent()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = url.trim()
    if (!trimmed) return
    if (!IG_URL_RE.test(trimmed)) {
      setError('Link inválido do Instagram')
      return
    }
    setError('')
    mutation.mutate(
      { source_url: trimmed, source_platform: 'instagram' },
      {
        onSuccess: () => {
          setUrl('')
          inputRef.current?.focus()
        },
      }
    )
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-1.5">
      <div className="flex items-stretch gap-2">
        <div className="relative flex-1">
          <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none">
            <Instagram className="w-4 h-4 text-pink-500" />
          </div>
          <input
            ref={inputRef}
            type="url"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value)
              if (error) setError('')
            }}
            placeholder="Cole um link do Instagram..."
            className={cn(
              'w-full pl-9 pr-3 py-2.5 rounded-lg border bg-background text-sm',
              'focus:outline-none focus:ring-2 focus:ring-pink-500/20 transition-shadow',
              error ? 'border-red-400' : 'border-border'
            )}
            disabled={mutation.isPending}
          />
        </div>
        <button
          type="submit"
          disabled={!url.trim() || mutation.isPending}
          className={cn(
            'flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-medium',
            'bg-gradient-to-r from-pink-500 to-purple-600 text-white',
            'transition-opacity hover:opacity-90',
            'disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0'
          )}
        >
          {mutation.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <ArrowRight className="w-4 h-4" />
          )}
          Processar
        </button>
      </div>
      {error && (
        <p className="text-xs text-red-500 px-1">{error}</p>
      )}
    </form>
  )
}
