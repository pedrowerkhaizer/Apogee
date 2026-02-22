-- =============================================================
-- 001_initial_schema.sql
-- Apogee Engine – schema inicial do banco de dados
-- Criado: 2026-02-22
-- Rollback: ver comentários ao final de cada bloco
-- =============================================================

-- ── Extensões ────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Enums ────────────────────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE topic_status   AS ENUM ('pending', 'approved', 'rejected', 'published');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE video_status   AS ENUM ('draft', 'scripted', 'rendered', 'published', 'failed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE agent_status   AS ENUM ('success', 'failed', 'retry');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- =============================================================
-- 1. channel_config
--    Configurações do canal YouTube (uma linha por canal)
-- =============================================================
CREATE TABLE IF NOT EXISTS channel_config (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel_name    TEXT        NOT NULL,
    niche           TEXT        NOT NULL,                  -- ex: "tecnologia", "finanças"
    tone            TEXT        NOT NULL DEFAULT 'educativo-direto',
    target_audience TEXT        NOT NULL,                  -- descrição do público-alvo
    language        TEXT        NOT NULL DEFAULT 'pt-BR',
    weekly_target   INTEGER     NOT NULL DEFAULT 2,        -- vídeos por semana
    youtube_channel_id TEXT,                               -- preenchido após criação do canal
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- ROLLBACK: DROP TABLE IF EXISTS channel_config;

-- =============================================================
-- 2. topics
--    Tópicos minerados pelo topic_miner agent
-- =============================================================
CREATE TABLE IF NOT EXISTS topics (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel_id      UUID        NOT NULL REFERENCES channel_config(id) ON DELETE CASCADE,
    title           TEXT        NOT NULL,
    rationale       TEXT,                                  -- por que esse tópico
    source_urls     TEXT[]      NOT NULL DEFAULT '{}',
    status          topic_status NOT NULL DEFAULT 'pending',
    embedding       VECTOR(384),                           -- all-MiniLM-L6-v2
    similarity_score FLOAT,                                -- cosine similarity na deduplicação
    rejected_reason TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- ROLLBACK: DROP TABLE IF EXISTS topics;

-- =============================================================
-- 3. videos
--    Registro central de cada vídeo no pipeline
-- =============================================================
CREATE TABLE IF NOT EXISTS videos (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel_id      UUID        NOT NULL REFERENCES channel_config(id) ON DELETE CASCADE,
    topic_id        UUID        NOT NULL REFERENCES topics(id) ON DELETE RESTRICT,
    title           TEXT,
    status          video_status NOT NULL DEFAULT 'draft',
    youtube_video_id TEXT,                                 -- preenchido após publicação
    published_at    TIMESTAMPTZ,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- ROLLBACK: DROP TABLE IF EXISTS videos;

-- =============================================================
-- 4. claims
--    Claims factuais extraídos do script para fact-checking
-- =============================================================
CREATE TABLE IF NOT EXISTS claims (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id        UUID        NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    claim_text      TEXT        NOT NULL,
    source_url      TEXT,
    verified        BOOLEAN     NOT NULL DEFAULT FALSE,
    risk_score      FLOAT       NOT NULL DEFAULT 0.0,      -- 0.0–1.0; rejeita se > 0.60
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- ROLLBACK: DROP TABLE IF EXISTS claims;

-- =============================================================
-- 5. scripts
--    Scripts gerados pelo script_writer agent
-- =============================================================
CREATE TABLE IF NOT EXISTS scripts (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id        UUID        NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    hook            TEXT        NOT NULL CHECK (char_length(hook) <= 200),
    beats           JSONB       NOT NULL DEFAULT '[]',     -- lista de ScriptBeat
    payoff          TEXT        NOT NULL,
    cta             TEXT,                                  -- sem "não esqueça de se inscrever"
    template_score  FLOAT       NOT NULL DEFAULT 0.0,      -- pipeline pausa se > 0.70
    version         INTEGER     NOT NULL DEFAULT 1,
    embedding       VECTOR(384),                           -- all-MiniLM-L6-v2
    similarity_score FLOAT,                                -- cosine similarity na deduplicação
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- ROLLBACK: DROP TABLE IF EXISTS scripts;

-- =============================================================
-- 6. assets
--    Assets de mídia associados a um vídeo (imagens, B-roll, etc.)
-- =============================================================
CREATE TABLE IF NOT EXISTS assets (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id        UUID        NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    asset_type      TEXT        NOT NULL,                  -- 'image' | 'broll' | 'audio'
    file_path       TEXT        NOT NULL,
    url             TEXT,
    metadata        JSONB       NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- ROLLBACK: DROP TABLE IF EXISTS assets;

-- =============================================================
-- 7. renders
--    Arquivos de vídeo renderizados pelo Remotion
-- =============================================================
CREATE TABLE IF NOT EXISTS renders (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id        UUID        NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    file_path       TEXT        NOT NULL,
    duration_secs   FLOAT,
    file_size_bytes BIGINT,
    resolution      TEXT        NOT NULL DEFAULT '1920x1080',
    codec           TEXT        NOT NULL DEFAULT 'h264',
    lufs            FLOAT,                                  -- target: -14 LUFS
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- ROLLBACK: DROP TABLE IF EXISTS renders;

-- =============================================================
-- 8. performance_daily
--    Métricas diárias de performance por vídeo (YouTube Analytics)
-- =============================================================
CREATE TABLE IF NOT EXISTS performance_daily (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id        UUID        NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    report_date     DATE        NOT NULL,
    views           INTEGER     NOT NULL DEFAULT 0,
    watch_time_mins FLOAT       NOT NULL DEFAULT 0.0,
    likes           INTEGER     NOT NULL DEFAULT 0,
    comments        INTEGER     NOT NULL DEFAULT 0,
    ctr             FLOAT,                                  -- click-through rate
    avg_view_pct    FLOAT,                                  -- % médio assistido
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (video_id, report_date)
);
-- ROLLBACK: DROP TABLE IF EXISTS performance_daily;

-- =============================================================
-- 9. agent_runs
--    Log de toda execução de agente LLM
-- =============================================================
CREATE TABLE IF NOT EXISTS agent_runs (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name      TEXT        NOT NULL,
    video_id        UUID        REFERENCES videos(id) ON DELETE SET NULL,
    topic_id        UUID        REFERENCES topics(id) ON DELETE SET NULL,
    status          agent_status NOT NULL DEFAULT 'success',
    input_json      JSONB       NOT NULL DEFAULT '{}',
    output_json     JSONB,
    tokens_input    INTEGER     NOT NULL DEFAULT 0,
    tokens_output   INTEGER     NOT NULL DEFAULT 0,
    cost_usd        NUMERIC(10,6) NOT NULL DEFAULT 0.0,
    duration_ms     INTEGER,
    error_message   TEXT,
    langsmith_run_id TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- ROLLBACK: DROP TABLE IF EXISTS agent_runs;

-- =============================================================
-- Índices
-- =============================================================

-- ── Lookups comuns ────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_topics_channel_status
    ON topics (channel_id, status);

CREATE INDEX IF NOT EXISTS idx_videos_channel_status
    ON videos (channel_id, status);

CREATE INDEX IF NOT EXISTS idx_videos_topic
    ON videos (topic_id);

CREATE INDEX IF NOT EXISTS idx_agent_runs_agent_name
    ON agent_runs (agent_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_runs_video
    ON agent_runs (video_id);

CREATE INDEX IF NOT EXISTS idx_performance_daily_video_date
    ON performance_daily (video_id, report_date DESC);

-- ── ivfflat (cosine) para embeddings ─────────────────────────
-- Requer ao menos 1 linha para probes eficientes; funciona com 0 linhas em dev.
CREATE INDEX IF NOT EXISTS idx_topics_embedding
    ON topics USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_scripts_embedding
    ON scripts USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
