'use client'

import { useState } from 'react'
import { StatusBadge } from '@/components/app/status-badge'
import { PipelineStepper } from '@/components/app/pipeline-stepper'
import { VideoDetailSheet } from '@/components/app/video-detail-sheet'
import type { Video } from '@/lib/types'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { ChevronRight, Pencil } from 'lucide-react'
import Link from 'next/link'

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
            className="px-5 py-4 hover:bg-bg-overlay transition-colors flex items-center gap-6"
          >
            {/* Título + data — clicável para abrir sheet */}
            <div
              className="flex-1 min-w-0 cursor-pointer"
              onClick={() => setSelected(video)}
            >
              <p className="text-sm font-medium text-content-primary truncate">
                {video.title ?? video.topic?.title ?? 'Sem título'}
              </p>
              <p className="text-xs text-content-tertiary mt-0.5">
                {formatDistanceToNow(new Date(video.created_at), { addSuffix: true, locale: ptBR })}
              </p>
            </div>

            <PipelineStepper currentStatus={video.status} className="flex-shrink-0" />

            {/* Botão editar */}
            <Link
              href={`/videos/${video.id}/edit`}
              className="p-1.5 rounded-sm text-content-tertiary hover:text-content-primary hover:bg-bg-elevated transition-colors flex-shrink-0"
              onClick={e => e.stopPropagation()}
              title="Editar vídeo"
            >
              <Pencil size={13} />
            </Link>

            <ChevronRight
              size={14}
              className="text-content-tertiary flex-shrink-0 cursor-pointer"
              onClick={() => setSelected(video)}
            />
          </div>
        ))}
      </div>

      <VideoDetailSheet video={selected} onClose={() => setSelected(null)} />
    </>
  )
}
