import { LucideIcon } from 'lucide-react'
import { Card } from './Card'
import { cn } from '../utils/cn'

interface StatsCardProps {
  title: string
  value: string | number
  icon: LucideIcon
  trend?: string
  trendUp?: boolean
  className?: string
}

export function StatsCard({ title, value, icon: Icon, trend, trendUp, className }: StatsCardProps) {
  return (
    <Card className={cn('', className)}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          <h3 className="mt-2 text-3xl font-semibold tracking-tight text-foreground">{value}</h3>
          {trend && (
            <p className={cn('mt-1 text-xs font-medium', trendUp ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500')}>
              {trend}
            </p>
          )}
        </div>
        <div className="rounded-lg bg-primary/8 p-2.5">
          <Icon className="h-4 w-4 text-primary" />
        </div>
      </div>
    </Card>
  )
}
