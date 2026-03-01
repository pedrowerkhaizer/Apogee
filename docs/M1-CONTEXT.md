# M1 Web App — Contexto para sessões Claude

> Leia este arquivo no início de qualquer sessão que continue o M1.
> Ele resume todas as decisões tomadas, o estado atual e como continuar.

---

## O que é o M1

Dashboard web para controlar o pipeline de vídeo do Apogee. Substitui a interação manual com o banco (approve de tópicos, monitoramento) por uma interface visual. Construído em Next.js 14 dentro do mesmo repositório que o backend Python.

---

## Decisões de arquitetura (não rever sem motivo)

| Decisão | Escolha | Motivo |
|---------|---------|--------|
| Onde fica o Next.js | `ui/` dentro do monorepo Apogee | Simples, mesmo repo, CI único |
| Como UI lê dados | Direto ao Supabase via `@supabase/ssr` | Sem camada intermediária, Server Components nativos |
| Como disparar pipeline | `child_process.spawn pipeline.py --once` via API route | RQ/Redis já existente; sem FastAPI extra |
| Monitoramento de jobs | Polling Redis (`apogee:job:{id}`) a cada 3-5s | Simples e eficaz para uso solo |
| Logs em tempo real | SSE (`/api/pipeline/logs`) fazendo poll do arquivo de log | Sem WebSockets, sem infra extra |
| Auth | Supabase magic link | Sem senha, uso solo |
| Deploy | Vercel apontando para `ui/` | Preview deploys automáticos por branch |

---

## Stack do frontend

```
Next.js 14 (App Router, TypeScript)
Tailwind CSS com tokens customizados (ver tailwind.config.ts)
shadcn/ui — tema dark com Zinc base
Geist font (sans + mono)
@supabase/ssr — server + browser clients
ioredis — leitura de jobs RQ no Redis
date-fns — formatação de datas
lucide-react — ícones
```

---

## Estrutura de pastas (`ui/src/`)

```
app/
  (auth)/
    login/page.tsx          ← magic link login
  (dashboard)/
    layout.tsx              ← sidebar + header (Server Component)
    page.tsx                ← dashboard: KPIs + activity feed
    topics/page.tsx         ← topic management: lista + approve/reject
    videos/page.tsx         ← video queue: stepper por vídeo
    pipeline/page.tsx       ← pipeline runner: run + logs + monitor
  api/
    pipeline/route.ts       ← POST: dispara pipeline.py --once
    pipeline/[id]/route.ts  ← GET: status do job (Redis)
    pipeline/logs/route.ts  ← GET: SSE com tail do log file
    rerun/route.ts          ← POST: re-run de agente específico
  actions/
    topics.ts               ← Server Actions: approve, reject, bulk
  auth/callback/route.ts    ← OAuth callback Supabase
  globals.css               ← design tokens CSS + dot grid

components/
  ui/                       ← shadcn/ui (gerado, não editar manualmente)
  app/
    sidebar.tsx             ← nav lateral com section groups + badges
    breadcrumb-nav.tsx      ← breadcrumb dinâmico por pathname
    status-badge.tsx        ← badge colorido por status (video/topic/agent)
    kpi-card.tsx            ← card de métrica com valor + delta
    pipeline-stepper.tsx    ← stepper visual: draft→scripted→rendered→published
    activity-feed.tsx       ← feed de agent_runs com polling 10s
    quick-actions.tsx       ← botões Run Pipeline + Approve Topics
    topics-table.tsx        ← tabela de tópicos com tabs + bulk actions
    reject-modal.tsx        ← modal de rejeição com campo reason
    video-detail-sheet.tsx  ← sheet lateral com agent_runs do vídeo
    run-button.tsx          ← botão Run Pipeline com estados
    log-stream.tsx          ← terminal SSE de logs em tempo real
    rq-monitor.tsx          ← monitor de jobs recentes + re-run

lib/
  types.ts                  ← interfaces TypeScript (Topic, Video, AgentRun, etc.)
  supabase/
    client.ts               ← browser client (uso em Client Components)
    server.ts               ← server client + service client (uso em Server Components)
  redis.ts                  ← ioredis singleton + getRqJobStatus()

middleware.ts               ← protege rotas (dashboard) com auth Supabase
```

---

## Design system (resumo rápido)

Referência completa: `docs/design-system.md`

```
Backgrounds:  bg-bg-base (#080808) · bg-bg-surface (#111111) · bg-bg-elevated (#1a1a1a)
Borders:      border-border-default (rgba(255,255,255,0.10))
Texto:        text-content-primary (#f0f0f0) · text-content-secondary (#a1a1aa) · text-content-tertiary (#52525b)
Accent:       text-accent / bg-accent (#14b8a6 teal)
Status:       green-500 (success/published) · amber-500 (warning/pending) · red-500 (error/failed) · blue-500 (scripted)
Fonte:        font-sans (GeistSans) · font-mono (GeistMono)
Utilitários:  .section-label (text-xs uppercase tracking) · .card-base (bg-surface + border + rounded-md)
Body:         dot grid background via radial-gradient
```

