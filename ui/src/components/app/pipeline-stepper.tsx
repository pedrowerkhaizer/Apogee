import { cn } from '@/lib/utils'
import type { VideoStatus } from '@/lib/types'
import { Check, X, Loader2 } from 'lucide-react'

const STEPS: { key: VideoStatus; label: string }[] = [
  { key: 'draft',     label: 'Draft' },
  { key: 'scripted',  label: 'Scripted' },
  { key: 'rendered',  label: 'Rendered' },
  { key: 'published', label: 'Published' },
]

const ORDER: Record<VideoStatus, number> = {
  draft: 0, scripted: 1, rendered: 2, published: 3, failed: -1,
}

interface PipelineStepperProps {
  currentStatus: VideoStatus
  className?: string
}

export function PipelineStepper({ currentStatus, className }: PipelineStepperProps) {
  const currentIdx = ORDER[currentStatus]
  const failed = currentStatus === 'failed'

  return (
    <div className={cn('flex items-center gap-0', className)}>
      {STEPS.map(({ key, label }, i) => {
        const stepIdx   = ORDER[key]
        const completed = currentIdx > stepIdx
        const active    = currentIdx === stepIdx && !failed
        const isFailed  = failed && i === Math.max(0, currentIdx)

        return (
          <div key={key} className="flex items-center">
            {/* Step node */}
            <div className="flex flex-col items-center gap-1">
              <div className={cn(
                'w-6 h-6 rounded-full flex items-center justify-center text-xs border',
                completed && 'bg-green-500/20 border-green-500 text-green-400',
                active    && 'bg-accent/20 border-accent text-accent animate-pulse',
                isFailed  && 'bg-red-500/20 border-red-500 text-red-400',
                !completed && !active && !isFailed && 'bg-bg-elevated border-border-default text-content-tertiary'
              )}>
                {completed ? <Check size={12} /> : isFailed ? <X size={12} /> : active ? <Loader2 size={12} className="animate-spin" /> : <span>{i + 1}</span>}
              </div>
              <span className={cn(
                'text-xs whitespace-nowrap',
                completed ? 'text-green-400' : active ? 'text-accent' : isFailed ? 'text-red-400' : 'text-content-tertiary'
              )}>
                {label}
              </span>
            </div>

            {/* Connector */}
            {i < STEPS.length - 1 && (
              <div className={cn(
                'w-8 h-px mb-4',
                completed ? 'bg-green-500/40' : 'border-t border-dashed border-border-default'
              )} />
            )}
          </div>
        )
      })}
    </div>
  )
}
