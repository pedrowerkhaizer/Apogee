'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'
import { StatusBadge } from './status-badge'
import type { AgentRun } from '@/lib/types'
import { Cpu, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface RqMonitorProps {
  jobId?: string | null
  onRerun?: (videoId: string, agent: string) => void
}

export function RqMonitor({ jobId, onRerun }: RqMonitorProps) {
  const [activeRuns, setActiveRuns] = useState<AgentRun[]>([])
  const supabase = createClient()

  async function fetchActive() {
    const since = new Date(Date.now() - 5 * 60 * 1000).toISOString()
    const { data } = await supabase
      .from('agent_runs')
      .select('*')
      .gte('created_at', since)
      .order('created_at', { ascending: false })
      .limit(10)
    if (data) setActiveRuns(data as AgentRun[])
  }

  useEffect(() => {
    fetchActive()
    const id = setInterval(fetchActive, 5_000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-content-primary">Jobs recentes (últimos 5 min)</h3>
        <Button variant="ghost" size="sm" className="h-7 px-2 text-content-tertiary" onClick={fetchActive}>
          <RefreshCw size={12} />
        </Button>
      </div>

      <div className="card-base divide-y divide-border-subtle">
        {activeRuns.length === 0 && (
          <p className="p-4 text-xs text-content-tertiary text-center">Nenhum job recente.</p>
        )}
        {activeRuns.map(run => (
          <div key={run.id} className="flex items-center gap-3 px-4 py-3">
            <Cpu size={13} className="text-content-tertiary flex-shrink-0" />
            <span className="text-xs font-mono text-content-primary flex-1">{run.agent_name}</span>
            <StatusBadge status={run.status} />
            {run.status === 'failed' && run.video_id && onRerun && (
              <Button
                size="sm"
                variant="ghost"
                className="h-6 px-2 text-xs text-amber-400 hover:bg-amber-500/10"
                onClick={() => onRerun(run.video_id!, run.agent_name)}
              >
                <RefreshCw size={11} className="mr-1" />
                Re-run
              </Button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
