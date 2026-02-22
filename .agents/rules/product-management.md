---
trigger: manual
---

Você é o agente de implementação do projeto Apogee — pipeline automatizado de criação e publicação de vídeos em canais YouTube de curiosidade científica em pt-BR.

Implemente a Fase 0 completa em sequência. Após cada entrega, informe o que foi criado e aguarde confirmação antes de avançar para a próxima.

---

# CONTEXTO DO PROJETO

## Stack
- Python 3.11+ com uv como package manager
- Supabase (Postgres + pgvector)
- Claude API (Anthropic) via SDK Python
- sentence-transformers (all-MiniLM-L6-v2, dimensão 384, CPU only)
- RQ + Redis (Docker local em dev, Upstash em prod)
- Remotion (Node/React, chamado via subprocess Python — nunca escreva lógica de negócio em Node)
- Edge-TTS (gratuito, voz padrão pt-BR-AntonioNeural)
- FFmpeg para pós-processamento
- LangSmith para observabilidade (@traceable em todo call LLM)
- scikit-learn para modelos simples
- Pydantic v2 (use model_dump, nunca .dict())

## Estrutura de pastas
```
apogee/
  agents/
  workers/
  models.py
  db.py
  embeddings.py
migrations/
scripts/
remotion/
```

## Regras invioláveis
- Nunca use ORM — SQL puro para queries
- Nunca use pip diretamente — sempre uv add
- Nunca passe dicionários crus entre agentes — use Pydantic models
- Todo call LLM registra tokens, custo e duração em agent_runs
- Migrations sempre em SQL numerado (001_, 002_...)
- Testes com pytest, nunca unittest

## Thresholds de negócio (não altere sem instrução explícita)
- Similaridade de tópicos: rejeita se cosine_similarity > 0.75
- Similaridade de scripts: bloqueia se cosine_similarity > 0.80
- template_score: pausa pipeline se score > 0.70
- Fact checker: rejeita script se risk_score > 0.60, máximo 2 tentativas

---

# FASE 0 — FUNDAÇÃO

## E0.1 — Ambiente local

Crie:

1. `pyproject.toml` com dependências:
   anthropic, supabase, sentence-transformers, rq, redis, edge-tts,
   pydantic, python-dotenv, langsmith, mutagen, ffmpeg-python,
   scikit-learn, pandas, pytest, psycopg2-binary

2. `.env.example` com as variáveis:
   ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_KEY, SUPABASE_DB_URL,
   REDIS_URL, LANGSMITH_API_KEY

3. `.gitignore` incluindo .env, __pycache__, .venv, *.pyc
   (uv.lock NÃO deve ser ignorado — deve ser versionado)

4. `docker-compose.yml` com Redis redis:7-alpine na porta 6379

5. `scripts/check_env.py` que:
   - Carrega .env com python-dotenv
   - Testa conexão real com Supabase (SELECT 1)
   - Testa conexão real com Redis (PING)
   - Testa instanciação do cliente Anthropic
   - Testa import do LangSmith
   - Imprime OK ou FAIL por serviço com mensagem de erro se FAIL
   - Exit code 1 se qualquer serviço falhar

Critério de conclusão: `python scripts/check_env.py` retorna OK para todos os serviços.

---

## E0.2 — Schema Postgres

Crie:

1. `migrations/001_initial_schema.sql` com:
   - CREATE EXTENSION IF NOT EXISTS vector
   - Tabelas exatamente como abaixo:

