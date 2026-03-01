import { cn } from '@/lib/utils'
import { type LucideIcon } from 'lucide-react'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface KpiCardProps {
  title: string
  value: string | number
  delta?: { value: number; label: string }
  icon?: LucideIcon
  className?: string
  mono?: boolean
}

export function KpiCard({ title, value, delta, icon: Icon, className, mono }: KpiCardProps) {
  const deltaPositive = delta && delta.value > 0
  const deltaNeutral  = delta && delta.value === 0

  return (
    <div className={cn('card-base p-6 space-y-3', className)}>
      <div className="flex items-center justify-between">
        <p className="section-label">{title}</p>
        {Icon && <Icon size={16} className="text-content-tertiary" />}
      </div>

      <div className="space-y-1">
        <p className={cn(
          'text-3xl font-bold text-content-primary leading-none',
          mono && 'font-mono'
        )}>
          {value}
        </p>

        {delta && (
          <div className={cn(
            'flex items-center gap-1 text-sm font-medium',
            deltaPositive ? 'text-green-400' : deltaNeutral ? 'text-content-tertiary' : 'text-red-400'
          )}>
            {deltaPositive ? <TrendingUp size={14} /> : deltaNeutral ? <Minus size={14} /> : <TrendingDown size={14} />}
            <span>{delta.label}</span>
          </div>
        )}
      </div>
    </div>
  )
}
