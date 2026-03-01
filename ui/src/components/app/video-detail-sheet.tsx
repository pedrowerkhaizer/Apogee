'use client'

import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { StatusBadge } from './status-badge'
import type { Video, AgentRun } from '@/lib/types'
import { createClient } from '@/lib/supabase/client'
import { useEffect, useState } from 'react'
import { DollarSign, Clock, Cpu } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'

interface VideoDetailSheetProps {
  video: Video | null
  onClose: () => void
}

export function VideoDetailSheet({ video, onClose }: VideoDetailSheetProps) {
  const [runs, setRuns] = useState<AgentRun[]>([])
  const supabase = createClient()

  useEffect(() => {
    if (!video) return
    supabase
      .from('agent_runs')
      .select('*')
      .eq('video_id', video.id)
      .order('created_at')
      .then(({ data }) => setRuns((data ?? []) as AgentRun[]))
  }, [video?.id])

  const totalCost = runs.reduce((sum, r) => sum + Number(r.cost_usd), 0)

  return (
    <Sheet open={!!video} onOpenChange={onClose}>
      <SheetContent className="bg-bg-elevated border-border-default w-[480px]">
        {video && (
          <>
            <SheetHeader>
              <SheetTitle className="text-content-primary text-base leading-snug">
                {video.title ?? video.topic?.title ?? 'Sem título'}
              </SheetTitle>
              <StatusBadge status={video.status} className="w-fit" />
            </SheetHeader>

            <div className="mt-6 space-y-5">
              {/* Stats */}
              <div className="grid grid-cols-2 gap-3">
                <div className="card-base px-3 py-2.5">
                  <p className="section-label mb-1">Custo total</p>
                  <p className="text-lg font-bold font-mono text-content-primary">
                    ${totalCost.toFixed(3)}
                  </p>
                </div>
                <div className="card-base px-3 py-2.5">
                  <p className="section-label mb-1">Agent runs</p>
                  <p className="text-lg font-bold font-mono text-content-primary">
                    {runs.length}
                  </p>
                </div>
              </div>

              {/* Agent runs */}
              <div>
                <p className="section-label mb-2">Execuções</p>
                <div className="card-base divide-y divide-border-subtle">
                  {runs.map(run => (
                    <div key={run.id} className="flex items-center gap-2.5 px-3 py-2.5">
                      <Cpu size={13} className="text-content-tertiary flex-shrink-0" />
                      <span className="text-xs font-mono text-content-primary flex-1">{run.agent_name}</span>
                      <StatusBadge status={run.status} />
                      {run.duration_ms != null && (
                        <span className="text-xs text-content-tertiary flex items-center gap-1">
                          <Clock size={11} />
                          {run.duration_ms < 1000 ? `${run.duration_ms}ms` : `${(run.duration_ms/1000).toFixed(1)}s`}
                        </span>
                      )}
                      <span className="text-xs font-mono text-content-tertiary">
                        ${Number(run.cost_usd).toFixed(3)}
                      </span>
                    </div>
                  ))}
                  {runs.length === 0 && (
                    <p className="px-3 py-4 text-xs text-content-tertiary text-center">
                      Sem execuções registradas.
                    </p>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
