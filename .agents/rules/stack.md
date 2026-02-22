---
trigger: always_on
---

## Stack Apogee Engine

### Linguagens e runtimes
- Python 3.11+ (lógica principal, agentes, pipeline)
- Node.js (apenas para Remotion via subprocess — nunca escreva lógica de negócio em Node)

### Package manager
- Python: `uv` — sempre use `uv add` e `uv run`
- Node: `npm` — apenas para Remotion

### Banco de dados
- Supabase (Postgres gerenciado) via `supabase-py`
- pgvector habilitado — use `VECTOR(384)` para embeddings all-MiniLM-L6-v2
- Nunca use ORM — SQL puro para queries, `supabase-py` para operações CRUD simples

### LLM
- Claude API via Anthropic SDK Python
- Modelo padrão: claude-sonnet (balanceio custo/qualidade)
- Todo call LLM deve logar tokens usados e custo estimado na tabela `agent_runs`
- Custo referência: $3/MTok input, $15/MTok output (Sonnet)

### Queue
- RQ + Redis (Upstash free tier em prod, Docker em dev)
- Workers ficam em `videoops/workers/`

### Embeddings
- sentence-transformers, modelo `all-MiniLM-L6-v2`, dimensão 384
- Rode sempre em CPU (não assuma GPU)

### Observabilidade
- LangSmith para todos os calls LLM — use o decorator `@traceable`
- Toda execução de agente persiste em `agent_runs` com: tokens, custo, duração, status

### Render
- Remotion chamado via `subprocess.run()` a partir de Python
- Nunca importe bibliotecas Node dentro de Python
- Componentes React ficam em `remotion/src/`

### TTS
- Edge-TTS (gratuito) em dev e fase inicial
- Voz padrão: `pt-BR-AntonioNeural`

### Pós-processamento
- FFmpeg via `ffmpeg-python` ou `subprocess`
- Padrão de output: H.264, CRF 23, LUFS -14