'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Play, Loader2, CheckCircle2, AlertTriangle } from 'lucide-react'

type State = 'idle' | 'running' | 'done' | 'error'

interface RunButtonProps {
  onJobStarted?: (jobId: string) => void
}

export function RunButton({ onJobStarted }: RunButtonProps) {
  const [state, setState] = useState<State>('idle')
  const [jobId, setJobId] = useState<string | null>(null)

  async function handleRun() {
    setState('running')
    try {
      const res  = await fetch('/api/pipeline', { method: 'POST' })
      const data = await res.json()

      if (!res.ok) throw new Error(data.error)

      setJobId(data.jobId)
      onJobStarted?.(data.jobId)
      setState('done')
      setTimeout(() => setState('idle'), 5000)
    } catch {
      setState('error')
      setTimeout(() => setState('idle'), 4000)
    }
  }

  return (
    <div className="flex items-center gap-3">
      <Button
        size="lg"
        onClick={handleRun}
        disabled={state === 'running'}
        className="gap-2"
      >
        {state === 'idle'    && <><Play size={16} /> Run Pipeline</>}
        {state === 'running' && <><Loader2 size={16} className="animate-spin" /> Iniciando...</>}
        {state === 'done'    && <><CheckCircle2 size={16} /> Pipeline iniciado</>}
        {state === 'error'   && <><AlertTriangle size={16} /> Erro ao iniciar</>}
      </Button>
      {jobId && state === 'done' && (
        <p className="text-xs text-content-tertiary font-mono">job: {jobId.slice(0, 8)}...</p>
      )}
    </div>
  )
}
