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

export function StatsCard({
  title,
  value,
  icon: Icon,
  trend,
  trendUp,
  className,
}: StatsCardProps) {
  return (
    <Card className={cn('', className)}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          <h3 className="mt-2 text-3xl font-semibold text-foreground">{value}</h3>
          {trend && (
            <p
              className={cn(
                'mt-1 text-xs font-medium',
                trendUp ? 'text-green-600' : 'text-red-600'
              )}
            >
              {trend}
            </p>
          )}
        </div>
        <div className="rounded-lg bg-muted p-3">
          <Icon className="h-5 w-5 text-muted-foreground" />
        </div>
      </div>
    </Card>
  )
}
