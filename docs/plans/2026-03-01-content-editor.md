# Content Editor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow the user to manually edit video title, script (with versioning), narrator voice, and preview rendered video — all on a dedicated page `/videos/[id]/edit`.

**Architecture:** Dedicated edit page (Next.js Server Component fetching data + Client Component for form). Single server action saves all changes atomically. Each script edit creates a new version row in `scripts`. TTS agent reads voice from DB with cascade fallback. Video preview serves the `.mp4` file via API route.

**Tech Stack:** Next.js 14 App Router, TypeScript, Tailwind CSS, shadcn/ui (dark), @supabase/ssr, psycopg2 (Python TTS agent)

**Jira:** SCRUM-46 (parent: SCRUM-6 M1 Web App Epic)
- Ao iniciar: transition_id `21` (Em andamento)
- Ao concluir: transition_id `41` (Concluído)
- Jira Cloud ID: `4160db2e-b859-457c-b762-d963c6808b02`

---

## Contexto crítico para o próximo Claude

### Estrutura do projeto
```
/Users/pedrowerkhaizer/Documents/AXIOM Labs/Apogee/   ← raiz Python
  agents/tts.py          ← TTS agent (Edge-TTS, precisa ser atualizado)
  migrations/            ← SQL numerado (005 já aplicado)
  models.py              ← VideoSpec, Script, ScriptBeat
  output/renders/        ← arquivos .mp4 em output/renders/{video_id}.mp4
  ui/                    ← projeto Next.js
    src/
      app/
        (dashboard)/videos/
          client.tsx     ← lista de vídeos (adicionar botão editar)
          page.tsx       ← server component (não alterar)
        actions/
          topics.ts      ← server actions existentes (adicionar videos.ts aqui)
        api/
          videos/[id]/render/route.ts  ← CRIAR (serve .mp4)
      components/app/
        status-badge.tsx
        pipeline-stepper.tsx
      lib/
        types.ts         ← interfaces TypeScript (adicionar voice fields)
        supabase/
          server.ts      ← createClient(), createServiceClient()
          client.ts      ← createClient() (browser)
```

### Schema do banco (tabelas relevantes)
```sql
videos  (id, channel_id, topic_id, title, status, voice_override, ...)
  -- voice_override TEXT NULL — já existe (migration 005 aplicada)

scripts (id, video_id, hook, beats JSONB, payoff, cta, version, template_score, similarity_score, created_at)
  -- beats: [{"fact": "...", "analogy": "..."}, ...]  -- exatamente 3 itens
  -- version: INTEGER DEFAULT 1 — incrementar a cada edição

channel_config (id, channel_name, default_voice, ...)
  -- default_voice TEXT DEFAULT 'pt-BR-AntonioNeural' — já existe (migration 005 aplicada)
```

### ⚠️ Migration 005 já está aplicada no banco
NÃO rodar `migrations/005_editor_fields.sql` novamente. As colunas `videos.voice_override` e `channel_config.default_voice` já existem.

### Design system (Tailwind classes obrigatórias)
```
bg-bg-base (#080808) · bg-bg-surface (#111111) · bg-bg-elevated (#1a1a1a)
border-border-default (rgba(255,255,255,0.10)) · border-border-subtle (rgba(255,255,255,0.06))
text-content-primary (#f0f0f0) · text-content-secondary (#a1a1aa) · text-content-tertiary (#52525b)
accent: teal-500 (#14b8a6)
.card-base = bg-bg-surface + border-border-default + rounded-md
.section-label = text-xs font-medium text-content-tertiary uppercase tracking-widest
font-mono para números, hooks, IDs
```

### Vozes PT-BR disponíveis no Edge-TTS
```typescript
const PT_BR_VOICES = [
  { value: 'pt-BR-AntonioNeural',           label: 'Antônio (Masculino)' },
  { value: 'pt-BR-FranciscaNeural',         label: 'Francisca (Feminino)' },
  { value: 'pt-BR-ThalitaNeural',           label: 'Thalita (Feminino)' },
  { value: 'pt-BR-MacerioMultilingualNeural', label: 'Macério (Masculino, multilingual)' },
]
```

