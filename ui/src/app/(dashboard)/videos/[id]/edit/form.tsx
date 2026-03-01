'use client'

import { useState, useTransition } from 'react'
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
  const [payoff, setPayoff] = useState(script?.payoff ?? '')
  const [cta, setCta]       = useState(script?.cta ?? '')

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
              onClick={() =>
                setVoiceOverride(v.value === effectiveVoice && voiceOverride ? '' : v.value)
              }
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
