import { useState } from 'react'
import { Search as SearchIcon, Sparkles } from 'lucide-react'
import { useSearch } from '../hooks/useContents'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { Card } from '../components/Card'
import { cn } from '../utils/cn'

export function Search() {
  const [query, setQuery] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  const { data: results, isLoading } = useSearch(searchQuery, true)

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      setSearchQuery(query)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Semantic Search</h1>
        <p className="text-muted-foreground mt-1">
          Find content using natural language
        </p>
      </div>

      {/* Search Input */}
      <form onSubmit={handleSearch}>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
            <Sparkles className="h-5 w-5 text-muted-foreground" />
          </div>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search for anything... (e.g., 'AI agents', 'productivity tips')"
            className={cn(
              'block w-full pl-12 pr-4 py-4 rounded-xl border bg-card',
              'text-foreground placeholder:text-muted-foreground',
              'focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary',
              'transition-all'
            )}
          />
          <button
            type="submit"
            disabled={!query.trim() || isLoading}
            className={cn(
              'absolute right-2 top-1/2 -translate-y-1/2',
              'px-4 py-2 rounded-lg bg-primary text-primary-foreground',
              'hover:bg-primary/90 transition-colors',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            {isLoading ? (
              <LoadingSpinner className="h-4 w-4" />
            ) : (
              <SearchIcon className="h-4 w-4" />
            )}
          </button>
        </div>
      </form>

      {/* Results */}
      {searchQuery && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-medium text-foreground">
              Results for "{searchQuery}"
            </h2>
            <span className="text-sm text-muted-foreground">
              {results?.length || 0} results
            </span>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <LoadingSpinner />
            </div>
          ) : results?.length ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {results.map((result) => (
                <Card key={result.id} className="p-4 hover:border-primary/30 transition-colors">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <h4 className="font-medium text-foreground truncate">
                        {result.title || 'Untitled'}
                      </h4>
                      <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                        {result.summary}
                      </p>
                    </div>
                    <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950 px-2 py-1 rounded-full">
                      {Math.round(result.similarity_score * 100)}%
                    </span>
                  </div>

                  <div className="mt-3 flex items-center gap-2">
                    {result.category && (
                      <span className="text-xs bg-secondary px-2 py-0.5 rounded">
                        {result.category}
                      </span>
                    )}
                    <a
                      href={`/content/${result.id}`}
                      className="ml-auto text-xs text-primary hover:underline"
                    >
                      View →
                    </a>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <p className="text-muted-foreground">
                No results found. Try a different search query.
              </p>
            </div>
          )}
        </div>
      )}

      {!searchQuery && (
        <div className="flex flex-col sm:flex-row gap-4">
          <Card className="flex-1 p-5 bg-muted/50">
            <h3 className="font-medium text-foreground mb-3">Example searches</h3>
            <ul className="flex flex-wrap gap-2">
              {['AI automation tools', 'Productivity tips', 'Startup advice', 'Marketing strategies'].map((q) => (
                <li key={q}>
                  <button
                    type="button"
                    onClick={() => {
                      (document.querySelector('input[type="text"]') as HTMLInputElement)?.focus()
                    }}
                    className="inline-flex items-center px-2.5 py-1 rounded-md bg-background border border-border text-xs text-muted-foreground hover:border-primary/40 hover:text-primary transition-colors"
                  >
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          </Card>

          <Card className="flex-1 p-5 bg-muted/50">
            <h3 className="font-medium text-foreground mb-3">How it works</h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Our AI understands the meaning behind your content, not just keywords.
              Search naturally and find exactly what you need.
            </p>
          </Card>
        </div>
      )}
    </div>
  )
}