### Padrões de código obrigatórios
```tsx
// Server Component (leitura de dados)
import { createClient } from '@/lib/supabase/server'
export default async function Page() {
  const supabase = await createClient()
  const { data } = await supabase.from('table').select('*')
  return <ClientComponent data={data} />
}

// Server Action (mutations)
'use server'
import { createServiceClient } from '@/lib/supabase/server'
import { revalidatePath } from 'next/cache'
export async function action(id: string) {
  const supabase = await createServiceClient()
  await supabase.from('table').update({...}).eq('id', id)
  revalidatePath('/videos')
}
```

---

## Mapa de execução

```
Task 1: Atualizar tipos TypeScript (lib/types.ts)
Task 2: Server action saveVideoEdits (actions/videos.ts)
Task 3: API route para servir .mp4 (api/videos/[id]/render/route.ts)
Task 4: Página de edição (videos/[id]/edit/page.tsx + form.tsx)
Task 5: Botão editar + badge de versão na lista de vídeos (videos/client.tsx)
Task 6: Atualizar TTS agent (agents/tts.py)
→ commit final + Jira SCRUM-46 Concluído
```

---

## Task 1: Atualizar tipos TypeScript

**Arquivos:**
- Modificar: `ui/src/lib/types.ts`

**Step 1: Abrir e ler o arquivo atual**

```bash
cat ui/src/lib/types.ts
```

**Step 2: Adicionar os campos de voz nas interfaces existentes**

Localizar a interface `Video` e adicionar `voice_override`:

```typescript
export interface Video {
  id: string
  channel_id: string
  topic_id: string
  title: string | null
  status: VideoStatus
  youtube_video_id: string | null
  error_message: string | null
  voice_override: string | null   // ← ADICIONAR
  created_at: string
  updated_at: string
  topic?: Pick<Topic, 'id' | 'title'>
}
```

Adicionar a constante de vozes e a interface `ChannelConfig` no final do arquivo:

```typescript
export const PT_BR_VOICES = [
  { value: 'pt-BR-AntonioNeural',             label: 'Antônio (Masculino)' },
  { value: 'pt-BR-FranciscaNeural',           label: 'Francisca (Feminino)' },
  { value: 'pt-BR-ThalitaNeural',             label: 'Thalita (Feminino)' },
  { value: 'pt-BR-MacerioMultilingualNeural', label: 'Macério (Masculino, multilingual)' },
] as const

export interface ChannelConfig {
  id: string
  channel_name: string
  default_voice: string
}

export interface ScriptVersion {
  id: string
  video_id: string
  hook: string
  beats: { fact: string; analogy: string }[]
  payoff: string
  cta: string | null
  version: number
  template_score: number
  created_at: string
}
```

**Step 3: Verificar TypeScript**

```bash
cd ui && npx tsc --noEmit
```

Esperado: sem erros.

**Step 4: Commit**

```bash
cd /Users/pedrowerkhaizer/Documents/AXIOM\ Labs/Apogee
git add ui/src/lib/types.ts
git commit -m "feat(M1.6): add voice + ScriptVersion types"
```

---

## Task 2: Server Action — saveVideoEdits

**Arquivos:**
- Criar: `ui/src/app/actions/videos.ts`

**Step 1: Criar o arquivo**

```typescript
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
```

**Step 2: Verificar TypeScript**

```bash
cd ui && npx tsc --noEmit
```

Esperado: sem erros.

**Step 3: Commit**

```bash
cd /Users/pedrowerkhaizer/Documents/AXIOM\ Labs/Apogee
git add ui/src/app/actions/videos.ts
git commit -m "feat(M1.6): server action saveVideoEdits — atomic title + voice + script version"
```

---

## Task 3: API Route para servir o arquivo .mp4

**Arquivos:**
- Criar: `ui/src/app/api/videos/[id]/render/route.ts`

**Step 1: Criar diretórios**

```bash
mkdir -p "ui/src/app/api/videos/[id]/render"
```

**Step 2: Criar o arquivo**