```sql
CREATE TABLE channel_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel_name TEXT NOT NULL,
  niche TEXT NOT NULL,
  language TEXT DEFAULT 'pt-BR',
  target_duration_sec INT DEFAULT 55,
  upload_frequency TEXT DEFAULT '3x_semana',
  tone TEXT DEFAULT 'curioso_direto',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE topics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel_id UUID REFERENCES channel_config(id),
  title TEXT NOT NULL,
  status TEXT DEFAULT 'pending',
  similarity_score FLOAT,
  embedding VECTOR(384),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE videos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  topic_id UUID REFERENCES topics(id),
  status TEXT DEFAULT 'draft',
  style_hash TEXT,
  template_score FLOAT,
  created_at TIMESTAMPTZ DEFAULT now(),
  published_at TIMESTAMPTZ
);

CREATE TABLE claims (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id UUID REFERENCES videos(id),
  claim_text TEXT NOT NULL,
  source_url TEXT,
  confidence FLOAT,
  verified BOOLEAN DEFAULT false
);

CREATE TABLE scripts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id UUID REFERENCES videos(id),
  hook TEXT NOT NULL,
  beats JSONB NOT NULL,
  payoff TEXT NOT NULL,
  cta TEXT,
  full_text TEXT NOT NULL,
  embedding VECTOR(384),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE assets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id UUID REFERENCES videos(id),
  asset_type TEXT,
  origin TEXT,
  file_path TEXT,
  checksum TEXT
);

CREATE TABLE renders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id UUID REFERENCES videos(id),
  output_path TEXT,
  codec TEXT DEFAULT 'h264',
  fps INT DEFAULT 30,
  render_time_sec FLOAT,
  file_size_mb FLOAT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE performance_daily (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id UUID REFERENCES videos(id),
  date DATE NOT NULL,
  views INT DEFAULT 0,
  avg_view_duration_sec FLOAT,
  ctr FLOAT,
  likes INT DEFAULT 0,
  shares INT DEFAULT 0,
  retention_30s FLOAT,
  UNIQUE(video_id, date)
);

CREATE TABLE agent_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id UUID REFERENCES videos(id),
  agent_name TEXT NOT NULL,
  input_snapshot JSONB,
  output_snapshot JSONB,
  duration_ms INT,
  tokens_used INT,
  cost_usd FLOAT,
  status TEXT,
  error_text TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON topics USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX ON scripts USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

2. `scripts/apply_migrations.py` que lê e executa o SQL via psycopg2 usando SUPABASE_DB_URL

3. `scripts/seed_channel.py` que insere 1 linha em channel_config com valores placeholder para o canal Apogee

Critério de conclusão: 9 tabelas visíveis no Supabase após rodar apply_migrations.py.

---

## E0.3 — Pydantic Models

Crie `apogee/models.py` com:

```python
# Enums
TopicStatus: pending | approved | rejected | published
VideoStatus: draft | scripted | rendered | published | failed
AgentStatus: success | failed | retry

# Models
Claim:
  - claim_text: str
  - source_url: Optional[str]
  - confidence: float (0.0–1.0)
  - verified: bool = False

ScriptBeat:
  - fact: str
  - analogy: str

Script:
  - hook: str (max 200 chars)
  - beats: list[ScriptBeat] (exatamente 3)
  - payoff: str
  - cta: Optional[str]
  - full_text: str (gerado automaticamente via model_validator concatenando hook + beats + payoff + cta)

VideoSpec:
  - video_id: Optional[UUID]
  - topic_id: UUID
  - topic_title: str
  - channel_id: UUID
  - status: VideoStatus = draft
  - claims: list[Claim] (mínimo 1)
  - script: Script
  - similarity_score: Optional[float] (0.0–1.0)
  - template_score: Optional[float] (0.0–1.0)
  - created_at: Optional[datetime]
  - método to_db_rows() que retorna dict com chaves videos, scripts, claims prontas para inserção
```

Critério de conclusão: VideoSpec(**exemplo_dict) valida sem erro e round-trip JSON funciona sem perda.

---

## E0.4 — Smoke Test

Crie `scripts/smoke_test.py` que executa em sequência:

```
[1/6] Validando VideoSpec com dados fake... 
[2/6] Serializando para JSON e deserializando...
[3/6] Inserindo topic em Supabase...
[4/6] Inserindo video em Supabase...
[5/6] Inserindo script e claims em Supabase...
[6/6] Recuperando do banco e comparando topic_title, script.hook, claims[0].confidence...
```

Regras:
- Sem mocks — testa integração real com Supabase
- Idempotente — deleta todos os registros inseridos ao final (ordem: claims → scripts → renders → assets → videos → topics → channel_config)
- Se qualquer passo falhar: imprime "SMOKE TEST FAILED — passo N: [erro]" e exit code 1
- Se tudo passar: imprime "SMOKE TEST PASSED"
- Deve rodar em menos de 15 segundos

Critério de conclusão: `python scripts/smoke_test.py` imprime SMOKE TEST PASSED e nenhum registro permanece no banco.