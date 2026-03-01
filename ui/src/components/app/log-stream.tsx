'use client'

import { useEffect, useRef, useState } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Pause, Play, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'

interface LogLine {
  raw: string
  level: 'INFO' | 'WARN' | 'WARNING' | 'ERROR' | 'DEBUG' | 'UNKNOWN'
}

function parseLine(raw: string): LogLine {
  if (/ERROR/i.test(raw))             return { raw, level: 'ERROR' }
  if (/WARN(?:ING)?/i.test(raw))      return { raw, level: 'WARN' }
  if (/INFO/i.test(raw))              return { raw, level: 'INFO' }
  if (/DEBUG/i.test(raw))             return { raw, level: 'DEBUG' }
  return { raw, level: 'UNKNOWN' }
}

const LEVEL_COLOR: Record<LogLine['level'], string> = {
  INFO:    'text-content-secondary',
  WARN:    'text-amber-400',
  WARNING: 'text-amber-400',
  ERROR:   'text-red-400',
  DEBUG:   'text-content-tertiary',
  UNKNOWN: 'text-content-tertiary',
}

export function LogStream() {
  const [lines, setLines]   = useState<LogLine[]>([])
  const [paused, setPaused] = useState(false)
  const bottomRef           = useRef<HTMLDivElement>(null)
  const esRef               = useRef<EventSource | null>(null)

  useEffect(() => {
    const es = new EventSource('/api/pipeline/logs')
    esRef.current = es

    es.onmessage = (event) => {
      if (paused) return
      try {
        const { line } = JSON.parse(event.data) as { line: string }
        if (!line.trim()) return
        setLines(prev => [...prev.slice(-500), parseLine(line)])
      } catch {}
    }

    return () => es.close()
  }, [paused])

  useEffect(() => {
    if (!paused && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [lines, paused])

  return (
    <div className="card-base overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border-subtle">
        <span className="section-label">Log stream</span>
        <div className="flex items-center gap-1.5">
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-content-tertiary"
            onClick={() => setPaused(p => !p)}
          >
            {paused ? <Play size={12} className="mr-1" /> : <Pause size={12} className="mr-1" />}
            <span className="text-xs">{paused ? 'Retomar' : 'Pausar'}</span>
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-content-tertiary"
            onClick={() => setLines([])}
          >
            <Trash2 size={12} />
          </Button>
        </div>
      </div>

      {/* Log area */}
      <ScrollArea className="h-80">
        <div className="p-4 font-mono text-xs space-y-0.5">
          {lines.length === 0 && (
            <p className="text-content-tertiary">Aguardando logs...</p>
          )}
          {lines.map((line, i) => {
            const [, timestamp, rest] = line.raw.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(.*)$/) ?? [, '', line.raw]
            return (
              <div key={i} className="flex gap-2">
                <span className="text-content-disabled flex-shrink-0">{timestamp}</span>
                <span className={LEVEL_COLOR[line.level]}>{rest || line.raw}</span>
              </div>
            )
          })}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>
    </div>
  )
}