```typescript
import { NextRequest, NextResponse } from 'next/server'
import { existsSync, createReadStream, statSync } from 'fs'
import { join } from 'path'

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: videoId } = await params
  const apogee = process.env.APOGEE_PATH!

  // Segurança: garantir que o videoId é um UUID válido
  if (!/^[0-9a-f-]{36}$/.test(videoId)) {
    return NextResponse.json({ error: 'ID inválido' }, { status: 400 })
  }

  const filePath = join(apogee, 'output', 'renders', `${videoId}.mp4`)

  if (!existsSync(filePath)) {
    return NextResponse.json({ error: 'Render não encontrado' }, { status: 404 })
  }

  const stat = statSync(filePath)

  // Stream do arquivo com suporte a Range (para o player HTML5)
  const range = _req.headers.get('range')

  if (range) {
    const parts   = range.replace(/bytes=/, '').split('-')
    const start   = parseInt(parts[0], 10)
    const end     = parts[1] ? parseInt(parts[1], 10) : stat.size - 1
    const chunkSize = end - start + 1

    const stream = createReadStream(filePath, { start, end })
    const body = stream as unknown as ReadableStream

    return new Response(body, {
      status:  206,
      headers: {
        'Content-Range':  `bytes ${start}-${end}/${stat.size}`,
        'Accept-Ranges':  'bytes',
        'Content-Length': String(chunkSize),
        'Content-Type':   'video/mp4',
      },
    })
  }

  const stream = createReadStream(filePath) as unknown as ReadableStream

  return new Response(stream, {
    headers: {
      'Content-Type':   'video/mp4',
      'Content-Length': String(stat.size),
      'Accept-Ranges':  'bytes',
    },
  })
}
```

**Step 3: Verificar TypeScript**

```bash
cd ui && npx tsc --noEmit
```

Esperado: sem erros.

**Step 4: Commit**

```bash
cd /Users/pedrowerkhaizer/Documents/AXIOM\ Labs/Apogee
git add "ui/src/app/api/videos/[id]/render/"
git commit -m "feat(M1.6): API route to stream rendered .mp4 with Range support"
```

---

## Task 4: Página de edição `/videos/[id]/edit`

**Arquivos:**
- Criar: `ui/src/app/(dashboard)/videos/[id]/edit/page.tsx` (Server Component)
- Criar: `ui/src/app/(dashboard)/videos/[id]/edit/form.tsx` (Client Component)

**Step 1: Criar diretório**

```bash
mkdir -p "ui/src/app/(dashboard)/videos/[id]/edit"
```

**Step 2: Criar o Server Component `page.tsx`**

Busca o vídeo, o script mais recente e o canal para saber a voz padrão:

```tsx
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
```

**Step 3: Criar o Client Component `form.tsx`**

