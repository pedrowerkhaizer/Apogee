import { createClient } from '@/lib/supabase/server'
import type { Video } from '@/lib/types'
import { VideosClient } from './client'

export default async function VideosPage() {
  const supabase = await createClient()
  const { data } = await supabase
    .from('videos')
    .select(`
      *,
      topic:topics(id, title)
    `)
    .order('created_at', { ascending: false })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-content-primary">Videos</h1>
        <p className="text-sm text-content-tertiary mt-0.5">
          Rastreamento do pipeline por vídeo
        </p>
      </div>
      <VideosClient videos={(data ?? []) as Video[]} />
    </div>
  )
}
