'use client'

import { useState } from 'react'
import { RunButton } from '@/components/app/run-button'
import { LogStream } from '@/components/app/log-stream'
import { RqMonitor } from '@/components/app/rq-monitor'
import { Workflow } from 'lucide-react'

export default function PipelinePage() {
  const [currentJobId, setCurrentJobId] = useState<string | null>(null)

  async function handleRerun(videoId: string, agent: string) {
    await fetch('/api/rerun', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ videoId, agent }),
    })
  }

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-content-primary">Pipeline</h1>
          <p className="text-sm text-content-tertiary mt-0.5">
            Controle e monitore o pipeline de vídeo
          </p>
        </div>
        <RunButton onJobStarted={setCurrentJobId} />
      </div>

      {/* Status do job atual */}
      {currentJobId && (
        <div className="card-base border-l-2 border-accent px-5 py-4">
          <div className="flex items-center gap-2">
            <Workflow size={14} className="text-accent" />
            <span className="text-sm text-content-primary font-medium">Pipeline em execução</span>
            <span className="text-xs font-mono text-content-tertiary ml-2">
              job: {currentJobId.slice(0, 16)}...
            </span>
          </div>
        </div>
      )}

      {/* Monitor + Logs */}
      <div className="grid grid-cols-1 gap-6">
        <RqMonitor jobId={currentJobId} onRerun={handleRerun} />
        <LogStream />
      </div>
    </div>
  )
}