```tsx
'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { saveVideoEdits } from '@/app/actions/videos'
import type { Video, ScriptVersion, ChannelConfig } from '@/lib/types'
import { PT_BR_VOICES } from '@/lib/types'
import { Save, Loader2, ChevronLeft } from 'lucide-react'
import Link from 'next/link'
import { cn } from '@/lib/utils'

interface EditFormProps {
  video: Video
  script: ScriptVersion | null
  channel: ChannelConfig
}

export function EditForm({ video, script, channel }: EditFormProps) {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [saved, setSaved] = useState(false)

  // State do formulário
  const [title, setTitle]               = useState(video.title ?? '')
  const [voiceOverride, setVoiceOverride] = useState(video.voice_override ?? '')
  const [hook, setHook]                 = useState(script?.hook ?? '')
  const [beats, setBeats]               = useState(
    script?.beats ?? [
      { fact: '', analogy: '' },
      { fact: '', analogy: '' },
      { fact: '', analogy: '' },
    ]
  )
  const [payoff, setPayoff]             = useState(script?.payoff ?? '')
  const [cta, setCta]                   = useState(script?.cta ?? '')

  function updateBeat(idx: number, field: 'fact' | 'analogy', value: string) {
    setBeats(prev => prev.map((b, i) => i === idx ? { ...b, [field]: value } : b))
  }

  function handleSave() {
    startTransition(async () => {
      await saveVideoEdits(video.id, {
        title,
        voiceOverride: voiceOverride || null,
        script: { hook, beats, payoff, cta },
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    })
  }

  const effectiveVoice = voiceOverride || channel.default_voice
  const hookLen = hook.length

  return (
    <div className="space-y-8">
      {/* Preview de vídeo (se renderizado) */}
      {(video.status === 'rendered' || video.status === 'published') && (
        <div className="card-base overflow-hidden">
          <p className="section-label px-4 py-2 border-b border-border-subtle">Preview</p>
          <video
            controls
            className="w-full max-h-96 bg-black"
            src={`/api/videos/${video.id}/render`}
          />
        </div>
      )}

      {/* Título */}
      <div className="card-base p-6 space-y-3">
        <p className="section-label">Título</p>
        <Input
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="Título do vídeo"
          className="text-content-primary"
        />
      </div>

      {/* Voz do narrador */}
      <div className="card-base p-6 space-y-3">
        <div className="flex items-center justify-between">
          <p className="section-label">Voz do narrador</p>
          {!voiceOverride && (
            <span className="text-xs text-content-tertiary bg-bg-elevated px-2 py-0.5 rounded-xs">
              padrão do canal
            </span>
          )}
        </div>
        <div className="grid grid-cols-2 gap-2">
          {PT_BR_VOICES.map(v => (
            <button
              key={v.value}
              type="button"
              onClick={() => setVoiceOverride(v.value === channel.default_voice && !voiceOverride ? '' : v.value)}
              className={cn(
                'px-3 py-2.5 rounded-sm text-sm text-left transition-all border',
                effectiveVoice === v.value
                  ? 'bg-accent/10 border-accent text-content-primary'
                  : 'bg-bg-elevated border-border-default text-content-secondary hover:border-border-strong'
              )}
            >
              {v.label}
              {v.value === channel.default_voice && (
                <span className="ml-2 text-xs text-content-tertiary">(canal)</span>
              )}
            </button>
          ))}
        </div>
        {voiceOverride && (
          <button
            type="button"
            onClick={() => setVoiceOverride('')}
            className="text-xs text-content-tertiary hover:text-content-secondary underline"
          >
            Usar voz padrão do canal ({channel.default_voice})
          </button>
        )}
      </div>

      {/* Script */}
      <div className="card-base p-6 space-y-6">
        <div className="flex items-center justify-between">
          <p className="section-label">Script</p>
          {script && (
            <span className="text-xs font-mono text-content-tertiary">
              v{script.version} — editando como v{script.version + 1}
            </span>
          )}
        </div>

        {/* Hook */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-content-secondary text-xs uppercase tracking-wide">Hook</Label>
            <span className={cn('text-xs font-mono', hookLen > 180 ? 'text-amber-400' : 'text-content-tertiary')}>
              {hookLen}/200
            </span>
          </div>
          <Textarea
            value={hook}
            onChange={e => setHook(e.target.value.slice(0, 200))}
            placeholder="Primeira frase impactante — máximo 200 caracteres"
            rows={2}
            className="resize-none text-content-primary font-mono text-sm"
          />
        </div>

        {/* Beats */}
        {beats.map((beat, i) => (
          <div key={i} className="space-y-3 pt-4 border-t border-border-subtle">
            <p className="text-xs font-medium text-content-tertiary uppercase tracking-wide">
              Beat {i + 1}
            </p>
            <div className="space-y-2">
              <Label className="text-content-secondary text-xs">Fato</Label>
              <Textarea
                value={beat.fact}
                onChange={e => updateBeat(i, 'fact', e.target.value)}
                placeholder="Fato ou dado concreto"
                rows={2}
                className="resize-none text-content-primary text-sm"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-content-secondary text-xs">Analogia</Label>
              <Textarea
                value={beat.analogy}
                onChange={e => updateBeat(i, 'analogy', e.target.value)}
                placeholder="Analogia ou explicação acessível"
                rows={2}
                className="resize-none text-content-primary text-sm"
              />
            </div>
          </div>
        ))}

        {/* Payoff */}
        <div className="space-y-2 pt-4 border-t border-border-subtle">
          <Label className="text-content-secondary text-xs uppercase tracking-wide">Payoff</Label>
          <Textarea
            value={payoff}
            onChange={e => setPayoff(e.target.value)}
            placeholder="Conclusão e insight final"
            rows={2}
            className="resize-none text-content-primary text-sm"
          />
        </div>

        {/* CTA */}
        <div className="space-y-2 pt-4 border-t border-border-subtle">
          <Label className="text-content-secondary text-xs uppercase tracking-wide">
            CTA <span className="normal-case text-content-tertiary font-normal">(opcional)</span>
          </Label>
          <Input
            value={cta}
            onChange={e => setCta(e.target.value)}
            placeholder="Deixe vazio para omitir. Não usar 'não esqueça de se inscrever'."
            className="text-content-primary text-sm"
          />
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pb-8">
        <Button variant="ghost" asChild>
          <Link href="/videos">
            <ChevronLeft size={14} className="mr-1" />
            Voltar
          </Link>
        </Button>
        <Button onClick={handleSave} disabled={pending} className="gap-2">
          {pending
            ? <><Loader2 size={14} className="animate-spin" /> Salvando...</>
            : saved
            ? 'Salvo ✓'
            : <><Save size={14} /> Salvar alterações</>
          }
        </Button>
      </div>
    </div>
  )
}
```

