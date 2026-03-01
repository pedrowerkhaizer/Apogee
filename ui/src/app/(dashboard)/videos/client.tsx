'use client'

import { useState } from 'react'
import { StatusBadge } from '@/components/app/status-badge'
import { PipelineStepper } from '@/components/app/pipeline-stepper'
import { VideoDetailSheet } from '@/components/app/video-detail-sheet'
import type { Video } from '@/lib/types'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { ChevronRight } from 'lucide-react'

export function VideosClient({ videos }: { videos: Video[] }) {
  const [selected, setSelected] = useState<Video | null>(null)

  return (
    <>
      <div className="card-base divide-y divide-border-subtle">
        {videos.length === 0 && (
          <p className="p-8 text-center text-sm text-content-tertiary">
            Nenhum vídeo no pipeline ainda.
          </p>
        )}
        {videos.map(video => (
          <div
            key={video.id}
            className="px-5 py-4 hover:bg-bg-overlay cursor-pointer transition-colors flex items-center gap-6"
            onClick={() => setSelected(video)}
          >
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-content-primary truncate">
                {video.title ?? video.topic?.title ?? 'Sem título'}
              </p>
              <p className="text-xs text-content-tertiary mt-0.5">
                {formatDistanceToNow(new Date(video.created_at), { addSuffix: true, locale: ptBR })}
              </p>
            </div>

            <PipelineStepper currentStatus={video.status} className="flex-shrink-0" />

            <ChevronRight size={14} className="text-content-tertiary flex-shrink-0" />
          </div>
        ))}
      </div>

      <VideoDetailSheet video={selected} onClose={() => setSelected(null)} />
    </>
  )
}
