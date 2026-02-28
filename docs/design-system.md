# Apogee — Design System

> Versão 1.0 · Fevereiro 2026
> Stack: Next.js 14 · Tailwind CSS · shadcn/ui · Geist Font

---

## 1. Princípios

| Princípio | Descrição |
|-----------|-----------|
| **Clareza operacional** | Interface de controle, não de consumo. Dados densos, leitura rápida. |
| **Dark-first** | Tema escuro como padrão absoluto. Nunca modo claro. |
| **Sinal, não ruído** | Cor carrega significado. Só usa cor para comunicar estado ou ação. |
| **Densidade confortável** | Informação densa, mas com espaço suficiente para respirar. |

---

## 2. Cores

### 2.1 Paleta base (CSS custom properties)

```css
:root {
  /* Backgrounds */
  --bg-base:        #080808;   /* canvas, body */
  --bg-surface:     #111111;   /* cards, painéis */
  --bg-elevated:    #1a1a1a;   /* dropdowns, modais, tooltips */
  --bg-overlay:     #242424;   /* hover em itens de lista */

  /* Borders */
  --border-subtle:  rgba(255, 255, 255, 0.06);
  --border-default: rgba(255, 255, 255, 0.10);
  --border-strong:  rgba(255, 255, 255, 0.18);

  /* Texto */
  --text-primary:   #f0f0f0;
  --text-secondary: #a1a1aa;   /* zinc-400 */
  --text-tertiary:  #52525b;   /* zinc-600 */
  --text-disabled:  #3f3f46;   /* zinc-700 */

  /* Accent — teal */
  --accent:         #14b8a6;   /* teal-500 */
  --accent-hover:   #0d9488;   /* teal-600 */
  --accent-muted:   rgba(20, 184, 166, 0.12);
  --accent-glow:    rgba(20, 184, 166, 0.25);

  /* Status */
  --status-success: #22c55e;   /* green-500 */
  --status-warning: #f59e0b;   /* amber-500 */
  --status-error:   #ef4444;   /* red-500 */
  --status-info:    #3b82f6;   /* blue-500 */
  --status-neutral: #71717a;   /* zinc-500 */

  /* Muted backgrounds de status */
  --status-success-muted: rgba(34, 197, 94,  0.10);
  --status-warning-muted: rgba(245, 158, 11, 0.10);
  --status-error-muted:   rgba(239, 68,  68, 0.10);
  --status-info-muted:    rgba(59,  130, 246, 0.10);
}
```

### 2.2 Mapeamento de estados de vídeo

| Status | Cor | Hex |
|--------|-----|-----|
| `draft` | neutral | `#71717a` |
| `scripted` | info | `#3b82f6` |
| `rendered` | warning | `#f59e0b` |
| `published` | success | `#22c55e` |
| `failed` | error | `#ef4444` |

### 2.3 Mapeamento de estados de tópico

| Status | Cor | Hex |
|--------|-----|-----|
| `pending` | warning | `#f59e0b` |
| `approved` | success | `#22c55e` |
| `rejected` | error | `#ef4444` |
| `published` | accent | `#14b8a6` |

### 2.4 Mapeamento de agent_run

| Status | Cor |
|--------|-----|
| `success` | `--status-success` |
| `failed` | `--status-error` |
| `retry` | `--status-warning` |

---

## 3. Tipografia