**Step 4: Verificar TypeScript**

```bash
cd ui && npx tsc --noEmit
```

Esperado: sem erros.

**Step 5: Commit**

```bash
cd /Users/pedrowerkhaizer/Documents/AXIOM\ Labs/Apogee
git add "ui/src/app/(dashboard)/videos/[id]/"
git commit -m "feat(M1.6): edit page — title, voice selector, script versioning, video preview"
```

---

## Task 5: Botão editar + badge de versão na lista de vídeos

**Arquivos:**
- Modificar: `ui/src/app/(dashboard)/videos/client.tsx`

**Step 1: Ler o arquivo atual**

```bash
cat "ui/src/app/(dashboard)/videos/client.tsx"
```

**Step 2: Adicionar o import de `Pencil` e `Link`**

No topo do arquivo, adicionar nos imports existentes:

```tsx
import { ChevronRight, Pencil } from 'lucide-react'
import Link from 'next/link'
```

**Step 3: Atualizar cada row da lista de vídeos**

Localizar o trecho que renderiza cada vídeo e adicionar o botão de edição antes do `ChevronRight`:

```tsx
{/* Substitui o bloco existente de cada vídeo */}
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
    className="p-1.5 rounded-sm text-content-tertiary hover:text-content-primary hover:bg-bg-overlay transition-colors flex-shrink-0"
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
```

**Step 4: Verificar TypeScript**

```bash
cd ui && npx tsc --noEmit
```

Esperado: sem erros.

**Step 5: Commit**

```bash
cd /Users/pedrowerkhaizer/Documents/AXIOM\ Labs/Apogee
git add "ui/src/app/(dashboard)/videos/client.tsx"
git commit -m "feat(M1.6): add edit button to video list"
```

---

## Task 6: Atualizar TTS agent para ler voz do banco

**Arquivos:**
- Modificar: `agents/tts.py`

**Step 1: Ler o arquivo atual**

```bash
cat agents/tts.py
```

**Step 2: Localizar a constante `TTS_VOICE` (linha ~45)**

```python
# Antes
TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "pt-BR-AntonioNeural")
TTS_RATE = os.getenv("EDGE_TTS_RATE", "+20%")
```

**Step 3: Substituir por função com fallback em cascata**

Remover a constante `TTS_VOICE` e adicionar a função `_get_voice` logo após os imports:

```python
TTS_RATE = os.getenv("EDGE_TTS_RATE", "+20%")
_DEFAULT_VOICE = os.getenv("EDGE_TTS_VOICE", "pt-BR-AntonioNeural")


def _get_voice(conn: psycopg2.extensions.connection, video_id: UUID) -> str:
    """Resolve a voz a usar com fallback em cascata:
    videos.voice_override → channel_config.default_voice → env EDGE_TTS_VOICE
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(v.voice_override, c.default_voice, %s)
            FROM   videos v
            JOIN   channel_config c ON c.id = v.channel_id
            WHERE  v.id = %s
            """,
            (_DEFAULT_VOICE, str(video_id)),
        )
        row = cur.fetchone()
    return row[0] if row else _DEFAULT_VOICE
```

**Step 4: Atualizar `generate_audio` para usar `_get_voice`**

Localizar a linha dentro de `generate_audio` que usa `TTS_VOICE` e substituir:

```python
# Dentro de generate_audio, após _fetch_script:
script = _fetch_script(conn, video_id)
voice  = _get_voice(conn, video_id)   # ← ADICIONAR esta linha
segments = _build_segments(script)
```

Localizar `_generate_segment` e atualizar a chamada passando `voice`:

```python
# Assinatura de _generate_segment — atualizar para receber voice
def _generate_segment(text: str, output_path: Path, voice: str) -> float:
    """Gera .mp3 para um segmento e retorna a duração em segundos."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(text, voice, rate=TTS_RATE)
    communicate.save_sync(str(output_path))
    audio = MP3(str(output_path))
    return round(audio.info.length, 3)
```

