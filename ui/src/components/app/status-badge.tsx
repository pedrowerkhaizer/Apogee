import { cn } from '@/lib/utils'
import type { TopicStatus, VideoStatus, AgentStatus } from '@/lib/types'

type Status = TopicStatus | VideoStatus | AgentStatus

const CONFIG: Record<Status, { dot: string; bg: string; text: string; label: string }> = {
  // video
  draft:     { dot: 'bg-content-tertiary', bg: 'bg-bg-elevated', text: 'text-content-tertiary', label: 'Draft' },
  scripted:  { dot: 'bg-blue-500',   bg: 'bg-blue-500/10',   text: 'text-blue-400',   label: 'Scripted' },
  rendered:  { dot: 'bg-amber-500',  bg: 'bg-amber-500/10',  text: 'text-amber-400',  label: 'Rendered' },
  published: { dot: 'bg-green-500',  bg: 'bg-green-500/10',  text: 'text-green-400',  label: 'Published' },
  failed:    { dot: 'bg-red-500',    bg: 'bg-red-500/10',    text: 'text-red-400',    label: 'Failed' },
  // topic
  pending:   { dot: 'bg-amber-500',  bg: 'bg-amber-500/10',  text: 'text-amber-400',  label: 'Pending' },
  approved:  { dot: 'bg-green-500',  bg: 'bg-green-500/10',  text: 'text-green-400',  label: 'Approved' },
  rejected:  { dot: 'bg-red-500',    bg: 'bg-red-500/10',    text: 'text-red-400',    label: 'Rejected' },
  // agent
  success:   { dot: 'bg-green-500',  bg: 'bg-green-500/10',  text: 'text-green-400',  label: 'Success' },
  retry:     { dot: 'bg-amber-500',  bg: 'bg-amber-500/10',  text: 'text-amber-400',  label: 'Retry' },
}

interface StatusBadgeProps {
  status: Status
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const cfg = CONFIG[status]
  if (!cfg) return null

  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-xs font-medium',
      cfg.bg, cfg.text, className
    )}>
      <span className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', cfg.dot)} />
      {cfg.label}
    </span>
  )
}