**Font family:** [Geist](https://vercel.com/font) (sans) + Geist Mono (código/números técnicos)

```css
--font-sans: 'Geist', 'Inter', system-ui, sans-serif;
--font-mono: 'Geist Mono', 'Fira Code', monospace;
```

### Escala tipográfica

| Token | Size | Line Height | Weight | Uso |
|-------|------|-------------|--------|-----|
| `text-xs` | 11px | 16px | 400 | Labels, badges, metadata |
| `text-sm` | 13px | 20px | 400 | Corpo de tabelas, descrições |
| `text-base` | 15px | 24px | 400 | Corpo padrão |
| `text-lg` | 17px | 28px | 500 | Subtítulos de seção |
| `text-xl` | 20px | 30px | 600 | Títulos de card |
| `text-2xl` | 24px | 32px | 600 | KPI values, headings de página |
| `text-3xl` | 30px | 40px | 700 | KPI principal |
| `text-4xl` | 36px | 44px | 700 | Números de destaque |

### Estilos nomeados

```
page-title     → text-2xl, weight-600, text-primary
section-label  → text-xs, weight-500, text-tertiary, UPPERCASE, letter-spacing: 0.08em
card-title     → text-base, weight-600, text-primary
body-default   → text-sm, weight-400, text-secondary
kpi-value      → text-3xl / text-4xl, weight-700, font-mono, text-primary
kpi-delta      → text-sm, weight-500, (green/red depending on sign)
code-inline    → font-mono, text-xs, bg-elevated, border-subtle, px-1.5 py-0.5, rounded
```

---

## 4. Espaçamento

Base unit: **4px** (Tailwind default)

| Token | px | Uso |
|-------|-----|-----|
| `space-1` | 4px | Gaps mínimos, ícone↔label |
| `space-2` | 8px | Padding interno de badges |
| `space-3` | 12px | Padding de inputs |
| `space-4` | 16px | Padding interno de cards (mobile) |
| `space-5` | 20px | Gap entre cards |
| `space-6` | 24px | Padding interno de cards |
| `space-8` | 32px | Gap entre seções |
| `space-10` | 40px | Padding de página |
| `space-12` | 48px | Separação de seções maiores |

---

## 5. Border Radius

```css
--radius-xs:  4px;   /* badges, chips */
--radius-sm:  6px;   /* inputs, botões pequenos */
--radius-md:  10px;  /* cards, dropdowns */
--radius-lg:  14px;  /* modais, painéis */
--radius-xl:  20px;  /* elementos de destaque */
--radius-full: 9999px; /* pills, avatars */
```

---

## 6. Sombras

```css
--shadow-sm:  0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3);
--shadow-md:  0 4px 12px rgba(0,0,0,0.5), 0 2px 6px rgba(0,0,0,0.3);
--shadow-lg:  0 10px 32px rgba(0,0,0,0.6), 0 4px 12px rgba(0,0,0,0.4);
--shadow-accent: 0 0 20px rgba(20, 184, 166, 0.20);  /* glow teal */
```

---

## 7. Texturas de fundo

### Dot grid (fundo da página)
```css
background-color: var(--bg-base);
background-image: radial-gradient(
  circle,
  rgba(255, 255, 255, 0.035) 1px,
  transparent 1px
);
background-size: 24px 24px;
```

### Gradient de card com border
```css
background: var(--bg-surface);
border: 1px solid var(--border-default);
border-radius: var(--radius-md);
```

---

## 8. Componentes

### 8.1 Card base

```
┌─────────────────────────────────┐  border: 1px solid --border-default
│  Card Title               ···   │  bg: --bg-surface
│  ─────────────────────────────  │  border-radius: --radius-md
│                                 │  padding: 20px 24px
│  Conteúdo                       │
│                                 │
└─────────────────────────────────┘
```

**Variantes:**
- `card-default` — base acima
- `card-interactive` — adiciona `hover: border-color: --border-strong` + `hover: bg: --bg-overlay`
- `card-accent` — borda esquerda 3px `--accent`, usada para alertas e destaques

---

### 8.2 Botões

| Variante | Background | Texto | Borda | Uso |
|----------|-----------|-------|-------|-----|
| `primary` | `--accent` | white | – | Ação principal (Run Pipeline) |
| `secondary` | `--bg-elevated` | `--text-primary` | `--border-default` | Ações secundárias |
| `ghost` | transparent | `--text-secondary` | transparent | Nav, inline actions |
| `destructive` | `--status-error-muted` | `--status-error` | `1px --status-error` | Rejeitar, deletar |
| `success` | `--status-success-muted` | `--status-success` | `1px --status-success` | Aprovar |

**Tamanhos:**

| Size | Height | Padding H | Font | Radius |
|------|--------|-----------|------|--------|
| `sm` | 28px | 10px | 12px | 6px |
| `md` | 36px | 14px | 13px | 8px |
| `lg` | 44px | 20px | 15px | 10px |

---

### 8.3 Badges de status

```
  ● published          ● pending           ● failed
  ─────────────        ──────────          ────────
  dot: green           dot: amber          dot: red
  bg: success-muted    bg: warning-muted   bg: error-muted
  text: success        text: warning       text: error
  px-2 py-0.5 rounded-xs text-xs font-medium
```

---

### 8.4 Sidebar

```
┌──────────────┐
│  ⬡ Apogee   │  logo + nome (height: 56px)
│              │
│  ⌕ Buscar   │  search bar (opcional)
│              │
│ ── MAIN ─── │  section label
│  ⊞ Dashboard │  item ativo: bg-overlay + accent-left-border
│  ◷ Topics  4│  badge contador (pending)
│  ▷ Videos    │
│              │
│ ─ PIPELINE ─│
│  ⚙ Pipeline  │
│  ☰ Logs      │
│              │
└──────────────┘
  width: 220px (expanded) / 56px (collapsed)
```

**Regras:**
- Item ativo: `bg: --bg-overlay`, borda esquerda `3px --accent`
- Section labels: `text-xs uppercase tracking-widest text-tertiary px-3 mb-1`
- Item hover: `bg: rgba(255,255,255,0.04)`
- Badge de contagem: pill `bg-accent-muted text-accent text-xs`

---

### 8.5 KPI Card

```
┌────────────────────────────┐
│ Vídeos Publicados    ↗     │  title: section-label
│                            │
│  24                        │  value: kpi-value (font-mono)
│  ↑ 3 essa semana           │  delta: text-sm text-success
│                            │
└────────────────────────────┘
```

**Variantes de delta:**
- `↑ N` positivo → `text-success`
- `↓ N` negativo → `text-error`
- `→ sem mudança` → `text-tertiary`

---

### 8.6 Pipeline Stepper

```
  ● draft  ──  ● scripted  ──  ● rendered  ──  ○ published
  (green)      (green)         (amber)          (gray)
     |
     └─ 12s ago · $0.024
```

**Estados de cada passo:**

| Estado | Dot | Linha | Texto |
|--------|-----|-------|-------|
| completo | `--status-success` filled | sólida | `text-primary` |
| atual/em progresso | `--accent` pulsando | – | `text-accent` |
| pendente | `--border-default` | tracejada | `text-tertiary` |
| falhou | `--status-error` | vermelha | `text-error` |

---

### 8.7 Activity Feed (agent_runs)

```
│ ● researcher     ✓ success    124ms   $0.018    2m ago  │
│ ● scriptwriter   ✓ success    3.2s    $0.016    2m ago  │
│ ● fact_checker   ✗ failed     —       —         1m ago  │
│ ● tts            ✓ success    21s     $0.000    30s ago │
```

- Dot colorido por status
- Colunas fixas: agent · status · duration · cost · time
- Hover: `bg: --bg-overlay`
- Falha: linha completa com `text-error` leve

---

### 8.8 Inputs

```css
/* Base */
background: var(--bg-elevated);
border: 1px solid var(--border-default);
border-radius: var(--radius-sm);
padding: 8px 12px;
color: var(--text-primary);
font-size: 13px;

/* Focus */
border-color: var(--accent);
outline: none;
box-shadow: 0 0 0 3px var(--accent-muted);

/* Disabled */
opacity: 0.5;
cursor: not-allowed;
```

---

### 8.9 Log Stream (terminal)

```
┌─ Pipeline Logs ─────────────────────────────── [pause] ─┐
│  [INFO]  2026-02-28 14:32:01  topic_miner: 20 candidatos│
│  [INFO]  2026-02-28 14:32:03  researcher: claim 1/5     │
│  [WARN]  2026-02-28 14:32:08  fact_checker: risk 0.52   │
│  [ERROR] 2026-02-28 14:32:09  scriptwriter: retry 1/2   │
└─────────────────────────────────────────────────────────┘
```

```css
font-family: var(--font-mono);
font-size: 12px;
background: #050505;
border: 1px solid var(--border-subtle);
border-radius: var(--radius-md);
padding: 12px 16px;
```

Cores por nível:
- `[INFO]` → `--text-tertiary`
- `[WARN]` → `--status-warning`
- `[ERROR]` → `--status-error`
- timestamp → `--text-disabled`
- mensagem → `--text-secondary`

---

## 9. Iconografia

**Biblioteca:** [Lucide React](https://lucide.dev/) (já incluso no shadcn/ui)

| Seção/Conceito | Ícone Lucide |
|----------------|-------------|
| Dashboard | `LayoutDashboard` |
| Topics | `Lightbulb` |
| Videos | `Film` |
| Pipeline | `Workflow` |
| Logs | `Terminal` |
| Aprovado | `CheckCircle2` |
| Rejeitado | `XCircle` |
| Pendente | `Clock` |
| Run Pipeline | `Play` |
| Re-run | `RefreshCw` |
| Custo | `DollarSign` |
| Similaridade | `GitMerge` |
| Worker ativo | `Cpu` |
| Falha | `AlertTriangle` |
| Sucesso | `CheckCircle` |
| Log stream | `ScrollText` |

Tamanhos: `16px` (inline/nav) · `20px` (card header) · `24px` (ações primárias)

---

## 10. Animações e transições

```css
/* Padrão para hover/focus */
transition: all 150ms ease;

/* Fade-in de conteúdo */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
}
animation: fadeIn 200ms ease forwards;

/* Pulse para status "em progresso" */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.4; }
}
animation: pulse 1.5s ease-in-out infinite;

/* Spinner */
@keyframes spin {
  to { transform: rotate(360deg); }
}
animation: spin 700ms linear infinite;
```

**Regra:** Nunca usar animação com duração > 300ms para feedback de ação. Reservar animações longas para onboarding ou estados vazios.

---

## 11. Layout

### Grid de página

```
┌──────────────────────────────────────────────────┐
│  Sidebar 220px │  Header 56px (breadcrumb + ações)│
│                │─────────────────────────────────│
│                │                                  │
│                │  Conteúdo (padding: 24px)        │
│                │                                  │
│                │  Grid: 12 cols, gap-6            │
│                │                                  │
└──────────────────────────────────────────────────┘
```

### Grid de KPI cards

```
[ 1/4 col ]  [ 1/4 col ]  [ 1/4 col ]  [ 1/4 col ]
  Publicados   Custo mês    Pendentes    Última run
```

Breakpoints responsivos:
- `xl` (1280px+): 4 colunas
- `lg` (1024px): 2 colunas
- `md` (768px): 2 colunas, sidebar colapsada
- `sm` (< 640px): 1 coluna, sidebar como drawer

---

## 12. Tailwind config (tokens principais)

```ts
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        bg: {
          base:     '#080808',
          surface:  '#111111',
          elevated: '#1a1a1a',
          overlay:  '#242424',
        },
        border: {
          subtle:  'rgba(255,255,255,0.06)',
          default: 'rgba(255,255,255,0.10)',
          strong:  'rgba(255,255,255,0.18)',
        },
        accent: {
          DEFAULT: '#14b8a6',
          hover:   '#0d9488',
          muted:   'rgba(20,184,166,0.12)',
        },
        content: {
          primary:   '#f0f0f0',
          secondary: '#a1a1aa',
          tertiary:  '#52525b',
          disabled:  '#3f3f46',
        },
      },
      fontFamily: {
        sans: ['Geist', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['Geist Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        xs: '4px',
        sm: '6px',
        md: '10px',
        lg: '14px',
        xl: '20px',
      },
      boxShadow: {
        sm:     '0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)',
        md:     '0 4px 12px rgba(0,0,0,0.5), 0 2px 6px rgba(0,0,0,0.3)',
        lg:     '0 10px 32px rgba(0,0,0,0.6), 0 4px 12px rgba(0,0,0,0.4)',
        accent: '0 0 20px rgba(20,184,166,0.20)',
      },
    },
  },
}
```

---

## 13. shadcn/ui — overrides

O shadcn/ui é instalado com `--theme dark`. Os seguintes tokens são sobrescritos no `globals.css`:

```css
@layer base {
  :root {
    --background:       8 8 8;        /* #080808 */
    --foreground:       240 240 240;  /* #f0f0f0 */
    --card:             17 17 17;     /* #111111 */
    --card-foreground:  240 240 240;
    --popover:          26 26 26;     /* #1a1a1a */
    --popover-foreground: 240 240 240;
    --primary:          20 184 166;   /* teal-500 */
    --primary-foreground: 255 255 255;
    --secondary:        36 36 36;     /* #242424 */
    --secondary-foreground: 161 161 170;
    --muted:            26 26 26;
    --muted-foreground: 113 113 122;  /* zinc-500 */
    --accent:           20 184 166;
    --accent-foreground: 255 255 255;
    --destructive:      239 68 68;    /* red-500 */
    --destructive-foreground: 255 255 255;
    --border:           255 255 255 / 0.10;
    --input:            255 255 255 / 0.10;
    --ring:             20 184 166;
    --radius:           0.625rem;     /* 10px */
  }
}
```

---

## Referências visuais (moodboard)

| Referência | O que usar |
|------------|-----------|
| Canvas AI app | Dot grid background, card style, teal accent |
| Bubblee dashboard | Sidebar com section groups + badges, KPI layout |
| Skejulio Calendar | Tab navigation, modais de ação |
| Oriva / Clarity | Tipografia forte, hierarquia de seções |
