import { useState } from 'react'
import { Filter, Grid, List, ChevronLeft, ChevronRight, X } from 'lucide-react'
import { useContents, useCategories } from '../hooks/useContents'
import { ContentCard } from '../components/ContentCard'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { cn } from '../utils/cn'

const PAGE_SIZE = 20

export function Library() {
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [selectedType, setSelectedType] = useState<string>('')
  const [selectedChannel, setSelectedChannel] = useState<string>('')
  const [selectedSource, setSelectedSource] = useState<string>('')
  const [selectedStatus, setSelectedStatus] = useState<string>('')
  const [page, setPage] = useState(1)

  const { data: contents, isLoading } = useContents({
    category: selectedCategory || undefined,
    type: selectedType || undefined,
    ingestion_channel: selectedChannel || undefined,
    source_platform: selectedSource || undefined,
    status: selectedStatus || undefined,
    page,
    page_size: PAGE_SIZE,
  })

  const { data: categories } = useCategories()

  const totalPages = contents ? Math.ceil(contents.total / PAGE_SIZE) : 1
  const canPrev = page > 1
  const canNext = page < totalPages

  const handleFilterChange =
    (setter: (v: string) => void) => (e: React.ChangeEvent<HTMLSelectElement>) => {
      setter(e.target.value)
      setPage(1)
    }

  const hasFilters = selectedCategory || selectedType || selectedChannel || selectedSource || selectedStatus

  const clearFilters = () => {
    setSelectedCategory('')
    setSelectedType('')
    setSelectedChannel('')
    setSelectedSource('')
    setSelectedStatus('')
    setPage(1)
  }

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
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Filter className="w-4 h-4" />
          <span className="text-sm">Filtros:</span>
        </div>

        {/* Channel */}
        <select
          value={selectedChannel}
          onChange={handleFilterChange(setSelectedChannel)}
          className="px-3 py-1.5 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
        >
          <option value="">Todos os canais</option>
          <option value="telegram">Telegram</option>
          <option value="whatsapp">WhatsApp</option>
        </select>

        {/* Source platform */}
        <select
          value={selectedSource}
          onChange={handleFilterChange(setSelectedSource)}
          className="px-3 py-1.5 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
        >
          <option value="">Todas as fontes</option>
          <option value="instagram">Instagram</option>
          <option value="web">Web</option>
        </select>

        {/* Type */}
        <select
          value={selectedType}
          onChange={handleFilterChange(setSelectedType)}
          className="px-3 py-1.5 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
        >
          <option value="">Todos os tipos</option>
          <option value="text">Texto</option>
          <option value="link">Link</option>
          <option value="image">Imagem</option>
          <option value="file">Arquivo</option>
          <option value="forward">Forward</option>
        </select>

        {/* Status */}
        <select
          value={selectedStatus}
          onChange={handleFilterChange(setSelectedStatus)}
          className="px-3 py-1.5 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
        >
          <option value="">Todos os status</option>
          <option value="queued">Pendente</option>
          <option value="processing">Processando</option>
          <option value="completed">Concluído</option>
          <option value="failed">Falhou</option>
        </select>

        {/* Category */}
        <select
          value={selectedCategory}
          onChange={handleFilterChange(setSelectedCategory)}
          className="px-3 py-1.5 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
        >
          <option value="">Todas as categorias</option>
          {categories?.map((cat) => (
            <option key={cat.category} value={cat.category}>
              {cat.category} ({cat.count})
            </option>
          ))}
        </select>

        {hasFilters && (
          <button
            onClick={clearFilters}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
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
