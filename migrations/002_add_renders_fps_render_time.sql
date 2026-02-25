-- =============================================================
-- 002_add_renders_fps_render_time.sql
-- Adiciona fps e render_time_sec à tabela renders
-- Criado: 2026-02-24
-- Rollback: ALTER TABLE renders DROP COLUMN IF EXISTS fps, DROP COLUMN IF EXISTS render_time_sec;
-- =============================================================

ALTER TABLE renders ADD COLUMN IF NOT EXISTS fps INTEGER NOT NULL DEFAULT 30;
ALTER TABLE renders ADD COLUMN IF NOT EXISTS render_time_sec FLOAT;
