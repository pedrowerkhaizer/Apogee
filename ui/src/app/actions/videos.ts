'use server'

import { createServiceClient } from '@/lib/supabase/server'
import { revalidatePath } from 'next/cache'

interface ScriptInput {
  hook: string
  beats: { fact: string; analogy: string }[]
  payoff: string
  cta: string
}

export async function saveVideoEdits(
  videoId: string,
  {
    title,
    voiceOverride,
    script,
  }: {
    title: string
    voiceOverride: string | null
    script: ScriptInput
  }
) {
  const supabase = await createServiceClient()

  // 1. Calcular próxima versão do script
  const { data: versions } = await supabase
    .from('scripts')
    .select('version')
    .eq('video_id', videoId)
    .order('version', { ascending: false })
    .limit(1)

  const nextVersion = versions && versions.length > 0 ? versions[0].version + 1 : 1

  // 2. Inserir novo script (nova versão)
  const { error: scriptError } = await supabase
    .from('scripts')
    .insert({
      video_id:       videoId,
      hook:           script.hook.slice(0, 200),
      beats:          script.beats,
      payoff:         script.payoff,
      cta:            script.cta || null,
      version:        nextVersion,
      template_score: 0.0,
    })

  if (scriptError) throw new Error(`Erro ao salvar script: ${scriptError.message}`)

  // 3. Atualizar título e voz no vídeo
  const { error: videoError } = await supabase
    .from('videos')
    .update({
      title:          title || null,
      voice_override: voiceOverride || null,
      updated_at:     new Date().toISOString(),
    })
    .eq('id', videoId)

  if (videoError) throw new Error(`Erro ao salvar vídeo: ${videoError.message}`)

  revalidatePath('/videos')
  revalidatePath(`/videos/${videoId}/edit`)
}