Atualizar o loop de geração dentro de `generate_audio`:

```python
for beat_id, text in segments.items():
    out_path = OUTPUT_BASE / str(video_id) / f"{beat_id}.mp3"
    log.info("  [%s] %d chars → %s (voz: %s)", beat_id, len(text), out_path, voice)
    duration = _generate_segment(text, out_path, voice)   # ← passar voice
    durations[beat_id] = duration
```

**Step 5: Testar manualmente (não requer banco ativo)**

```bash
cd /Users/pedrowerkhaizer/Documents/AXIOM\ Labs/Apogee
uv run python -c "
import ast, sys
with open('agents/tts.py') as f:
    source = f.read()
ast.parse(source)
print('Sintaxe OK')
"
```

Esperado: `Sintaxe OK`

**Step 6: Commit**

```bash
git add agents/tts.py
git commit -m "feat(M1.6): TTS agent reads voice from DB — voice_override → default_voice → env"
```

---

## Task 7: Verificação final + Jira

**Step 1: TypeScript check completo**

```bash
cd ui && npx tsc --noEmit
```

Esperado: sem erros.

**Step 2: Verificar arquivos criados**

```bash
find ui/src -path "*/videos*" -name "*.tsx" | sort
```

Esperado ver:
```
ui/src/app/(dashboard)/videos/[id]/edit/form.tsx
ui/src/app/(dashboard)/videos/[id]/edit/page.tsx
ui/src/app/(dashboard)/videos/client.tsx
ui/src/app/(dashboard)/videos/page.tsx
ui/src/app/api/videos/[id]/render/route.ts
```

**Step 3: Testar o fluxo no dev server**

```bash
cd ui && npm run dev
```

Checklist manual:
- [ ] `/videos` lista vídeos com ícone de lápis em cada row
- [ ] Clicar no lápis navega para `/videos/[id]/edit`
- [ ] Página de edição carrega título, voz e script atual
- [ ] Se vídeo com status `rendered`, aparece o player `<video>`
- [ ] Selecionar voz diferente ativa o botão correto
- [ ] Salvar cria nova versão do script (verificar no Supabase dashboard: `SELECT version FROM scripts WHERE video_id = '...' ORDER BY version DESC`)
- [ ] Voz salva em `videos.voice_override`

**Step 4: Transicionar Jira SCRUM-46 para Concluído**

```
Cloud ID: 4160db2e-b859-457c-b762-d963c6808b02
Issue: SCRUM-46
Transition ID: 41 (Concluído)
```

Usar: `mcp__plugin_atlassian_atlassian__transitionJiraIssue`

**Step 5: Commit final (se houver arquivos não commitados)**

```bash
cd /Users/pedrowerkhaizer/Documents/AXIOM\ Labs/Apogee
git add -A
git commit -m "feat(M1.6): content editor complete — edit page, voice, script versioning, video preview"
```

---

## Checklist de entrega

- [ ] `ui/src/lib/types.ts` — `Video.voice_override`, `PT_BR_VOICES`, `ScriptVersion`, `ChannelConfig`
- [ ] `ui/src/app/actions/videos.ts` — `saveVideoEdits` atômica
- [ ] `ui/src/app/api/videos/[id]/render/route.ts` — serve `.mp4` com suporte a Range
- [ ] `ui/src/app/(dashboard)/videos/[id]/edit/page.tsx` — server component
- [ ] `ui/src/app/(dashboard)/videos/[id]/edit/form.tsx` — client component com formulário completo
- [ ] `ui/src/app/(dashboard)/videos/client.tsx` — botão lápis adicionado
- [ ] `agents/tts.py` — `_get_voice()` com fallback em cascata
- [ ] `npx tsc --noEmit` sem erros
- [ ] SCRUM-46 → Concluído

## O que NÃO fazer

- ❌ Não rodar `migrations/005_editor_fields.sql` — já foi aplicada
- ❌ Não criar novas tabelas — schema já suporta tudo
- ❌ Não adicionar regeneração automática de TTS — o usuário dispara manualmente
- ❌ Não implementar Remotion Player (Nível 2 de preview) — escopo futuro
