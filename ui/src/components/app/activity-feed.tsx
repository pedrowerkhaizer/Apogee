'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'
import type { AgentRun } from '@/lib/types'
import { StatusBadge } from './status-badge'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { Cpu } from 'lucide-react'

export function ActivityFeed() {
  const [runs, setRuns] = useState<AgentRun[]>([])
  const supabase = createClient()

  async function fetch() {
    const { data } = await supabase
      .from('agent_runs')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(20)
    if (data) setRuns(data as AgentRun[])
  }

  useEffect(() => {
    fetch()
    const id = setInterval(fetch, 10_000)
    return () => clearInterval(id)
  }, [])

  if (!runs.length) return (
    <div className="card-base p-8 text-center text-content-tertiary text-sm">
      Nenhuma execução registrada ainda.
    </div>
  )

  return (
    <div className="card-base divide-y divide-border-subtle">
      {runs.map(run => (
        <div key={run.id} className="flex items-center gap-3 px-4 py-3 hover:bg-bg-overlay transition-colors">
          <Cpu size={14} className="text-content-tertiary flex-shrink-0" />
          <span className="text-sm font-mono text-content-primary flex-1 truncate">
            {run.agent_name}
          </span>
          <StatusBadge status={run.status} />
          {run.duration_ms != null && (
            <span className="text-xs text-content-tertiary w-14 text-right">
              {run.duration_ms < 1000
                ? `${run.duration_ms}ms`
                : `${(run.duration_ms / 1000).toFixed(1)}s`}
            </span>
          )}
          <span className="text-xs text-content-tertiary w-14 text-right font-mono">
            {run.cost_usd ? `$${Number(run.cost_usd).toFixed(3)}` : '—'}
          </span>
          <span className="text-xs text-content-tertiary w-20 text-right">
            {formatDistanceToNow(new Date(run.created_at), { addSuffix: true, locale: ptBR })}
          </span>
        </div>
      ))}
    </div>
  )
}
