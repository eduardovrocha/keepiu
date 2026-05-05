import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { FileText, CheckCircle, Clock, TrendingUp } from 'lucide-react'
import { useDashboardStats, useContents } from '../hooks/useContents'
import { StatsCard } from '../components/StatsCard'
import { ContentCard } from '../components/ContentCard'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { Card } from '../components/Card'
import { ContentBatchButton } from '../components/ContentBatchButton'

export function Dashboard() {
  const queryClient = useQueryClient()

  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    queryClient.invalidateQueries({ queryKey: ['contents'] })
  }, [queryClient])

  const { data: stats, isLoading: statsLoading } = useDashboardStats()
  const { data: contents, isLoading: contentsLoading } = useContents({ page_size: 6 })

  const isLoading = statsLoading || contentsLoading

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Dashboard</h1>
          <p className="text-muted-foreground mt-1">Overview of your captured content</p>
        </div>
        <div className="flex flex-col gap-2 sm:w-auto">
          <ContentBatchButton />
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Total Content"
          value={stats?.total_contents || 0}
          icon={FileText}
          trend={`+${stats?.recent_contents || 0} this week`}
          trendUp={true}
        />
        <StatsCard
          title="Processed"
          value={stats?.processed_contents || 0}
          icon={CheckCircle}
          trend={`${Math.round(((stats?.processed_contents || 0) / (stats?.total_contents || 1)) * 100)}% complete`}
          trendUp={true}
        />
        <StatsCard
          title="Pending"
          value={stats?.pending_contents || 0}
          icon={Clock}
        />
        <StatsCard
          title="Avg Score"
          value={stats?.average_importance_score || 0}
          icon={TrendingUp}
        />
      </div>

      {/* Top Categories */}
      <Card className="p-6">
        <h3 className="font-semibold text-foreground mb-4">Top Categories</h3>
        <div className="flex flex-wrap gap-2">
          {stats?.top_categories.map((cat) => (
            <div
              key={cat.category}
              className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted"
            >
              <span className="text-sm font-medium text-foreground">{cat.category}</span>
              <span className="text-xs text-muted-foreground">{cat.count}</span>
            </div>
          ))}
          {stats?.top_categories.length === 0 && (
            <p className="text-sm text-muted-foreground">No categories yet</p>
          )}
        </div>
      </Card>

      {/* Recent Content */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-foreground">Recent Content</h3>
          <a
            href="/library"
            className="text-sm text-primary hover:text-primary/80 transition-colors"
          >
            View all →
          </a>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {contents?.items?.map((content) => (
            <ContentCard key={content.id} content={content} />
          ))}
          {!contents?.items?.length && (
            <div className="col-span-full py-12 text-center">
              <p className="text-muted-foreground">
                No content yet. Start by sending a message to your Telegram bot!
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
