-- =============================================================
-- 004_performance_daily_youtube_metrics.sql
-- Apogee Engine — adiciona colunas de métricas YouTube à performance_daily
-- Criado: 2026-02-28
-- Rollback: ALTER TABLE performance_daily
--               DROP COLUMN IF EXISTS avg_view_duration_sec,
--               DROP COLUMN IF EXISTS shares;
-- =============================================================

ALTER TABLE performance_daily
    ADD COLUMN IF NOT EXISTS avg_view_duration_sec FLOAT,
    ADD COLUMN IF NOT EXISTS shares               INTEGER NOT NULL DEFAULT 0;
