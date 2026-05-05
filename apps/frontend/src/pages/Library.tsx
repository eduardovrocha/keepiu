import { useState, useRef, useEffect } from 'react'
import {
  Filter, Grid, List, ChevronLeft, ChevronRight, X, ChevronDown, Check,
  Instagram, Globe, Clock, Loader2, CheckCircle2, XCircle, Hash,
} from 'lucide-react'
import { useContents, useCategories } from '../hooks/useContents'
import { ContentCard } from '../components/ContentCard'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { cn } from '../utils/cn'
import { normalizeCategories } from '../utils/categories'

const PAGE_SIZE = 20

// ── Dropdown ───────────────────────────────────────────────────────────────────

interface DropdownOption { label: string; value: string; icon?: React.ElementType }

function FilterDropdown({
  value,
  onChange,
  options,
  placeholder,
}: {
  value: string
  onChange: (v: string) => void
  options: DropdownOption[]
  placeholder: string
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const selected = options.find((o) => o.value === value)
  const isActive = !!value

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm transition-colors',
          isActive
            ? 'border-primary/40 bg-primary/8 text-primary'
            : 'border-border bg-background text-foreground hover:bg-muted'
        )}
      >
        <span>{selected ? selected.label : placeholder}</span>
        <ChevronDown className={cn('w-3.5 h-3.5 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 min-w-[200px] w-max rounded-lg border border-border bg-card shadow-lg overflow-hidden">
          {[{ label: placeholder, value: '', icon: undefined }, ...options].map((opt) => {
            const Icon = opt.icon
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => { onChange(opt.value); setOpen(false) }}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors',
                  opt.value === value
                    ? 'bg-primary/8 text-primary'
                    : 'text-foreground hover:bg-muted'
                )}
              >
                {Icon && <Icon className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />}
                <span className="flex-1">{opt.label}</span>
                {opt.value === value && opt.value !== '' && (
                  <Check className="w-3.5 h-3.5 shrink-0" />
                )}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

export function Library() {
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [selectedSource, setSelectedSource] = useState<string>('')
  const [selectedStatus, setSelectedStatus] = useState<string>('')
  const [page, setPage] = useState(1)

  const { data: contents, isLoading } = useContents({
    category: selectedCategory || undefined,
    source_platform: selectedSource || undefined,
    status: selectedStatus || undefined,
    page,
    page_size: PAGE_SIZE,
  })

  const { data: categories } = useCategories()

  const totalPages = contents ? Math.ceil(contents.total / PAGE_SIZE) : 1
  const canPrev = page > 1
  const canNext = page < totalPages

  const setFilter = (setter: (v: string) => void) => (v: string) => {
    setter(v)
    setPage(1)
  }

  const hasFilters = selectedCategory || selectedSource || selectedStatus

  const clearFilters = () => {
    setSelectedCategory('')
    setSelectedSource('')
    setSelectedStatus('')
    setPage(1)
  }

  const categoryOptions: DropdownOption[] = normalizeCategories(categories ?? []).map(
    ({ label, value, count }) => ({ value, label: `${label} (${count})`, icon: Hash })
  )

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Library</h1>
          <p className="text-muted-foreground mt-1">
            {contents?.total ?? 0} items in your collection
          </p>
        </div>

        {/* View Toggle */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode('grid')}
            className={cn(
              'p-2 rounded-lg transition-colors',
              viewMode === 'grid'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            )}
            aria-label="Grid view"
          >
            <Grid className="w-5 h-5" />
          </button>
          <button
            onClick={() => setViewMode('list')}
            className={cn(
              'p-2 rounded-lg transition-colors',
              viewMode === 'list'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            )}
            aria-label="List view"
          >
            <List className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-2 text-muted-foreground mr-1">
          <Filter className="w-4 h-4" />
          <span className="text-sm">Filtros:</span>
        </div>

        <FilterDropdown
          value={selectedSource}
          onChange={setFilter(setSelectedSource)}
          placeholder="Todas as fontes"
          options={[
            { label: 'Instagram', value: 'instagram', icon: Instagram },
            { label: 'Web', value: 'web', icon: Globe },
          ]}
        />

        <FilterDropdown
          value={selectedStatus}
          onChange={setFilter(setSelectedStatus)}
          placeholder="Todos os status"
          options={[
            { label: 'Pendente',     value: 'queued',      icon: Clock },
            { label: 'Processando',  value: 'processing',  icon: Loader2 },
            { label: 'Concluído',    value: 'completed',   icon: CheckCircle2 },
            { label: 'Falhou',       value: 'failed',      icon: XCircle },
          ]}
        />

        <FilterDropdown
          value={selectedCategory}
          onChange={setFilter(setSelectedCategory)}
          placeholder="Todas as categorias"
          options={categoryOptions}
        />

        {hasFilters && (
          <button
            onClick={clearFilters}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors ml-1"
          >
            <X className="w-3.5 h-3.5" />
            Limpar
          </button>
        )}
      </div>

      {/* Content Grid / List */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner />
        </div>
      ) : (
        <>
          <div
            className={cn(
              viewMode === 'grid'
                ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4'
                : 'space-y-3'
            )}
          >
            {contents?.items.map((content) => (
              <ContentCard key={content.id} content={content} />
            ))}
            {contents?.items.length === 0 && (
              <div className="col-span-full py-12 text-center">
                <p className="text-muted-foreground">
                  Nenhum conteúdo encontrado com esses filtros.
                </p>
              </div>
            )}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-4 border-t border-border">
              <p className="text-sm text-muted-foreground">
                Página {page} de {totalPages}
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => p - 1)}
                  disabled={!canPrev}
                  className={cn(
                    'flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                    canPrev
                      ? 'bg-muted hover:bg-muted/80 text-foreground'
                      : 'opacity-40 cursor-not-allowed bg-muted text-muted-foreground'
                  )}
                >
                  <ChevronLeft className="w-4 h-4" />
                  Anterior
                </button>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={!canNext}
                  className={cn(
                    'flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                    canNext
                      ? 'bg-muted hover:bg-muted/80 text-foreground'
                      : 'opacity-40 cursor-not-allowed bg-muted text-muted-foreground'
                  )}
                >
                  Próxima
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