**Regra de ouro:** sempre `card-base` para cards, `section-label` para labels de seção, `font-mono` para números/KPIs/logs.

---

## Esquema do banco (tabelas usadas pela UI)

```sql
topics    (id, channel_id, title, rationale, source_urls, status, similarity_score, rejected_reason, created_at)
videos    (id, channel_id, topic_id, title, status, youtube_video_id, error_message, created_at, updated_at)
scripts   (id, video_id, hook, beats JSONB, payoff, template_score, similarity_score, created_at)
agent_runs(id, agent_name, video_id, topic_id, status, tokens_input, tokens_output, cost_usd NUMERIC, duration_ms, created_at)
performance_daily(id, video_id, report_date, views, likes, ctr, avg_view_duration_sec, shares)
```

Status enums:
- `topics.status`: `pending | approved | rejected | published`
- `videos.status`: `draft | scripted | rendered | published | failed`
- `agent_runs.status`: `success | failed | retry`

---

## Env vars necessárias (`ui/.env.local`)

```
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
REDIS_URL=redis://localhost:6379
APOGEE_PATH=/Users/pedrowerkhaizer/Documents/AXIOM Labs/Apogee
APOGEE_CHANNEL_ID=<uuid do canal em channel_config>
```

---

## Estado atual da implementação

| Task | Descrição | Status |
|------|-----------|--------|
| T1 — Scaffold | `ui/` criado, deps instaladas, tokens aplicados | ✅ `944958f` |
| T2 — Auth | types.ts, supabase clients, middleware, login page | ✅ `cc4694c` |
| T3 — Layout | sidebar, breadcrumb, dashboard layout | ✅ `cc4694c` |
| T4 — Shared components | StatusBadge, KpiCard, PipelineStepper | ✅ `cc4694c` |
| T5 — Dashboard page | KPIs + activity feed | ✅ `edf3e05` |
| T6 — Topics page | lista + approve/reject + bulk | ✅ `edf3e05` |
| T7 — Videos page | queue + stepper + detail sheet | ✅ `edf3e05` |
| T8 — API routes | pipeline trigger + SSE + rerun | ✅ `edf3e05` |
| T9 — Pipeline page | Run button + log stream + RQ monitor | ✅ `345cc39` |
| T10 — Deploy | next.config, .env.example, vercel.json | ✅ `345cc39` |

---

## Como continuar

### Para implementar a próxima task

1. Leia o plano completo: `docs/plans/2026-02-28-m1-web-app.md`
2. Vá até a task correspondente no plano — ela contém o código exato a criar
3. Crie os arquivos conforme indicado no plano
4. Rode `npx tsc --noEmit` dentro de `ui/` para checar tipos
5. Faça commit com a mensagem indicada no plano
6. Atualize este arquivo (`docs/M1-CONTEXT.md`) marcando a task como ✅

### Ordem obrigatória (dependências)

```
T1 (scaffold) → T2 (auth) → T3 (layout) → T4 (shared components)
                                                    ↓
                    T5 (dashboard) ┐
                    T6 (topics)    ├── podem ser feitas em paralelo
                    T7 (videos)    │   após T4 estar commitada
                    T8 (api)       ┘
                                                    ↓
                    T9 (pipeline page) ← depende de T8
                                                    ↓
                    T10 (deploy config)
```

### Padrões de código para seguir

```tsx
// Server Component (leitura de dados)
import { createClient } from '@/lib/supabase/server'
export default async function Page() {
  const supabase = await createClient()
  const { data } = await supabase.from('table').select('*')
  return <ClientComponent data={data} />
}

// Client Component (interatividade, polling)
'use client'
import { createClient } from '@/lib/supabase/client'
export function Component() {
  const supabase = createClient()
  // ...
}

// Server Action (mutations)
'use server'
import { createServiceClient } from '@/lib/supabase/server'
import { revalidatePath } from 'next/cache'
export async function updateSomething(id: string) {
  const supabase = await createServiceClient()
  await supabase.from('table').update({ ... }).eq('id', id)
  revalidatePath('/path')
}
```

### Troubleshooting comum

- **`GeistSans is not exported`**: Verificar se `geist` está instalado com `npm install geist`
- **Erro de build com env vars**: Não rodar `npm run build` sem env vars reais. Usar `npx tsc --noEmit` para checar tipos
- **shadcn component não encontrado**: Rodar `npx shadcn@latest add <component>` dentro de `ui/`
- **Supabase client em Server Component**: Usar `createClient()` de `@/lib/supabase/server`, não de `client`
- **`revalidatePath` não funciona**: Garantir que a Server Action tem `'use server'` no topo

---

## Referências

- Plano completo (código + comandos): `docs/plans/2026-02-28-m1-web-app.md`
- Design system completo: `docs/design-system.md`
- Schema do banco: `migrations/001_initial_schema.sql`
- Jira cards M1: SCRUM-29 a SCRUM-45 (epic: SCRUM-6)
- Jira Cloud ID: `4160db2e-b859-457c-b762-d963c6808b02`
- Jira transitions: `21` = Em andamento · `41` = Concluído
