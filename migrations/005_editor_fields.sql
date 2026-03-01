-- =============================================================
-- 005_editor_fields.sql
-- Apogee Engine — campos para o editor de vídeo (M2 Content Editor)
-- Criado: 2026-03-01
--
-- Mudanças:
--   channel_config → adiciona default_voice (voz padrão do canal)
--   videos         → adiciona voice_override (voz específica por vídeo)
--
-- A tabela scripts já tem version INTEGER DEFAULT 1 — sem mudanças.
-- Precedência de voz no TTS agent:
--   videos.voice_override → channel_config.default_voice → env EDGE_TTS_VOICE
--
-- Rollback: ver comentários ao final
-- =============================================================

-- ── channel_config: voz padrão do canal ──────────────────────
ALTER TABLE channel_config
    ADD COLUMN IF NOT EXISTS default_voice TEXT NOT NULL DEFAULT 'pt-BR-AntonioNeural';

-- ── videos: override de voz por vídeo (NULL = usar padrão do canal) ──
ALTER TABLE videos
    ADD COLUMN IF NOT EXISTS voice_override TEXT;

-- ── Comentário de rollback ────────────────────────────────────
-- ALTER TABLE channel_config DROP COLUMN IF EXISTS default_voice;
-- ALTER TABLE videos         DROP COLUMN IF EXISTS voice_override;
