import { createClient } from '@/lib/supabase/server'
import { notFound } from 'next/navigation'
import { EditForm } from './form'
import type { Video, ScriptVersion, ChannelConfig } from '@/lib/types'

export default async function EditVideoPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const supabase = await createClient()

  // Buscar vídeo
  const { data: video } = await supabase
    .from('videos')
    .select('*, topic:topics(id, title)')
    .eq('id', id)
    .single()

  if (!video) notFound()

  // Buscar script mais recente
  const { data: script } = await supabase
    .from('scripts')
    .select('*')
    .eq('video_id', id)
    .order('version', { ascending: false })
    .limit(1)
    .single()

  // Buscar config do canal (para voz padrão)
  const { data: channel } = await supabase
    .from('channel_config')
    .select('id, channel_name, default_voice')
    .eq('id', video.channel_id)
    .single()

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-content-primary">Editar vídeo</h1>
        <p className="text-sm text-content-tertiary mt-0.5">
          {video.topic?.title ?? video.title ?? 'Sem título'}
        </p>
      </div>

      <EditForm
        video={video as Video}
        script={script as ScriptVersion | null}
        channel={channel as ChannelConfig}
      />
    </div>
  )
}
